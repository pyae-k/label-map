"""Conversational insight chat UI for the map-bottom data panel."""

from __future__ import annotations

import base64
import re
from pathlib import Path

import streamlit as st
from pandas import DataFrame

from labelmap.data_filter import (
    apply_data_filters,
    available_locations,
    clear_filter_state,
    filter_status_text,
    get_filter_state,
    location_filter_key,
)
from labelmap.data_insights import (
    action_intro_text,
    chart_data,
    column_chart_data,
    comparison_combo_chart,
    comparison_chart_data,
    full_table,
    missing_table,
    ranked_table,
    summary_table,
)
from labelmap.export import dataframe_csv_download_href, insight_map_screenshot
from labelmap.ui_copy import UI_COPY, display_value_column

_CHAT_ASSISTANT_AVATAR = Path(__file__).resolve().parent / "assets" / "chat_avatar.svg"
_CHAT_USER_AVATAR = Path(__file__).resolve().parent / "assets" / "chat_user_avatar.svg"
_METRIC_ACTIONS = frozenset({"top10", "bottom10", "bar_chart", "column_chart"})
_TOGGLE_MENU_KINDS = frozenset(
    {"location_filter_menu", "metric_compare_menu"}
)
_PRIMARY_MENU_OPTIONS: tuple[tuple[str, str], ...] = (
    ("summary", UI_COPY.insight_summary),
    ("__filter__", UI_COPY.insight_filter),
    ("top10", UI_COPY.insight_top10),
    ("bar_chart", UI_COPY.insight_chart),
    ("full_table", UI_COPY.insight_full_table),
    ("map", UI_COPY.insight_map),
    ("download", UI_COPY.insight_download_label),
)
_RESET_CHAT_OPTION: tuple[str, str] = ("reset_chat", UI_COPY.insight_reset_chat)

_LOCATION_TOGGLE_PREFIX = "__location_toggle__:"
_FILTER_APPLY_KEY = "__filter_apply__"
_CHART_SINGLE_PREFIX = "__chart_single__:"
_CHART_COMPARE_KEY = "__chart_compare__"
_METRIC_TOGGLE_PREFIX = "__metric_toggle__:"
_CHART_COMPARE_APPLY_KEY = "__chart_compare_apply__"
_CHAT_STORE_KEY = "data_insight_chats"
_GLOBAL_CHAT_KEY = "__global__"


def _active_chat_key() -> str:
    upload_key = st.session_state.get("active_upload_key")
    return str(upload_key) if upload_key else "_default"


def _chat_store() -> dict:
    return st.session_state.setdefault(_CHAT_STORE_KEY, {})


def _dataset_bucket_for(upload_key: str | None = None) -> dict:
    """Per-dataset bucket for filters and metric (not messages)."""
    bucket_key = upload_key or _active_chat_key()
    return _chat_store().setdefault(bucket_key, {})


def _global_bucket() -> dict:
    bucket = _chat_store().setdefault(_GLOBAL_CHAT_KEY, {})
    if not isinstance(bucket.get("messages"), list):
        bucket["messages"] = []
    return bucket


def _migrate_to_global_messages() -> None:
    global_bucket = _global_bucket()
    if global_bucket["messages"]:
        return

    legacy = st.session_state.get("data_insight_messages")
    if isinstance(legacy, list) and legacy:
        global_bucket["messages"] = legacy
        st.session_state.pop("data_insight_messages", None)
        return

    store = _chat_store()
    active_key = st.session_state.get("active_upload_key")
    candidate_messages: list[dict] | None = None

    if active_key and active_key in store:
        msgs = store[active_key].get("messages")
        if isinstance(msgs, list) and msgs:
            candidate_messages = msgs

    if candidate_messages is None:
        for key, bucket in store.items():
            if key == _GLOBAL_CHAT_KEY or not isinstance(bucket, dict):
                continue
            msgs = bucket.get("messages")
            if isinstance(msgs, list) and msgs and (
                candidate_messages is None or len(msgs) > len(candidate_messages)
            ):
                candidate_messages = msgs

    if candidate_messages:
        global_bucket["messages"] = candidate_messages


