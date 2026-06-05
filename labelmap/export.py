"""High-quality map image export (Playwright with Pillow fallback)."""

import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from functools import lru_cache
from io import BytesIO

import folium
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

from labelmap.charts import draw_chart_on_image, marker_radius
from labelmap.config import (
    CHART_ICON_SIZE,
    EXPORT_CAPTURE_HEIGHT,
    EXPORT_CAPTURE_WIDTH,
    EXPORT_DEVICE_SCALE,
    EXPORT_HEIGHT,
    EXPORT_WIDTH,
)
from labelmap.folium_elements import ExportMapStyles, ExportReady
from labelmap.geo import (
    best_zoom,
    connector_points_px,
    deg_lonlat_to_global_pixels,
    fit_bounds_for_points,
    global_pixels_to_tile,
)
from labelmap.labels import build_label_content
from labelmap.map_builder import populate_map_layers
from labelmap.map_session import apply_map_view, parse_map_view
from labelmap.paths import playwright_browsers_path, template_file_path


def ensure_playwright_browser():
    browsers_path = playwright_browsers_path()
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", browsers_path)
    if os.path.isdir(browsers_path) and os.listdir(browsers_path):
        return
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=True,
        env={**os.environ, "PLAYWRIGHT_BROWSERS_PATH": browsers_path},
    )


def capture_map_screenshot(
    m,
    width=EXPORT_CAPTURE_WIDTH,
    height=EXPORT_CAPTURE_HEIGHT,
    export_bounds=None,
    export_zoom=None,
):
    from playwright.sync_api import sync_playwright

    browsers_path = playwright_browsers_path()
    ensure_playwright_browser()
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", browsers_path)
    ExportMapStyles(width, height).add_to(m)
    ExportReady(m.get_name(), export_bounds, export_zoom).add_to(m)

    html_path = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".html", delete=False, mode="w", encoding="utf-8"
        ) as tmp:
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


def make_placeholder_tile(message="Background map unavailable"):
    tile = Image.new("RGB", (256, 256), "#eef2f7")
    draw = ImageDraw.Draw(tile)
    font = ImageFont.load_default()
    draw.rectangle([(0, 0), (255, 255)], outline="#cbd5e1", width=2)
    draw.text((16, 112), message, fill="#64748b", font=font)
    return tile


@lru_cache(maxsize=1024)
def fetch_tile(z, x, y):
    max_tile = 2**z - 1
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
