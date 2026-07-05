"""Centered modal picker for built-in dataset / data-source selection."""

from __future__ import annotations

import html
from collections.abc import Callable, Sequence

import streamlit as st

from labelmap.ui_copy import UI_COPY, display_picker_source
from labelmap.world_bank_baselines import (
    WORLD_BANK_BASELINE_BY_LABEL,
    WORLD_BANK_BASELINE_LABELS,
    world_bank_source_label,
)

WORLD_INDEX_METRIC_OPTIONS = (
    "Index ETF 1d%",
    "Index ETF 7d%",
    "Index ETF 30d%",
)

PICKER_SECTIONS = (
    (UI_COPY.picker_section_markets, WORLD_INDEX_METRIC_OPTIONS),
    (UI_COPY.picker_section_countries, WORLD_BANK_BASELINE_LABELS),
)

_PICKER_OPEN_KEY = "_kpi_picker_open"
_STARTUP_DONE_KEY = "_kpi_picker_startup_done"


def _open_kpi_picker() -> None:
    st.session_state[_PICKER_OPEN_KEY] = True
    st.session_state.pop("kpi_picker_search", None)


def _finish_kpi_picker() -> None:
    """Close the picker and skip the first-startup auto-open for this session."""
    st.session_state[_PICKER_OPEN_KEY] = False
    st.session_state[_STARTUP_DONE_KEY] = True


def _option_search_text(option: str, format_func: Callable[[str], str]) -> str:
    """Build searchable text for one dataset option."""
    parts = [
        option,
        format_func(option),
        display_picker_source(option),
    ]
    if option in WORLD_INDEX_METRIC_OPTIONS:
        parts.append(UI_COPY.picker_section_markets)
    elif option in WORLD_BANK_BASELINE_BY_LABEL:
        parts.append(UI_COPY.picker_section_countries)
    baseline = WORLD_BANK_BASELINE_BY_LABEL.get(option)
    if baseline is not None:
        full_label = world_bank_source_label(baseline)
        if full_label.startswith("Source: "):
            parts.append(full_label[len("Source: ") :])
        else:
            parts.append(full_label)
    return " ".join(parts).casefold()


def filter_baseline_options(
    options: Sequence[str],
    query: str,
    format_func: Callable[[str], str],
) -> list[str]:
    """Filter dataset options by label, source, section, or indicator code."""
    normalized = query.strip().casefold()
    if not normalized:
        return list(options)
    filtered: list[str] = []
    for option in options:
        if normalized in _option_search_text(option, format_func):
            filtered.append(option)
    return filtered


def _render_option_row(
    option: str,
    current: str,
    session_key: str,
    format_func: Callable[[str], str],
) -> None:
    selected = option == current
    row_class = "labelmap-kpi-row-selected" if selected else ""
    name_col, source_col = st.columns([0.55, 0.45])
    with name_col:
        if st.button(
            format_func(option),
            key=f"kpi_pick_{option}",
            use_container_width=True,
            type="primary" if selected else "secondary",
        ):
            _finish_kpi_picker()
            st.session_state[session_key] = option
            st.session_state.pop("kpi_picker_search", None)
            st.rerun(scope="app")
    with source_col:
        st.markdown(
            (
                f'<p class="labelmap-kpi-source {row_class}">'
                f"{display_picker_source(option)}"
                "</p>"
            ),
            unsafe_allow_html=True,
        )


def _render_picker_rows(
    options: Sequence[str],
    current: str,
    session_key: str,
    format_func: Callable[[str], str],
    *,
    search_query: str = "",
) -> None:
    if not options:
        st.caption(UI_COPY.picker_empty_state)
        return

    with st.container(height=360, key="kpi_picker_scroll"):
        if search_query.strip():
            for option in options:
                _render_option_row(option, current, session_key, format_func)
            return

        options_set = set(options)
        for section_title, section_keys in PICKER_SECTIONS:
            section_options = [key for key in section_keys if key in options_set]
            if not section_options:
                continue
            st.markdown(
                f'<p class="labelmap-kpi-picker-section">{section_title}</p>',
                unsafe_allow_html=True,
            )
            for option in section_options:
                _render_option_row(option, current, session_key, format_func)


@st.dialog(
    UI_COPY.choose_dataset,
    width="medium",
    dismissible=True,
    on_dismiss=_finish_kpi_picker,
)
def kpi_picker_dialog(
    current: str,
    *,
    options: Sequence[str],
    session_key: str,
    format_func: Callable[[str], str],
) -> None:
    """Open the centered dataset picker modal."""
    current = st.session_state.get(session_key, current)
    st.text_input(
        "Search",
        key="kpi_picker_search",
        placeholder=UI_COPY.picker_search_placeholder,
        label_visibility="collapsed",
    )
    search_query = str(st.session_state.get("kpi_picker_search", ""))
    filtered = filter_baseline_options(options, search_query, format_func)
    _render_picker_rows(
        filtered,
        current,
        session_key,
        format_func,
        search_query=search_query,
    )
    if st.button(
        UI_COPY.picker_upload_file,
        key="kpi_picker_upload",
        type="tertiary",
    ):
        _finish_kpi_picker()
        st.session_state["custom_map_toggle"] = True
        st.session_state.pop("kpi_picker_search", None)
        st.rerun(scope="app")


def render_kpi_picker_trigger(
    options: Sequence[str],
    *,
    session_key: str,
    format_func: Callable[[str], str],
) -> str:
    """Render a dropdown-styled trigger and return the active data source."""
    if not options:
        return ""

    if session_key not in st.session_state or st.session_state[session_key] not in options:
        st.session_state[session_key] = options[0]

    st.session_state.setdefault(_PICKER_OPEN_KEY, False)
    st.session_state.setdefault(_STARTUP_DONE_KEY, False)

    if not st.session_state[_STARTUP_DONE_KEY] and not st.session_state[_PICKER_OPEN_KEY]:
        st.session_state[_PICKER_OPEN_KEY] = True

    current = st.session_state[session_key]
    current_label = format_func(current)
    chevron = getattr(UI_COPY, "choose_dataset_chevron", "▾")

    with st.container(key="kpi_picker_stack"):
        st.markdown(
            (
                '<div class="labelmap-kpi-trigger-face">'
                f'<div class="labelmap-kpi-trigger-action">{html.escape(UI_COPY.choose_dataset)} '
                f'<span class="labelmap-kpi-chevron">{chevron}</span></div>'
                f'<div class="labelmap-kpi-trigger-selection">'
                f"({html.escape(current_label)})"
                "</div></div>"
            ),
            unsafe_allow_html=True,
        )
        st.button(
            UI_COPY.choose_dataset,
            key="kpi_picker_trigger",
            use_container_width=True,
            type="secondary",
            help=current_label,
            on_click=_open_kpi_picker,
        )

    if st.session_state.get(_PICKER_OPEN_KEY):
        kpi_picker_dialog(
            current,
            options=options,
            session_key=session_key,
            format_func=format_func,
        )

    return st.session_state[session_key]