def save_chat_session(upload_key: str) -> None:
    """Persist chat filter/metric state for a dataset before switching KPIs."""
    if not upload_key:
        return
    bucket = _dataset_bucket_for(upload_key)
    bucket["filter_state"] = get_filter_state(st.session_state)
    metric = st.session_state.get("data_insight_metric")
    if metric is not None:
        bucket["metric"] = metric


def restore_chat_session(upload_key: str) -> None:
    """Restore chat filter/metric state for a dataset after switching KPIs."""
    clear_filter_state(st.session_state)
    st.session_state.pop("data_insight_metric", None)
    bucket = _chat_store().get(upload_key)
    if not isinstance(bucket, dict):
        return

    saved_filter = bucket.get("filter_state")
    if isinstance(saved_filter, dict):
        locations = list(saved_filter.get("locations") or [])
        st.session_state["data_insight_filter_regions"] = list(saved_filter.get("regions") or [])
        st.session_state["data_insight_filter_countries"] = list(
            saved_filter.get("countries") or []
        )
        st.session_state["data_insight_filter_locations"] = locations
        st.session_state["data_insight_filter_pending_locations"] = list(locations)
        search = saved_filter.get("search")
        if search:
            st.session_state["data_insight_search"] = str(search)

    metric = bucket.get("metric")
    if metric is not None:
        st.session_state["data_insight_metric"] = metric


def _messages() -> list[dict]:
    _migrate_to_global_messages()
    return _global_bucket()["messages"]


def _set_messages(messages: list[dict]) -> None:
    _global_bucket()["messages"] = messages


def _append_message(message: dict) -> None:
    messages = _messages()
    messages.append(message)
    _set_messages(messages)


def _primary_menu_options() -> list[tuple[str, str]]:
    return list(_PRIMARY_MENU_OPTIONS)


def _append_menu_message(
    text: str,
    options: list[tuple[str, str]],
    *,
    kind: str = "menu",
    show_reset: bool = False,
) -> None:
    message: dict = {
        "role": "assistant",
        "text": text,
        "streamed": False,
        "kind": kind,
        "options": options,
    }
    if show_reset:
        message["show_reset"] = True
    _append_message(message)


def _ensure_initial_conversation() -> None:
    if _messages():
        return
    _append_message(
        {
            "role": "assistant",
            "text": UI_COPY.insight_greeting,
            "streamed": False,
            "kind": "menu",
            "options": list(_PRIMARY_MENU_OPTIONS),
        }
    )


def _selected_metric(value_cols: list[str]) -> str:
    metric = st.session_state.get("data_insight_metric")
    if metric in value_cols:
        return metric
    return value_cols[0]


def _pending_locations() -> list[str]:
    return list(st.session_state.get("data_insight_filter_pending_locations") or [])


def _applied_locations() -> list[str]:
    return list(st.session_state.get("data_insight_filter_locations") or [])


def _sync_location_filter(locations: list[str]) -> None:
    """Keep pending and applied location filters in sync for map + chat."""
    applied = [key for key in (location_filter_key(location) for location in locations) if key]
    st.session_state["data_insight_filter_pending_locations"] = applied
    st.session_state["data_insight_filter_locations"] = applied


def _set_pending_locations(locations: list[str]) -> None:
    st.session_state["data_insight_filter_pending_locations"] = [
        key for key in (location_filter_key(location) for location in locations) if key
    ]


def _pending_chart_metrics() -> list[str]:
    return list(st.session_state.get("data_insight_pending_chart_metrics") or [])


def _set_pending_chart_metrics(metrics: list[str]) -> None:
    st.session_state["data_insight_pending_chart_metrics"] = metrics


def _toggle_item(items: list[str], value: str) -> list[str]:
    if value in items:
        return [item for item in items if item != value]
    return [*items, value]


def _toggle_chart_metric(metrics: list[str], value: str, *, max_selected: int = 2) -> list[str]:
    if value in metrics:
        return [metric for metric in metrics if metric != value]
    if len(metrics) >= max_selected:
        return metrics
    return [*metrics, value]


def _stream_words(text: str):
    for word in text.split(" "):
        yield word + " "


def _render_streamed_text(text: str, *, streamed: bool) -> None:
    if streamed:
        st.markdown(text)
        return
    st.write_stream(_stream_words(text))


