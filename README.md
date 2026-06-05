# LabelMap

Turn location spreadsheets into interactive maps with pie or column chart markers, auto-placed labels, and drag-to-adjust positioning.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.33+-FF4B4B.svg)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Features

- Upload `.xlsx`, `.xls`, or `.csv` spreadsheets with location names and coordinates
- Pie or vertical bar chart markers sized by total value
- Automatic label placement with overlap avoidance
- Draggable labels that persist across map interactions
- Sample template (`data/map.xlsx`) for quick demos
- Deploy-ready for [Streamlit Community Cloud](https://share.streamlit.io)

## Quick start

### Prerequisites

- Python 3.11 or newer
- Internet access (OpenStreetMap tiles)

### Run locally

```bash
git clone https://github.com/pyaek/label-map.git
cd label-map
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run label_map.py
```

Open `http://localhost:8501` in your browser.

### Spreadsheet format

| Column | Content | Example |
|--------|---------|---------|
| A | Location name | `Site A` |
| B | Latitude | `16.80` |
| C | Longitude | `96.15` |
| D+ | Numeric values (one or more) | `12`, `5` |

Column mapping is configurable in the app. Value columns default to column D onward.

Download the bundled template from the app UI or use [`data/map.xlsx`](data/map.xlsx).

## Deploy on Streamlit Community Cloud

1. Push this repository to GitHub.
2. Sign in at [share.streamlit.io](https://share.streamlit.io).
3. Create a new app and connect your repo.
4. Set **Main file path** to `label_map.py`.
5. Set **Python version** to `3.11`.

No secrets are required. Map tiles are fetched from OpenStreetMap at runtime.

## Project structure

```
label-map/
├── label_map.py          # Streamlit entry point (do not rename for Cloud deploy)
├── labelmap/             # Application package
│   ├── charts.py         # Pie/column marker rendering
│   ├── config.py         # Constants and copy
│   ├── data_io.py        # Spreadsheet loading
│   ├── export.py         # Map image export
│   ├── folium_elements.py
│   ├── geo.py            # Bounds, zoom, coordinates
│   ├── labels.py         # Label placement and content
│   ├── map_builder.py    # Folium map assembly
│   ├── map_session.py    # Session state for drags/view
│   ├── paths.py          # Asset paths
│   └── ui.py             # Streamlit UI components
├── data/
│   └── map.xlsx          # Sample spreadsheet
├── .streamlit/
│   └── config.toml
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Optional: high-quality export

For Playwright-based map export (used as a fallback path in `labelmap/export.py`):

```bash
pip install -e ".[export]"
playwright install chromium
```

## Development

```bash
pip install -e ".[dev]"
ruff check labelmap label_map.py
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## License

MIT — see [LICENSE](LICENSE).

## Contact

**Pyae Phyo Kyaw** — [pyaek@icloud.com](mailto:pyaek@icloud.com) · [LinkedIn](https://www.linkedin.com/in/pyaek)
