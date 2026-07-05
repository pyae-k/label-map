"""Streamlit session state for map view and label drag persistence."""

import hashlib
import math

import streamlit as st

from labelmap.config import default_interactive_zoom
from labelmap.geo import fit_bounds_for_points, normalize_bounds, normalize_zoom
from labelmap.labels import build_label_content, place_labels_near_markers, scaled_label_latlon

# Default label layout for Index ETF sample (matches reference screenshot).
DEFAULT_MARKET_LABEL_POSITIONS = {
    "Canada60": {"lat": 55.0, "lon": -100.0},
    "SPX500": {"lat": 41.0, "lon": -62.0},
    "UK100": {"lat": 58.0, "lon": 5.0},
    "GRA40": {"lat": 53.0, "lon": 10.0},
    "JPN225": {"lat": 36.0, "lon": 162.0},
    "HKG50": {"lat": 28.0, "lon": 120.0},
    "AUS200": {"lat": -36.0, "lon": 168.0},
}


def _saved_map_zoom_start(view, world_fit=False):
    """Use persisted absolute zoom on map boot when available."""
    if world_fit:
        return default_interactive_zoom()
    saved = normalize_zoom(view.get("zoom"))
    if saved is None or saved <= 0:
        return default_interactive_zoom()
    return saved


def folium_widget_key(upload_key: str) -> str:
    """Stable Streamlit widget key per dataset so folium remounts on source switch."""
    digest = hashlib.sha256(str(upload_key).encode()).hexdigest()[:16]
    return f"label_map_{digest}"


def clear_folium_widget_state() -> None:
    """Drop cached folium widget state when the active dataset changes."""
    for key in list(st.session_state.keys()):
        if key == "label_map" or str(key).startswith("label_map_"):
            del st.session_state[key]


def _coords_unchanged(old_lat, old_lon, new_lat, new_lon, eps=1e-7):
    if old_lat is None or old_lon is None:
        return False
    return math.isclose(old_lat, new_lat, abs_tol=eps) and math.isclose(
        old_lon, new_lon, abs_tol=eps
    )


def _bounds_usable_for_view(south, west, north, east):
    """Reject degenerate bounds; allow viewport-sized reads, not full-data boxes."""
    lat_span = abs(north - south)
    lng_span = abs(east - west)
    if lat_span < 1e-6 and lng_span > 45:
        return False
    if lat_span < 1e-9 and lng_span < 1e-9:
        return False
    if lat_span > 120 or lng_span > 120:
        return False
    return lat_span > 1e-6 and lng_span > 1e-6


def _center_jump_suspicious(current, center_lat, center_lon, max_delta=60.0):
    """Ignore bounds-derived centers that would teleport the map implausibly."""
    old_lat = current.get("center_lat")
    old_lon = current.get("center_lon")
    if old_lat is None or old_lon is None:
        return False
    try:
        return abs(center_lat - float(old_lat)) > max_delta or abs(
            center_lon - float(old_lon)
        ) > max_delta
    except (TypeError, ValueError):
        return False


def _label_drag_zoom_to_persist(current, drag_zoom):
    """Keep the higher zoom so a stale fit-zoom read cannot zoom out after label drag."""
    session_z = normalize_zoom(current.get("zoom"))
    drag_z = normalize_zoom(drag_zoom)
    if session_z is None:
        return drag_z
    if drag_z is None:
        return session_z
    return max(session_z, drag_z)


def persist_map_view(center_lat, center_lon, zoom, upload_key, fullscreen=None, bounds=None):
    zoom_val = normalize_zoom(zoom)
    if zoom_val is None:
        zoom_val = st.session_state.get("map_view", {}).get("zoom", 10)
    if fullscreen is None:
        fullscreen = bool(st.session_state.get("map_view", {}).get("fullscreen", False))
    view = {
        "center_lat": float(center_lat),
        "center_lon": float(center_lon),
        "zoom": zoom_val,
        "fullscreen": bool(fullscreen),
    }
    if bounds is not None:
        view["bounds"] = bounds
    elif isinstance(st.session_state.get("map_view"), dict):
        existing_bounds = st.session_state["map_view"].get("bounds")
        if existing_bounds is not None:
            view["bounds"] = existing_bounds
    st.session_state["map_view"] = view
    st.session_state["map_view_upload_key"] = upload_key