def _button_key(action_key: str) -> str:
    return re.sub(r"[^\w\-]", "_", action_key)


def _chip_label(label: str, *, selected: bool) -> str:
    return f"✓ {label}" if selected else label


def _selected_toggle_keys(
    kind: str,
    options: list[tuple[str, str]],
) -> set[str]:
    if kind == "location_filter_menu":
        pending = set(_pending_locations())
        return {
            action_key
            for action_key, label in options
            if location_filter_key(label) in pending
        }
    if kind == "metric_compare_menu":
        pending = set(_pending_chart_metrics())
        return {
            action_key
            for action_key, _label in options
            if action_key.startswith(_METRIC_TOGGLE_PREFIX)
            and action_key[len(_METRIC_TOGGLE_PREFIX) :] in pending
        }
    return set()


def _chip_container_key(
    message_index: int,
    action_key: str,
    *,
    selected: bool,
    row_suffix: str | None = None,
) -> str:
    suffix = _button_key(action_key)
    if selected:
        return f"insight_chip_selected_{message_index}_{suffix}"
    if (
        row_suffix in {"controls", "reset"}
        or _action_chip_role(action_key) in {"control", "reset"}
    ):
        return f"insight_chat_chip_action_control_{message_index}_{suffix}"
    return f"insight_chat_chip_{message_index}_{suffix}"


def _action_chip_role(action_key: str) -> str:
    if action_key == "reset_chat":
        return "reset"
    if action_key in {_FILTER_APPLY_KEY, _CHART_COMPARE_APPLY_KEY, "clear_filters"}:
        return "control"
    return "default"


def _location_filter_rows(
    options: list[tuple[str, str]],
) -> list[tuple[str, list[tuple[str, str]]]]:
    toggles = [
        (action_key, label)
        for action_key, label in options
        if action_key.startswith(_LOCATION_TOGGLE_PREFIX)
    ]
    controls = [
        (action_key, label)
        for action_key, label in options
        if action_key in {_FILTER_APPLY_KEY, "clear_filters"}
    ]
    rows: list[tuple[str, list[tuple[str, str]]]] = []
    if toggles:
        rows.append(("locations", toggles))
    actions = [*controls, _RESET_CHAT_OPTION]
    if actions:
        rows.append(("controls", actions))
    return rows


def _metric_compare_rows(
    options: list[tuple[str, str]],
) -> list[tuple[str, list[tuple[str, str]]]]:
    toggles = [
        (action_key, label)
        for action_key, label in options
        if action_key.startswith(_METRIC_TOGGLE_PREFIX)
    ]
    controls = [
        (action_key, label)
        for action_key, label in options
        if action_key == _CHART_COMPARE_APPLY_KEY
    ]
    rows: list[tuple[str, list[tuple[str, str]]]] = []
    if toggles:
        rows.append(("metrics", toggles))
    if controls:
        rows.append(("controls", controls))
    return rows


def _chat_avatar_for_role(role: str) -> str:
    if role == "user":
        return str(_CHAT_USER_AVATAR)
    return str(_CHAT_ASSISTANT_AVATAR)


def _number_column_config(df: DataFrame) -> dict[str, st.column_config.NumberColumn]:
    """Build Streamlit column config so numeric cells show thousands separators."""
    config: dict[str, st.column_config.NumberColumn] = {}
    for column in df.columns:
        series = df[column]
        if not series.dtype.kind in "iufc":
            continue
        if series.dtype.kind in "iu":
            config[column] = st.column_config.NumberColumn(format="%,d")
        else:
            config[column] = st.column_config.NumberColumn(format="localized")
    return config


def _display_insight_table(table: DataFrame) -> None:
    st.dataframe(
        table,
        use_container_width=True,
        column_config=_number_column_config(table),
    )


def _location_from_toggle_key(action_key: str) -> str | None:
    if not action_key.startswith(_LOCATION_TOGGLE_PREFIX):
        return None
    index_text = action_key[len(_LOCATION_TOGGLE_PREFIX) :]
    try:
        index = int(index_text)
    except ValueError:
        return index_text or None
    options = st.session_state.get("data_insight_filter_location_options") or []
    if 0 <= index < len(options):
        return str(options[index])
    return None


