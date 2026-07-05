"""Label content, sizing, and auto-placement near map markers."""

import math
from html import escape

from labelmap.config import (
    APP_MUTED_COLOR,
    APP_TEXT_COLOR,
    DEFAULT_MAP_STYLE,
    LABEL_POSITION_ORDER,
    MAP_VIEW_HEIGHT,
    MAP_VIEW_WIDTH,
    build_label_style,
    label_theme_for_map_style,
)
from labelmap.geo import latlon_distance

LABEL_PANEL_FONT_STACK = "'Inter', 'Geometric Sans', sans-serif"
LABEL_PANEL_TEXT_SIZE = "8pt"
LABEL_BASE_STYLE = (
    f"font-family:{LABEL_PANEL_FONT_STACK};"
    f"font-size:{LABEL_PANEL_TEXT_SIZE};"
    "line-height:1.15;"
)
COMPARE_POSITIVE_COLOR = "#4DA3FF"
COMPARE_NEGATIVE_COLOR = "#FF6B6B"


def format_value(value):
    numeric = float(value)
    return f"{int(numeric):,}" if numeric.is_integer() else f"{numeric:,.1f}"


def format_value_label(label):
    return str(label).replace("_", " ").strip()


def format_compares(values, neutral_color=APP_TEXT_COLOR):
    if values is None or len(values) < 2:
        return []
    try:
        baseline = float(values[0])
    except (TypeError, ValueError):
        return []
    if baseline == 0:
        return []

    comparisons = []
    for compared_raw in values[1:]:
        try:
            compared = float(compared_raw)
        except (TypeError, ValueError):
            continue
        pct_change = ((compared - baseline) / abs(baseline)) * 100
        text = f"{pct_change:+,.1f}%"
        color = (
            COMPARE_POSITIVE_COLOR
            if pct_change > 0
            else COMPARE_NEGATIVE_COLOR if pct_change < 0 else neutral_color
        )
        comparisons.append((text, color))
    return comparisons


def build_marker_tooltip_html(
    name,
    labels,
    values,
    total,
    show_name,
    show_values,
    show_total,
    marker_type=None,
    force_compare_total=False,
):
    if values is None:
        values = []
    if labels is None:
        labels = []

    tooltip_rows = []
    if show_name:
        location = str(name).strip()
        if location:
            tooltip_rows.append(
                f'<div style="{LABEL_BASE_STYLE}"><strong>Location:</strong> '
                f"{escape(location)}</div>"
            )

    compare_rows = []
    include_compare_total = show_total or force_compare_total
    if include_compare_total and marker_type in {"bar", "column"}:
        compare_rows = format_compares(values)

    if show_values:
        for idx, value in enumerate(values):
            label = format_value_label(labels[idx]) if idx < len(labels) else f"Value {idx + 1}"
            row_text = f"{label}: {format_value(value)}"
            tooltip_rows.append(f'<div style="{LABEL_BASE_STYLE}">{escape(row_text)}</div>')

    if include_compare_total:
        if compare_rows:
            baseline_label = (
                format_value_label(labels[0]) if labels else "baseline"
            )
            for idx, (compare_text, _) in enumerate(compare_rows, start=1):
                against_label = (
                    format_value_label(labels[idx]) if idx < len(labels) else f"Value {idx + 1}"
                )
                compare_line = f"Compare ({against_label} vs {baseline_label}): {compare_text}"
                tooltip_rows.append(f'<div style="{LABEL_BASE_STYLE}">{escape(compare_line)}</div>')
        elif total is not None:
            tooltip_rows.append(
                f'<div style="{LABEL_BASE_STYLE}"><strong>Total:</strong> '
                f"{escape(format_value(total))}</div>"
            )

    if not tooltip_rows:
        fallback = str(name).strip() or "Point"
        tooltip_rows.append(f'<div style="{LABEL_BASE_STYLE}">{escape(fallback)}</div>')

    return "".join(tooltip_rows)


def labels_enabled(show_name, show_values, show_total):
    return show_name or show_values or show_total


