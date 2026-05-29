import streamlit as st
import pandas as pd
import folium
from folium.elements import MacroElement
from streamlit_folium import st_folium
from jinja2 import Template
import tempfile
import os
import sys
import base64
from functools import lru_cache
from io import BytesIO
import math
import json
import hashlib
import urllib.request
from PIL import Image, ImageDraw, ImageFont


def app_dir():
    """App root: PyInstaller bundle dir, env override, or script directory."""
    env_dir = os.environ.get("LABELMAP_APP_DIR")
    if env_dir and os.path.isdir(env_dir):
        return env_dir
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def is_streamlit_cloud():
    """True when running on Streamlit Community Cloud (not local/desktop bundle)."""
    if os.environ.get("STREAMLIT_RUNTIME_ENV") == "cloud":
        return True
    if os.environ.get("STREAMLIT_SHARING_MODE"):
        return True
    return False


def jpeg_export_supported():
    """JPEG export uses Playwright locally; unavailable on Streamlit Cloud."""
    return not is_streamlit_cloud()

st.set_page_config(
    page_title="LabelMap",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DEFAULT_CHART_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]
MIN_MARKER_RADIUS = 10
MAX_MARKER_RADIUS = 36
CHART_ICON_SIZE = 72
EXPORT_WIDTH = 2400
EXPORT_HEIGHT = 1400
LABEL_STYLE = (
    "display:inline-block;"
    "width:max-content;"
    "min-width:100%;"
    "background-color:rgba(255,255,255,0.5);"
    "border-radius:6px;"
    "padding:6px 10px;"
    "text-align:left;"
    "line-height:1.35;"
    "white-space:nowrap;"
    "cursor:grab;"
    "box-sizing:border-box;"
    "border:1px solid rgba(15,23,42,0.06);"
)
CONNECTOR_COLOR = "#64748b"
CONNECTOR_OPACITY = 0.5
MAP_VIEW_HEIGHT = 650
MAP_VIEW_WIDTH = 900
EXPORT_CAPTURE_WIDTH = 1400
EXPORT_CAPTURE_HEIGHT = 650
EXPORT_DEVICE_SCALE = 2
PLAYWRIGHT_BROWSERS_PATH = os.path.join(app_dir(), ".playwright-browsers")

# --- App copy (edit footer text here) ---
HERO_TAGLINE = "Upload spreadsheet → labeled map in seconds"
PRIVACY_NOTICE = "Uploads are processed on Streamlit Cloud to build your map in this session."
PRIVACY_POLICY_URL = "https://streamlit.io/privacy-policy"
CONTACT_NAME = "Pyae Phyo Kyaw"
CONTACT_EMAIL = "pyaek@icloud.com"
CONTACT_LINKEDIN = "https://www.linkedin.com/in/pyaek"
ABOUT_TEXT = (
    "LabelMap turns location spreadsheets into interactive maps with pie or column "
    "charts, draggable labels, and JPEG export."
)
HOW_IT_WORKS_STEPS = (
    "Upload your spreadsheet",
    "View and adjust the map",
    "Download the map (JPEG)",
)


def template_file_path():
    path = os.path.join(app_dir(), "map.xlsx")
    return path if os.path.exists(path) else None


def read_spreadsheet(source):
    if isinstance(source, str):
        if source.lower().endswith(".csv"):
            return pd.read_csv(source)
        return pd.read_excel(source)
    if source.name.lower().endswith(".csv"):
        return pd.read_csv(source)
    return pd.read_excel(source)


def spreadsheet_upload_key(source, df):
    if isinstance(source, str):
        mtime = int(os.path.getmtime(source))
        return f"default:{os.path.basename(source)}:{mtime}:{len(df)}"
    size = getattr(source, "size", "")
    return f"{source.name}:{size}:{len(df)}"


def render_app_intro():
    st.title("LabelMap")
    st.markdown(
        f'<p style="color:#6b7280;font-size:0.95rem;margin:0 0 0.75rem 0;">{HERO_TAGLINE}</p>',
        unsafe_allow_html=True,
    )
    step_cols = st.columns(3)
    for col, step in zip(step_cols, HOW_IT_WORKS_STEPS):
        with col:
            st.markdown(
                f'<p style="color:#374151;font-size:0.875rem;margin:0;">{step}</p>',
                unsafe_allow_html=True,
            )
    st.markdown("<div style='margin-bottom:0.75rem;'></div>", unsafe_allow_html=True)