def _render_action_content(
    df: DataFrame,
    name_col: str,
    value_cols: list[str],
    action: str,
    *,
    dataset_label: str,
    metric: str | None = None,
    chart_metrics: list[str] | None = None,
    map_image_b64: str | None = None,
) -> None:
    if df.empty:
        st.caption(UI_COPY.insight_no_results)
        return

    if action == "summary":
        table = summary_table(df, value_cols)
        if table.empty:
            st.caption("No numeric metrics to summarize.")
        else:
            _display_insight_table(table)
        return

    if action == "missing":
        _display_insight_table(missing_table(df))
        return

    if action == "full_table":
        _display_insight_table(full_table(df))
        return

    if action == "download":
        href = dataframe_csv_download_href(df)
        filename = re.sub(r"[^\w\-]+", "_", dataset_label).strip("_") or "dataset"
        st.markdown(
            f'<a href="{href}" download="{filename}.csv">{UI_COPY.insight_download_label}</a>',
            unsafe_allow_html=True,
        )
        return

    if action == "map":
        if map_image_b64:
            st.image(base64.b64decode(map_image_b64), width="stretch")
        else:
            st.caption("Map snapshot is not available.")
        return

    if action == "bar_chart_compare":
        metrics = chart_metrics or []
        if len(metrics) >= 2:
            combo_chart = comparison_combo_chart(df, name_col, metrics)
            if combo_chart is not None:
                st.altair_chart(combo_chart, use_container_width=True)
                return
        if metrics:
            st.bar_chart(comparison_chart_data(df, name_col, metrics))
        return

    if action in _METRIC_ACTIONS:
        selected = metric or _selected_metric(value_cols)
        if action == "top10":
            _display_insight_table(
                ranked_table(df, name_col, selected, ascending=False),
            )
        elif action == "bottom10":
            _display_insight_table(
                ranked_table(df, name_col, selected, ascending=True),
            )
        elif action == "column_chart":
            st.bar_chart(column_chart_data(df, name_col, selected))
        else:
            st.bar_chart(chart_data(df, name_col, selected))


def _reset_chat_and_seed() -> None:
    _set_messages([])
    clear_filter_state(st.session_state)
    st.session_state.pop("data_insight_metric", None)
    st.session_state.pop("data_insight_pending_action", None)
    st.session_state.pop("data_insight_pending_action_label", None)
    st.session_state.pop("data_insight_pending_chart_metrics", None)
    st.session_state.pop("data_insight_filter_location_options", None)
    _ensure_initial_conversation()


def _handle_clear_filters(full_count: int) -> None:
    clear_filter_state(st.session_state)
    _append_message(
        {
            "role": "assistant",
            "text": UI_COPY.insight_filter_cleared.format(count=full_count),
            "streamed": False,
        }
    )
    _append_menu_message(UI_COPY.insight_followup, _primary_menu_options(), show_reset=True)


def _execute_action(
    action: str,
    metric: str | None,
    value_cols: list[str],
    *,
    chart_metrics: list[str] | None = None,
) -> None:
    if metric:
        st.session_state["data_insight_metric"] = metric
    intro = action_intro_text(
        action,
        metric,
        metrics=chart_metrics,
    )
    message: dict = {
        "role": "assistant",
        "text": intro,
        "action": action,
        "metric": metric,
        "streamed": False,
    }
    if chart_metrics:
        message["chart_metrics"] = chart_metrics
    if action == "map":
        image_bytes = insight_map_screenshot()
        if image_bytes:
            message["map_image_b64"] = base64.b64encode(image_bytes).decode("ascii")
    _append_message(message)
    _append_menu_message(UI_COPY.insight_followup, _primary_menu_options(), show_reset=True)


def _location_filter_options(location_names: list[str]) -> list[tuple[str, str]]:
    options = [
        (f"{_LOCATION_TOGGLE_PREFIX}{index}", name)
        for index, name in enumerate(location_names)
    ]
    options.append((_FILTER_APPLY_KEY, UI_COPY.insight_filter_apply))
    options.append(("clear_filters", UI_COPY.insight_clear_filters))
    return options


