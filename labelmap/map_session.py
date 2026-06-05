"""Streamlit session state for map view and label drag persistence."""

import math

import streamlit as st

from labelmap.config import EXPORT_CAPTURE_HEIGHT, EXPORT_CAPTURE_WIDTH
from labelmap.geo import best_zoom, fit_bounds_for_points, normalize_bounds, normalize_zoom
from labelmap.labels import scaled_label_latlon


def _coords_unchanged(old_lat, old_lon, new_lat, new_lon, eps=1e-7):
    if old_lat is None or old_lon is None:
        return False
    return math.isclose(old_lat, new_lat, abs_tol=eps) and math.isclose(
        old_lon, new_lon, abs_tol=eps
    )


def persist_map_view(center_lat, center_lon, zoom, upload_key):
    zoom_val = normalize_zoom(zoom)
    if zoom_val is None:
        zoom_val = st.session_state.get("map_view", {}).get("zoom", 10)
    st.session_state["map_view"] = {
        "center_lat": float(center_lat),
        "center_lon": float(center_lon),
        "zoom": zoom_val,
    }
    st.session_state["map_view_upload_key"] = upload_key


def parse_label_drag_tooltip(tooltip):
    """Parse label drag payload: label:{idx}:{lat}:{lon}|{center_lat},{center_lon},{zoom}."""
    text = str(tooltip)
    if not text.startswith("label:"):
        return None
    payload, _, view_part = text.partition("|")
    try:
        _, idx, lat, lon = payload.split(":", 3)
        result = {
            "idx": idx,
            "lat": float(lat),
            "lon": float(lon),
            "center_lat": None,
            "center_lon": None,
            "zoom": None,
        }
    except (ValueError, IndexError):
        return None
    if view_part:
        try:
            center_lat, center_lon, zoom = view_part.split(",", 2)
            result["center_lat"] = float(center_lat)
            result["center_lon"] = float(center_lon)
            result["zoom"] = float(zoom)
        except (ValueError, IndexError):
            pass
    return result


def sync_dragged_labels(map_state, upload_key):
    if not map_state:
        return False
    tooltip = map_state.get("last_object_clicked_tooltip")
    drag = parse_label_drag_tooltip(tooltip)
    if not drag:
        return False

    lat_key = f"label_lat_{drag['idx']}"
    lon_key = f"label_lon_{drag['idx']}"
    label_moved = not _coords_unchanged(
        st.session_state.get(lat_key),
        st.session_state.get(lon_key),
        drag["lat"],
        drag["lon"],
    )
    if label_moved:
        st.session_state[lat_key] = drag["lat"]
        st.session_state[lon_key] = drag["lon"]

    if drag["center_lat"] is not None and drag["center_lon"] is not None:
        persist_map_view(
            drag["center_lat"],
            drag["center_lon"],
            drag["zoom"],
            upload_key,
        )

    return label_moved


def default_map_view_from_df(df, lat_col, lon_col):
    fit = fit_bounds_for_points(df, lat_col, lon_col)
    min_lat, min_lon = fit[0]
    max_lat, max_lon = fit[1]
    zoom = best_zoom(
        min_lon, max_lon, min_lat, max_lat, EXPORT_CAPTURE_WIDTH, EXPORT_CAPTURE_HEIGHT
    )
    return {
        "center_lat": (min_lat + max_lat) / 2,
        "center_lon": (min_lon + max_lon) / 2,
        "zoom": max(2, min(16, int(zoom))),
    }


def get_map_view(df, lat_col, lon_col, upload_key):
    view = st.session_state.get("map_view")
    if view and st.session_state.get("map_view_upload_key") == upload_key:
        return view
    view = default_map_view_from_df(df, lat_col, lon_col)
    st.session_state["map_view"] = view
    st.session_state["map_view_upload_key"] = upload_key
    return view


def label_positions_from_session(marker_rows, lat_span, lon_span):
    positions = {}
    for marker in marker_rows:
        idx = marker["idx"]
        positions[idx] = (
            st.session_state.get(
                f"label_lat_{idx}",
                scaled_label_latlon(marker, "right", lat_span, lon_span),
            ),
            st.session_state.get(f"label_lon_{idx}", marker["lon"]),
        )
    return positions


def map_export_ready(map_state):
    if not isinstance(map_state, dict):
        return False
    raw_bounds = map_state.get("bounds")
    if not isinstance(raw_bounds, dict):
        return False
    south_west = raw_bounds.get("_southWest", {})
    north_east = raw_bounds.get("_northEast", {})
    try:
        south = float(south_west.get("lat"))
        west = float(south_west.get("lng"))
        north = float(north_east.get("lat"))
        east = float(north_east.get("lng"))
    except (TypeError, ValueError):
        return False
    if None in (south, west, north, east):
        return False
    return abs(north - south) > 1e-9 or abs(east - west) > 1e-9


def parse_map_view(map_state, df, lat_col, lon_col):
    bounds = None
    zoom = None
    if isinstance(map_state, dict):
        zoom = normalize_zoom(map_state.get("zoom"))
        raw_bounds = map_state.get("bounds")
        if isinstance(raw_bounds, dict):
            south_west = raw_bounds.get("_southWest", {})
            north_east = raw_bounds.get("_northEast", {})
            south = south_west.get("lat")
            west = south_west.get("lng")
            north = north_east.get("lat")
            east = north_east.get("lng")
            if None not in (south, west, north, east):
                bounds = normalize_bounds(
                    {"south": south, "west": west, "north": north, "east": east}
                )
    if bounds is None and df is not None and lat_col is not None and lon_col is not None:
        fit = fit_bounds_for_points(df, lat_col, lon_col)
        bounds = normalize_bounds(
            {
                "south": fit[0][0],
                "west": fit[0][1],
                "north": fit[1][0],
                "east": fit[1][1],
            }
        )
    return bounds, zoom


def apply_map_view(m, map_state, df, lat_col, lon_col):
    bounds, zoom = parse_map_view(map_state, df, lat_col, lon_col)
    fit_bounds = [[bounds["south"], bounds["west"]], [bounds["north"], bounds["east"]]]
    if zoom is not None:
        m.fit_bounds(fit_bounds, max_zoom=zoom)
    else:
        m.fit_bounds(fit_bounds)
