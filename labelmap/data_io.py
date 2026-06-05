"""Spreadsheet loading and column-mapping helpers."""

import os

import pandas as pd
import streamlit as st

from labelmap.paths import template_file_path


@st.cache_data(show_spinner=False)
def load_sample_dataframe():
    sample_path = template_file_path()
    if not sample_path:
        return None
    return pd.read_excel(sample_path)


def user_uploaded_spreadsheet(uploaded_file):
    if uploaded_file is None:
        return False
    size = getattr(uploaded_file, "size", None)
    if size is not None:
        return size > 0
    return True


def resolve_spreadsheet_source(uploaded_file):
    """Use uploaded file when present; otherwise load bundled map.xlsx as the example."""
    if user_uploaded_spreadsheet(uploaded_file):
        return uploaded_file, uploaded_file.name, False
    sample_path = template_file_path()
    if sample_path:
        return sample_path, os.path.basename(sample_path), True
    return None, None, False


def read_spreadsheet(source):
    if isinstance(source, str):
        if source.lower().endswith(".csv"):
            return pd.read_csv(source)
        return pd.read_excel(source)
    if source.name.lower().endswith(".csv"):
        return pd.read_csv(source)
    return pd.read_excel(source)


def spreadsheet_upload_key(source, df):
    if isinstance(source, str):
        mtime = int(os.path.getmtime(source))
        return f"default:{os.path.basename(source)}:{mtime}:{len(df)}"
    size = getattr(source, "size", "")
    return f"{source.name}:{size}:{len(df)}"


def pick_default(candidates, columns):
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return columns[0] if columns else None


def column_default(columns, index, fallback_candidates=None):
    if index < len(columns):
        return columns[index]
    return pick_default(fallback_candidates or [], columns)


def get_nonzero_values(row, value_cols):
    values = []
    labels = []
    for label in value_cols:
        value = row[label]
        if pd.notnull(value) and value != 0:
            try:
                value = float(value)
            except Exception:
                continue
            values.append(value)
            labels.append(label)
    return values, labels