def _filter_confirmation_text(
    full_df: DataFrame,
    name_col: str,
    *,
    locations: list[str],
) -> str:
    filter_state = get_filter_state(st.session_state)
    filter_state["locations"] = locations
    filtered_df = apply_data_filters(full_df, name_col=name_col, **filter_state)
    status = filter_status_text(
        len(filtered_df),
        len(full_df),
        regions=filter_state["regions"],
        countries=filter_state["countries"],
        locations=locations,
        search=filter_state["search"],
    )
    if status:
        return status
    return f"Showing all {len(full_df):,} locations."


def _handle_filter_menu(full_df: DataFrame, name_col: str) -> None:
    _append_message({"role": "user", "text": UI_COPY.insight_filter})
    location_options = available_locations(full_df, name_col)
    if location_options:
        applied = _applied_locations()
        _sync_location_filter(applied)
        st.session_state["data_insight_filter_location_options"] = location_options
        _append_message(
            {
                "role": "assistant",
                "text": UI_COPY.insight_filter_prompt,
                "streamed": False,
                "kind": "location_filter_menu",
                "location_names": location_options,
                "options": _location_filter_options(location_options),
            }
        )
    else:
        _append_message(
            {
                "role": "assistant",
                "text": UI_COPY.insight_filter_unavailable,
                "streamed": False,
            }
        )
        _append_menu_message(UI_COPY.insight_followup, _primary_menu_options(), show_reset=True)


def _handle_filter_apply(full_df: DataFrame, name_col: str) -> None:
    pending = _pending_locations()
    _sync_location_filter(pending)
    _append_message({"role": "user", "text": UI_COPY.insight_filter_apply})
    status = _filter_confirmation_text(full_df, name_col, locations=pending)
    _append_message(
        {
            "role": "assistant",
            "text": UI_COPY.insight_filter_applied.format(status=status),
            "streamed": False,
        }
    )
    _append_menu_message(UI_COPY.insight_followup, _primary_menu_options(), show_reset=True)


def _chart_mode_options(value_cols: list[str]) -> list[tuple[str, str]]:
    options = [
        (f"{_CHART_SINGLE_PREFIX}{column}", display_value_column(column))
        for column in value_cols
    ]
    options.append((_CHART_COMPARE_KEY, UI_COPY.insight_chart_compare))
    return options


def _handle_chart_mode_menu(value_cols: list[str]) -> None:
    _append_message(
        {
            "role": "assistant",
            "text": UI_COPY.insight_chart_mode_prompt,
            "streamed": False,
            "kind": "chart_mode_menu",
            "options": _chart_mode_options(value_cols),
        }
    )


def _metric_compare_options(value_cols: list[str]) -> list[tuple[str, str]]:
    options = [
        (f"{_METRIC_TOGGLE_PREFIX}{column}", display_value_column(column))
        for column in value_cols
    ]
    options.append((_CHART_COMPARE_APPLY_KEY, UI_COPY.insight_filter_apply))
    return options


def _handle_chart_compare_menu(value_cols: list[str]) -> None:
    _set_pending_chart_metrics([])
    _append_message(
        {
            "role": "assistant",
            "text": UI_COPY.insight_chart_compare_prompt,
            "streamed": False,
            "kind": "metric_compare_menu",
            "options": _metric_compare_options(value_cols),
        }
    )


def _handle_chart_compare_apply(value_cols: list[str]) -> None:
    pending = _pending_chart_metrics()
    if len(pending) != 2:
        _append_message(
            {
                "role": "assistant",
                "text": UI_COPY.insight_chart_compare_min,
                "streamed": False,
                "kind": "metric_compare_menu",
                "options": _metric_compare_options(value_cols),
            }
        )
        st.rerun()

    _append_message({"role": "user", "text": UI_COPY.insight_filter_apply})
    _execute_action(
        "bar_chart_compare",
        None,
        value_cols,
        chart_metrics=pending,
    )
    st.session_state.pop("data_insight_pending_chart_metrics", None)
    st.rerun()


