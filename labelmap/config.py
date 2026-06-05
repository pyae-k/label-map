"""Application constants and user-facing copy."""

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
INTERACTIVE_MAP_WIDTH = MAP_VIEW_WIDTH
INTERACTIVE_MAP_HEIGHT = MAP_VIEW_HEIGHT
EXPORT_CAPTURE_WIDTH = 1400
EXPORT_CAPTURE_HEIGHT = 650
LABEL_SAVE_MESSAGE = "Saving…"
EXPORT_DEVICE_SCALE = 2

HERO_TAGLINE = "Upload spreadsheet → labeled map in seconds"
PRIVACY_NOTICE = "Uploads are processed on Streamlit Cloud to build your map in this session."
PRIVACY_POLICY_URL = "https://streamlit.io/privacy-policy"
CONTACT_NAME = "Pyae Phyo Kyaw"
CONTACT_EMAIL = "pyaek@icloud.com"
CONTACT_LINKEDIN = "https://www.linkedin.com/in/pyaek"
ABOUT_TEXT = (
    "LabelMap turns location spreadsheets into interactive maps with pie or column "
    "charts and draggable labels."
)
HOW_IT_WORKS_STEPS = (
    "Upload your spreadsheet",
    "View and adjust the map",
)

LABEL_POSITION_ORDER = [
    "right",
    "left",
    "below",
    "above",
    "below-right",
    "below-left",
    "above-right",
    "above-left",
]