def build_label_content(
    name,
    labels,
    values,
    total,
    show_name,
    show_values,
    show_total,
    value_colors=None,
    marker_type=None,
    text_color=APP_TEXT_COLOR,
    muted_color=APP_MUTED_COLOR,
    swatch_border_color="rgba(255,255,255,0.45)",
):
    text_lines = []
    html_parts = []
    compare_rows = []
    use_compare_rows = (
        show_total and marker_type in {"bar", "column"} and values is not None and total is not None
    )
    if use_compare_rows:
        compare_rows = format_compares(values, neutral_color=text_color)

    if show_name:
        name_str = str(name).strip()
        if name_str:
            text_lines.append(name_str)
            html_parts.append(
                f'<div style="{LABEL_BASE_STYLE}font-weight:700;'
                f'color:{text_color};">{name_str}</div>'
            )

    if show_values:
        for idx, value in enumerate(values):
            if value is None:
                continue
            color = (
                value_colors[idx]
                if value_colors is not None and idx < len(value_colors)
                else muted_color
            )
            base_text = format_value(value)
            compare_text = None
            compare_color = text_color
            if use_compare_rows and compare_rows and idx > 0 and (idx - 1) < len(compare_rows):
                compare_text, compare_color = compare_rows[idx - 1]
            row_text = f"{base_text} ({compare_text})" if compare_text else base_text
            text_lines.append(row_text)
            value_row_style = (
                f"{LABEL_BASE_STYLE}font-weight:400;color:{text_color};"
                "display:flex;align-items:center;gap:0;"
            )
            compare_html = (
                f'<span style="color:{compare_color};">&nbsp;({compare_text})</span>'
                if compare_text
                else ""
            )
            html_parts.append(
                f'<div style="{value_row_style}">'
                f'<span style="display:inline-block;width:9px;height:9px;border-radius:2px;'
                f"background:{color};border:1px solid {swatch_border_color};"
                'box-sizing:border-box;flex:0 0 auto;"></span>'
                f"<span>&nbsp;{base_text}</span>"
                f"{compare_html}</div>"
            )

    if show_total and values is not None and total is not None:
        if marker_type in {"bar", "column"}:
            if compare_rows:
                if not show_values:
                    for text, color in compare_rows:
                        text_lines.append(text)
                        html_parts.append(
                            (
                                f'<div style="{LABEL_BASE_STYLE}font-weight:700;'
                                f'color:{color};">{text}</div>'
                            )
                        )
            else:
                text = format_value(total)
                text_lines.append(text)
                html_parts.append(
                    (
                        f'<div style="{LABEL_BASE_STYLE}font-weight:700;'
                        f'color:{text_color};">{text}</div>'
                    )
                )
        else:
            text = format_value(total)
            text_lines.append(text)
            html_parts.append(
                (
                    f'<div style="{LABEL_BASE_STYLE}font-weight:700;'
                    f'color:{text_color};">{text}</div>'
                )
            )

    if not text_lines:
        return [], "", 0, 0

    # Ensure HTML is generated even if specific parts were skipped or empty
    if not html_parts and text_lines:
        for line in text_lines:
            html_parts.append(
                f'<div style="{LABEL_BASE_STYLE}font-weight:400;color:{muted_color};">'
                f"{line}</div>"
            )

    max_chars = max(len(line) for line in text_lines)
    icon_w = min(240, max(72, int(max_chars * 6.2) + 24))
    icon_h = 16 + len(text_lines) * 17
    return text_lines, "".join(html_parts), icon_w, icon_h


def make_label_icon_html(
    name,
    labels,
    values,
    total,
    show_name,
    show_values,
    show_total,
    value_colors=None,
    marker_type=None,
    map_style=DEFAULT_MAP_STYLE,
):
    theme = label_theme_for_map_style(map_style)
    _, labels_html, icon_w, icon_h = build_label_content(
        name,
        labels,
        values,
        total,
        show_name,
        show_values,
        show_total,
        value_colors=value_colors,
        marker_type=marker_type,
        text_color=theme["text_color"],
        muted_color=theme["muted_color"],
        swatch_border_color=theme["swatch_border"],
    )
    if not labels_html:
        return "", 0, 0
    html = f'<div style="{build_label_style(map_style)}">{labels_html}</div>'
    return html, icon_w, icon_h