def _handle_action(
    action: str,
    label: str,
    *,
    full_df: DataFrame,
    name_col: str,
    value_cols: list[str],
    metric: str | None = None,
    append_user: bool = True,
) -> None:
    if action == "reset_chat":
        _reset_chat_and_seed()
        st.rerun()

    if action == "clear_filters":
        if append_user:
            _append_message({"role": "user", "text": label})
        _handle_clear_filters(full_count=st.session_state.get("_data_insight_full_count", 0))
        st.rerun()

    if action == "map":
        _execute_action(action, metric, value_cols)
        st.rerun()

    if append_user:
        _append_message({"role": "user", "text": label})

    if action == "bar_chart" and len(value_cols) > 1 and metric is None:
        _handle_chart_mode_menu(value_cols)
        st.rerun()

    if action in _METRIC_ACTIONS and action != "bar_chart" and len(value_cols) > 1 and metric is None:
        st.session_state["data_insight_pending_action"] = action
        st.session_state["data_insight_pending_action_label"] = label
        metric_options = [
            (f"__metric__:{column}", display_value_column(column)) for column in value_cols
        ]
        _append_message(
            {
                "role": "assistant",
                "text": UI_COPY.insight_metric_prompt,
                "streamed": False,
                "kind": "metric_menu",
                "options": metric_options,
            }
        )
        st.rerun()

    _execute_action(action, metric, value_cols)
    st.rerun()


def _handle_menu_click(
    action_key: str,
    label: str,
    *,
    full_df: DataFrame,
    name_col: str,
    value_cols: list[str],
) -> None:
    if action_key == "__filter__":
        _handle_filter_menu(full_df, name_col)
        st.rerun()

    if action_key.startswith(_LOCATION_TOGGLE_PREFIX):
        location = _location_from_toggle_key(action_key)
        if location is not None:
            location_key = location_filter_key(location)
            _sync_location_filter(_toggle_item(_pending_locations(), location_key))
        st.rerun()

    if action_key == _FILTER_APPLY_KEY:
        _handle_filter_apply(full_df, name_col)
        st.rerun()

    if action_key.startswith(_CHART_SINGLE_PREFIX):
        metric = action_key[len(_CHART_SINGLE_PREFIX) :]
        _append_message({"role": "user", "text": label})
        _execute_action("bar_chart", metric, value_cols)
        st.rerun()

    if action_key == _CHART_COMPARE_KEY:
        _append_message({"role": "user", "text": label})
        _handle_chart_compare_menu(value_cols)
        st.rerun()

    if action_key.startswith(_METRIC_TOGGLE_PREFIX):
        metric = action_key[len(_METRIC_TOGGLE_PREFIX) :]
        if metric in value_cols:
            _set_pending_chart_metrics(_toggle_chart_metric(_pending_chart_metrics(), metric))
        st.rerun()

    if action_key == _CHART_COMPARE_APPLY_KEY:
        _handle_chart_compare_apply(value_cols)
        st.rerun()

    if action_key.startswith("__metric__:"):
        metric = action_key.split("__metric__:", 1)[1]
        pending_action = st.session_state.pop("data_insight_pending_action", None)
        st.session_state.pop("data_insight_pending_action_label", None)
        if pending_action:
            _append_message({"role": "user", "text": label})
            _execute_action(pending_action, metric, value_cols)
        st.rerun()

    _handle_action(
        action_key,
        label,
        full_df=full_df,
        name_col=name_col,
        value_cols=value_cols,
    )


def _render_message_button_row(
    options: list[tuple[str, str]],
    message_index: int,
    row_suffix: str,
    *,
    selected_keys: set[str],
    interactive: bool,
    full_df: DataFrame,
    name_col: str,
    value_cols: list[str],
) -> None:
    if not options:
        return

    with st.container(key=f"insight_chat_chips_{message_index}_{row_suffix}"):
        for action_key, option_label in options:
            selected = action_key in selected_keys
            display_label = _chip_label(option_label, selected=selected)
            button_key = f"insight_btn_{message_index}_{_button_key(action_key)}"
            chip_container_key = _chip_container_key(
                message_index,
                action_key,
                selected=selected,
                row_suffix=row_suffix,
            )
            with st.container(key=chip_container_key):
                if interactive and st.button(display_label, key=button_key):
                    _handle_menu_click(
                        action_key,
                        option_label,
                        full_df=full_df,
                        name_col=name_col,
                        value_cols=value_cols,
                    )
                elif not interactive:
                    st.button(display_label, key=button_key, disabled=True)