def sync_live_map_view(folium_state, upload_key):
    """Merge live bounds/zoom from st_folium into map_view for export/screenshots."""
    if not isinstance(folium_state, dict):
        return
    stored_key = st.session_state.get("map_view_upload_key")
    if stored_key is not None and stored_key != upload_key:
        return

    raw_bounds = folium_state.get("bounds")
    live_zoom = normalize_zoom(folium_state.get("zoom"))
    bounds_valid = False
    south = west = north = east = None
    if isinstance(raw_bounds, dict):
        south_west = raw_bounds.get("_southWest", {})
        north_east = raw_bounds.get("_northEast", {})
        try:
            south = float(south_west.get("lat"))
            west = float(south_west.get("lng"))
            north = float(north_east.get("lat"))
            east = float(north_east.get("lng"))
            bounds_valid = (
                None not in (south, west, north, east)
                and _bounds_usable_for_view(south, west, north, east)
            )
        except (TypeError, ValueError):
            bounds_valid = False

    if not bounds_valid and live_zoom is None:
        return

    current = dict(st.session_state.get("map_view") or {})
    before = dict(current)
    if bounds_valid:
        center_lat = (south + north) / 2.0
        center_lon = (west + east) / 2.0
        if not _center_jump_suspicious(current, center_lat, center_lon):
            current["bounds"] = raw_bounds
            current["center_lat"] = center_lat
            current["center_lon"] = center_lon
        else:
            bounds_valid = False
    if live_zoom is not None:
        prev_zoom = normalize_zoom(current.get("zoom"))
        if prev_zoom is None or abs(live_zoom - prev_zoom) > 0.03:
            current["zoom"] = live_zoom

    current.setdefault("fullscreen", False)
    if current == before:
        return
    st.session_state["map_view"] = current
    st.session_state["map_view_upload_key"] = upload_key


def reset_map_to_startup_view():
    """Clear saved zoom and dragged labels so the next map load matches first open."""
    st.session_state.pop("map_view", None)
    st.session_state.pop("map_view_upload_key", None)
    st.session_state.pop("map_world_fit_pending", None)
    st.session_state.pop("map_world_fit_done", None)
    for key in list(st.session_state.keys()):
        if key.startswith("label_lat_") or key.startswith("label_lon_"):
            del st.session_state[key]


def parse_label_drag_tooltip(tooltip):
    """Parse label drag payload: label:{idx}:{lat}:{lon}|{center_lat},{center_lon},{zoom},{fs}."""
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
            "fullscreen": None,
        }
    except (ValueError, IndexError):
        return None
    if view_part:
        try:
            center_lat, center_lon, zoom, *rest = view_part.split(",")
            result["center_lat"] = float(center_lat)
            result["center_lon"] = float(center_lon)
            result["zoom"] = float(zoom)
            if rest:
                result["fullscreen"] = str(rest[0]).strip().lower() in {"1", "true", "yes"}
        except (ValueError, IndexError):
            pass
    return result


def parse_map_sync_tooltip(tooltip):
    """Parse view sync payload: view:fs:{0|1}|{center_lat},{center_lon},{zoom}."""
    text = str(tooltip)
    if not text.startswith("view:fs:"):
        return None
    payload, _, view_part = text.partition("|")
    try:
        fs_flag = payload.split(":", 2)[2]
        fullscreen = str(fs_flag).strip().lower() in {"1", "true", "yes"}
    except (ValueError, IndexError):
        return None
    result = {
        "fullscreen": fullscreen,
        "center_lat": None,
        "center_lon": None,
        "zoom": None,
    }
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

    view_sync = parse_map_sync_tooltip(tooltip)
    if view_sync and view_sync["center_lat"] is not None and view_sync["center_lon"] is not None:
        current = st.session_state.get("map_view", {})
        fs_changed = view_sync["fullscreen"] != bool(current.get("fullscreen", False))
        center_changed = not math.isclose(
            float(current.get("center_lat", 0)),
            view_sync["center_lat"],
            abs_tol=1e-6,
        ) or not math.isclose(
            float(current.get("center_lon", 0)),
            view_sync["center_lon"],
            abs_tol=1e-6,
        )
        zoom_changed = normalize_zoom(current.get("zoom")) != normalize_zoom(view_sync["zoom"])
        if fs_changed or center_changed or zoom_changed:
            persist_map_view(
                view_sync["center_lat"],
                view_sync["center_lon"],
                view_sync["zoom"],
                upload_key,
                fullscreen=view_sync["fullscreen"],
            )
        return False

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

    zoom_changed = None
    center_changed = None
    fs_changed = None
    if drag["center_lat"] is not None and drag["center_lon"] is not None:
        current = st.session_state.get("map_view", {})
        fs_changed = drag.get("fullscreen") is not None and drag.get("fullscreen") != bool(
            current.get("fullscreen", False)
        )
        center_changed = not math.isclose(
            float(current.get("center_lat", 0)),
            drag["center_lat"],
            abs_tol=1e-6,
        ) or not math.isclose(
            float(current.get("center_lon", 0)),
            drag["center_lon"],
            abs_tol=1e-6,
        )
        zoom_changed = normalize_zoom(current.get("zoom")) != normalize_zoom(drag["zoom"])
        zoom_to_persist = _label_drag_zoom_to_persist(current, drag["zoom"])
        if zoom_changed or center_changed or fs_changed:
            persist_map_view(
                drag["center_lat"],
                drag["center_lon"],
                zoom_to_persist,
                upload_key,
                fullscreen=drag.get("fullscreen"),
            )

    return label_moved


