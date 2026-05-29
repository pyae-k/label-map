# LabelMap (Streamlit Cloud)

Interactive map from spreadsheets: pie/column markers, auto-placed labels, drag to adjust.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run label_map.py
```

## Deploy on Streamlit Community Cloud

1. Push this repo to GitHub.
2. Connect at [share.streamlit.io](https://share.streamlit.io).
3. **Main file path:** `label_map.py`
4. **Python:** 3.11

No secrets required. Map tiles need internet (OpenStreetMap).
