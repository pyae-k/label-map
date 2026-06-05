"""Folium map construction and marker/label layer population."""

import folium

from labelmap.charts import make_chart_icon_html, marker_radius
from labelmap.config import CHART_ICON_SIZE
from labelmap.folium_elements import (
    DynamicConnectors,
    LabelDragSync,
    MapDragGuard,
    MapSaveComplete,
    MapViewRestore,
)
from labelmap.labels import make_label_icon_html
from labelmap.map_session import get_map_view


def build_interactive_map(df, lat_col, lon_col, upload_key):
    view = get_map_view(df, lat_col, lon_col, upload_key)
    m = folium.Map(
        location=[view["center_lat"], view["center_lon"]],
        zoom_start=view["zoom"],
        tiles="OpenStreetMap",
    )
    MapViewRestore(m.get_name(), view["center_lat"], view["center_lon"], view["zoom"]).add_to(
        m
    )
    return m, view


def populate_map_layers(
    m,
    marker_rows,
    label_positions,
    min_total,
    max_total,
    marker_type,
    chart_colors,
    scale_by_total,
    show_name,
    show_values,
    show_total,
    draggable_labels=True,
    drag_locked=False,
    unlock_after_save=False,
):
    drag_sync_items = []
    connector_items = []

    for marker in marker_rows:
        idx = marker["idx"]
        radius = marker_radius(marker["total"], min_total, max_total, scale_by_total)
        chart_html = make_chart_icon_html(
            marker["values"], radius, marker_type, chart_colors
        )
        folium.Marker(
            location=[marker["lat"], marker["lon"]],
            icon=folium.DivIcon(
                html=chart_html,
                icon_size=(CHART_ICON_SIZE, CHART_ICON_SIZE),
                icon_anchor=(CHART_ICON_SIZE // 2, CHART_ICON_SIZE // 2),
            ),
            tooltip=str(marker["name"]),
        ).add_to(m)

        label_lat, label_lon = label_positions[idx]
        label_html, icon_w, icon_h = make_label_icon_html(
            str(marker["name"]),
            marker["labels"],
            marker["values"],
            marker["total"],
            show_name,
            show_values,
            show_total,
        )
        if label_html:
            label_marker = folium.Marker(
                location=[label_lat, label_lon],
                icon=folium.DivIcon(
                    html=label_html,
                    icon_size=(icon_w, icon_h),
                    icon_anchor=(0, 0),
                ),
                draggable=draggable_labels,
                tooltip=f"label:{idx}",
            )
            label_marker.add_to(m)
            if draggable_labels:
                drag_sync_items.append(
                    {"idx": idx, "marker_name": label_marker.get_name()}
                )
            connector_items.append(
                {
                    "idx": idx,
                    "chart_lat": marker["lat"],
                    "chart_lon": marker["lon"],
                    "label_marker_name": label_marker.get_name(),
                    "icon_w": icon_w,
                    "icon_h": icon_h,
                }
            )

    if connector_items:
        DynamicConnectors(m.get_name(), connector_items, CHART_ICON_SIZE // 2).add_to(m)
    if draggable_labels and drag_sync_items:
        label_marker_names = [item["marker_name"] for item in drag_sync_items]
        MapDragGuard(m.get_name(), label_marker_names, drag_locked).add_to(m)
        LabelDragSync(drag_sync_items).add_to(m)
        if unlock_after_save:
            MapSaveComplete(m.get_name()).add_to(m)
    return connector_items