def render_footer():
    st.divider()
    st.markdown(
        f"""
        <div style="color:#6b7280;font-size:0.8rem;line-height:1.5;">
          <p style="margin:0 0 0.5rem;"><span style="color:#374151;font-weight:600;">About</span> — {ABOUT_TEXT}</p>
          <p style="margin:0 0 0.5rem;"><span style="color:#374151;font-weight:600;">Privacy</span> — {PRIVACY_NOTICE} See <a href="{PRIVACY_POLICY_URL}" target="_blank" rel="noopener noreferrer" style="color:#2563eb;text-decoration:none;">Streamlit's privacy policy</a>.</p>
          <p style="margin:0 0 0.5rem;"><span style="color:#374151;font-weight:600;">Contact</span> — {CONTACT_NAME} · <a href="mailto:{CONTACT_EMAIL}" style="color:#2563eb;text-decoration:none;">{CONTACT_EMAIL}</a> · <a href="{CONTACT_LINKEDIN}" target="_blank" rel="noopener noreferrer" style="color:#2563eb;text-decoration:none;">LinkedIn</a></p>
          <p style="text-align:center;color:#9ca3af;font-size:0.75rem;margin:0.75rem 0 0;">© LabelMap</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_value(value):
    numeric = float(value)
    return str(int(numeric)) if numeric.is_integer() else str(round(numeric, 1))


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def pick_default(candidates, columns):
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return columns[0] if columns else None


def column_default(columns, index, fallback_candidates=None):
    if index < len(columns):
        return columns[index]
    return pick_default(fallback_candidates or [], columns)


def marker_radius(total, min_total, max_total, scale_by_total):
    if not scale_by_total or total <= 0:
        return (MIN_MARKER_RADIUS + MAX_MARKER_RADIUS) / 2
    if max_total <= min_total:
        return (MIN_MARKER_RADIUS + MAX_MARKER_RADIUS) / 2
    span = max_total - min_total
    if span <= 0:
        return (MIN_MARKER_RADIUS + MAX_MARKER_RADIUS) / 2
    return MIN_MARKER_RADIUS + (total - min_total) / span * (
        MAX_MARKER_RADIUS - MIN_MARKER_RADIUS
    )


LABEL_POSITION_ORDER = [
    "right", "left", "below", "above",
    "below-right", "below-left", "above-right", "above-left",
]


def make_chart_icon_html(values, radius, marker_type, chart_colors):
    chart_svg = make_chart_svg(values, chart_colors, radius, marker_type)
    if not chart_svg:
        return (
            f'<div style="width:{CHART_ICON_SIZE}px;height:{CHART_ICON_SIZE}px;"></div>'
        )
    return (
        f'<div style="width:{CHART_ICON_SIZE}px;height:{CHART_ICON_SIZE}px;'
        f'display:flex;align-items:center;justify-content:center;">{chart_svg}</div>'
    )


def display_column_name(column):
    name = str(column).replace("_", " ").strip()
    for prefix in ("value ", "value"):
        if name.lower().startswith(prefix):
            name = name[len(prefix) :].strip()
    return name if name else str(column)


def labels_enabled(show_name, show_values, show_total):
    return show_name or show_values or show_total


def build_label_content(name, labels, values, total, show_name, show_values, show_total):
    text_lines = []
    html_parts = []

    if show_name:
        text_lines.append(str(name))
        html_parts.append(
            f'<div style="font-size:11px;font-weight:600;color:#111827;">{name}</div>'
        )

    if show_values:
        for label, value in zip(labels, values):
            short = display_column_name(label)
            text = f"{short} · {format_value(value)}"
            text_lines.append(text)
            html_parts.append(
                f'<div style="font-size:10px;color:#475569;">{text}</div>'
            )

    if show_total and values:
        text = f"{format_value(total)} total"
        text_lines.append(text)
        html_parts.append(
            f'<div style="font-size:10px;font-weight:600;color:#111827;">{text}</div>'
        )

    if not text_lines:
        return [], "", 0, 0

    max_chars = max(len(line) for line in text_lines)
    icon_w = min(240, max(72, int(max_chars * 6.2) + 24))
    icon_h = 12 + len(text_lines) * 15
    return text_lines, "".join(html_parts), icon_w, icon_h


def make_label_icon_html(name, labels, values, total, show_name, show_values, show_total):
    _, labels_html, icon_w, icon_h = build_label_content(
        name, labels, values, total, show_name, show_values, show_total
    )
    if not labels_html:
        return "", 0, 0
    html = f'<div style="{LABEL_STYLE}">{labels_html}</div>'
    return html, icon_w, icon_h


def initial_label_latlon(marker, position_key, lat_span, lon_span):
    dlat = max(lat_span * 0.06, 0.05)
    dlon = max(lon_span * 0.06, 0.05)
    offsets = {
        "right": (0, dlon),
        "left": (0, -dlon),
        "below": (-dlat, 0),
        "above": (dlat, 0),
        "below-right": (-dlat, dlon),
        "below-left": (-dlat, -dlon),
        "above-right": (dlat, dlon),
        "above-left": (dlat, -dlon),
    }
    lat_off, lon_off = offsets.get(position_key, (0, dlon))
    return marker["lat"] + lat_off, marker["lon"] + lon_off


def sync_dragged_labels(map_state):
    if not map_state:
        return
    tooltip = map_state.get("last_object_clicked_tooltip")
    if not tooltip or not str(tooltip).startswith("label:"):
        return
    try:
        _, idx, lat, lon = str(tooltip).split(":", 3)
        st.session_state[f"label_lat_{idx}"] = float(lat)
        st.session_state[f"label_lon_{idx}"] = float(lon)
    except (ValueError, IndexError):
        return


def estimate_label_deg(icon_w, icon_h, lat_span, lon_span):
    deg_lon = lon_span * (icon_w / MAP_VIEW_WIDTH)
    deg_lat = lat_span * (icon_h / MAP_VIEW_HEIGHT)
    return max(deg_lat, lat_span * 0.015), max(deg_lon, lon_span * 0.015)


def resolve_label_overlaps(marker_rows, label_positions, label_sizes, lat_span, lon_span):
    adjusted = {idx: [pos[0], pos[1]] for idx, pos in label_positions.items()}
    idx_list = [marker["idx"] for marker in marker_rows]

    for _ in range(50):
        for i, idx_a in enumerate(idx_list):
            for idx_b in idx_list[i + 1 :]:
                lat_a, lon_a = adjusted[idx_a]
                lat_b, lon_b = adjusted[idx_b]
                w_a, h_a = label_sizes[idx_a]
                w_b, h_b = label_sizes[idx_b]
                box_lat_a, box_lon_a = estimate_label_deg(w_a, h_a, lat_span, lon_span)
                box_lat_b, box_lon_b = estimate_label_deg(w_b, h_b, lat_span, lon_span)

                min_lat_sep = (box_lat_a + box_lat_b) * 0.55
                min_lon_sep = (box_lon_a + box_lon_b) * 0.55
                dlat = lat_a - lat_b
                dlon = lon_a - lon_b

                push_lat = min_lat_sep - abs(dlat)
                push_lon = min_lon_sep - abs(dlon)
                if push_lat <= 0 or push_lon <= 0:
                    continue

                shift_lat = push_lat / 2 * (1 if dlat >= 0 else -1 or 1)
                shift_lon = push_lon / 2 * (1 if dlon >= 0 else -1 or 1)
                adjusted[idx_a][0] += shift_lat
                adjusted[idx_a][1] += shift_lon
                adjusted[idx_b][0] -= shift_lat
                adjusted[idx_b][1] -= shift_lon

    return {idx: (coords[0], coords[1]) for idx, coords in adjusted.items()}


def connector_points_px(chart_px, label_px, icon_w, icon_h, chart_radius_px):
    box_cx = label_px[0] + icon_w / 2
    box_cy = label_px[1] + icon_h / 2
    dx = box_cx - chart_px[0]
    dy = box_cy - chart_px[1]
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return chart_px, (box_cx, box_cy)

    edge_scale = min((icon_w / 2) / abs(dx), (icon_h / 2) / abs(dy))
    label_edge = (box_cx - dx * edge_scale, box_cy - dy * edge_scale)

    dist = math.hypot(dx, dy) or 1.0
    chart_edge = (
        chart_px[0] + dx / dist * chart_radius_px,
        chart_px[1] + dy / dist * chart_radius_px,
    )
    return chart_edge, label_edge


class DynamicConnectors(MacroElement):
    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            var map = {{ this.map_name }};
            var items = {{ this.items | tojson }};
            var chartRadiusPx = {{ this.chart_radius_px }};
            var layerGroup = L.layerGroup().addTo(map);

            function edgePoints(chartLatLng, labelLatLng, iconW, iconH) {
                var chartPx = map.latLngToContainerPoint(chartLatLng);
                var labelPx = map.latLngToContainerPoint(labelLatLng);
                var boxCx = labelPx.x + iconW / 2;
                var boxCy = labelPx.y + iconH / 2;
                var dx = boxCx - chartPx.x;
                var dy = boxCy - chartPx.y;
                if (Math.abs(dx) < 1e-6 && Math.abs(dy) < 1e-6) {
                    return [chartLatLng, labelLatLng];
                }
                var edgeScale = Math.min((iconW / 2) / Math.abs(dx), (iconH / 2) / Math.abs(dy));
                var labelEdgePx = L.point(boxCx - dx * edgeScale, boxCy - dy * edgeScale);
                var dist = Math.hypot(dx, dy) || 1;
                var chartEdgePx = L.point(
                    chartPx.x + dx / dist * chartRadiusPx,
                    chartPx.y + dy / dist * chartRadiusPx
                );
                return [
                    map.containerPointToLatLng(chartEdgePx),
                    map.containerPointToLatLng(labelEdgePx)
                ];
            }

            function updateLines() {
                layerGroup.clearLayers();
                items.forEach(function(item) {
                    var labelMarker = window[item.label_marker_name];
                    if (!labelMarker) return;
                    var pts = edgePoints(
                        L.latLng(item.chart_lat, item.chart_lon),
                        labelMarker.getLatLng(),
                        item.icon_w,
                        item.icon_h
                    );
                    L.polyline(pts, {
                        color: '{{ this.connector_color }}',
                        weight: 1.5,
                        opacity: {{ this.connector_opacity }}
                    }).addTo(layerGroup);
                });
            }

            updateLines();
            map.on('zoomend moveend', updateLines);
            items.forEach(function(item) {
                var labelMarker = window[item.label_marker_name];
                if (!labelMarker) return;
                labelMarker.on('drag dragend', updateLines);
            });
            window._updateMapConnectors = updateLines;
        })();
        {% endmacro %}
        """
    )

    def __init__(self, map_name, items, chart_radius_px):
        super().__init__()
        self._name = "DynamicConnectors"
        self.map_name = map_name
        self.items = items
        self.chart_radius_px = chart_radius_px
        self.connector_color = CONNECTOR_COLOR
        self.connector_opacity = CONNECTOR_OPACITY


