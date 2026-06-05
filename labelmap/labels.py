"""Label content, sizing, and auto-placement near map markers."""

import math

from labelmap.config import (
    LABEL_POSITION_ORDER,
    LABEL_STYLE,
    MAP_VIEW_HEIGHT,
    MAP_VIEW_WIDTH,
)
from labelmap.geo import latlon_distance


def format_value(value):
    numeric = float(value)
    return str(int(numeric)) if numeric.is_integer() else str(round(numeric, 1))


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


def build_label_html(name, labels, values, total, show_name, show_values, show_total):
    _, html, _, _ = build_label_content(
        name, labels, values, total, show_name, show_values, show_total
    )
    return html


def scaled_label_latlon(marker, position_key, lat_span, lon_span, scale=1.0):
    dlat = max(lat_span * 0.06, 0.05) * scale
    dlon = max(lon_span * 0.06, 0.05) * scale
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


def initial_label_latlon(marker, position_key, lat_span, lon_span):
    return scaled_label_latlon(marker, position_key, lat_span, lon_span, scale=1.0)


def estimate_label_deg(icon_w, icon_h, lat_span, lon_span):
    deg_lon = lon_span * (icon_w / MAP_VIEW_WIDTH)
    deg_lat = lat_span * (icon_h / MAP_VIEW_HEIGHT)
    return max(deg_lat, lat_span * 0.015), max(deg_lon, lon_span * 0.015)


def label_box_bounds(lat, lon, icon_w, icon_h, lat_span, lon_span, padding=0.12):
    """Axis-aligned bounds for a DivIcon label anchored at its top-left (lat, lon)."""
    box_lat, box_lon = estimate_label_deg(icon_w, icon_h, lat_span, lon_span)
    pad_lat = box_lat * padding
    pad_lon = box_lon * padding
    return {
        "north": lat + pad_lat,
        "south": lat - box_lat - pad_lat,
        "west": lon - pad_lon,
        "east": lon + box_lon + pad_lon,
    }


def label_boxes_overlap(bounds_a, bounds_b):
    return not (
        bounds_a["south"] >= bounds_b["north"]
        or bounds_a["north"] <= bounds_b["south"]
        or bounds_a["east"] <= bounds_b["west"]
        or bounds_a["west"] >= bounds_b["east"]
    )


def marker_neighbor_count(marker, marker_rows, threshold):
    count = 0
    for other in marker_rows:
        if other["idx"] == marker["idx"]:
            continue
        if latlon_distance(marker["lat"], marker["lon"], other["lat"], other["lon"]) < threshold:
            count += 1
    return count


def generate_label_placement_candidates(marker, lat_span, lon_span):
    """Candidates ordered by distance from the chart point (nearest first)."""
    candidates = []
    seen = set()

    def add_candidate(lat, lon):
        key = (round(lat, 6), round(lon, 6))
        if key in seen:
            return
        seen.add(key)
        dist = math.hypot(lat - marker["lat"], lon - marker["lon"])
        candidates.append((dist, lat, lon))

    for scale in (1.0, 1.15, 1.3, 1.5, 1.75, 2.0, 2.5, 3.0, 3.75, 4.5):
        for position_key in LABEL_POSITION_ORDER:
            lat, lon = scaled_label_latlon(
                marker, position_key, lat_span, lon_span, scale
            )
            add_candidate(lat, lon)

    candidates.sort(key=lambda item: item[0])
    return candidates


def place_labels_near_markers(marker_rows, label_sizes, lat_span, lon_span):
    """Place each label as close as possible to its point while avoiding overlap."""
    if not marker_rows:
        return {}

    overlap_threshold = min(lat_span, lon_span) * 0.06
    markers_with_labels = [
        marker
        for marker in marker_rows
        if label_sizes.get(marker["idx"], (0, 0)) != (0, 0)
    ]
    placement_order = sorted(
        markers_with_labels,
        key=lambda marker: -marker_neighbor_count(marker, marker_rows, overlap_threshold),
    )

    placed_bounds = []
    result = {}
    for marker in placement_order:
        idx = marker["idx"]
        icon_w, icon_h = label_sizes[idx]
        chosen = None
        for _, lat, lon in generate_label_placement_candidates(
            marker, lat_span, lon_span
        ):
            bounds = label_box_bounds(lat, lon, icon_w, icon_h, lat_span, lon_span)
            if any(label_boxes_overlap(bounds, prev) for prev in placed_bounds):
                continue
            chosen = (lat, lon)
            placed_bounds.append(bounds)
            break

        if chosen is None:
            candidates = generate_label_placement_candidates(
                marker, lat_span, lon_span
            )
            chosen = (candidates[-1][1], candidates[-1][2]) if candidates else (
                scaled_label_latlon(marker, "right", lat_span, lon_span)
            )
            placed_bounds.append(
                label_box_bounds(chosen[0], chosen[1], icon_w, icon_h, lat_span, lon_span)
            )
        result[idx] = chosen

    return result
