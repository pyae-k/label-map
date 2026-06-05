"""Streamlit UI components for LabelMap."""

import streamlit as st
from streamlit_folium import st_folium

from labelmap.config import (
    ABOUT_TEXT,
    CONTACT_EMAIL,
    CONTACT_LINKEDIN,
    CONTACT_NAME,
    HERO_TAGLINE,
    HOW_IT_WORKS_STEPS,
    INTERACTIVE_MAP_HEIGHT,
    INTERACTIVE_MAP_WIDTH,
    PRIVACY_NOTICE,
    PRIVACY_POLICY_URL,
)
from labelmap.export import template_download_href
from labelmap.map_builder import build_interactive_map, populate_map_layers
from labelmap.map_session import label_positions_from_session, sync_dragged_labels
from labelmap.paths import template_file_path


def render_app_intro():
    st.title("LabelMap")
    st.markdown(
        f'<p style="color:#6b7280;font-size:0.95rem;margin:0 0 0.75rem 0;">{HERO_TAGLINE}</p>',
        unsafe_allow_html=True,
    )
    step_cols = st.columns(len(HOW_IT_WORKS_STEPS))
    for col, step in zip(step_cols, HOW_IT_WORKS_STEPS):
        with col:
            st.markdown(
                f'<p style="color:#374151;font-size:0.875rem;margin:0;">{step}</p>',
                unsafe_allow_html=True,
            )
    st.markdown("<div style='margin-bottom:0.75rem;'></div>", unsafe_allow_html=True)


def render_footer():
    st.divider()
    st.markdown(
        f"""
        <div style="color:#6b7280;font-size:0.8rem;line-height:1.5;">
          <p style="margin:0 0 0.5rem;"><span style="color:#374151;font-weight:600;">About</span> — {ABOUT_TEXT}</p>
          <p style="margin:0 0 0.5rem;"><span style="color:#374151;font-weight:600;">Privacy</span> — {PRIVACY_NOTICE} See <a href="{PRIVACY_POLICY_URL}" target="_blank" rel="noopener noreferrer" style="color:#2563eb;text-decoration:none;">Streamlit's privacy policy</a>.</p>
          <p style="margin:0 0 0.5rem;"><span style="color:#374151;font-weight:600;">Contact</span> — {CONTACT_NAME} · <a href="mailto:{CONTACT_EMAIL}" style="color:#2563eb;text-decoration:none;">{CONTACT_EMAIL}</a> · <a href="{CONTACT_LINKEDIN}" target="_blank" rel="noopener noreferrer" style="color:#2563eb;text-decoration:none;">LinkedIn</a></p>
          <p style="text-align:center;color:#9ca3af;font-size:0.75rem;margin:0.75rem 0 0;">© LabelMap</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_template_link():
    if template_file_path():
        href = template_download_href()
        st.markdown(
            f'<p style="margin:0.25rem 0 0;font-size:0.875rem;color:#6b7280;">'
            f'Need a starter file? '
            f'<a href="{href}" download="map.xlsx" '
            f'style="color:#2563eb;text-decoration:none;">Download template</a></p>',
            unsafe_allow_html=True,
        )


def render_privacy_notice():
    st.markdown(
        f'<p style="color:#6b7280;font-size:0.875rem;margin:0;">{PRIVACY_NOTICE} See '
        f'<a href="{PRIVACY_POLICY_URL}" target="_blank" rel="noopener noreferrer" '
        f'style="color:#2563eb;text-decoration:none;">Streamlit\'s privacy policy</a>.</p>',
        unsafe_allow_html=True,
    )


@st.fragment
def render_label_map_fragment(
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
):
    """Map-only rerun on label drag; preserves zoom and blocks drags while saving."""
    completing_save = st.session_state.get("map_label_updating", False)
    prior_map_state = st.session_state.get("label_map")
    if isinstance(prior_map_state, dict):
        sync_dragged_labels(prior_map_state, upload_key)

    label_positions = label_positions_from_session(marker_rows, lat_span, lon_span)

    m, map_view = build_interactive_map(df, lat_col, lon_col, upload_key)
    populate_map_layers(
        m,
        marker_rows,
        label_positions,
        min_total,
        max_total,
        marker_type,
        chart_colors,
        scale_by_total,
        show_name,
        show_values,
        show_total,
        draggable_labels=True,
        drag_locked=completing_save,
        unlock_after_save=completing_save,
    )
    map_state = st_folium(
        m,
        width=INTERACTIVE_MAP_WIDTH,
        height=INTERACTIVE_MAP_HEIGHT,
        center=(map_view["center_lat"], map_view["center_lon"]),
        zoom=map_view["zoom"],
        key="label_map",
        returned_objects=["last_object_clicked_tooltip"],
    )

    label_moved = sync_dragged_labels(map_state, upload_key)
    if label_moved:
        st.session_state["map_label_updating"] = True
    elif completing_save:
        st.session_state["map_label_updating"] = False

    st.caption(
        "Drag labels to adjust. Map zoom is kept while each move saves."
    )