class LabelDragSync(MacroElement):
    _template = Template(
        """
        {% macro script(this, kwargs) %}
        {% for item in this.items %}
        {{ item.marker_name }}.on('dragend', function(e) {
            var ll = e.target.getLatLng();
            e.target.setTooltipContent(
                'label:{{ item.idx }}:' + ll.lat + ':' + ll.lng
            );
            if (window._updateMapConnectors) {
                window._updateMapConnectors();
            }
            e.target.fire('click');
        });
        {% endfor %}
        {% endmacro %}
        """
    )

    def __init__(self, items):
        super().__init__()
        self._name = "LabelDragSync"
        self.items = items


class ExportMapStyles(MacroElement):
    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            var style = document.createElement('style');
            style.textContent = `
                html, body {
                    margin: 0;
                    padding: 0;
                    width: {{ this.width }}px;
                    height: {{ this.height }}px;
                    overflow: hidden;
                    background: #fff;
                }
                .folium-map, .leaflet-container {
                    width: {{ this.width }}px !important;
                    height: {{ this.height }}px !important;
                }
                .leaflet-control-container { display: none !important; }
            `;
            document.head.appendChild(style);
        })();
        {% endmacro %}
        """
    )

    def __init__(self, width, height):
        super().__init__()
        self._name = "ExportMapStyles"
        self.width = width
        self.height = height


class ExportReady(MacroElement):
    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            var map = {{ this.map_name }};
            var exportBounds = {{ this.export_bounds | tojson }};
            var exportZoom = {{ this.export_zoom | tojson }};

            function markReady() {
                document.body.setAttribute('data-map-export-ready', 'true');
            }
            function tilesReady() {
                var tiles = document.querySelectorAll('.leaflet-tile');
                if (!tiles.length) return false;
                return Array.from(tiles).every(function(tile) {
                    return tile.complete && tile.naturalWidth > 0;
                });
            }
            function applyView() {
                map.invalidateSize();
                if (exportBounds) {
                    map.fitBounds(
                        L.latLngBounds(
                            L.latLng(exportBounds.south, exportBounds.west),
                            L.latLng(exportBounds.north, exportBounds.east)
                        ),
                        {padding: [0, 0], animate: false, maxZoom: exportZoom || 18}
                    );
                } else if (exportZoom !== null && exportZoom !== undefined) {
                    map.setZoom(exportZoom, {animate: false});
                }
                if (window._updateMapConnectors) {
                    window._updateMapConnectors();
                }
            }
            function waitForTiles(attempts) {
                if (tilesReady()) {
                    applyView();
                    if (window._updateMapConnectors) window._updateMapConnectors();
                    setTimeout(function() {
                        if (window._updateMapConnectors) window._updateMapConnectors();
                        markReady();
                    }, 500);
                    return;
                }
                if (attempts <= 0) {
                    applyView();
                    markReady();
                    return;
                }
                setTimeout(function() { waitForTiles(attempts - 1); }, 250);
            }
            map.whenReady(function() {
                applyView();
                waitForTiles(50);
            });
        })();
        {% endmacro %}
        """
    )

    def __init__(self, map_name, export_bounds=None, export_zoom=None):
        super().__init__()
        self._name = "ExportReady"
        self.map_name = map_name
        self.export_bounds = export_bounds
        self.export_zoom = export_zoom


