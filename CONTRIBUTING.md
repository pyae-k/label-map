# Contributing to LabelMap

Thank you for your interest in improving LabelMap.

## Getting started

1. Fork the repository on GitHub.
2. Clone your fork locally.
3. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   pip install -e ".[dev]"
   ```

4. Run the app to verify your environment:

   ```bash
   streamlit run label_map.py
   ```

## Code guidelines

- Keep `label_map.py` as the Streamlit entry point — Streamlit Cloud expects this filename.
- Place reusable logic in the `labelmap/` package, grouped by concern.
- Match existing naming and import style.
- Run `ruff check labelmap label_map.py` before opening a pull request.

## Pull requests

1. Create a feature branch from `main`.
2. Make focused changes with a clear commit message.
3. Update `CHANGELOG.md` for user-visible changes.
4. Open a pull request describing what changed and how you tested it.

## Reporting issues

Include:

- Steps to reproduce
- Expected vs. actual behavior
- Python version and OS
- Sample spreadsheet (if relevant), with sensitive data removed

## Questions

Contact [pyaek@icloud.com](mailto:pyaek@icloud.com) or open a GitHub issue.
