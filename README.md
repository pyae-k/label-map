# LabelMap

Turn location spreadsheets into interactive maps with pie or column charts and draggable labels.

**Live app:** deploy from this repo to [Streamlit Community Cloud](https://share.streamlit.io).

## Deploy to Streamlit Cloud

1. Create a **new GitHub repository**.
2. Upload **all files in this folder** as the repo root (not the parent `Code` folder).
3. Go to [share.streamlit.io](https://share.streamlit.io) → **Create app**.
4. Connect your GitHub repo.
5. Set **Main file path** to:

   ```
   label_map.py
   ```

6. Click **Deploy**.

Streamlit installs packages from `requirements.txt` automatically.

## Files in this repo

```
label_map.py              # Main app
map.xlsx                  # Sample data (loads on start)
requirements.txt          # Python dependencies
.streamlit/config.toml    # App settings
.gitignore
README.md
```

## Features

- Upload CSV or Excel spreadsheets
- Column mapping (location, latitude, longitude, values)
- Pie and column chart markers on the map
- Draggable labels with connector lines
- Sample `map.xlsx` loads automatically

## Privacy

Uploads are processed on **Streamlit Cloud** to build your map in this session. See [Streamlit's privacy policy](https://streamlit.io/privacy-policy).

## JPEG export on Streamlit Cloud

JPEG download uses Playwright + Chromium, which is **not included** in this cloud deployment. Map viewing, upload, and charts work on Streamlit Cloud; use a local/desktop build if you need JPEG export.

## Local run (optional)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install playwright
PLAYWRIGHT_BROWSERS_PATH=.playwright-browsers playwright install chromium
streamlit run label_map.py
```

## Contact

Pyae Phyo Kyaw — [pyaek@icloud.com](mailto:pyaek@icloud.com) · [LinkedIn](https://www.linkedin.com/in/pyaek)