def normalize_zoom(zoom):
    if isinstance(zoom, (int, float)) and not isinstance(zoom, bool):
        value = float(zoom)
        if value > 0:
            return int(round(value))
    return None


def normalize_bounds(bounds):
    south = min(float(bounds["south"]), float(bounds["north"]))
    north = max(float(bounds["south"]), float(bounds["north"]))
    west = min(float(bounds["west"]), float(bounds["east"]))
    east = max(float(bounds["west"]), float(bounds["east"]))
    min_span = 1e-4
    if north - south < min_span:
        mid = (north + south) / 2
        south, north = mid - min_span / 2, mid + min_span / 2
    if east - west < min_span:
        mid = (east + west) / 2
        west, east = mid - min_span / 2, mid + min_span / 2
    return {"south": south, "west": west, "north": north, "east": east}


def expand_chart_colors(chart_colors, count):
    palette = chart_colors or DEFAULT_CHART_COLORS
    if count <= 0:
        return []
    repeats = (count // len(palette)) + 1
    return (palette * repeats)[:count]


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
    if bounds is None:
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
        LabelDragSync(drag_sync_items).add_to(m)
    return connector_items


def ensure_playwright_browser():
    import subprocess
    import sys

    if is_streamlit_cloud():
        raise RuntimeError("Playwright browser install is not supported on Streamlit Cloud.")

    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", PLAYWRIGHT_BROWSERS_PATH)
    if os.path.isdir(PLAYWRIGHT_BROWSERS_PATH) and os.listdir(PLAYWRIGHT_BROWSERS_PATH):
        return
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=True,
        env={**os.environ, "PLAYWRIGHT_BROWSERS_PATH": PLAYWRIGHT_BROWSERS_PATH},
    )


def capture_map_screenshot(
    m,
    width=EXPORT_CAPTURE_WIDTH,
    height=EXPORT_CAPTURE_HEIGHT,
    export_bounds=None,
    export_zoom=None,
):
    from playwright.sync_api import sync_playwright

    ensure_playwright_browser()
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", PLAYWRIGHT_BROWSERS_PATH)
    ExportMapStyles(width, height).add_to(m)
    ExportReady(m.get_name(), export_bounds, export_zoom).add_to(m)

    html_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as tmp:
            m.save(tmp.name)
            html_path = tmp.name

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": width, "height": height},
                device_scale_factor=EXPORT_DEVICE_SCALE,
            )
            page.goto(f"file://{html_path}")
            page.wait_for_selector('[data-map-export-ready="true"]', timeout=30000)
            map_el = page.locator(".leaflet-container").first
            map_el.wait_for(state="visible", timeout=10000)
            screenshot = map_el.screenshot(type="jpeg", quality=98)
            browser.close()
        return screenshot
    finally:
        if html_path and os.path.exists(html_path):
            os.unlink(html_path)


def export_map_image(
    df,
    lat_col,
    lon_col,
    marker_rows,
    label_positions,
    map_state,
    min_total,
    max_total,
    marker_type,
    chart_colors,
    scale_by_total,
    show_name,
    show_values,
    show_total,
):
    export_bounds, export_zoom = parse_map_view(map_state, df, lat_col, lon_col)
    try:
        export_map = folium.Map(
            location=[df[lat_col].mean(), df[lon_col].mean()],
            tiles="OpenStreetMap",
        )
        populate_map_layers(
            export_map,
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
            draggable_labels=False,
        )
        apply_map_view(export_map, map_state, df, lat_col, lon_col)
        return capture_map_screenshot(
            export_map,
            export_bounds=export_bounds,
            export_zoom=export_zoom,
        )
    except Exception:
        return generate_map_jpeg(
            df,
            lat_col,
            lon_col,
            marker_rows,
            label_positions,
            map_state,
            min_total,
            max_total,
            marker_type,
            chart_colors,
            scale_by_total,
            show_name,
            show_values,
            show_total,
        )


def get_export_font(size=16):
    for path in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def fit_bounds_for_points(df, lat_col, lon_col, padding=0.12):
    min_lat, max_lat = df[lat_col].min(), df[lat_col].max()
    min_lon, max_lon = df[lon_col].min(), df[lon_col].max()
    if min_lat == max_lat:
        min_lat -= 0.1
        max_lat += 0.1
    if min_lon == max_lon:
        min_lon -= 0.1
        max_lon += 0.1
    lat_pad = (max_lat - min_lat) * padding
    lon_pad = (max_lon - min_lon) * padding
    return [
        [min_lat - lat_pad, min_lon - lon_pad],
        [max_lat + lat_pad, max_lon + lon_pad],
    ]


def build_label_html(name, labels, values, total, show_name, show_values, show_total):
    _, html, _, _ = build_label_content(
        name, labels, values, total, show_name, show_values, show_total
    )
    return html


def chart_type_label(marker_type):
    if marker_type == "pie":
        return "Pie chart"
    return "Vertical bar"


def normalize_marker_type(marker_type):
    return "column" if marker_type == "bar" else marker_type


def make_chart_svg(values, chart_colors, radius, marker_type):
    total = sum(values)
    if total <= 0:
        return ""

    marker_type = normalize_marker_type(marker_type)
    colors = expand_chart_colors(chart_colors, len(values))
    if marker_type == "column":
        positive = [(value, color) for value, color in zip(values, colors) if value > 0]
        if not positive:
            return ""
        bar_h = max(20, int(radius * 1.6))
        bar_w = max(6, min(14, int(radius * 0.5)))
        max_val = max(value for value, _ in positive) or 1
        total_w = len(positive) * bar_w
        segments = []
        x_cursor = 0.0
        for value, color in positive:
            seg_h = (value / max_val) * bar_h
            y_top = bar_h - seg_h
            segments.append(
                f'<rect x="{x_cursor:.1f}" y="{y_top:.1f}" width="{bar_w}" height="{seg_h:.1f}" '
                f'fill="{color}"/>'
            )
            x_cursor += bar_w
        return (
            f'<svg width="{total_w:.0f}" height="{bar_h}" viewBox="0 0 {total_w} {bar_h}" '
            f'style="display:block;">{"".join(segments)}</svg>'
        )

    size = radius * 2
    cx = cy = radius
    svg_segments = []
    start_angle = 0.0
    for value, color in zip(values, colors):
        angle = 360.0 * value / total
        if angle <= 0:
            continue
        end_angle = start_angle + angle
        x1 = cx + radius * math.cos(math.radians(start_angle))
        y1 = cy + radius * math.sin(math.radians(start_angle))
        x2 = cx + radius * math.cos(math.radians(end_angle))
        y2 = cy + radius * math.sin(math.radians(end_angle))
        large_arc = 1 if angle > 180 else 0
        path = (
            f"M {cx},{cy} L {x1:.2f},{y1:.2f} "
            f"A {radius},{radius} 0 {large_arc},1 {x2:.2f},{y2:.2f} Z"
        )
        svg_segments.append(
            f'<path d="{path}" fill="{color}" stroke="#ffffff" stroke-width="1"/>'
        )
        start_angle = end_angle
    return (
        f'<svg width="{size:.0f}" height="{size:.0f}" viewBox="0 0 {size} {size}" '
        f'style="display:block;">{"".join(svg_segments)}</svg>'
        )


