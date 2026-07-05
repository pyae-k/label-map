"""LabelMap — Streamlit entry point.

Run locally:
    streamlit run label_map.py
"""

from html import escape

import streamlit as st
import streamlit.components.v1 as components

from labelmap.charts import chart_type_label
from labelmap.config import (
    DEFAULT_CHART_COLORS,
    DEFAULT_MAP_STYLE,
    INTERACTIVE_MAP_HEIGHT_CSS,
    MAP_STYLE_OPTIONS,
)
from labelmap.data_filter import apply_data_filters, get_filter_state
from labelmap.data_insight_chat import restore_chat_session, save_chat_session
from labelmap.data_insight_ui import render_data_insight_panel, set_insight_map_context
from labelmap.data_io import (
    column_default,
    coordinate_column_errors,
    get_nonzero_values,
    load_sample_dataframe,
    pick_default,
    read_spreadsheet,
    spreadsheet_upload_key,
)
from labelmap.export import sample_template_download_href
from labelmap.kpi_picker import render_kpi_picker_trigger
from labelmap.map_session import (
    clear_folium_widget_state,
    label_positions_from_session,
    reset_map_to_startup_view,
)
from labelmap.ui import render_contact_with_docs, render_label_map_fragment
from labelmap.ui_copy import UI_COPY, display_dataset, display_source_attribution, display_value_column
from labelmap.world_bank_baselines import (
    WORLD_BANK_BASELINE_BY_LABEL,
    WORLD_BANK_BASELINE_LABELS,
    world_bank_source_label,
)


def _value_label_text(value_col, max_chars=24):
    label = display_value_column(value_col)
    if len(label) <= max_chars:
        return label, label
    return f"{label[: max_chars - 1]}…", label


def _dataset_dropdown_label(dataset_key):
    return display_dataset(dataset_key)


def _value_dropdown_label(value_col):
    return display_value_column(value_col)


def _default_color_for_value_col(value_col, color_idx):
    normalized = str(value_col).strip().lower().replace("_", " ")
    if "last value" in normalized or "current value" in normalized:
        return "#00DAC3"
    if "ago" in normalized:
        return "#FF9230"
    if "1d %" in normalized or "1 day" in normalized:
        return "#FF9230"
    if "7d %" in normalized or "7 day" in normalized:
        return "#00DAC3"
    if "30d %" in normalized or "30 day" in normalized:
        return "#7A6BFF"
    return DEFAULT_CHART_COLORS[color_idx % len(DEFAULT_CHART_COLORS)]


def _world_index_legend_items():
    return [
        {
            "label": display_source_attribution("Source: Yahoo Finance"),
            "muted": True,
            "spacer_before": True,
        }
    ]


def _world_bank_legend_items(source_mode):
    baseline = WORLD_BANK_BASELINE_BY_LABEL.get(source_mode)
    if baseline is None:
        return []
    return [
        {
            "label": display_source_attribution(world_bank_source_label(baseline)),
            "muted": True,
            "spacer_before": True,
        }
    ]


WORLD_INDEX_METRIC_OPTIONS = [
    "Index ETF 1d%",
    "Index ETF 7d%",
    "Index ETF 30d%",
]
BASELINE_DATA_SOURCE_OPTIONS = [
    *WORLD_INDEX_METRIC_OPTIONS,
    *WORLD_BANK_BASELINE_LABELS,
]
WORLD_INDEX_COMPARISON_COLUMNS = {
    "Index ETF 1d%": ["1d Ago", "Last value"],
    "Index ETF 7d%": ["7d Ago", "Last value"],
    "Index ETF 30d%": ["30d Ago", "Last value"],
}
WORLD_INDEX_PERCENT_COLUMNS = {
    "Index ETF 1d%": "World Index 1d %",
    "Index ETF 7d%": "World Index 7d %",
    "Index ETF 30d%": "World Index 30d %",
}


def _comparison_columns_have_data(df, comparison_cols):
    if not comparison_cols or not all(column in df.columns for column in comparison_cols):
        return False
    return bool(df[comparison_cols].notna().any().all())


def _world_index_value_cols(available_value_cols, selected_world_index_metric, df=None):
    comparison_cols = [
        column
        for column in WORLD_INDEX_COMPARISON_COLUMNS.get(selected_world_index_metric, [])
        if column in available_value_cols
    ]
    percent_col = WORLD_INDEX_PERCENT_COLUMNS.get(selected_world_index_metric)
    if df is not None and comparison_cols and _comparison_columns_have_data(df, comparison_cols):
        return comparison_cols
    if percent_col in available_value_cols:
        return [percent_col]
    return comparison_cols


def _default_value_cols(
    available_value_cols,
    all_cols,
    *,
    using_world_bank_baseline,
    source_mode,
    using_sample,
    selected_world_index_metric,
    df=None,
):
    positional_value_cols = [col for col in all_cols[3:] if col in available_value_cols]
    preferred_value_cols = []
    for candidate in [
        "World Index 1d %",
        "World Index 7d %",
        "World Index 30d %",
        "Index ETF 1d%",
        "Index ETF 7d%",
        "Index ETF 30d%",
    ]:
        matched_col = pick_default([candidate], available_value_cols)
        if matched_col is not None and matched_col not in preferred_value_cols:
            preferred_value_cols.append(matched_col)
    if preferred_value_cols:
        default_value_cols = preferred_value_cols[:3]
    else:
        fallback_defaults = positional_value_cols or available_value_cols
        if using_world_bank_baseline:
            baseline = WORLD_BANK_BASELINE_BY_LABEL[source_mode]
            if baseline.value_column in available_value_cols:
                default_value_cols = [baseline.value_column]
            else:
                default_value_cols = fallback_defaults[:1] if fallback_defaults else []
        else:
            default_value_cols = fallback_defaults[:3]

    if (
        using_sample
        and selected_world_index_metric is not None
        and selected_world_index_metric in WORLD_INDEX_COMPARISON_COLUMNS
    ):
        comparison_cols = _world_index_value_cols(
            available_value_cols,
            selected_world_index_metric,
            df=df,
        )
        return comparison_cols or default_value_cols
    return default_value_cols


def _panel_divider():
    st.markdown('<div class="labelmap-panel-divider"></div>', unsafe_allow_html=True)


