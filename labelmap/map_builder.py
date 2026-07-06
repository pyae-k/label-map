"""Folium map construction and marker/label layer population."""

import folium
import streamlit as st
from labelmap.charts import make_chart_icon_html, marker_radius
from labelmap.config import (
    APP_FONT_STACK,
    APP_TEXT_COLOR,
    CHART_ICON_SIZE,
    DEFAULT_MAP_STYLE,
    FULLSCREEN_ZOOM_IN_CLICKS,
    INTERACTIVE_DEFAULT_ZOOM_OFFSET,
    INTERACTIVE_MIN_ZOOM,
    INTERACTIVE_ZOOM_HOLD_DELAY_MS,
    INTERACTIVE_ZOOM_MAX_STEP,
    INTERACTIVE_ZOOM_REPEAT_MS,
    INTERACTIVE_ZOOM_STEP,
    MAP_STYLE_OPTIONS,
    default_interactive_zoom,
)
from labelmap.folium_elements import (
    DynamicConnectors,
    FullscreenStateSync,
    LabelDragSync,
    MapDragGuard,
    MapFrameFill,
    MapFullscreenControl,
    MapLegend,
    MapSaveComplete,
    MapViewRestore,
    SingleWorldMap,
    SmoothZoomControl,
)
from labelmap.labels import build_marker_tooltip_html, make_label_icon_html
from labelmap.map_session import get_map_view, _saved_map_zoom_start

MAP_CONTROL_STYLES = (
"""
<style>
html, body {
    width: 100% !important;
    height: 100% !important;
    margin: 0 !important;
    overflow: hidden !important;
}
#root,
#parent,
.float-container,
.float-child {
    width: 100% !important;
    height: 100% !important;
}
#map_div,
.folium-map,
.leaflet-container {
    width: 100% !important;
    height: 100% !important;
}
.leaflet-control-zoom {
    border: 0 !important;
    border-radius: 14px !important;
    overflow: hidden;
    box-shadow: 0 10px 26px rgba(0, 0, 0, 0.35) !important;
}
.leaflet-control-zoom a,
.leaflet-control-zoom-fullscreen {
    background: rgba(28, 28, 30, 0.96) !important;
    color: __TEXT_COLOR__ !important;
    border: 0 !important;
    text-decoration: none !important;
    display: flex !important;
    align-items: center;
    justify-content: center;
    transition: background-color 0.15s ease, transform 0.08s ease;
}
.leaflet-control-zoom a {
    width: 40px !important;
    height: 40px !important;
    padding: 0 !important;
    font-family: __FONT_STACK__ !important;
    font-size: 22px !important;
    font-weight: 700 !important;
    line-height: 40px !important;
}
.leaflet-control-zoom-in {
    font-size: 24px !important;
}
.leaflet-control-zoom-out {
    font-size: 0 !important;
    position: relative;
}
.leaflet-control-zoom-out::before {
    content: "−";
    font-family: __FONT_STACK__;
    font-size: 24px;
    font-weight: 700;
    line-height: 1;
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
}
.leaflet-control-zoom-in {
    border-bottom: 1px solid rgba(255, 255, 255, 0.12) !important;
}
.leaflet-control-zoom-fullscreen {
    width: 40px !important;
    height: 40px !important;
    border-radius: 0 !important;
    padding: 0 !important;
    font-family: __FONT_STACK__ !important;
    font-size: 0 !important;
    font-weight: 700 !important;
    line-height: 40px !important;
    position: relative;
    border-top: 1px solid rgba(255, 255, 255, 0.12) !important;
}
.leaflet-control-zoom-fullscreen.fullscreen-icon {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='__TEXT_COLOR_URI__' stroke-width='2.2' stroke-linecap='square'%3E%3Cpolyline points='9 3 3 3 3 9'/%3E%3Cpolyline points='15 3 21 3 21 9'/%3E%3Cpolyline points='9 21 3 21 3 15'/%3E%3Cpolyline points='15 21 21 21 21 15'/%3E%3C/svg%3E") !important;
    background-repeat: no-repeat !important;
    background-position: center !important;
    background-size: 18px 18px !important;
}
.leaflet-touch .leaflet-control-zoom-fullscreen.fullscreen-icon {
    background-position: center !important;
}
.leaflet-touch .leaflet-control-zoom a,
.leaflet-touch .leaflet-control-zoom-fullscreen {
    width: 44px !important;
    height: 44px !important;
    line-height: 44px !important;
}
.leaflet-control-zoom-fullscreen.fullscreen-icon.leaflet-fullscreen-on {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='__TEXT_COLOR_URI__' stroke-width='2.2' stroke-linecap='square'%3E%3Cpolyline points='9 9 3 9 3 3'/%3E%3Cpolyline points='15 9 21 9 21 3'/%3E%3Cpolyline points='9 15 3 15 3 21'/%3E%3Cpolyline points='15 15 21 15 21 21'/%3E%3C/svg%3E") !important;
}
html.labelmap-fs-active,
body.labelmap-fs-active,
html.labelmap-fs-active #map_div,
html.labelmap-fs-active .folium-map,
html.labelmap-fs-active .leaflet-container {
    width: 100% !important;
    height: 100% !important;
    min-height: 100% !important;
}
html.labelmap-fs-active,
body.labelmap-fs-active {
    overflow: hidden !important;
}
.leaflet-control-zoom a:hover,
.leaflet-control-zoom-fullscreen:hover {
    background: rgba(44, 44, 46, 0.96) !important;
}
.leaflet-control-zoom a:active,
.leaflet-control-zoom-fullscreen:active {
    transform: scale(0.97);
}
.leaflet-pseudo-fullscreen {
    position: fixed !important;
    width: 100vw !important;
    height: 100vh !important;
    top: 0 !important;
    left: 0 !important;
    right: 0 !important;
    bottom: 0 !important;
    z-index: 99999 !important;
}
</style>
"""
    .replace("__FONT_STACK__", APP_FONT_STACK)
    .replace("__TEXT_COLOR__", APP_TEXT_COLOR)
    .replace("__TEXT_COLOR_URI__", APP_TEXT_COLOR.replace("#", "%23"))
)