def export_state_signature(
    upload_key,
    map_state,
    label_positions,
    marker_type,
    chart_colors,
    scale_by_total,
    show_name,
    show_values,
    show_total,
):
    payload = {
        "upload_key": upload_key,
        "bounds": map_state.get("bounds") if isinstance(map_state, dict) else None,
        "zoom": map_state.get("zoom") if isinstance(map_state, dict) else None,
        "labels": sorted(
            (idx, round(lat, 5), round(lon, 5))
            for idx, (lat, lon) in label_positions.items()
        ),
        "marker_type": marker_type,
        "chart_colors": list(chart_colors),
        "scale_by_total": scale_by_total,
        "show_name": show_name,
        "show_values": show_values,
        "show_total": show_total,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()


@st.cache_data(show_spinner="Rendering high-quality map image...")
def build_map_jpeg_export(
    signature,
    df,
    lat_col,
    lon_col,
    marker_rows,
    label_positions,
    map_state,
    min_total,
    max_total,
    marker_type,
    chart_colors,
    scale_by_total,
    show_name,
    show_values,
    show_total,
):
    return export_map_image(
        df,
        lat_col,
        lon_col,
        marker_rows,
        label_positions,
        map_state,
        min_total,
        max_total,
        marker_type,
        chart_colors,
        scale_by_total,
        show_name,
        show_values,
        show_total,
    )


def latlon_distance(lat1, lon1, lat2, lon2):
    return math.hypot(lat2 - lat1, lon2 - lon1)


def label_positions_conflict(pos_a, pos_b):
    if pos_a == pos_b:
        return True
    primary = {"below", "above", "left", "right"}
    if pos_a in primary and pos_b in primary:
        opposites = {("below", "above"), ("above", "below"), ("left", "right"), ("right", "left")}
        return (pos_a, pos_b) not in opposites
    return pos_a.split("-")[0] == pos_b.split("-")[0]


def resolve_label_positions(marker_rows, min_distance):
    if not marker_rows:
        return {}
    center_lat = sum(m["lat"] for m in marker_rows) / len(marker_rows)
    center_lon = sum(m["lon"] for m in marker_rows) / len(marker_rows)

    def preferred_positions(marker):
        order = list(LABEL_POSITION_ORDER)
        if marker["lon"] >= center_lon:
            order = ["left", "above-left", "below-left"] + [
                p for p in order if p not in {"left", "above-left", "below-left"}
            ]
        else:
            order = ["right", "above-right", "below-right"] + [
                p for p in order if p not in {"right", "above-right", "below-right"}
            ]
        if marker["lat"] >= center_lat:
            order = ["below", "below-right", "below-left"] + [
                p for p in order if not p.startswith("below")
            ]
        else:
            order = ["above", "above-right", "above-left"] + [
                p for p in order if not p.startswith("above")
            ]
        return order

    assignments = {}
    placed = []
    for marker in marker_rows:
        chosen = preferred_positions(marker)[0]
        for position_key in preferred_positions(marker):
            conflict = False
            for placed_lat, placed_lon, placed_pos in placed:
                if latlon_distance(marker["lat"], marker["lon"], placed_lat, placed_lon) >= min_distance:
                    continue
                if label_positions_conflict(position_key, placed_pos):
                    conflict = True
                    break
            if not conflict:
                chosen = position_key
                break
        else:
            prefs = preferred_positions(marker)
            chosen = prefs[len(placed) % len(prefs)]
        assignments[marker["idx"]] = chosen
        placed.append((marker["lat"], marker["lon"], chosen))
    return assignments


def deg_lonlat_to_global_pixels(lon, lat, zoom):
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x = (lon + 180.0) / 360.0 * 256.0 * n
    y = (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * 256.0 * n
    return x, y


def global_pixels_to_tile(px, py):
    return int(px // 256), int(py // 256)


def make_placeholder_tile(message="Background map unavailable"):
    tile = Image.new("RGB", (256, 256), "#eef2f7")
    draw = ImageDraw.Draw(tile)
    font = ImageFont.load_default()
    draw.rectangle([(0, 0), (255, 255)], outline="#cbd5e1", width=2)
    draw.text((16, 112), message, fill="#64748b", font=font)
    return tile


@lru_cache(maxsize=1024)
def fetch_tile(z, x, y):
    max_tile = 2 ** z - 1
    if x < 0 or y < 0 or x > max_tile or y > max_tile:
        return make_placeholder_tile("Outside map extent")
    url = f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "label-map-export/1.0",
                "Accept": "image/png,image/*;q=0.8,*/*;q=0.5",
            },
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return Image.open(BytesIO(response.read())).convert("RGB")
    except Exception:
        return make_placeholder_tile("Tile fetch failed")


def best_zoom(min_lon, max_lon, min_lat, max_lat, width, height):
    for z in range(10, 0, -1):
        x0, y0 = deg_lonlat_to_global_pixels(min_lon, max_lat, z)
        x1, y1 = deg_lonlat_to_global_pixels(max_lon, min_lat, z)
        if x1 - x0 <= width and y1 - y0 <= height:
            return z
    return 1


def draw_chart_on_image(draw, x, y, values, chart_colors, radius, marker_type):
    total = sum(values)
    if total <= 0:
        return
    marker_type = normalize_marker_type(marker_type)
    colors = expand_chart_colors(chart_colors, len(values))
    rgb_colors = [hex_to_rgb(color) for color in colors]

    if marker_type == "column":
        positive = [(value, color) for value, color in zip(values, rgb_colors) if value > 0]
        if not positive:
            return
        bar_h = max(20, int(radius * 1.6))
        bar_w = max(6, min(14, int(radius * 0.5)))
        max_val = max(value for value, _ in positive) or 1
        total_w = len(positive) * bar_w
        left = x - total_w // 2
        bottom = y + bar_h // 2
        x_cursor = left
        for value, color in positive:
            seg_h = int((value / max_val) * bar_h)
            top = bottom - seg_h
            draw.rectangle([x_cursor, top, x_cursor + bar_w, bottom], fill=color)
            x_cursor += bar_w
        return

    start_angle = 0
    for value, color in zip(values, rgb_colors):
        if value <= 0:
            continue
        angle = 360.0 * value / total
        draw.pieslice(
            [x - radius, y - radius, x + radius, y + radius],
            start=start_angle,
            end=start_angle + angle,
            fill=color,
            outline="white",
        )
        start_angle += angle


def generate_map_jpeg(
    df,
    lat_col,
    lon_col,
    marker_rows,
    label_positions,
    map_state,
    min_total,
    max_total,
    marker_type,
    chart_colors,
    scale_by_total,
    show_name,
    show_values,
    show_total,
):
    width, height = EXPORT_WIDTH, EXPORT_HEIGHT
    bounds = None
    zoom = None
    if isinstance(map_state, dict):
        zoom = map_state.get("zoom")
        raw_bounds = map_state.get("bounds")
        if isinstance(raw_bounds, dict):
            south_west = raw_bounds.get("_southWest", {})
            north_east = raw_bounds.get("_northEast", {})
            south = south_west.get("lat")
            west = south_west.get("lng")
            north = north_east.get("lat")
            east = north_east.get("lng")
            if None not in (south, west, north, east):
                bounds = (south, west, north, east)

    if bounds is not None:
        south, west, north, east = bounds
        min_lat, max_lat = south, north
        min_lon, max_lon = west, east
        if zoom is None:
            zoom = best_zoom(min_lon, max_lon, min_lat, max_lat, width - 40, height - 40)
    else:
        fit = fit_bounds_for_points(df, lat_col, lon_col)
        min_lat, min_lon = fit[0]
        max_lat, max_lon = fit[1]
        zoom = best_zoom(min_lon, max_lon, min_lat, max_lat, width - 40, height - 40)

    min_px, min_py = deg_lonlat_to_global_pixels(min_lon, max_lat, zoom)
    max_px, max_py = deg_lonlat_to_global_pixels(max_lon, min_lat, zoom)
    if min_px > max_px:
        min_px, max_px = max_px, min_px
    if min_py > max_py:
        min_py, max_py = max_py, min_py
    span_x = max(max_px - min_px, 1.0)
    span_y = max(max_py - min_py, 1.0)
    tile_x0, tile_y0 = global_pixels_to_tile(min_px, min_py)
    tile_x1, tile_y1 = global_pixels_to_tile(max_px, max_py)

    tile_canvas = Image.new("RGB", ((tile_x1 - tile_x0 + 1) * 256, (tile_y1 - tile_y0 + 1) * 256))
    for tx in range(tile_x0, tile_x1 + 1):
        for ty in range(tile_y0, tile_y1 + 1):
            tile = fetch_tile(zoom, tx, ty)
            tile_canvas.paste(tile, ((tx - tile_x0) * 256, (ty - tile_y0) * 256))

    crop_left = int(min_px - tile_x0 * 256)
    crop_top = int(min_py - tile_y0 * 256)
    crop_right = int(max_px - tile_x0 * 256)
    crop_bottom = int(max_py - tile_y0 * 256)
    map_image = tile_canvas.crop((crop_left, crop_top, crop_right, crop_bottom))
    map_image = map_image.resize((width, height), Image.LANCZOS)
    draw = ImageDraw.Draw(map_image)
    font = get_export_font(16)

    def project(lat, lon):
        gx, gy = deg_lonlat_to_global_pixels(lon, lat, zoom)
        px = (gx - min_px) / span_x * width
        py = (gy - min_py) / span_y * height
        return int(px), int(py)

    def draw_label_panel(top_left, lines):
        line_height = 18
        padding = 10
        max_line_width = max(font.getlength(line) for line in lines) if lines else 0
        box_w = int(max_line_width + padding * 2)
        box_h = len(lines) * line_height + padding * 2
        x0, y0 = top_left
        x0 = max(0, min(x0, map_image.width - box_w))
        y0 = max(0, min(y0, map_image.height - box_h))

        region = map_image.crop((x0, y0, x0 + box_w, y0 + box_h)).convert("RGBA")
        overlay = Image.new("RGBA", region.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rounded_rectangle(
            [(0, 0), (box_w - 1, box_h - 1)],
            radius=8,
            fill=(255, 255, 255, 128),
            outline=(15, 23, 42, 15),
        )
        blended = Image.alpha_composite(region, overlay)
        map_image.paste(blended.convert("RGB"), (x0, y0))
        text_y = y0 + padding
        for line in lines:
            draw.text((x0 + padding, text_y), line, fill="#111827", font=font)
            text_y += line_height
        return x0, y0, box_w, box_h

    def measure_label_box(lines):
        line_height = 18
        padding = 10
        max_line_width = max(font.getlength(line) for line in lines) if lines else 0
        box_w = int(max_line_width + padding * 2)
        box_h = len(lines) * line_height + padding * 2
        return box_w, box_h

    def draw_connector(chart_x, chart_y, label_x, label_y, box_w, box_h):
        chart_edge, label_edge = connector_points_px(
            (chart_x, chart_y),
            (label_x, label_y),
            box_w,
            box_h,
            CHART_ICON_SIZE // 2,
        )
        connector = Image.new("RGBA", map_image.size, (0, 0, 0, 0))
        connector_draw = ImageDraw.Draw(connector)
        connector_draw.line(
            [chart_edge, label_edge],
            fill=(100, 116, 139, 128),
            width=2,
        )
        map_image.paste(Image.alpha_composite(map_image.convert("RGBA"), connector).convert("RGB"))

    pending_labels = []
    for marker in marker_rows:
        idx = marker["idx"]
        values = marker["values"]
        labels = marker["labels"]
        total = marker["total"]
        radius = marker_radius(total, min_total, max_total, scale_by_total)
        chart_x, chart_y = project(marker["lat"], marker["lon"])

        label_lat, label_lon = label_positions[idx]
        label_x, label_y = project(label_lat, label_lon)
        text_lines, _, _, _ = build_label_content(
            str(marker["name"]),
            labels,
            values,
            total,
            show_name,
            show_values,
            show_total,
        )
        if not text_lines:
            continue
        box_w, box_h = measure_label_box(text_lines)
        label_x = max(0, min(label_x, map_image.width - box_w))
        label_y = max(0, min(label_y, map_image.height - box_h))
        pending_labels.append(
            (chart_x, chart_y, label_x, label_y, box_w, box_h, text_lines, values, radius)
        )

    for chart_x, chart_y, label_x, label_y, box_w, box_h, _, _, _ in pending_labels:
        draw_connector(chart_x, chart_y, label_x, label_y, box_w, box_h)

    for chart_x, chart_y, _, _, _, _, _, values, radius in pending_labels:
        draw_chart_on_image(draw, chart_x, chart_y, values, chart_colors, radius, marker_type)

    for _, _, label_x, label_y, _, _, text_lines, _, _ in pending_labels:
        draw_label_panel((label_x, label_y), text_lines)

    output = BytesIO()
    map_image.save(output, format="JPEG", quality=95, optimize=True)
    return output.getvalue()


def template_download_href():
    template_path = template_file_path() or "map.xlsx"
    mtime = int(os.path.getmtime(template_path)) if os.path.exists(template_path) else 0
    return _template_download_href_cached(template_path, mtime)


@lru_cache(maxsize=4)
def _template_download_href_cached(template_path, mtime):
    with open(template_path, "rb") as template_file:
        encoded = base64.b64encode(template_file.read()).decode()
    return (
        "data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,"
        + encoded
    )


def render_template_link():
    if template_file_path():
        href = template_download_href()
        st.markdown(
            f'<p style="margin:0.25rem 0 0;font-size:0.875rem;color:#6b7280;">'
            f'Need a starter file? '
            f'<a href="{href}" download="map.xlsx" '
            f'style="color:#2563eb;text-decoration:none;">Download template</a></p>',
            unsafe_allow_html=True,
        )


render_app_intro()

uploaded_file = st.file_uploader(
    "Spreadsheet",
    type=["xlsx", "xls", "csv"],
    help="Column A: location, B: latitude, C: longitude, D onward: health value columns",
)
render_template_link()
st.markdown(
    f'<p style="color:#6b7280;font-size:0.875rem;margin:0;">{PRIVACY_NOTICE} See '
    f'<a href="{PRIVACY_POLICY_URL}" target="_blank" rel="noopener noreferrer" '
    f'style="color:#2563eb;text-decoration:none;">Streamlit\'s privacy policy</a>.</p>',
    unsafe_allow_html=True,
)

st.divider()

if uploaded_file is not None:
    try:
        df = read_spreadsheet(uploaded_file)
        data_label = uploaded_file.name
        upload_key = spreadsheet_upload_key(uploaded_file, df)

        if st.session_state.get("active_upload_key") != upload_key:
            st.session_state["active_upload_key"] = upload_key
            st.session_state.pop("labels_overlap_resolved", None)
            for key in list(st.session_state.keys()):
                if key.startswith("label_lat_") or key.startswith("label_lon_"):
                    del st.session_state[key]

        all_cols = df.columns.tolist()

        st.subheader("Column mapping")
        map_col1, map_col2, map_col3 = st.columns(3)
        with map_col1:
            name_col = st.selectbox(
                "Location name column",
                all_cols,
                index=all_cols.index(
                    column_default(all_cols, 0, ["location", "location_name", "name", "village"])
                ),
            )
        with map_col2:
            lat_col = st.selectbox(
                "Latitude column",
                all_cols,
                index=all_cols.index(column_default(all_cols, 1, ["latitude", "lat"])),
            )
        with map_col3:
            lon_col = st.selectbox(
                "Longitude column",
                all_cols,
                index=all_cols.index(
                    column_default(all_cols, 2, ["longitude", "long", "lng", "lon"])
                ),
            )

        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        available_value_cols = [
            col for col in numeric_cols if col not in {name_col, lat_col, lon_col}
        ]
        positional_value_cols = [col for col in all_cols[3:] if col in available_value_cols]
        default_value_cols = positional_value_cols or available_value_cols
        value_cols = st.multiselect(
            "Value columns",
            available_value_cols,
            default=default_value_cols,
            help="Defaults to column D onward. Used for pie or column charts.",
        )

        mapping_errors = []
        if lat_col not in numeric_cols:
            mapping_errors.append(f"'{lat_col}' must be numeric")
        if lon_col not in numeric_cols:
            mapping_errors.append(f"'{lon_col}' must be numeric")
        if not value_cols:
            mapping_errors.append("Select at least one chart value column")

        if mapping_errors:
            for error in mapping_errors:
                st.error(error)
        else:
            def get_nonzero_values(row):
                values = []
                labels = []
                for label in value_cols:
                    value = row[label]
                    if pd.notnull(value) and value != 0:
                        try:
                            value = float(value)
                        except Exception:
                            continue
                        values.append(value)
                        labels.append(label)
                return values, labels

            st.subheader("Chart settings")
            chart_col1, chart_col2 = st.columns([1, 3])
            with chart_col1:
                if st.session_state.get("marker_type") == "bar":
                    st.session_state["marker_type"] = "column"
                marker_type = st.radio(
                    "Chart type",
                    ["pie", "column"],
                    format_func=chart_type_label,
                    horizontal=True,
                    key="marker_type",
                )
            with chart_col2:
                color_pickers = st.columns(len(value_cols))
                chart_colors = []
                for i, col in enumerate(value_cols):
                    default = DEFAULT_CHART_COLORS[i % len(DEFAULT_CHART_COLORS)]
                    if f"chart_color_{col}" not in st.session_state:
                        st.session_state[f"chart_color_{col}"] = default
                    with color_pickers[i]:
                        st.color_picker(f"{col} color", key=f"chart_color_{col}")
                    chart_colors.append(st.session_state[f"chart_color_{col}"])

            for key, default in (
                ("show_lbl_name", True),
                ("show_lbl_values", True),
                ("show_lbl_total", True),
                ("scale_by_total", True),
            ):
                if key not in st.session_state:
                    st.session_state[key] = default

            st.subheader("Labels")
            lbl_col1, lbl_col2, lbl_col3, lbl_col4 = st.columns(4)
            with lbl_col1:
                st.checkbox("Show location name", key="show_lbl_name")
            with lbl_col2:
                st.checkbox("Show values", key="show_lbl_values")
            with lbl_col3:
                st.checkbox("Show total", key="show_lbl_total")
            with lbl_col4:
                st.checkbox("Scale size by total", key="scale_by_total")

            show_name = st.session_state.show_lbl_name
            show_values = st.session_state.show_lbl_values
            show_total = st.session_state.show_lbl_total
            scale_by_total = st.session_state.scale_by_total

            marker_rows = []
            totals = []
            for idx, row in df.iterrows():
                values, labels = get_nonzero_values(row)
                total = sum(values)
                totals.append(total)
                marker_rows.append(
                    {
                        "idx": idx,
                        "lat": row[lat_col],
                        "lon": row[lon_col],
                        "values": values,
                        "labels": labels,
                        "total": total,
                        "name": row[name_col],
                    }
                )

            positive_totals = [total for total in totals if total > 0]
            min_total = min(positive_totals) if positive_totals else 0
            max_total = max(totals) if totals else 1
            lat_span = df[lat_col].max() - df[lat_col].min() or 1
            lon_span = df[lon_col].max() - df[lon_col].min() or 1
            overlap_threshold = min(lat_span, lon_span) * 0.06
            auto_label_positions = resolve_label_positions(marker_rows, overlap_threshold)
            label_positions = {}
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
                )
                label_sizes[idx] = (icon_w, icon_h)

                if f"label_lat_{idx}" not in st.session_state:
                    init_lat, init_lon = initial_label_latlon(
                        marker, auto_label_positions[idx], lat_span, lon_span
                    )
                    st.session_state[f"label_lat_{idx}"] = init_lat
                    st.session_state[f"label_lon_{idx}"] = init_lon

            if labels_enabled(show_name, show_values, show_total):
                if not st.session_state.get("labels_overlap_resolved"):
                    draft_positions = {
                        idx: (
                            st.session_state[f"label_lat_{idx}"],
                            st.session_state[f"label_lon_{idx}"],
                        )
                        for idx in label_sizes
                        if label_sizes[idx] != (0, 0)
                    }
                    resolved = resolve_label_overlaps(
                        marker_rows, draft_positions, label_sizes, lat_span, lon_span
                    )
                    for idx, (lat, lon) in resolved.items():
                        st.session_state[f"label_lat_{idx}"] = lat
                        st.session_state[f"label_lon_{idx}"] = lon
                    st.session_state["labels_overlap_resolved"] = True

            for marker in marker_rows:
                idx = marker["idx"]
                label_positions[idx] = (
                    st.session_state[f"label_lat_{idx}"],
                    st.session_state[f"label_lon_{idx}"],
                )

            st.subheader("Data preview")
            preview_df = pd.DataFrame(
                {
                    name_col: df[name_col],
                    "total": df[value_cols].apply(pd.to_numeric, errors="coerce").sum(axis=1),
                }
            )
            st.dataframe(preview_df, use_container_width=True)

            st.subheader("Map")
            m = folium.Map(
                location=[df[lat_col].mean(), df[lon_col].mean()],
                tiles="OpenStreetMap",
            )
            m.fit_bounds(fit_bounds_for_points(df, lat_col, lon_col))
            populate_map_layers(
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
            )

            map_state = st_folium(
                m,
                width=EXPORT_CAPTURE_WIDTH,
                height=EXPORT_CAPTURE_HEIGHT,
                key="label_map",
                returned_objects=[
                    "last_object_clicked",
                    "last_object_clicked_tooltip",
                    "bounds",
                    "zoom",
                ],
            )
            sync_dragged_labels(map_state)
            for marker in marker_rows:
                idx = marker["idx"]
                label_positions[idx] = (
                    st.session_state[f"label_lat_{idx}"],
                    st.session_state[f"label_lon_{idx}"],
                )

            st.caption(
                "Drag labels to reposition. Lines connect each chart to the nearest label edge and update while you move."
            )

            st.divider()
            if not jpeg_export_supported():
                st.caption(
                    "JPEG download is available in the desktop app. "
                    "On Streamlit Cloud, use the interactive map above."
                )
            elif map_export_ready(map_state):
                export_signature = export_state_signature(
                    upload_key,
                    map_state,
                    label_positions,
                    marker_type,
                    chart_colors,
                    st.session_state.scale_by_total,
                    st.session_state.show_lbl_name,
                    st.session_state.show_lbl_values,
                    st.session_state.show_lbl_total,
                )
                try:
                    jpeg_data = build_map_jpeg_export(
                        export_signature,
                        df,
                        lat_col,
                        lon_col,
                        marker_rows,
                        label_positions,
                        map_state,
                        min_total,
                        max_total,
                        marker_type,
                        chart_colors,
                        st.session_state.scale_by_total,
                        st.session_state.show_lbl_name,
                        st.session_state.show_lbl_values,
                        st.session_state.show_lbl_total,
                    )
                except Exception as e:
                    st.error(f"Map export failed: {e}")
                else:
                    st.download_button(
                        label="Download map (JPEG)",
                        data=jpeg_data,
                        file_name="label_map.jpg",
                        mime="image/jpeg",
                        type="primary",
                        key="download_map_jpeg",
                    )
                    st.caption(
                        "Adjust the map first, then click download. Your browser will ask where to save the file."
                    )
            else:
                st.caption("Preparing map export…")
    except Exception as e:
        st.error(f"Could not process file: {str(e)}")
else:
    st.info("Upload a spreadsheet (.xlsx, .xls, or .csv) to build your map.")

render_footer()
