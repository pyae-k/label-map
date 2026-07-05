"""Application constants and user-facing copy."""

import math

APP_FONT_STACK = (
    "'Inter', -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'SF Pro Display', "
    "'Helvetica Neue', Arial, sans-serif"
)
APP_TEXT_COLOR = "#F5F5F7"
APP_MUTED_COLOR = "rgba(245,245,247,0.72)"
APP_ACCENT_COLOR = "#0A84FF"
APP_SURFACE_COLOR = "rgba(28,28,30,0.96)"
APP_SURFACE_BORDER = "rgba(255,255,255,0.12)"
APP_TEXT_SIZE = "10pt"
APP_TEXT_SIZE_LG = "10pt"

DEFAULT_CHART_COLORS = ["#FF4245", "#FF9230", "#00DAC3", "#d62728", "#9467bd", "#8c564b"]
MIN_MARKER_RADIUS = 10
MAX_MARKER_RADIUS = 36
CHART_ICON_SIZE = 72
EXPORT_WIDTH = 2400
EXPORT_HEIGHT = 1400
CONNECTOR_COLOR_DARK = "rgba(255,255,255,0.44)"
CONNECTOR_COLOR_LIGHT = "#64748B"
CONNECTOR_OPACITY = 0.68
MAP_VIEW_HEIGHT = 900
MAP_VIEW_WIDTH = 1200
INTERACTIVE_MAP_WIDTH = 1100
INTERACTIVE_MAP_HEIGHT = MAP_VIEW_HEIGHT
INTERACTIVE_MAP_HEIGHT_BOOTSTRAP = 680
INTERACTIVE_MAP_HEIGHT_CSS = "33vh"
LEAFLET_TILE_SIZE = 256


def world_fit_zoom(width, height=None, tile_size=LEAFLET_TILE_SIZE, *, width_only=False):
    """Most zoomed-out level where the world fills the viewport (no side gutters at width_only)."""
    if width_only or height is None:
        return max(0.0, math.log2(width / tile_size))
    fit_x = math.log2(width / tile_size)
    fit_y = math.log2(height / tile_size)
    return max(0.0, min(fit_x, fit_y))


INTERACTIVE_ZOOM_STEP = 0.12
INTERACTIVE_ZOOM_MAX_STEP = 0.75
INTERACTIVE_ZOOM_HOLD_DELAY_MS = 400
INTERACTIVE_ZOOM_REPEAT_MS = 100
# Floor zoom; SingleWorldMap sets the real width-fit minimum per container.
INTERACTIVE_MIN_ZOOM = 0
INTERACTIVE_DEFAULT_ZOOM_OFFSET = 0.0
FULLSCREEN_ZOOM_IN_CLICKS = 4
FULLSCREEN_ZOOM_DELTA = INTERACTIVE_ZOOM_STEP * FULLSCREEN_ZOOM_IN_CLICKS


def default_interactive_zoom(min_zoom=INTERACTIVE_MIN_ZOOM):
    """Default zoom: let the client fit the world to the live map width."""
    return min_zoom
EXPORT_CAPTURE_WIDTH = 1400
EXPORT_CAPTURE_HEIGHT = 650
LABEL_SAVE_MESSAGE = "Saving…"
MAP_LOADING_MESSAGE = "Loading map…"
EXPORT_DEVICE_SCALE = 2

HERO_TAGLINE = "Upload CSV → labeled map in seconds"
PRIVACY_NOTICE = "Uploads are processed on Streamlit Cloud to build your map in this session."
PRIVACY_POLICY_URL = "https://streamlit.io/privacy-policy"
CONTACT_NAME = "Pyae Phyo Kyaw"
CONTACT_EMAIL = "pyaek@icloud.com"
CONTACT_LINKEDIN = "https://www.linkedin.com/in/pyaek/"
ABOUT_TEXT = (
    "LabelMap turns location CSV files into interactive maps with pie or column "
    "charts and draggable labels."
)
HOW_IT_WORKS_STEPS = (
    "Upload your CSV",
    "View and adjust the map",
)

