"""Geospatial math for map bounds, zoom, and coordinate transforms."""

import math

MERCATOR_MAX_LAT = 85.05112878


def latlon_distance(lat1, lon1, lat2, lon2):
    return math.hypot(lat2 - lat1, lon2 - lon1)


def _normalize_lon_lat(lon, lat):
    try:
        lon_value = float(lon)
        lat_value = float(lat)
    except (TypeError, ValueError) as exc:
        raise ValueError("Longitude and latitude must be numeric.") from exc

    if not (math.isfinite(lon_value) and math.isfinite(lat_value)):
        raise ValueError("Longitude and latitude must be finite numbers.")
    if not (-180.0 <= lon_value <= 180.0):
        raise ValueError(f"Longitude must be between -180 and 180, got {lon_value}")
    if not (-90.0 <= lat_value <= 90.0):
        raise ValueError(f"Latitude must be between -90 and 90, got {lat_value}")

    lat_value = max(-MERCATOR_MAX_LAT, min(MERCATOR_MAX_LAT, lat_value))
    return lon_value, lat_value


def normalize_lat_lon_for_projection(lon, lat):
    """Wrap longitude and clamp latitude so placement offsets can be projected."""
    lon_value = float(lon)
    lat_value = float(lat)
    if not (math.isfinite(lon_value) and math.isfinite(lat_value)):
        raise ValueError("Longitude and latitude must be finite numbers.")
    while lon_value > 180.0:
        lon_value -= 360.0
    while lon_value < -180.0:
        lon_value += 360.0
    lat_value = max(-MERCATOR_MAX_LAT, min(MERCATOR_MAX_LAT, lat_value))
    return lon_value, lat_value


def deg_lonlat_to_global_pixels(lon, lat, zoom):
    lon, lat = _normalize_lon_lat(lon, lat)
    lat_rad = math.radians(lat)
    n = 2.0**zoom
    x = (lon + 180.0) / 360.0 * 256.0 * n
    y = (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * 256.0 * n
    return x, y


def global_pixels_to_tile(px, py):
    return int(px // 256), int(py // 256)


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
        [
            max(-90.0, min_lat - lat_pad),
            max(-180.0, min_lon - lon_pad),
        ],
        [
            min(90.0, max_lat + lat_pad),
            min(180.0, max_lon + lon_pad),
        ],
    ]


def best_zoom(min_lon, max_lon, min_lat, max_lat, width, height):
    for z in range(10, 0, -1):
        x0, y0 = deg_lonlat_to_global_pixels(min_lon, max_lat, z)
        x1, y1 = deg_lonlat_to_global_pixels(max_lon, min_lat, z)
        if x1 - x0 <= width and y1 - y0 <= height:
            return z
    return 1


def normalize_zoom(zoom):
    if isinstance(zoom, (int, float)) and not isinstance(zoom, bool):
        value = float(zoom)
        if value >= 0:
            return round(value, 2)
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