def build_label_html(
    name,
    labels,
    values,
    total,
    show_name,
    show_values,
    show_total,
    value_colors=None,
    marker_type=None,
    map_style=DEFAULT_MAP_STYLE,
):
    theme = label_theme_for_map_style(map_style)
    _, html, _, _ = build_label_content(
        name,
        labels,
        values,
        total,
        show_name,
        show_values,
        show_total,
        value_colors=value_colors,
        marker_type=marker_type,
        text_color=theme["text_color"],
        muted_color=theme["muted_color"],
        swatch_border_color=theme["swatch_border"],
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


def market_code_from_label(name):
    head = str(name).split("•", 1)[0].strip()
    if "," in head:
        head = head.split(",")[-1].strip()
    return head


def generate_label_placement_candidates(
    marker, lat_span, lon_span, preferred_position=None, preferred_scales=None
):
    """Candidates ordered nearest-first; preset direction is tried before alternatives."""
    scales = (1.0, 1.15, 1.3, 1.5, 1.75, 2.0, 2.5, 3.0, 3.75, 4.5)
    candidates = []
    seen = set()

    def add_candidate(lat, lon):
        key = (round(lat, 6), round(lon, 6))
        if key in seen:
            return
        seen.add(key)
        dist = math.hypot(lat - marker["lat"], lon - marker["lon"])
        candidates.append((dist, lat, lon))

    if preferred_position:
        preset_scales = preferred_scales or scales
        for scale in preset_scales:
            lat, lon = scaled_label_latlon(
                marker, preferred_position, lat_span, lon_span, scale
            )
            add_candidate(lat, lon)
        other = []
        for scale in scales:
            for position_key in LABEL_POSITION_ORDER:
                if position_key == preferred_position:
                    continue
                lat, lon = scaled_label_latlon(
                    marker, position_key, lat_span, lon_span, scale
                )
                key = (round(lat, 6), round(lon, 6))
                if key in seen:
                    continue
                seen.add(key)
                dist = math.hypot(lat - marker["lat"], lon - marker["lon"])
                other.append((dist, lat, lon))
        other.sort(key=lambda item: item[0])
        candidates.extend(other)
        return candidates

    for scale in scales:
        for position_key in LABEL_POSITION_ORDER:
            lat, lon = scaled_label_latlon(
                marker, position_key, lat_span, lon_span, scale
            )
            add_candidate(lat, lon)

    candidates.sort(key=lambda item: item[0])
    return candidates


def place_labels_near_markers(
    marker_rows, label_sizes, lat_span, lon_span, market_presets=None
):
    """Place each label near its point, honoring market presets when overlap-free."""
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
        preferred = None
        preferred_scales = None
        if market_presets:
            preset = market_presets.get(market_code_from_label(marker.get("name", "")))
            if isinstance(preset, dict):
                abs_lat = preset.get("lat")
                abs_lon = preset.get("lon")
                if abs_lat is not None and abs_lon is not None:
                    chosen = (float(abs_lat), float(abs_lon))
                    placed_bounds.append(
                        label_box_bounds(
                            chosen[0], chosen[1], icon_w, icon_h, lat_span, lon_span
                        )
                    )
                    result[idx] = chosen
                    continue
                preferred = preset.get("position")
                raw_scales = preset.get("scales")
                if isinstance(raw_scales, (tuple, list)):
                    preferred_scales = tuple(raw_scales)
            elif isinstance(preset, str):
                preferred = preset
        if preferred:
            preferred_scales = preferred_scales or (1.8, 2.2, 1.4, 1.0, 2.6, 3.0, 3.75, 4.5)
        chosen = None
        for _, lat, lon in generate_label_placement_candidates(
            marker,
            lat_span,
            lon_span,
            preferred_position=preferred,
            preferred_scales=preferred_scales,
        ):
            bounds = label_box_bounds(lat, lon, icon_w, icon_h, lat_span, lon_span)
            if any(label_boxes_overlap(bounds, prev) for prev in placed_bounds):
                continue
            chosen = (lat, lon)
            placed_bounds.append(bounds)
            break

        if chosen is None:
            candidates = generate_label_placement_candidates(
                marker,
                lat_span,
                lon_span,
                preferred_position=preferred,
                preferred_scales=preferred_scales,
            )
            chosen = (candidates[0][1], candidates[0][2]) if candidates else (
                scaled_label_latlon(marker, "below", lat_span, lon_span)
            )
            placed_bounds.append(
                label_box_bounds(chosen[0], chosen[1], icon_w, icon_h, lat_span, lon_span)
            )
        result[idx] = chosen

    return result