LABEL_POSITION_ORDER = [
    "below",
    "below-right",
    "below-left",
    "right",
    "left",
    "above",
    "above-right",
    "above-left",
]

MAP_STYLE_OPTIONS = {
    "Voyager": "CartoDB voyager",
    "Dark": "CartoDB dark_matter",
    "Light": "CartoDB positron",
    "Street": "OpenStreetMap",
    "Terrain": "Stadia.StamenTerrain",
    "Topo": "OpenTopoMap",
}

MAP_STYLE_DARK_THEMES = {"Dark"}

MAP_TILE_URL_TEMPLATES = {
    "CartoDB dark_matter": "https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
    "CartoDB positron": "https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
    "CartoDB voyager": "https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
    "OpenStreetMap": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "Stadia.StamenTerrain": "https://tiles.stadiamaps.com/tiles/stamen_terrain/{z}/{x}/{y}.png",
    "OpenTopoMap": "https://tile.opentopomap.org/{z}/{x}/{y}.png",
}

DEFAULT_MAP_STYLE = "Voyager"

def map_style_is_dark(map_style):
    style = map_style or DEFAULT_MAP_STYLE
    return style in MAP_STYLE_DARK_THEMES


def connector_style_for_map_style(map_style):
    if map_style_is_dark(map_style):
        return {"color": CONNECTOR_COLOR_DARK, "opacity": CONNECTOR_OPACITY}
    return {"color": CONNECTOR_COLOR_LIGHT, "opacity": CONNECTOR_OPACITY}


def connector_rgba_for_map_style(map_style):
    style = connector_style_for_map_style(map_style)
    color = style["color"]
    alpha = int(style["opacity"] * 255)
    if color.startswith("#") and len(color) == 7:
        return (
            int(color[1:3], 16),
            int(color[3:5], 16),
            int(color[5:7], 16),
            alpha,
        )
    # rgba(r,g,b,a) from CONNECTOR_COLOR_DARK
    inner = color.removeprefix("rgba(").removesuffix(")")
    r, g, b, a = (float(part.strip()) for part in inner.split(","))
    effective_alpha = int(a * style["opacity"] * 255)
    return (int(r), int(g), int(b), effective_alpha)


def label_theme_for_map_style(map_style):
    if map_style_is_dark(map_style):
        return {
            "text_color": APP_TEXT_COLOR,
            "muted_color": APP_MUTED_COLOR,
            "panel_bg": "rgba(28,28,30,0.32)",
            "panel_shadow": "0 8px 20px rgba(0,0,0,0.32)",
            "swatch_border": "rgba(255,255,255,0.45)",
        }
    return {
        "text_color": "#111827",
        "muted_color": "rgba(17,24,39,0.75)",
        "panel_bg": "rgba(255,255,255,0.78)",
        "panel_shadow": "0 8px 20px rgba(15,23,42,0.18)",
        "swatch_border": "rgba(15,23,42,0.28)",
    }


def build_label_style(map_style):
    theme = label_theme_for_map_style(map_style)
    return (
        "display:inline-block;"
        "width:max-content;"
        "min-width:100%;"
        f'background-color:{theme["panel_bg"]};'
        "border-radius:8px;"
        "padding:7px 11px;"
        "text-align:left;"
        "line-height:1.3;"
        "white-space:nowrap;"
        "cursor:grab;"
        "box-sizing:border-box;"
        "border:0;"
        f'box-shadow:{theme["panel_shadow"]};'
        f"font-family:{APP_FONT_STACK};"
        f'color:{theme["text_color"]};'
        "font-weight:400;"
    )


def build_legend_style(map_style):
    theme = label_theme_for_map_style(map_style)
    return (
        f'background-color:{theme["panel_bg"]};'
        "border-radius:8px;"
        "padding:7px 11px;"
        f'box-shadow:{theme["panel_shadow"]};'
        f"font-family:{APP_FONT_STACK};"
        f'color:{theme["text_color"]};'
        "font-size:8pt;"
        "line-height:1.5;"
    )


LABEL_STYLE = build_label_style(DEFAULT_MAP_STYLE)
LEGEND_STYLE = build_legend_style(DEFAULT_MAP_STYLE)