def is_default_world_view(view):
    """True when the map is still at the startup full-world zoom-out view."""
    if not view:
        return False
    zoom = normalize_zoom(view.get("zoom"))
    default_zoom = normalize_zoom(default_interactive_zoom())
    if zoom is None and default_zoom is None:
        return False
    if zoom is None or default_zoom is None:
        return zoom == default_zoom
    return (
        math.isclose(float(view.get("center_lat", 0)), 0.0, abs_tol=1e-6)
        and math.isclose(float(view.get("center_lon", 0)), 0.0, abs_tol=1e-6)
        and abs(zoom - default_zoom) <= 0.02
        and not bool(view.get("fullscreen", False))
    )


def default_map_view_from_df(df, lat_col, lon_col):
    """Start with a full-world view; users can pan/zoom to their data."""
    return {
        "center_lat": 0.0,
        "center_lon": 0.0,
        "zoom": default_interactive_zoom(),
        "fullscreen": False,
    }


def get_map_view(df, lat_col, lon_col, upload_key):
    view = st.session_state.get("map_view")
    stored_key = st.session_state.get("map_view_upload_key")
    if view and stored_key == upload_key:
        view.setdefault("fullscreen", False)
        return view
    if view and stored_key is None:
        st.session_state["map_view_upload_key"] = upload_key
        view.setdefault("fullscreen", False)
        return view
    view = default_map_view_from_df(df, lat_col, lon_col)
    st.session_state["map_view"] = view
    st.session_state["map_view_upload_key"] = upload_key
    st.session_state["map_world_fit_pending"] = True
    st.session_state.pop("map_world_fit_done", None)
    return view


def label_positions_from_session(
    marker_rows,
    lat_span,
    lon_span,
    marker_type,
    show_name,
    show_values,
    show_total,
):
    label_sizes = {}
    for marker in marker_rows:
        idx = marker["idx"]
        _, _, icon_w, icon_h = build_label_content(
            str(marker["name"]),
            marker["labels"],
            marker["values"],
            marker["total"],
            show_name,
            show_values,
            show_total,
            value_colors=marker.get("colors"),
            marker_type=marker_type,
        )
        label_sizes[idx] = (icon_w, icon_h)

    default_positions = place_labels_near_markers(
        marker_rows,
        label_sizes,
        lat_span,
        lon_span,
        market_presets=DEFAULT_MARKET_LABEL_POSITIONS,
    )
    positions = {}
    for marker in marker_rows:
        idx = marker["idx"]
        lat_key = f"label_lat_{idx}"
        lon_key = f"label_lon_{idx}"
        default_lat, default_lon = default_positions.get(
            idx, scaled_label_latlon(marker, "below", lat_span, lon_span)
        )
        raw_lat = st.session_state.get(lat_key)
        raw_lon = st.session_state.get(lon_key)

        # Recover from older state where the latitude key was accidentally stored as (lat, lon).
        if isinstance(raw_lat, (tuple, list)) and len(raw_lat) >= 2:
            if raw_lon is None:
                raw_lon = raw_lat[1]
            raw_lat = raw_lat[0]
        if isinstance(raw_lon, (tuple, list)) and len(raw_lon) >= 2:
            if raw_lat is None:
                raw_lat = raw_lon[0]
            raw_lon = raw_lon[1]

        positions[idx] = (
            float(default_lat if raw_lat is None else raw_lat),
            float(default_lon if raw_lon is None else raw_lon),
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