st.set_page_config(
    page_title="LabelMap",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    :root {
        --labelmap-font: "Inter", -apple-system, BlinkMacSystemFont, "SF Pro Text",
            "SF Pro Display", "Helvetica Neue", Arial, sans-serif;
        --labelmap-text: #f5f5f7;
        --labelmap-muted: rgba(245,245,247,0.72);
        --labelmap-accent: #0a84ff;
        --labelmap-surface: rgba(28,28,30,0.96);
        --labelmap-border: rgba(255,255,255,0.12);
        --labelmap-control-bg: #3a3a3c;
        --labelmap-control-bg-hover: #48484a;
        --labelmap-control-bg-active: #525255;
        --labelmap-control-border: rgba(255,255,255,0.16);
        --labelmap-control-radius: 6px;
        --labelmap-control-focus: 0 0 0 3px rgba(10,132,255,0.35);
        --labelmap-switch-shell: #d1d1d6;
        --labelmap-switch-shell-border: #d1d1d6;
        --labelmap-switch-on-bg: #1c3a57;
        --labelmap-switch-on-text: #ffffff;
        --labelmap-switch-off-bg: #b8b8bd;
        --labelmap-switch-off-text: #ffffff;
        --labelmap-text-size: 10pt;
        --labelmap-heading-size: 10pt;
        --labelmap-italic-size: 8pt;
        --labelmap-panel-gap: 0;
        --labelmap-divider-gap: 0;
        --labelmap-section-gap: 0;
        --labelmap-column-gap: 1ch;
        --labelmap-map-height: """
    + INTERACTIVE_MAP_HEIGHT_CSS
    + """;
    }
    html, body, .stApp,
    .stApp p,
    .stApp div,
    .stApp span,
    .stApp label,
    .stApp button,
    .stApp input,
    .stApp textarea,
    .stApp select,
    .stApp [data-baseweb="select"] *,
    .stApp [data-baseweb="tag"] *,
    .stApp [data-testid="stMarkdownContainer"] *,
    .stApp [data-testid="stColorPicker"] * {
        font-family: var(--labelmap-font) !important;
    }
    .stApp {
        color: var(--labelmap-text);
    }
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(180deg, #111113 0%, #0b0b0c 100%);
        color: var(--labelmap-text);
    }
    [data-testid="stSidebar"] {
        background: #111113;
        border-right: 1px solid var(--labelmap-border);
    }
    [data-testid="stSidebar"] * {
        color: var(--labelmap-text);
    }
    .stApp h1,
    .stApp h2,
    .stApp h3,
    .stApp h4,
    .stApp h5,
    .stApp h6,
    .stMarkdown h1,
    .stMarkdown h2,
    .stMarkdown h3,
    .stMarkdown h4,
    .stMarkdown h5,
    .stMarkdown h6,
    .stApp p.labelmap-title,
    .labelmap-title {
        font-family: var(--labelmap-font) !important;
        font-size: var(--labelmap-heading-size) !important;
        font-weight: 700 !important;
        font-style: normal !important;
        color: var(--labelmap-text) !important;
        margin: 0 0 var(--labelmap-section-gap) 0 !important;
        padding: 0 !important;
        line-height: 1.2 !important;
    }
    .stApp p,
    .stApp label,
    .stApp button,
    .stApp input,
    .stApp textarea,
    .stApp select,
    .stApp [role="checkbox"],
    .stApp [role="radio"],
    .stApp [data-testid="stSelectbox"] *,
    .stApp [data-testid="stMultiSelect"] *,
    .stApp [data-testid="stColorPicker"] *,
    .stApp [data-testid="stFileUploader"] * {
        font-size: var(--labelmap-text-size) !important;
        font-weight: 400 !important;
        color: var(--labelmap-text) !important;
    }
    .labelmap-label {
        font-size: var(--labelmap-text-size) !important;
        font-style: italic !important;
        font-weight: 600 !important;
        color: var(--labelmap-text) !important;
        margin: 0 !important;
    }
    .labelmap-label a {
        font-size: var(--labelmap-text-size) !important;
        font-style: italic !important;
        font-weight: 600 !important;
        color: var(--labelmap-accent) !important;
        white-space: nowrap !important;
        word-break: keep-all !important;
        overflow-wrap: normal !important;
    }
    .stApp p.labelmap-contact-label {
        font-size: var(--labelmap-italic-size) !important;
        font-style: italic !important;
        font-weight: 400 !important;
        color: var(--labelmap-text) !important;
        margin: 0 !important;
        line-height: 1.2 !important;
    }
    .stApp p.labelmap-contact-label a {
        font-size: inherit !important;
        font-weight: inherit !important;
        font-style: inherit !important;
        white-space: nowrap !important;
        word-break: keep-all !important;
        overflow-wrap: normal !important;
    }
    .labelmap-contact-block .labelmap-contact-divider {
        height: 1px;
        margin: 0.5rem 0 !important;
        background: rgba(255, 255, 255, 0.14);
        width: 100%;
    }
    .labelmap-doc-icons {
        display: inline-flex !important;
        align-items: center !important;
        gap: 0.35rem !important;
        margin-left: 0.35rem !important;
        vertical-align: middle !important;
        flex-wrap: wrap !important;
    }
    .labelmap-contact-block .labelmap-doc-icons {
        display: flex !important;
        margin-left: 0 !important;
    }
    .labelmap-doc-icon {
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 22px !important;
        height: 22px !important;
        border-radius: 50% !important;
        background: var(--labelmap-control-bg) !important;
        border: 1px solid var(--labelmap-control-border) !important;
        color: var(--labelmap-muted) !important;
        text-decoration: none !important;
        flex-shrink: 0 !important;
        padding: 0 !important;
        cursor: pointer !important;
        line-height: 1 !important;
        font: inherit !important;
        appearance: none !important;
        -webkit-appearance: none !important;
    }
    .labelmap-doc-icon svg {
        width: 12px !important;
        height: 12px !important;
        display: block !important;
    }
    .labelmap-doc-icon:hover,
    .labelmap-doc-icon:focus {
        background: var(--labelmap-control-bg-hover) !important;
        color: var(--labelmap-text) !important;
        border-color: var(--labelmap-accent) !important;
        outline: none !important;
        box-shadow: var(--labelmap-control-focus) !important;
    }
    .st-key-doc_readme_trigger,
    .st-key-doc_technical_trigger,
    .st-key-doc_user_guide_trigger {
        display: none !important;
    }
    .labelmap-mode-label {
        font-size: var(--labelmap-italic-size) !important;
        font-style: normal !important;
        font-weight: 600 !important;
        color: var(--labelmap-text) !important;
        margin: 0 !important;
        text-align: center !important;
        line-height: 1.1 !important;
        white-space: normal !important;
    }
    .stApp p.labelmap-control-text,
    [data-testid="stRadio"] label p,
    [data-testid="stCheckbox"] label p {
        font-size: var(--labelmap-italic-size) !important;
        font-style: italic !important;
        font-weight: 400 !important;
        color: var(--labelmap-text) !important;
        margin: 0 !important;
        line-height: 1.2 !important;
        display: inline-flex !important;
        align-items: center !important;
    }
    [data-testid="stSelectbox"] [data-baseweb="select"] *,
    [data-testid="stMultiSelect"] [data-baseweb="select"] * {
        font-size: var(--labelmap-italic-size) !important;
        font-style: italic !important;
        font-weight: 400 !important;
    }
    .stApp [data-testid="stSelectbox"] [data-baseweb="select"],
    .stApp [data-testid="stMultiSelect"] [data-baseweb="select"] {
        background-color: var(--labelmap-control-bg) !important;
        border: 1px solid var(--labelmap-control-border) !important;
        border-radius: var(--labelmap-control-radius) !important;
        box-shadow: inset 0 0.5px 0 rgba(255,255,255,0.06) !important;
        transition: background-color 0.15s ease, border-color 0.15s ease !important;
    }
    .stApp [data-testid="stSelectbox"] [data-baseweb="select"] > div,
    .stApp [data-testid="stMultiSelect"] [data-baseweb="select"] > div {
        background-color: transparent !important;
    }
    .stApp [data-testid="stSelectbox"] [data-baseweb="select"]:hover,
    .stApp [data-testid="stMultiSelect"] [data-baseweb="select"]:hover {
        background-color: var(--labelmap-control-bg-hover) !important;
    }
    .stApp [data-testid="stSelectbox"] [data-baseweb="select"]:focus-within,
    .stApp [data-testid="stMultiSelect"] [data-baseweb="select"]:focus-within {
        box-shadow: var(--labelmap-control-focus) !important;
        border-color: var(--labelmap-accent) !important;
    }
    [data-baseweb="popover"] {
        background-color: var(--labelmap-control-bg) !important;
        border: 1px solid var(--labelmap-control-border) !important;
        border-radius: var(--labelmap-control-radius) !important;
    }
    [data-baseweb="popover"] [role="listbox"],
    [data-baseweb="popover"] ul {
        background-color: var(--labelmap-control-bg) !important;
        border: 1px solid var(--labelmap-control-border) !important;
        border-radius: var(--labelmap-control-radius) !important;
    }
    [data-baseweb="popover"] [role="option"]:hover,
    [data-baseweb="popover"] li:hover {
        background-color: var(--labelmap-control-bg-hover) !important;
    }
    [data-testid="stSelectbox"] [data-baseweb="select"] svg,
    [data-testid="stMultiSelect"] [data-baseweb="select"] svg {
        color: var(--labelmap-muted) !important;
        fill: var(--labelmap-muted) !important;
    }
    [data-testid="stFileUploaderDropzone"] button,
    [data-testid="stFileUploaderDropzone"] button * {
        display: none !important;
    }
    [data-testid="stFileUploader"] {
        display: none !important;
    }
    [data-testid="stFileUploaderDropzone"] {
        border: 0 !important;
        background: transparent !important;
        min-height: 0 !important;
        padding: 0 !important;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] {
        display: none !important;
    }
    .labelmap-panel-divider {
        height: 1px;
        margin: 0 !important;
        background: rgba(255, 255, 255, 0.14);
        width: 100%;
    }
    iframe[title="st.iframe"] {
        height: 0 !important;
        min-height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        border: 0 !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type {
        min-height: var(--labelmap-map-height) !important;
        align-items: stretch !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(2), > div[data-testid="stColumn"]:nth-child(2) {
        width: 100% !important;
        flex: 1 1 auto !important;
        max-width: none !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
        overflow: hidden !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(2), > div[data-testid="stColumn"]:nth-child(2) [data-testid="stVerticalBlock"] {
        height: 100% !important;
        overflow: hidden !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(2), > div[data-testid="stColumn"]:nth-child(2) [data-testid="stVerticalBlock"],
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(2), > div[data-testid="stColumn"]:nth-child(2) [data-testid="element-container"],
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(2), > div[data-testid="stColumn"]:nth-child(2) [data-testid="stCustomComponentV1"],
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(2), > div[data-testid="stColumn"]:nth-child(2) [data-testid="stIFrame"],
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(2), > div[data-testid="stColumn"]:nth-child(2) iframe {
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
        height: var(--labelmap-map-height) !important;
        min-height: var(--labelmap-map-height) !important;
        display: block !important;
        margin: 0 !important;
        padding: 0 !important;
        border: 0 !important;
        overflow: hidden !important;
    }
    .st-key-labelmap_data_insight {
        width: 100% !important;
        max-width: 100% !important;
        height: auto !important;
        min-height: 0 !important;
        margin-top: 0.5rem !important;
        border: 1px solid var(--labelmap-border) !important;
        border-radius: var(--labelmap-control-radius) !important;
        background: var(--labelmap-surface) !important;
        padding: 0.5rem 0.75rem !important;
        box-sizing: border-box !important;
    }
    .st-key-labelmap_data_insight [data-testid="stVerticalBlockBorderWrapper"] {
        height: auto !important;
        min-height: 0 !important;
        max-height: none !important;
        overflow: visible !important;
        border-color: var(--labelmap-border) !important;
    }
    .st-key-labelmap_data_insight [data-testid="stChatMessage"] {
        background: transparent !important;
        padding: 0 !important;
    }
    .st-key-labelmap_data_insight [data-testid="stChatMessage"] > img {
        width: 1.65rem !important;
        height: 1.65rem !important;
        border-radius: 50% !important;
    }
    .st-key-labelmap_data_insight [data-testid="stChatMessageContent"] .stImage img {
        width: 100% !important;
        height: auto !important;
        border-radius: var(--labelmap-control-radius) !important;
    }
    .st-key-labelmap_data_insight [data-testid="stChatMessageContent"] {
        background: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(255, 255, 255, 0.07) !important;
        border-radius: var(--labelmap-control-radius) !important;
        color: var(--labelmap-text) !important;
    }
    .st-key-labelmap_data_insight [class*="st-key-insight_chat_chips_"][data-testid="stVerticalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: wrap !important;
        align-items: center !important;
        gap: 0.3rem 0.45rem !important;
        margin-top: 0.35rem !important;
    }
    .st-key-labelmap_data_insight [data-testid="stChatMessageContent"]
        > [data-testid="stVerticalBlock"]:has([class*="st-key-insight_chat_chips_"]) {
        flex: 0 0 100% !important;
        width: 100% !important;
        max-width: 100% !important;
    }
    .st-key-labelmap_data_insight [class*="st-key-insight_chat_chips_"][class*="_controls"][data-testid="stVerticalBlock"],
    .st-key-labelmap_data_insight [class*="st-key-insight_chat_chips_"][class*="_reset"][data-testid="stVerticalBlock"] {
        margin-top: 0.55rem !important;
    }
    .st-key-labelmap_data_insight [class*="st-key-insight_chat_chips_"][data-testid="stVerticalBlock"]
        > [data-testid="stLayoutWrapper"] {
        width: auto !important;
        flex: 0 0 auto !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    .st-key-labelmap_data_insight [class*="st-key-insight_chat_chips_"] [data-testid="stElementContainer"],
    .st-key-labelmap_data_insight [class*="st-key-insight_chat_chips_"] [data-testid="element-container"] {
        width: auto !important;
        flex: 0 0 auto !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    .st-key-labelmap_data_insight [class*="st-key-insight_chat_chips_"] [data-testid="stButton"] {
        width: auto !important;
        min-width: 0 !important;
    }
    .st-key-labelmap_data_insight [class*="st-key-insight_chat_chips_"] [data-testid="stButton"] button {
        width: auto !important;
        min-height: 0 !important;
        height: auto !important;
        padding: 0.12rem 0.5rem !important;
        background: transparent !important;
        border: 1px solid rgba(255, 255, 255, 0.14) !important;
        border-radius: 999px !important;
        color: rgba(245, 245, 247, 0.86) !important;
        font-size: 0.68rem !important;
        font-weight: 400 !important;
        font-style: normal !important;
        line-height: 1.25 !important;
        letter-spacing: 0.01em !important;
        box-shadow: none !important;
        white-space: normal !important;
        word-break: break-word !important;
        text-align: center !important;
        max-width: 100% !important;
    }
    .st-key-labelmap_data_insight [class*="st-key-insight_chip_selected_"] [data-testid="stButton"] button {
        background: rgba(255, 255, 255, 0.1) !important;
        border-color: rgba(255, 255, 255, 0.26) !important;
        color: #f5f5f7 !important;
    }
    .st-key-labelmap_data_insight [class*="st-key-insight_chat_chips_"] [data-testid="stButton"] button:hover {
        background: rgba(255, 255, 255, 0.06) !important;
        border-color: rgba(255, 255, 255, 0.22) !important;
        color: #f5f5f7 !important;
    }
    .st-key-labelmap_data_insight [class*="st-key-insight_chat_chips_"] [data-testid="stButton"] button:active {
        transform: none !important;
        background: rgba(255, 255, 255, 0.08) !important;
    }
    .st-key-labelmap_data_insight [class*="st-key-insight_chat_chips_"] [data-testid="stButton"] button:disabled {
        background: transparent !important;
        border-color: rgba(255, 255, 255, 0.06) !important;
        color: rgba(245, 245, 247, 0.38) !important;
        opacity: 1 !important;
        cursor: default !important;
    }
    .st-key-labelmap_data_insight [class*="st-key-insight_chat_chip_action_control_"] [data-testid="stButton"] button {
        background: rgba(255, 255, 255, 0.08) !important;
        border-color: rgba(255, 255, 255, 0.18) !important;
        color: #f5f5f7 !important;
    }
    .st-key-labelmap_data_insight [class*="st-key-insight_chat_chip_action_control_"] [data-testid="stButton"] button:hover {
        background: rgba(255, 255, 255, 0.12) !important;
        border-color: rgba(255, 255, 255, 0.24) !important;
        color: #ffffff !important;
    }
    .st-key-labelmap_data_insight [class*="st-key-insight_chat_chip_action_control_"] [data-testid="stButton"] button:active {
        background: rgba(255, 255, 255, 0.14) !important;
        border-color: rgba(255, 255, 255, 0.28) !important;
        color: #ffffff !important;
    }
    .st-key-labelmap_data_insight [class*="st-key-insight_chat_chip_action_control_"] [data-testid="stButton"] button:disabled {
        background: rgba(255, 255, 255, 0.05) !important;
        border-color: rgba(255, 255, 255, 0.1) !important;
        color: rgba(245, 245, 247, 0.38) !important;
        opacity: 1 !important;
        cursor: default !important;
    }
    .st-key-labelmap_data_insight [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"] {
        background: rgba(10, 132, 255, 0.08) !important;
        border-color: rgba(10, 132, 255, 0.18) !important;
    }
    .st-key-labelmap_data_insight [data-testid="stChatInput"] textarea {
        background-color: var(--labelmap-control-bg) !important;
        border: 1px solid var(--labelmap-control-border) !important;
        border-radius: var(--labelmap-control-radius) !important;
        color: var(--labelmap-text) !important;
        font-size: var(--labelmap-italic-size) !important;
    }
    .stApp a {
        color: var(--labelmap-accent) !important;
        text-decoration: none !important;
        font-weight: 700 !important;
    }
    .stApp a:hover {
        text-decoration: underline !important;
    }
    .stApp [data-testid="stCaptionContainer"] p,
    .stApp [data-testid="stCaptionContainer"] span {
        font-family: var(--labelmap-font) !important;
        font-size: var(--labelmap-text-size) !important;
        font-weight: 700 !important;
        color: var(--labelmap-muted) !important;
    }
    .stApp [data-testid="stNotification"] *,
    .stApp [data-baseweb="notification"] * {
        font-family: var(--labelmap-font) !important;
        font-weight: 700 !important;
    }
    .main .block-container,
    [data-testid="stAppViewBlockContainer"],
    [data-testid="stMainBlockContainer"] {
        padding-top: 0 !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
    }
    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stDecoration"] {
        display: none !important;
        height: 0 !important;
    }
    [data-testid="stMainBlockContainer"] [data-testid="stHorizontalBlock"]:first-of-type {
        gap: 0 !important;
        align-items: stretch !important;
    }
    [data-testid="stMainBlockContainer"] [data-testid="stHorizontalBlock"]:first-of-type
        > [data-testid="stColumn"]:first-child {
        padding-left: 1ch !important;
        padding-right: 1ch !important;
    }
    [data-testid="stMainBlockContainer"] [data-testid="stHorizontalBlock"]:first-of-type
        > [data-testid="stColumn"]:last-child {
        padding-left: 1ch !important;
        padding-right: 1ch !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) {
        padding-left: 1ch !important;
        padding-right: 1ch !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) {
        padding-left: 1ch !important;
        padding-right: 1ch !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1),
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) {
        align-self: flex-start !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"], > div[data-testid="stColumn"] {
        min-width: 0 !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) > div,
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) > div {
        display: flex !important;
        flex-direction: column !important;
        justify-content: flex-start !important;
        gap: 0 !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3)
        [data-testid="stMultiSelect"] [data-baseweb="tag"] {
        width: 100% !important;
        margin-right: 0 !important;
        justify-content: flex-start !important;
        align-items: center !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3)
        [data-testid="stMultiSelect"] [data-baseweb="tag"] span {
        width: 100% !important;
        max-width: none !important;
        overflow: visible !important;
        text-overflow: clip !important;
        text-align: left !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) [data-testid="stRadio"] > div {
        gap: 0.45rem !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) [data-testid="stRadio"] [role="radiogroup"] {
        display: flex !important;
        column-gap: 0.95rem !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) [data-testid="stRadio"] [role="radiogroup"] > label {
        gap: 0.4rem !important;
        margin-right: 0.95rem !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) [data-testid="stRadio"] [role="radiogroup"] > label:last-child {
        margin-right: 0 !important;
    }
    [data-testid="stRadio"] [role="radiogroup"][aria-label="Chart style"] {
        display: flex !important;
        align-items: center !important;
        gap: 1.05rem !important;
    }
    [data-testid="stRadio"] [role="radiogroup"][aria-label="Chart style"] > label {
        display: inline-flex !important;
        align-items: center !important;
        gap: 0.08rem !important;
        margin-right: 0 !important;
        padding-right: 0 !important;
    }
    [data-testid="stRadio"] [role="radiogroup"][aria-label="Chart style"] > label > div {
        margin: 0 !important;
    }
    [data-testid="stRadio"] [role="radiogroup"][aria-label="Chart style"] > label p {
        margin-left: 0 !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="element-container"],
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) [data-testid="element-container"] {
        margin: 0 !important;
        padding: 0 !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stVerticalBlock"] > div,
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) [data-testid="stVerticalBlock"] > div {
        margin: 0 !important;
        padding: 0 !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stVerticalBlock"],
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) [data-testid="stVerticalBlock"] {
        gap: var(--labelmap-panel-gap) !important;
        row-gap: var(--labelmap-panel-gap) !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stVerticalBlock"] [data-testid="stVerticalBlock"],
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) [data-testid="stVerticalBlock"] [data-testid="stVerticalBlock"] {
        gap: var(--labelmap-panel-gap) !important;
        row-gap: var(--labelmap-panel-gap) !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stCheckbox"] > label > div,
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) [data-testid="stCheckbox"] > label > div {
            gap: 0.08rem !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stFileUploader"],
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stSelectbox"],
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stMultiSelect"],
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stButtonGroup"],
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) [data-testid="stCheckbox"],
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) [data-testid="stRadio"],
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) [data-testid="stColorPicker"] {
        margin: 0 !important;
        padding: 0 !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stFileUploader"] > label,
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stSelectbox"] > label,
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stMultiSelect"] > label,
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stButtonGroup"] > label,
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) [data-testid="stCheckbox"] > label,
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) [data-testid="stRadio"] > label,
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) [data-testid="stColorPicker"] > label {
        margin: 0 !important;
        padding: 0 !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stDivider"],
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) [data-testid="stDivider"] {
        margin: 0 !important;
        padding: 0 !important;
        min-height: 0 !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) hr,
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) hr {
        margin: var(--labelmap-divider-gap) 0 !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stCheckbox"] > div,
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) [data-testid="stCheckbox"] > div {
        gap: 0 !important;
        row-gap: 0 !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stCheckbox"] label,
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) [data-testid="stCheckbox"] label {
        min-height: 0 !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stSelectbox"] [data-baseweb="select"],
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stMultiSelect"] [data-baseweb="select"],
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) [data-testid="stSelectbox"] [data-baseweb="select"] {
        min-height: 1.65rem !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stFileUploader"] section,
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stFileUploaderDropzone"] {
        padding-top: 0 !important;
        padding-bottom: 0 !important;
        min-height: 0 !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) [data-testid="stColorPicker"] > div {
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) [data-testid="stRadio"] label {
        justify-content: flex-start !important;
        align-items: center !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) [data-testid="stRadio"] label p {
        width: auto !important;
        text-align: left !important;
        line-height: 1.2 !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) p.labelmap-title {
        font-family: var(--labelmap-font) !important;
        font-size: var(--labelmap-text-size) !important;
        font-weight: 700 !important;
        font-style: normal !important;
        color: var(--labelmap-text) !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stMarkdownContainer"] p,
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) [data-testid="stMarkdownContainer"] p {
        margin-top: 0 !important;
        margin-bottom: 0 !important;
    }
    [data-testid="stSelectbox"] div,
    [data-testid="stMultiSelect"] div,
    [data-testid="stRadio"] div,
    [data-testid="stCheckbox"] div {
        font-family: var(--labelmap-font) !important;
    }
    [data-testid="stCheckbox"] label {
        justify-content: flex-start !important;
        align-items: center !important;
        width: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
        min-height: 1.25rem !important;
    }
    [data-testid="stRadio"] label {
        margin: 0 !important;
        padding: 0 !important;
        min-height: 1.25rem !important;
    }
    [data-testid="stCheckbox"] label p,
    [data-testid="stRadio"] label p {
        line-height: 1.05 !important;
    }
    [data-testid="stMultiSelect"] [data-baseweb="tag"] {
        margin-top: 0 !important;
        margin-bottom: 0 !important;
        background-color: var(--labelmap-control-bg-active) !important;
        border: 1px solid var(--labelmap-control-border) !important;
        border-radius: 4px !important;
    }
    .st-key-value_cols_picker [data-testid="stButtonGroup"] {
        width: 100% !important;
    }
    .st-key-value_cols_picker [data-testid="stButtonGroup"] [role="group"] {
        display: flex !important;
        flex-wrap: wrap !important;
        gap: 0.35rem !important;
        width: 100% !important;
    }
    .st-key-value_cols_picker [data-testid="stButtonGroup"] button {
        min-height: 0 !important;
        height: auto !important;
        padding: 0.15rem 0.45rem !important;
        background: transparent !important;
        border: 1px solid var(--labelmap-control-border) !important;
        border-radius: 4px !important;
        color: var(--labelmap-muted) !important;
        font-family: var(--labelmap-font) !important;
        font-size: var(--labelmap-italic-size) !important;
        font-style: italic !important;
        font-weight: 400 !important;
        line-height: 1.25 !important;
        box-shadow: none !important;
        white-space: nowrap !important;
        transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease !important;
    }
    .st-key-value_cols_picker [data-testid="stButtonGroup"] button:hover {
        background: rgba(255, 255, 255, 0.06) !important;
        border-color: rgba(255, 255, 255, 0.22) !important;
        color: var(--labelmap-text) !important;
    }
    .st-key-value_cols_picker [data-testid="stButtonGroup"] button[aria-pressed="true"] {
        background: var(--labelmap-control-bg-active) !important;
        border-color: var(--labelmap-control-border) !important;
        color: var(--labelmap-text) !important;
    }
    .st-key-value_cols_picker [data-testid="stButtonGroup"] button[aria-pressed="true"]:hover {
        background: var(--labelmap-control-bg-hover) !important;
        border-color: rgba(255, 255, 255, 0.22) !important;
        color: var(--labelmap-text) !important;
    }
    /* Additional spacing tightening */
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stSelectbox"] > div,
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stMultiSelect"] > div,
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stButtonGroup"] > div,
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) [data-testid="stSelectbox"] > div,
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) [data-testid="stColorPicker"] > div,
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stFileUploader"] > div,
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(3), > div[data-testid="stColumn"]:nth-child(3) [data-testid="stRadio"] > div {
        margin-top: 0 !important;
        margin-bottom: 0 !important;
    }
    /* iOS-style Toggle Switch */
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stCheckbox"] {
        margin: 0.3rem 0 0 !important;
        padding: 0 !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stCheckbox"] label {
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        justify-content: space-between !important;
        width: 100% !important;
        gap: 0.5rem !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stCheckbox"] label p {
        font-size: var(--labelmap-text-size) !important;
        font-weight: 600 !important;
        margin: 0 !important;
        order: 1 !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stCheckbox"] label > div {
        order: 2 !important;
    }
    /* iOS Toggle Switch Styling */
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stCheckbox"] input[type="checkbox"] {
        appearance: none !important;
        -webkit-appearance: none !important;
        width: 2.5rem !important;
        height: 1.5rem !important;
        background: #c8c8cc !important;
        border-radius: 1rem !important;
        position: relative !important;
        cursor: pointer !important;
        transition: background 0.3s ease !important;
        border: none !important;
        outline: none !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stCheckbox"] input[type="checkbox"]:checked {
        background: #34c759 !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stCheckbox"] input[type="checkbox"]::before {
        content: '' !important;
        position: absolute !important;
        width: 1.3rem !important;
        height: 1.3rem !important;
        border-radius: 50% !important;
        background: white !important;
        top: 0.1rem !important;
        left: 0.1rem !important;
        transition: transform 0.3s ease !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2) !important;
    }
    .main .block-container > div > div > div[data-testid="stHorizontalBlock"]:first-of-type
        > div[data-testid="column"]:nth-child(1), > div[data-testid="stColumn"]:nth-child(1) [data-testid="stCheckbox"] input[type="checkbox"]:checked::before {
        transform: translateX(1rem) !important;
    }
    .st-key-kpi_picker_stack {
        display: grid !important;
        grid-template-columns: minmax(0, 1fr) !important;
        width: 100% !important;
    }
    .st-key-kpi_picker_stack > div {
        grid-area: 1 / 1 !important;
        width: 100% !important;
        min-width: 0 !important;
        margin: 0 !important;
    }
    .labelmap-kpi-trigger-face {
        box-sizing: border-box !important;
        width: 100% !important;
        min-height: 3.75rem !important;
        margin: 0 !important;
        padding: 0.55rem 0.75rem !important;
        border: 1px solid var(--labelmap-control-border) !important;
        border-radius: var(--labelmap-control-radius) !important;
        background-color: var(--labelmap-control-bg) !important;
        box-shadow: inset 0 0.5px 0 rgba(255,255,255,0.06) !important;
        text-align: left !important;
        pointer-events: none !important;
        position: relative !important;
        z-index: 1 !important;
    }
    .labelmap-kpi-trigger-action {
        color: var(--labelmap-text) !important;
        font-size: var(--labelmap-text-size) !important;
        font-style: normal !important;
        font-weight: 500 !important;
        line-height: 1.25 !important;
        text-align: left !important;
    }
    .labelmap-kpi-chevron {
        font-size: 1.2em !important;
        line-height: 1 !important;
    }
    .labelmap-kpi-trigger-selection {
        margin: 0.2rem 0 0 !important;
        color: var(--labelmap-muted) !important;
        font-size: var(--labelmap-italic-size) !important;
        font-style: italic !important;
        font-weight: 400 !important;
        line-height: 1.2 !important;
        text-align: left !important;
        white-space: normal !important;
        overflow: visible !important;
        word-break: break-word !important;
    }
    .st-key-kpi_picker_stack:has(.st-key-kpi_picker_trigger button:hover) .labelmap-kpi-trigger-face,
    .st-key-kpi_picker_stack:has(.st-key-kpi_picker_trigger button:focus) .labelmap-kpi-trigger-face {
        background-color: var(--labelmap-control-bg-hover) !important;
    }
    .st-key-kpi_picker_stack:has(.st-key-kpi_picker_trigger button:focus) .labelmap-kpi-trigger-face {
        border-color: var(--labelmap-accent) !important;
        box-shadow: var(--labelmap-control-focus) !important;
    }
    .st-key-kpi_picker_stack .st-key-kpi_picker_trigger {
        position: relative !important;
        z-index: 2 !important;
        width: 100% !important;
        height: 100% !important;
        align-self: stretch !important;
    }
    .st-key-kpi_picker_stack .st-key-kpi_picker_trigger button {
        min-height: 100% !important;
        height: 100% !important;
        background: transparent !important;
        border: 1px solid transparent !important;
        color: transparent !important;
        box-shadow: none !important;
        width: 100% !important;
    }
    .st-key-kpi_picker_trigger button p {
        color: transparent !important;
        opacity: 0 !important;
    }
    .st-key-kpi_picker_trigger button:hover,
    .st-key-kpi_picker_trigger button:focus {
        background: transparent !important;
        border-color: transparent !important;
        color: transparent !important;
        box-shadow: none !important;
    }
    [data-testid="stDialog"] {
        background: rgba(0, 0, 0, 0.28) !important;
        border: none !important;
        border-radius: 0 !important;
        box-shadow: none !important;
        backdrop-filter: blur(3px);
    }
    [data-testid="stDialog"] > div {
        background: transparent !important;
    }
    [data-testid="stDialog"] [role="dialog"] {
        background-color: var(--labelmap-surface) !important;
        border: 1px solid var(--labelmap-border) !important;
        border-radius: 12px !important;
        color: var(--labelmap-text) !important;
        box-shadow:
            0 24px 64px rgba(0, 0, 0, 0.55),
            0 8px 20px rgba(0, 0, 0, 0.35) !important;
    }
    [data-testid="stDialog"] [data-testid="stTextInput"] input {
        background-color: var(--labelmap-control-bg) !important;
        border: 1px solid var(--labelmap-control-border) !important;
        border-radius: var(--labelmap-control-radius) !important;
        color: var(--labelmap-text) !important;
    }
    [data-testid="stDialog"] [data-testid="stTextInput"] input:focus {
        box-shadow: 0 0 0 1px var(--labelmap-accent) !important;
        border-color: var(--labelmap-accent) !important;
    }
    [data-testid="stDialog"] .st-key-kpi_picker_upload {
        margin-top: 0.35rem !important;
    }
    [data-testid="stDialog"] .st-key-kpi_picker_upload button {
        background: transparent !important;
        border: 0 !important;
        box-shadow: none !important;
        color: var(--labelmap-muted) !important;
        font-size: 0.82rem !important;
        font-weight: 400 !important;
        min-height: auto !important;
        padding: 0 !important;
        text-decoration: underline !important;
        text-underline-offset: 0.15rem !important;
    }
    [data-testid="stDialog"] .st-key-kpi_picker_upload button:hover,
    [data-testid="stDialog"] .st-key-kpi_picker_upload button:focus {
        background: transparent !important;
        color: var(--labelmap-accent) !important;
    }
    .labelmap-kpi-picker-section {
        margin: 0.75rem 0 0.15rem 0 !important;
        padding-left: 0.5rem !important;
        color: var(--labelmap-muted) !important;
        font-size: 0.72rem !important;
        font-weight: 600 !important;
        font-style: normal !important;
        letter-spacing: 0.06em !important;
        text-transform: uppercase !important;
        opacity: 0.85;
    }
    .st-key-kpi_picker_scroll .labelmap-kpi-picker-section:first-of-type {
        margin-top: 0.25rem !important;
    }
    .st-key-kpi_picker_scroll .labelmap-kpi-picker-section:not(:first-of-type) {
        border-top: 1px solid var(--labelmap-border);
        padding-top: 0.6rem;
    }
    .labelmap-kpi-source {
        margin: 0 !important;
        min-height: 1.75rem !important;
        display: flex !important;
        align-items: center !important;
        justify-content: flex-end !important;
        padding-right: 0.5rem !important;
        color: var(--labelmap-muted) !important;
        font-size: var(--labelmap-italic-size) !important;
        font-style: normal !important;
        line-height: 1.35 !important;
        text-align: right !important;
        word-break: break-word !important;
    }
    .labelmap-kpi-source.labelmap-kpi-row-selected {
        color: var(--labelmap-text) !important;
    }
    .st-key-kpi_picker_scroll {
        background-color: rgba(255, 255, 255, 0.02) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: var(--labelmap-control-radius) !important;
        padding: 0.25rem 0 !important;
    }
    .st-key-kpi_picker_scroll [data-testid="stHorizontalBlock"] {
        gap: 0 !important;
        margin: 0 !important;
        padding: 0 0.25rem !important;
        border-radius: var(--labelmap-control-radius) !important;
        transition: background-color 120ms ease !important;
    }
    .st-key-kpi_picker_scroll [data-testid="stHorizontalBlock"]:hover {
        background-color: var(--labelmap-control-bg-hover) !important;
    }
    [data-testid="stDialog"] [data-testid="stButton"] button {
        background-color: transparent !important;
        border: 0 !important;
        color: var(--labelmap-text) !important;
        font-style: normal !important;
        font-size: var(--labelmap-text-size) !important;
        font-weight: 400 !important;
        text-align: left !important;
        justify-content: flex-start !important;
        box-shadow: none !important;
        min-height: 1.75rem !important;
        padding-left: 0.5rem !important;
    }
    [data-testid="stDialog"] .st-key-kpi_picker_scroll [data-testid="stButton"] button:hover {
        background-color: transparent !important;
        color: var(--labelmap-text) !important;
    }
    [data-testid="stDialog"] [data-testid="stButton"] button[kind="primary"] {
        background-color: rgba(10, 132, 255, 0.14) !important;
        border: 0 !important;
        box-shadow: inset 3px 0 0 var(--labelmap-accent) !important;
        color: var(--labelmap-text) !important;
        font-weight: 500 !important;
    }
    [data-testid="stDialog"] [data-testid="stButton"] button[kind="primary"]:focus {
        box-shadow: inset 3px 0 0 var(--labelmap-accent) !important;
    }
    [data-testid="stDialog"] [data-testid="stHorizontalBlock"] + [data-testid="stHorizontalBlock"]
        [data-testid="stButton"] button {
        border-radius: var(--labelmap-control-radius) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
col_left, col_center, col_right = st.columns([1, 8, 1], gap=None)
with col_left:
    st.markdown(
        f'<p class="labelmap-title" style="margin:0;">{UI_COPY.data_source_section}</p>',
        unsafe_allow_html=True,
    )
    custom_mode = st.toggle(
        UI_COPY.use_your_own_file,
        value=False,
        key="custom_map_toggle",
    )
    prev_custom_mode = st.session_state.get("_prev_custom_map_mode")
    if prev_custom_mode is True and not custom_mode:
        reset_map_to_startup_view()
    st.session_state["_prev_custom_map_mode"] = custom_mode
    if custom_mode:
        source_mode = "Upload CSV"
        st.button(UI_COPY.upload_file, key="upload_csv_trigger", use_container_width=True)
        sample_href = sample_template_download_href()
        if sample_href:
            st.markdown(
                (
                    '<p class="labelmap-label" style="margin:-0.35rem 0 0;">'
                    f'<a href="{sample_href}" download="labelmap-sample.csv">'
                    f"{UI_COPY.download_sample_file}"
                    "</a></p>"
                ),
                unsafe_allow_html=True,
            )
    else:
        source_mode = render_kpi_picker_trigger(
            BASELINE_DATA_SOURCE_OPTIONS,
            session_key="data_source_mode",
            format_func=_dataset_dropdown_label,
        )
    sample_kind = source_mode if source_mode in WORLD_BANK_BASELINE_BY_LABEL else "world_index"
    default_template_df = load_sample_dataframe(sample_kind=sample_kind)
    uploaded_file = st.file_uploader(
        UI_COPY.upload_file,
        type=["csv"],
        key="user_spreadsheet",
        label_visibility="collapsed",
    )
    if custom_mode:
        st.markdown(
            """
            <style>
            [data-testid="stFileUploader"] {
                display: none !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        components.html(
            f"""
            <script>
            (function() {{
                const parentDoc = window.parent && window.parent.document;
                if (!parentDoc || parentDoc._labelMapUploadButtonBound) return;
                parentDoc._labelMapUploadButtonBound = true;
                parentDoc.addEventListener("click", function(event) {{
                    const button = event.target && event.target.closest(
                        '[data-testid="stButton"] button'
                    );
                    if (!button) return;
                    if ((button.textContent || "").trim() !== {UI_COPY.upload_file!r}) return;
                    const input = parentDoc.querySelector(
                        '[data-testid="stFileUploaderDropzone"] input[type="file"]'
                    );
                    if (input) {{
                        input.click();
                    }}
                }}, true);
            }})();
            </script>
            """,
            height=0,
        )

using_sample = source_mode in BASELINE_DATA_SOURCE_OPTIONS
using_world_bank_baseline = source_mode in WORLD_BANK_BASELINE_BY_LABEL
selected_world_index_metric = (
    source_mode if source_mode in WORLD_INDEX_COMPARISON_COLUMNS else None
)
if using_sample:
    data_source = source_mode
else:
    data_source = uploaded_file

with col_left:
    if using_sample and default_template_df is None:
        st.warning(UI_COPY.baseline_missing_warning)

insight_panel_args = None

if data_source is not None:
    try:
        if using_sample:
            df = default_template_df
            if df is None:
                raise FileNotFoundError("Default baseline sample could not be loaded")
        else:
            df = read_spreadsheet(data_source)
        if using_sample:
            upload_key = (
                f"default:{source_mode}:{len(df)}:"
                f"{','.join(str(column) for column in df.columns)}"
            )
        else:
            upload_key = spreadsheet_upload_key(data_source, df)

        prev_upload_key = st.session_state.get("active_upload_key")
        if prev_upload_key is None:
            st.session_state["active_upload_key"] = upload_key
        elif prev_upload_key != upload_key:
            save_chat_session(prev_upload_key)
            st.session_state["active_upload_key"] = upload_key
            st.session_state.pop("labels_overlap_resolved", None)
            st.session_state.pop("map_view", None)
            st.session_state.pop("map_view_upload_key", None)
            st.session_state.pop("map_world_fit_pending", None)
            st.session_state.pop("map_world_fit_done", None)
            st.session_state.pop("map_label_updating", None)
            st.session_state.pop("marker_type", None)
            st.session_state.pop("_last_value_col_count", None)
            st.session_state.pop("value_cols_picker_widget", None)
            st.session_state.pop("data_insight_view", None)
            st.session_state.pop("data_insight_filter_location_options", None)
            st.session_state.pop("data_insight_last_processed_action", None)
            st.session_state.pop("data_insight_pending_action", None)
            st.session_state.pop("data_insight_pending_action_label", None)
            st.session_state.pop("data_insight_pending_chart_metrics", None)
            st.session_state.pop("data_insight_map_context", None)
            restore_chat_session(upload_key)
            clear_folium_widget_state()
            for key in list(st.session_state.keys()):
                if key.startswith("label_lat_") or key.startswith("label_lon_"):
                    del st.session_state[key]
            if selected_world_index_metric is not None:
                st.session_state["show_lbl_name"] = True
                st.session_state["show_lbl_values"] = True
                st.session_state["show_lbl_total"] = True
                st.session_state["scale_by_total"] = False
                st.session_state["marker_type"] = "column"
            elif using_world_bank_baseline:
                st.session_state["show_lbl_name"] = False
                st.session_state["show_lbl_values"] = False
                st.session_state["show_lbl_total"] = False
                st.session_state["scale_by_total"] = True
                st.session_state["marker_type"] = "pie"
        all_cols = df.columns.tolist()
        numeric_cols = df.select_dtypes(include="number").columns.tolist()

        if custom_mode:
            with col_left:
                st.markdown(
                    f'<p class="labelmap-title" style="margin:0;">{UI_COPY.match_your_columns}</p>',
                    unsafe_allow_html=True,
                )
                name_col = st.selectbox(
                    UI_COPY.location_column,
                    all_cols,
                    index=all_cols.index(
                        column_default(all_cols, 0, ["location", "location_name", "name", "village"])
                    ),
                )
                lat_col = st.selectbox(
                    UI_COPY.latitude_column,
                    all_cols,
                    index=all_cols.index(column_default(all_cols, 1, ["latitude", "lat"])),
                )
                lon_col = st.selectbox(
                    UI_COPY.longitude_column,
                    all_cols,
                    index=all_cols.index(
                        column_default(all_cols, 2, ["longitude", "long", "lng", "lon"])
                    ),
                )

                available_value_cols = [
                    col for col in numeric_cols if col not in {name_col, lat_col, lon_col}
                ]
                default_value_cols = _default_value_cols(
                    available_value_cols,
                    all_cols,
                    using_world_bank_baseline=using_world_bank_baseline,
                    source_mode=source_mode,
                    using_sample=False,
                    selected_world_index_metric=None,
                )
                with st.container(key="value_cols_picker"):
                    value_cols = st.pills(
                        UI_COPY.numbers_to_show,
                        available_value_cols,
                        default=default_value_cols,
                        selection_mode="multi",
                        format_func=_value_dropdown_label,
                        key="value_cols_picker_widget",
                    ) or []
        else:
            name_col = column_default(all_cols, 0, ["location", "location_name", "name", "village"])
            lat_col = column_default(all_cols, 1, ["latitude", "lat"])
            lon_col = column_default(all_cols, 2, ["longitude", "long", "lng", "lon"])
            available_value_cols = [
                col for col in numeric_cols if col not in {name_col, lat_col, lon_col}
            ]
            value_cols = _default_value_cols(
                available_value_cols,
                all_cols,
                using_world_bank_baseline=using_world_bank_baseline,
                source_mode=source_mode,
                using_sample=using_sample,
                selected_world_index_metric=selected_world_index_metric,
                df=df,
            )
        mapping_errors = []
        if lat_col not in numeric_cols:
            mapping_errors.append(UI_COPY.mapping_error_latitude.format(col=lat_col))
        else:
            mapping_errors.extend(coordinate_column_errors(df, lat_col, "latitude"))
        if lon_col not in numeric_cols:
            mapping_errors.append(UI_COPY.mapping_error_longitude.format(col=lon_col))
        else:
            mapping_errors.extend(coordinate_column_errors(df, lon_col, "longitude"))
        if not value_cols:
            mapping_errors.append(UI_COPY.mapping_error_no_values)

        if mapping_errors:
            with col_center:
                for error in mapping_errors:
                    st.error(error)
        else:
            for key, default in (
                ("show_lbl_name", True),
                ("show_lbl_values", True),
                ("show_lbl_total", True),
                ("scale_by_total", True),
                ("show_legend", True),
            ):
                if key not in st.session_state:
                    st.session_state[key] = default
            if "map_style" not in st.session_state:
                st.session_state["map_style"] = DEFAULT_MAP_STYLE

            with col_right:
                value_col_count = len(value_cols)
                previous_value_col_count = st.session_state.get("_last_value_col_count")
                single_value_mode = value_col_count == 1
                if single_value_mode:
                    st.session_state["marker_type"] = "pie"
                    st.session_state["show_lbl_total"] = False
                else:
                    if previous_value_col_count in {None, 1}:
                        st.session_state["marker_type"] = "column"
                    if previous_value_col_count == 1 and value_col_count >= 2:
                        st.session_state["show_lbl_total"] = True
                    if st.session_state.get("marker_type") == "bar":
                        st.session_state["marker_type"] = "column"

                st.markdown(
                    f'<p class="labelmap-title" style="margin:0;">{UI_COPY.map_style_section}</p>',
                    unsafe_allow_html=True,
                )
                map_style = st.selectbox(
                    UI_COPY.map_style_section,
                    list(MAP_STYLE_OPTIONS.keys()),
                    key="map_style",
                    label_visibility="collapsed",
                )
                _panel_divider()

                st.markdown(
                    f'<p class="labelmap-title" style="margin:0;">{UI_COPY.color_key_section}</p>',
                    unsafe_allow_html=True,
                )
                show_legend = st.checkbox(UI_COPY.show_color_key, key="show_legend")
                _panel_divider()

                st.markdown(
                    f'<p class="labelmap-title" style="margin:0;">{UI_COPY.text_on_map_section}</p>',
                    unsafe_allow_html=True,
                )
                show_name = st.checkbox(UI_COPY.show_location_label, key="show_lbl_name")
                show_values = st.checkbox(UI_COPY.numbers_checkbox, key="show_lbl_values")
                if single_value_mode:
                    show_total = False
                else:
                    total_toggle_label = (
                        UI_COPY.change_percent
                        if st.session_state.get("marker_type") == "column"
                        else UI_COPY.total_checkbox
                    )
                    show_total = st.checkbox(total_toggle_label, key="show_lbl_total")
                scale_by_total = st.checkbox(UI_COPY.size_by_value, key="scale_by_total")
                _panel_divider()

                if single_value_mode:
                    marker_type = "pie"
                else:
                    st.markdown(
                        f'<p class="labelmap-title" style="margin:0;">{UI_COPY.chart_style_section}</p>',
                        unsafe_allow_html=True,
                    )
                    marker_type = st.radio(
                        UI_COPY.chart_style_section,
                        ["column", "pie"],
                        format_func=chart_type_label,
                        horizontal=True,
                        key="marker_type",
                        label_visibility="collapsed",
                    )
                    _panel_divider()

                st.session_state["_last_value_col_count"] = value_col_count

                st.markdown(
                    f'<p class="labelmap-title" style="margin:0;">{UI_COPY.colors_section}</p>',
                    unsafe_allow_html=True,
                )

                chart_colors = []
                for color_idx, value_col in enumerate(value_cols):
                    default = _default_color_for_value_col(value_col, color_idx)
                    color_key = f"chart_color_{value_col}"
                    if color_key not in st.session_state:
                        st.session_state[color_key] = default
                    label_text, label_title = _value_label_text(value_col)
                    st.markdown(
                        (
                            f"<p title='{escape(label_title)}' "
                            "class='labelmap-control-text' "
                            "style='margin:0;white-space:nowrap;overflow:hidden;"
                            f"text-overflow:ellipsis;'>{escape(label_text)}</p>"
                        ),
                        unsafe_allow_html=True,
                    )
                    st.color_picker(UI_COPY.color_picker_label, key=color_key, label_visibility="collapsed")
                    chart_colors.append(st.session_state[color_key])

                legend_items = []
                if show_legend:
                    for value_col, color in zip(value_cols, chart_colors):
                        label_text, _ = _value_label_text(value_col)
                        legend_items.append({"label": label_text, "color": color})
                    if selected_world_index_metric is not None:
                        legend_items.extend(_world_index_legend_items())
                    elif using_world_bank_baseline:
                        legend_items.extend(_world_bank_legend_items(source_mode))

            filter_state = get_filter_state(st.session_state)
            filtered_df = apply_data_filters(
                df,
                name_col=name_col,
                **filter_state,
            )

            marker_rows = []
            totals = []
            comparison_cols = (
                WORLD_INDEX_COMPARISON_COLUMNS.get(selected_world_index_metric, [])
                if selected_world_index_metric is not None
                else []
            )
            using_comparison_mode = (
                selected_world_index_metric is not None
                and comparison_cols
                and list(value_cols) == comparison_cols
            )
            for idx, row in filtered_df.iterrows():
                values, labels, colors = get_nonzero_values(
                    row, value_cols, value_colors=chart_colors
                )
                if using_comparison_mode and len(values) < len(comparison_cols):
                    percent_col = WORLD_INDEX_PERCENT_COLUMNS.get(selected_world_index_metric)
                    if percent_col in row.index:
                        percent_color_idx = value_cols.index(percent_col) if percent_col in value_cols else 0
                        percent_colors = (
                            [chart_colors[percent_color_idx]]
                            if percent_color_idx < len(chart_colors)
                            else chart_colors[:1]
                        )
                        values, labels, colors = get_nonzero_values(
                            row, [percent_col], value_colors=percent_colors
                        )
                    else:
                        values, labels, colors = [], [], []
                total = sum(values)
                totals.append(total)
                marker_rows.append(
                    {
                        "idx": idx,
                        "lat": row[lat_col],
                        "lon": row[lon_col],
                        "values": values,
                        "labels": labels,
                        "colors": colors,
                        "total": total,
                        "name": row[name_col],
                    }
                )

            positive_totals = [total for total in totals if total > 0]
            min_total = min(positive_totals) if positive_totals else 0
            max_total = max(totals) if totals else 1
            if filtered_df.empty:
                lat_span = 1
                lon_span = 1
            else:
                lat_span = filtered_df[lat_col].max() - filtered_df[lat_col].min() or 1
                lon_span = filtered_df[lon_col].max() - filtered_df[lon_col].min() or 1
            with col_center:
                render_label_map_fragment(
                    filtered_df,
                    lat_col,
                    lon_col,
                    upload_key,
                    marker_rows,
                    lat_span,
                    lon_span,
                    min_total,
                    max_total,
                    marker_type,
                    chart_colors,
                    scale_by_total,
                    show_name,
                    show_values,
                    show_total,
                    force_compare_total_tooltip=selected_world_index_metric is not None,
                    map_style=map_style,
                    show_legend=show_legend,
                    legend_items=legend_items,
                )
                set_insight_map_context(
                    filtered_df=filtered_df,
                    lat_col=lat_col,
                    lon_col=lon_col,
                    upload_key=upload_key,
                    marker_rows=marker_rows,
                    label_positions=label_positions_from_session(
                        marker_rows,
                        lat_span,
                        lon_span,
                        marker_type,
                        show_name,
                        show_values,
                        show_total,
                    ),
                    min_total=min_total,
                    max_total=max_total,
                    marker_type=marker_type,
                    chart_colors=chart_colors,
                    scale_by_total=scale_by_total,
                    show_name=show_name,
                    show_values=show_values,
                    show_total=show_total,
                    map_style=map_style,
                    show_legend=show_legend,
                    legend_items=legend_items,
                )
                if using_sample:
                    dataset_label = display_dataset(source_mode)
                elif hasattr(data_source, "name"):
                    dataset_label = data_source.name
                else:
                    dataset_label = "Your data"
                insight_panel_args = (filtered_df, df, name_col, value_cols, dataset_label)
    except Exception as e:
        with col_center:
            st.error(f"Could not process file: {str(e)}")
else:
    with col_center:
        if source_mode == "Upload CSV":
            st.info(UI_COPY.upload_empty_state)
        else:
            st.info(UI_COPY.upload_prompt)
    insight_panel_args = None

if insight_panel_args:
    _, insight_col, _ = st.columns([1, 8, 1], gap=None)
    with insight_col:
        with st.container(key="labelmap_data_insight"):
            render_data_insight_panel(*insight_panel_args)

with col_left:
    _panel_divider()
    render_contact_with_docs()