def _menu_options_without_reset(
    options: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    return [
        (action_key, label)
        for action_key, label in options
        if action_key != "reset_chat"
    ]


def _render_message_buttons(
    options: list[tuple[str, str]],
    message_index: int,
    *,
    interactive: bool,
    full_df: DataFrame,
    name_col: str,
    value_cols: list[str],
    kind: str = "menu",
    show_reset: bool = False,
) -> None:
    if not options and not show_reset:
        return

    selected_keys = (
        _selected_toggle_keys(kind, options) if kind in _TOGGLE_MENU_KINDS else set()
    )

    if kind == "location_filter_menu":
        for row_suffix, row_options in _location_filter_rows(options):
            _render_message_button_row(
                row_options,
                message_index,
                row_suffix,
                selected_keys=selected_keys,
                interactive=interactive,
                full_df=full_df,
                name_col=name_col,
                value_cols=value_cols,
            )
        return

    if kind == "metric_compare_menu":
        for row_suffix, row_options in _metric_compare_rows(options):
            _render_message_button_row(
                row_options,
                message_index,
                row_suffix,
                selected_keys=selected_keys,
                interactive=interactive,
                full_df=full_df,
                name_col=name_col,
                value_cols=value_cols,
            )
        return

    menu_options = _menu_options_without_reset(options)
    if menu_options:
        _render_message_button_row(
            menu_options,
            message_index,
            "menu",
            selected_keys=selected_keys,
            interactive=interactive,
            full_df=full_df,
            name_col=name_col,
            value_cols=value_cols,
        )

    if show_reset or any(action_key == "reset_chat" for action_key, _ in options):
        _render_message_button_row(
            [_RESET_CHAT_OPTION],
            message_index,
            "reset",
            selected_keys=set(),
            interactive=interactive,
            full_df=full_df,
            name_col=name_col,
            value_cols=value_cols,
        )


def _render_message(
    message: dict,
    message_index: int,
    *,
    filtered_df: DataFrame,
    name_col: str,
    value_cols: list[str],
    dataset_label: str,
    full_df: DataFrame,
    is_latest: bool,
) -> None:
    role = message.get("role", "assistant")
    with st.chat_message(role, avatar=_chat_avatar_for_role(role)):
        text = message.get("text")
        action = message.get("action")
        kind = message.get("kind")

        if text:
            if role == "assistant" and not message.get("streamed"):
                _render_streamed_text(text, streamed=False)
                message["streamed"] = True
            elif text:
                st.markdown(text)

        menu_kinds = {
            "menu",
            "location_filter_menu",
            "filter_menu",
            "metric_menu",
            "chart_mode_menu",
            "metric_compare_menu",
        }
        if kind in menu_kinds:
            if kind == "location_filter_menu" and is_latest:
                location_names = message.get("location_names")
                if isinstance(location_names, list) and location_names:
                    st.session_state["data_insight_filter_location_options"] = location_names
            _render_message_buttons(
                list(message.get("options") or []),
                message_index,
                interactive=is_latest,
                full_df=full_df,
                name_col=name_col,
                value_cols=value_cols,
                kind=kind or "menu",
                show_reset=bool(message.get("show_reset")),
            )

        if action:
            _render_action_content(
                filtered_df,
                name_col,
                value_cols,
                action,
                dataset_label=dataset_label,
                metric=message.get("metric"),
                chart_metrics=message.get("chart_metrics"),
                map_image_b64=message.get("map_image_b64"),
            )


def render_data_insight_chat(
    filtered_df: DataFrame,
    full_df: DataFrame,
    name_col: str,
    value_cols: list[str],
    dataset_label: str,
) -> None:
    """Render the conversational insight chat below the map."""
    if full_df is None or full_df.empty or not value_cols:
        return

    st.session_state["_data_insight_full_count"] = len(full_df)
    _ensure_initial_conversation()
    messages = _messages()

    for index, message in enumerate(messages):
        _render_message(
            message,
            index,
            filtered_df=filtered_df,
            name_col=name_col,
            value_cols=value_cols,
            dataset_label=dataset_label,
            full_df=full_df,
            is_latest=index == len(messages) - 1,
        )
