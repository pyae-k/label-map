"""Chart rendering for map markers (SVG and raster)."""

import math

from labelmap.config import (
    CHART_ICON_SIZE,
    DEFAULT_CHART_COLORS,
    MAX_MARKER_RADIUS,
    MIN_MARKER_RADIUS,
)


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


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


def chart_type_label(marker_type):
    if marker_type == "pie":
        return "Pie chart"
    return "Vertical bar"


def normalize_marker_type(marker_type):
    return "column" if marker_type == "bar" else marker_type


def expand_chart_colors(chart_colors, count):
    palette = chart_colors or DEFAULT_CHART_COLORS
    if count <= 0:
        return []
    repeats = (count // len(palette)) + 1
    return (palette * repeats)[:count]


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
