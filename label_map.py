"""LabelMap — Streamlit entry point.

Run locally:
    streamlit run label_map.py

Deploy on Streamlit Community Cloud with main file path: label_map.py
"""

import pandas as pd
import streamlit as st

from labelmap.charts import chart_type_label
from labelmap.config import DEFAULT_CHART_COLORS
from labelmap.data_io import (
    column_default,
    get_nonzero_values,
    load_sample_dataframe,
    read_spreadsheet,
    resolve_spreadsheet_source,
    spreadsheet_upload_key,
    user_uploaded_spreadsheet,
)
from labelmap.labels import (
    build_label_content,
    labels_enabled,
    place_labels_near_markers,
    scaled_label_latlon,
)
from labelmap.paths import template_file_path
from labelmap.ui import (
    render_app_intro,
    render_footer,
    render_label_map_fragment,
    render_privacy_notice,
    render_template_link,
)

st.set_page_config(
    page_title="LabelMap",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

render_app_intro()

uploaded_file = st.file_uploader(
    "Spreadsheet",
    type=["xlsx", "xls", "csv"],
    help="Column A: location, B: latitude, C: longitude, D onward: health value columns",
    key="user_spreadsheet",
)
render_template_link()
render_privacy_notice()

st.divider()

data_source, data_label, using_sample = resolve_spreadsheet_source(uploaded_file)
if using_sample:
    st.caption(
        "Showing sample data from **map.xlsx**. Upload your own spreadsheet above to replace it."
    )
elif not user_uploaded_spreadsheet(uploaded_file) and template_file_path() is None:
    st.warning(
        "Sample file **map.xlsx** was not found in the app folder. "
        "Upload a spreadsheet to build your map."
    )

if data_source is not None:
    try:
        if using_sample:
            df = load_sample_dataframe()
            if df is None:
                raise FileNotFoundError("map.xlsx sample could not be loaded")
        else:
            df = read_spreadsheet(data_source)
        upload_key = spreadsheet_upload_key(data_source, df)

        if st.session_state.get("active_upload_key") != upload_key:
            st.session_state["active_upload_key"] = upload_key
            st.session_state.pop("labels_overlap_resolved", None)
            st.session_state.pop("map_view", None)
            st.session_state.pop("map_view_upload_key", None)
            st.session_state.pop("map_label_updating", None)
            for key in list(st.session_state.keys()):
                if key.startswith("label_lat_") or key.startswith("label_lon_"):
                    del st.session_state[key]

        all_cols = df.columns.tolist()

        st.subheader("Column mapping")
        map_col1, map_col2, map_col3 = st.columns(3)
        with map_col1:
            name_col = st.selectbox(
                "Location name column",
                all_cols,
                index=all_cols.index(
                    column_default(all_cols, 0, ["location", "location_name", "name", "village"])
                ),
            )
        with map_col2:
            lat_col = st.selectbox(
                "Latitude column",
                all_cols,
                index=all_cols.index(column_default(all_cols, 1, ["latitude", "lat"])),
            )
        with map_col3:
            lon_col = st.selectbox(
                "Longitude column",
                all_cols,
                index=all_cols.index(
                    column_default(all_cols, 2, ["longitude", "long", "lng", "lon"])
                ),
            )

        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        available_value_cols = [
            col for col in numeric_cols if col not in {name_col, lat_col, lon_col}
        ]
        positional_value_cols = [col for col in all_cols[3:] if col in available_value_cols]
        default_value_cols = positional_value_cols or available_value_cols
        value_cols = st.multiselect(
            "Value columns",
            available_value_cols,
            default=default_value_cols,
            help="Defaults to column D onward. Used for pie or column charts.",
        )

        mapping_errors = []
        if lat_col not in numeric_cols:
            mapping_errors.append(f"'{lat_col}' must be numeric")
        if lon_col not in numeric_cols:
            mapping_errors.append(f"'{lon_col}' must be numeric")
        if not value_cols:
            mapping_errors.append("Select at least one chart value column")

        if mapping_errors:
            for error in mapping_errors:
                st.error(error)
        else:
            st.subheader("Chart settings")
            chart_col1, chart_col2 = st.columns([1, 3])
            with chart_col1:
                if st.session_state.get("marker_type") == "bar":
                    st.session_state["marker_type"] = "column"
                marker_type = st.radio(
                    "Chart type",
                    ["pie", "column"],
                    format_func=chart_type_label,
                    horizontal=True,
                    key="marker_type",
                )
            with chart_col2:
                color_pickers = st.columns(len(value_cols))
                chart_colors = []
                for i, col in enumerate(value_cols):
                    default = DEFAULT_CHART_COLORS[i % len(DEFAULT_CHART_COLORS)]
                    if f"chart_color_{col}" not in st.session_state:
                        st.session_state[f"chart_color_{col}"] = default
                    with color_pickers[i]:
                        st.color_picker(f"{col} color", key=f"chart_color_{col}")
                    chart_colors.append(st.session_state[f"chart_color_{col}"])

            for key, default in (
                ("show_lbl_name", True),
                ("show_lbl_values", True),
                ("show_lbl_total", True),
                ("scale_by_total", True),
            ):
                if key not in st.session_state:
                    st.session_state[key] = default

            st.subheader("Labels")
            lbl_col1, lbl_col2, lbl_col3, lbl_col4 = st.columns(4)
            with lbl_col1:
                st.checkbox("Show location name", key="show_lbl_name")
            with lbl_col2:
                st.checkbox("Show values", key="show_lbl_values")
            with lbl_col3:
                st.checkbox("Show total", key="show_lbl_total")
            with lbl_col4:
                st.checkbox("Scale size by total", key="scale_by_total")

            show_name = st.session_state.show_lbl_name
            show_values = st.session_state.show_lbl_values
            show_total = st.session_state.show_lbl_total
            scale_by_total = st.session_state.scale_by_total

            marker_rows = []
            totals = []
            for idx, row in df.iterrows():
                values, labels = get_nonzero_values(row, value_cols)
                total = sum(values)
                totals.append(total)
                marker_rows.append(
                    {
                        "idx": idx,
                        "lat": row[lat_col],
                        "lon": row[lon_col],
                        "values": values,
                        "labels": labels,
                        "total": total,
                        "name": row[name_col],
                    }
                )

            positive_totals = [total for total in totals if total > 0]
            min_total = min(positive_totals) if positive_totals else 0
            max_total = max(totals) if totals else 1
            lat_span = df[lat_col].max() - df[lat_col].min() or 1
            lon_span = df[lon_col].max() - df[lon_col].min() or 1
            label_positions = {}
            label_sizes = {}

            for marker in marker_rows:
                idx = marker["idx"]
                _, _, icon_w, icon_h = build_label_content(
                    str(marker["name"]),
                    marker["labels"],
                    marker["values"],
                    marker["total"],
                    show_name,
                    show_values,
                    show_total,
                )
                label_sizes[idx] = (icon_w, icon_h)

            label_layout_sig = (
                show_name,
                show_values,
                show_total,
                tuple(value_cols),
            )
            if st.session_state.get("_label_layout_sig") != label_layout_sig:
                st.session_state.pop("labels_overlap_resolved", None)
                for key in list(st.session_state.keys()):
                    if key.startswith("label_lat_") or key.startswith("label_lon_"):
                        del st.session_state[key]
            st.session_state["_label_layout_sig"] = label_layout_sig

            if labels_enabled(show_name, show_values, show_total):
                if not st.session_state.get("labels_overlap_resolved"):
                    resolved = place_labels_near_markers(
                        marker_rows,
                        label_sizes,
                        lat_span,
                        lon_span,
                    )
                    for idx, (lat, lon) in resolved.items():
                        st.session_state[f"label_lat_{idx}"] = lat
                        st.session_state[f"label_lon_{idx}"] = lon
                    st.session_state["labels_overlap_resolved"] = True

            for marker in marker_rows:
                idx = marker["idx"]
                label_positions[idx] = (
                    st.session_state.get(
                        f"label_lat_{idx}",
                        scaled_label_latlon(marker, "right", lat_span, lon_span),
                    ),
                    st.session_state.get(
                        f"label_lon_{idx}",
                        marker["lon"],
                    ),
                )

            st.subheader("Data preview")
            preview_df = pd.DataFrame(
                {
                    name_col: df[name_col],
                    "total": df[value_cols].apply(pd.to_numeric, errors="coerce").sum(axis=1),
                }
            )
            st.dataframe(preview_df, use_container_width=True)

            st.subheader("Map")
            render_label_map_fragment(
                df,
                lat_col,
                lon_col,
                upload_key,
                marker_rows,
                lat_span,
                lon_span,
                min_total,
                max_total,
                marker_type,
                chart_colors,
                scale_by_total,
                show_name,
                show_values,
                show_total,
            )
    except Exception as e:
        st.error(f"Could not process file: {str(e)}")
else:
    st.info("Upload a spreadsheet (.xlsx, .xls, or .csv) to build your map.")

render_footer()