def build_base_map(location, zoom, map_style=DEFAULT_MAP_STYLE, zoom_control="topright"):
    """Single-world Leaflet map: no horizontal tile repeat, bounded panning."""
    tiles = MAP_STYLE_OPTIONS.get(map_style, MAP_STYLE_OPTIONS[DEFAULT_MAP_STYLE])
    tile_layer = folium.TileLayer(
        tiles=tiles,
        no_wrap=True,
    )
    return folium.Map(
        location=location,
        zoom_start=zoom,
        tiles=tile_layer,
        min_zoom=INTERACTIVE_MIN_ZOOM,
        max_bounds=True,
        zoom_control=zoom_control,
        zoom_snap=0.01,
    )


def build_interactive_map(
    df,
    lat_col,
    lon_col,
    upload_key,
    map_style=DEFAULT_MAP_STYLE,
    show_legend=True,
    legend_items=None,
):
    view = get_map_view(df, lat_col, lon_col, upload_key)
    world_fit = st.session_state.pop("map_world_fit_pending", False)
    m = build_base_map(
        [view["center_lat"], view["center_lon"]],
        _saved_map_zoom_start(view, world_fit),
        map_style=map_style,
        zoom_control="topright",
    )
    MapFullscreenControl(
        m.get_name(),
        title="Full screen",
        title_cancel="Exit full screen",
        zoom_step=INTERACTIVE_ZOOM_STEP,
        zoom_clicks=FULLSCREEN_ZOOM_IN_CLICKS,
    ).add_to(m)
    SmoothZoomControl(
        m.get_name(),
        INTERACTIVE_ZOOM_STEP,
        INTERACTIVE_ZOOM_MAX_STEP,
        INTERACTIVE_ZOOM_HOLD_DELAY_MS,
        INTERACTIVE_ZOOM_REPEAT_MS,
    ).add_to(m)
    m.get_root().header.add_child(folium.Element(MAP_CONTROL_STYLES))
    MapFrameFill(m.get_name(), 0).add_to(m)
    SingleWorldMap(
        m.get_name(),
        INTERACTIVE_MIN_ZOOM,
        0,
    ).add_to(m)
    MapViewRestore(
        m.get_name(),
        view["center_lat"],
        view["center_lon"],
        view["zoom"],
        view.get("fullscreen", False),
        world_fit=world_fit,
        default_zoom_offset=INTERACTIVE_DEFAULT_ZOOM_OFFSET,
        reference_default_zoom=INTERACTIVE_MIN_ZOOM,
    ).add_to(
        m
    )
    fs_flag = "1" if view.get("fullscreen", False) else "0"
    sync_marker = folium.Marker(
        location=[-89.9, 0],
        opacity=0,
        interactive=True,
        tooltip=(
            f"view:fs:{fs_flag}|"
            f"{view['center_lat']},{view['center_lon']},{view['zoom']}"
        ),
    )
    sync_marker.add_to(m)
    FullscreenStateSync(m.get_name(), sync_marker.get_name()).add_to(m)
    if show_legend and legend_items:
        MapLegend(m.get_name(), legend_items, map_style=map_style).add_to(m)
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
    force_compare_total_tooltip=False,
    map_style=DEFAULT_MAP_STYLE,
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
            tooltip=folium.Tooltip(
                build_marker_tooltip_html(
                    marker["name"],
                    marker["labels"],
                    marker["values"],
                    marker["total"],
                    show_name=True,
                    show_values=True,
                    show_total=show_total,
                    marker_type=marker_type,
                    force_compare_total=force_compare_total_tooltip,
                )
            ),
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
            value_colors=marker.get("colors"),
            marker_type=marker_type,
            map_style=map_style,
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
        DynamicConnectors(
            m.get_name(), connector_items, CHART_ICON_SIZE // 2, map_style=map_style
        ).add_to(m)
    if draggable_labels and drag_sync_items:
        label_marker_names = [item["marker_name"] for item in drag_sync_items]
        MapDragGuard(m.get_name(), label_marker_names, drag_locked).add_to(m)
        LabelDragSync(drag_sync_items).add_to(m)
        if unlock_after_save:
            MapSaveComplete(m.get_name()).add_to(m)
    return connector_items
