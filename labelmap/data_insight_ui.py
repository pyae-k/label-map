"""Streamlit chatbox UI for dataset insights below the map."""

from __future__ import annotations

from typing import Any

import streamlit as st
from pandas import DataFrame

from labelmap.data_insight_chat import render_data_insight_chat


def set_insight_map_context(
    *,
    filtered_df: DataFrame,
    lat_col: str,
    lon_col: str,
    upload_key: str,
    marker_rows: list[dict[str, Any]],
    label_positions: dict[Any, tuple[float, float]],
    min_total: float,
    max_total: float,
    marker_type: str,
    chart_colors: list[str],
    scale_by_total: bool,
    show_name: bool,
    show_values: bool,
    show_total: bool,
    map_style: str,
    show_legend: bool = True,
    legend_items: list[dict[str, Any]] | None = None,
) -> None:
    """Store the active map state so the chatbox can render map screenshots."""
    st.session_state["data_insight_map_context"] = {
        "df": filtered_df,
        "lat_col": lat_col,
        "lon_col": lon_col,
        "upload_key": upload_key,
        "marker_rows": marker_rows,
        "label_positions": label_positions,
        "map_state": st.session_state.get("map_view"),
        "min_total": min_total,
        "max_total": max_total,
        "marker_type": marker_type,
        "chart_colors": list(chart_colors),
        "scale_by_total": scale_by_total,
        "show_name": show_name,
        "show_values": show_values,
        "show_total": show_total,
        "map_style": map_style,
        "show_legend": show_legend,
        "legend_items": list(legend_items or []),
    }


def render_data_insight_panel(
    filtered_df: DataFrame,
    full_df: DataFrame,
    name_col: str,
    value_cols: list[str],
    dataset_label: str,
) -> None:
    """Render the map-bottom conversational insight chat."""
    render_data_insight_chat(
        filtered_df,
        full_df,
        name_col,
        value_cols,
        dataset_label,
    )
