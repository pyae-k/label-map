"""User-facing UI copy and display-only label mapping."""

from __future__ import annotations

from dataclasses import dataclass

from labelmap.world_bank_baselines import WORLD_BANK_BASELINE_BY_LABEL

DATASET_DISPLAY: dict[str, str] = {
    "Index ETF 1d%": "Stock indexes · 1 day",
    "Index ETF 7d%": "Stock indexes · 7 days",
    "Index ETF 30d%": "Stock indexes · 30 days",
    "GDP per capita": "GDP per person",
}

VALUE_COLUMN_DISPLAY: dict[str, str] = {
    "1d Ago": "Yesterday",
    "7d Ago": "7 days ago",
    "30d Ago": "30 days ago",
    "Last value": "Today",
}


@dataclass(frozen=True)
class UI:
    """Static panel strings."""

    data_source_section: str = "Choose your data"
    use_your_own_file: str = "Upload my csv"
    dataset_label: str = "Built-in data"
    download_sample_file: str = "Download a sample"
    match_your_columns: str = "Match your CSV columns"
    numbers_to_show: str = "Values on the chart"
    upload_file: str = "Upload CSV"
    upload_prompt: str = 'Turn on "Upload my csv" to add your own file'

    choose_dataset: str = "Choose built-in data"
    choose_dataset_chevron: str = "▾"
    picker_search_placeholder: str = "Search"
    picker_empty_state: str = "No results found."
    picker_section_markets: str = "Markets"
    picker_section_countries: str = "Countries"
    picker_upload_file: str = "Upload your own CSV file to build your map"

    map_style_section: str = "Map look"
    color_key_section: str = "Legend"
    show_color_key: str = "Show legend"
    text_on_map_section: str = "Labels on map"
    numbers_checkbox: str = "Values"
    change_percent: str = "Percent change"
    total_checkbox: str = "Combined total"
    size_by_value: str = "Bigger markers for higher values"
    chart_style_section: str = "Chart type"
    colors_section: str = "Chart colors"
    chart_type_pie: str = "Pie chart"
    chart_type_bar: str = "Bar chart"

    location_column: str = "Place name"
    latitude_column: str = "Latitude"
    longitude_column: str = "Longitude"
    show_location_label: str = "Place name"
    color_picker_label: str = "Color"

    upload_empty_state: str = "Upload your own CSV file to build your map"
    baseline_missing_warning: str = (
        "Built-in data is unavailable. Upload a CSV file to build your map."
    )
    mapping_error_latitude: str = '"{col}" must be a number (latitude)'
    mapping_error_longitude: str = '"{col}" must be a number (longitude)'
    mapping_error_no_values: str = "Choose at least one value column for the chart"

    insight_summary: str = "Summary"
    insight_top10: str = "Top 10"
    insight_bottom10: str = "Bottom 10"
    insight_chart: str = "Bar chart"
    insight_column_chart: str = "Column chart"
    insight_missing: str = "Missing data"
    insight_full_table: str = "Full table"
    insight_map: str = "Map image"
    insight_download_label: str = "Download CSV"
    insight_clear_filters: str = "Clear filters"
    insight_reset_chat: str = "Reset chat"
    insight_metric_label: str = "Metric"

    insight_greeting: str = "Hi, What would you like to know?"
    insight_filter: str = "Filter"
    insight_filter_prompt: str = "Pick one or more locations, then Apply."
    insight_filter_apply: str = "Apply"
    insight_filter_unavailable: str = "No locations available for this dataset."
    insight_metric_prompt: str = "Which metric would you like to use?"
    insight_chart_mode_prompt: str = "Pick a single metric or compare multiple:"
    insight_chart_compare_prompt: str = "Pick two metrics to compare, then Apply."
    insight_chart_compare_min: str = "Pick exactly two metrics to compare."
    insight_chart_compare: str = "Compare metrics"
    insight_followup: str = "Anything else you'd like to explore?"
    insight_filter_applied: str = "Filter applied. {status}"
    insight_filter_cleared: str = "Filters cleared. Showing all {count:,} locations."
    insight_chat_reset: str = "Chat reset. Ask me anything about this dataset."
    insight_no_results: str = "No locations match the current filters."
    insight_chat_input_placeholder: str = "Search by country or location, or type a command…"
    insight_download_ready: str = "[Download filtered data]({href})"
    insight_region_label: str = "Filter by region"
    insight_action_pills_label: str = "Choose an insight"


UI_COPY = UI()


def display_dataset(key: str) -> str:
    """Return friendly dataset name for picker and triggers."""
    return DATASET_DISPLAY.get(str(key), str(key).replace("_", " "))


def display_value_column(key: str) -> str:
    """Return friendly value-column name for controls, legend, and map labels."""
    normalized = str(key).replace("_", " ").strip()
    return VALUE_COLUMN_DISPLAY.get(normalized, normalized)


def display_source_attribution(text: str) -> str:
    """Rewrite source attribution for non-technical readers."""
    if text.startswith("Source: "):
        return f"Data from {text[len('Source: '):]}"
    return text


def display_picker_source(option: str) -> str:
    """Short source label for the dataset picker."""
    baseline = WORLD_BANK_BASELINE_BY_LABEL.get(option)
    if baseline is not None:
        return f"World Bank · {baseline.year}"
    return "Yahoo Finance"
