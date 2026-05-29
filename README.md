# LabelMap

Turn location spreadsheets into interactive maps with pie or column charts and draggable labels.

Deploy this folder to [Streamlit Community Cloud](https://share.streamlit.io).

## Quick deploy

1. Create a **GitHub repository** (public or private).
2. Upload **all files in this folder** as the **repo root**.
3. Go to [share.streamlit.io](https://share.streamlit.io) → **Create app**.
4. Select your repo and set **Main file path** to:

   ```
   label_map.py
   ```

5. Click **Deploy**.

## Repo files (upload all of these)

| File | Purpose |
|------|---------|
| `label_map.py` | Main app |
| `map.xlsx` | Sample template (auto-loads on start) |
| `requirements.txt` | Python dependencies |
| `.streamlit/config.toml` | App settings |
| `.gitignore` | Excludes secrets and caches |
| `README.md` | This file |

## Features on Streamlit Cloud

- Upload CSV or Excel spreadsheets
- Column mapping (location, latitude, longitude, values)
- Pie and column chart markers
- Draggable labels with connector lines
- Sample `map.xlsx` loads automatically

## JPEG export

Not available on Streamlit Cloud. The interactive map works fully; use a desktop build for JPEG download.

## Privacy

Uploads are processed on Streamlit Cloud to build your map in this session. See [Streamlit's privacy policy](https://streamlit.io/privacy-policy).

## Local run (optional)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run label_map.py
```

## Contact

Pyae Phyo Kyaw — [pyaek@icloud.com](mailto:pyaek@icloud.com) · [LinkedIn](https://www.linkedin.com/in/pyaek)
