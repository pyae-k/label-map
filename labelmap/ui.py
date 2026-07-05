"""Streamlit UI components for LabelMap."""

import json

import streamlit as st
import streamlit.components.v1 as components
from streamlit_folium import st_folium

from labelmap.config import (
    ABOUT_TEXT,
    APP_ACCENT_COLOR,
    APP_FONT_STACK,
    APP_MUTED_COLOR,
    APP_TEXT_COLOR,
    APP_TEXT_SIZE,
    APP_TEXT_SIZE_LG,
    CONTACT_EMAIL,
    CONTACT_LINKEDIN,
    CONTACT_NAME,
    DEFAULT_MAP_STYLE,
    HERO_TAGLINE,
    HOW_IT_WORKS_STEPS,
    INTERACTIVE_MAP_HEIGHT_BOOTSTRAP,
    PRIVACY_NOTICE,
    PRIVACY_POLICY_URL,
)
from labelmap.export import sample_template_download_href
from labelmap.map_builder import build_interactive_map, populate_map_layers
from labelmap.map_session import (
    folium_widget_key,
    label_positions_from_session,
    sync_dragged_labels,
    sync_live_map_view,
)
from labelmap.paths import repo_root, template_file_path


_DOC_FILES = {
    "readme": "README.md",
    "technical": "docs/TECHNICAL.md",
    "user_guide": "docs/USER_GUIDE.md",
}
_DOC_TRIGGER_KEYS = {
    "readme": "doc_readme_trigger",
    "technical": "doc_technical_trigger",
    "user_guide": "doc_user_guide_trigger",
}


def render_app_intro():
    # Title removed — unified font styles applied globally
    st.markdown(
        f'<p style="font-family:{APP_FONT_STACK};color:{APP_TEXT_COLOR};'
        f'font-size:{APP_TEXT_SIZE_LG};font-weight:700;margin:0 0 0.75rem 0;">'
        f'{HERO_TAGLINE}</p>',
        unsafe_allow_html=True,
    )
    step_cols = st.columns(len(HOW_IT_WORKS_STEPS))
    for col, step in zip(step_cols, HOW_IT_WORKS_STEPS):
        with col:
            st.markdown(
                f'<p style="font-family:{APP_FONT_STACK};color:{APP_TEXT_COLOR};'
                f'font-size:{APP_TEXT_SIZE};font-weight:700;margin:0;">{step}</p>',
                unsafe_allow_html=True,
            )
    st.markdown("<div style='margin-bottom:0.75rem;'></div>", unsafe_allow_html=True)


_DOC_LABELS = {
    "readme": "README",
    "technical": "Technical documentation",
    "user_guide": "User guide",
}
_DOC_ICON_SVGS = {
    "readme": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" aria-hidden="true">'
        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
        '<polyline points="14 2 14 8 20 8"/>'
        '<line x1="8" y1="13" x2="16" y2="13"/>'
        '<line x1="8" y1="17" x2="13" y2="17"/>'
        "</svg>"
    ),
    "technical": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" aria-hidden="true">'
        '<polyline points="16 18 22 12 16 6"/>'
        '<polyline points="8 6 2 12 8 18"/>'
        "</svg>"
    ),
    "user_guide": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" aria-hidden="true">'
        '<circle cx="12" cy="12" r="10"/>'
        '<path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>'
        '<line x1="12" y1="17" x2="12.01" y2="17"/>'
        "</svg>"
    ),
}


def _load_doc_markdown(relative_path: str) -> str:
    path = repo_root() / relative_path
    if not path.is_file():
        return f"*Document not found: `{relative_path}`*"
    text = path.read_text(encoding="utf-8")
    if path.parent.name == "docs":
        text = text.replace("](images/", "](docs/images/")
    return text


def _clear_doc_view():
    st.session_state.pop("_doc_view", None)


@st.dialog("Documentation", width="large", dismissible=True, on_dismiss=_clear_doc_view)
def _doc_dialog():
    doc_key = st.session_state.get("_doc_view", "readme")
    relative_path = _DOC_FILES.get(doc_key, _DOC_FILES["readme"])
    st.markdown(_load_doc_markdown(relative_path))


def _doc_icon_button(doc_key: str) -> str:
    label = _DOC_LABELS[doc_key]
    icon_svg = _DOC_ICON_SVGS[doc_key]
    return (
        f'<button type="button" class="labelmap-doc-icon" data-doc-key="{doc_key}" '
        f'title="{label}" aria-label="{label}">{icon_svg}</button>'
    )


def _render_doc_triggers():
    for doc_key in _DOC_FILES:
        if st.button(
            "open",
            key=_DOC_TRIGGER_KEYS[doc_key],
            help=_DOC_LABELS[doc_key],
        ):
            st.session_state["_doc_view"] = doc_key


def _bind_doc_icon_clicks():
    trigger_map = {doc_key: trigger_key for doc_key, trigger_key in _DOC_TRIGGER_KEYS.items()}
    components.html(
        f"""
        <script>
        (function() {{
            const parentDoc = window.parent && window.parent.document;
            if (!parentDoc) return;
            if (parentDoc._labelMapDocIconClickHandler) {{
                parentDoc.removeEventListener(
                    "click",
                    parentDoc._labelMapDocIconClickHandler,
                    true
                );
            }}
            const triggerKeys = {json.dumps(trigger_map)};
            parentDoc._labelMapDocIconClickHandler = function(event) {{
                const icon = event.target && event.target.closest("button.labelmap-doc-icon");
                if (!icon) return;
                const docKey = icon.getAttribute("data-doc-key");
                const triggerKey = triggerKeys[docKey];
                if (!triggerKey) return;
                event.preventDefault();
                const button = parentDoc.querySelector(
                    ".st-key-" + triggerKey + ' [data-testid="stButton"] button'
                );
                if (button) button.click();
            }};
            parentDoc.addEventListener("click", parentDoc._labelMapDocIconClickHandler, true);
        }})();
        </script>
        """,
        height=0,
    )


def render_contact_with_docs():
    doc_icons = (
        '<span class="labelmap-doc-icons">'
        + _doc_icon_button("readme")
        + _doc_icon_button("technical")
        + _doc_icon_button("user_guide")
        + "</span>"
    )
    st.markdown(
        '<div class="labelmap-contact-block">'
        '<p class="labelmap-contact-label" style="margin:0;">'
        f"{CONTACT_NAME} • "
        f'<a href="mailto:{CONTACT_EMAIL}" '
        'style="font-size:inherit;font-weight:inherit;white-space:nowrap;">'
        f"{CONTACT_EMAIL}</a> • "
        f'<a href="{CONTACT_LINKEDIN}" target="_blank" rel="noopener noreferrer" '
        'style="font-size:inherit;font-weight:inherit;white-space:nowrap;">'
        "linkedin.com/in/pyaek/</a>"
        "</p>"
        '<div class="labelmap-contact-divider"></div>'
        f"{doc_icons}"
        "</div>",
        unsafe_allow_html=True,
    )
    _render_doc_triggers()
    _bind_doc_icon_clicks()
    if st.session_state.get("_doc_view"):
        _doc_dialog()


def render_footer():
    st.divider()
    st.markdown(
        f"""
        <div style="font-family:{APP_FONT_STACK};color:{APP_TEXT_COLOR};font-size:{APP_TEXT_SIZE};line-height:1.5;font-weight:700;">
          <p style="margin:0 0 0.5rem;font-family:{APP_FONT_STACK};color:{APP_TEXT_COLOR};font-size:{APP_TEXT_SIZE};font-weight:700;">
            <span style="color:{APP_MUTED_COLOR};">About</span> — {ABOUT_TEXT}
          </p>
          <p style="margin:0 0 0.5rem;font-family:{APP_FONT_STACK};color:{APP_TEXT_COLOR};font-size:{APP_TEXT_SIZE};font-weight:700;">
            <span style="color:{APP_MUTED_COLOR};">Privacy</span> — {PRIVACY_NOTICE} See
            <a href="{PRIVACY_POLICY_URL}" target="_blank" rel="noopener noreferrer" style="color:{APP_ACCENT_COLOR};text-decoration:none;">Streamlit's privacy policy</a>.
          </p>
          <p style="margin:0 0 0.5rem;font-family:{APP_FONT_STACK};color:{APP_TEXT_COLOR};font-size:{APP_TEXT_SIZE};font-weight:700;">
            <span style="color:{APP_MUTED_COLOR};">Contact</span> — {CONTACT_NAME} ·
            <a href="mailto:{CONTACT_EMAIL}" style="color:{APP_ACCENT_COLOR};text-decoration:none;">{CONTACT_EMAIL}</a> ·
            <a href="{CONTACT_LINKEDIN}" target="_blank" rel="noopener noreferrer" style="color:{APP_ACCENT_COLOR};text-decoration:none;font-size:inherit;font-weight:inherit;white-space:nowrap;">linkedin.com/in/pyaek/</a>
          </p>
          <p style="text-align:center;color:{APP_MUTED_COLOR};font-family:{APP_FONT_STACK};font-size:{APP_TEXT_SIZE};font-weight:700;margin:0.75rem 0 0;">© LabelMap</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_template_link():
    href = sample_template_download_href()
    if href:
        st.markdown(
            f'<p style="margin:0.25rem 0 0;font-family:{APP_FONT_STACK};'
            f'font-size:{APP_TEXT_SIZE};font-weight:700;color:{APP_TEXT_COLOR};">'
            f'Need a starter file? '
            f'<a href="{href}" download="labelmap-sample.csv" '
            f'style="color:{APP_ACCENT_COLOR};text-decoration:none;">Download template</a></p>',
            unsafe_allow_html=True,
        )


def render_privacy_notice():
    st.markdown(
        f'<p style="font-family:{APP_FONT_STACK};color:{APP_TEXT_COLOR};'
        f'font-size:{APP_TEXT_SIZE};font-weight:700;margin:0;">{PRIVACY_NOTICE} See '
        f'<a href="{PRIVACY_POLICY_URL}" target="_blank" rel="noopener noreferrer" '
        f'style="color:{APP_ACCENT_COLOR};text-decoration:none;">Streamlit\'s privacy policy</a>.</p>',
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
    force_compare_total_tooltip=False,
    map_style=DEFAULT_MAP_STYLE,
    show_legend=True,
    legend_items=None,
):
    """Map-only rerun on label drag; preserves zoom and blocks drags while saving."""
    completing_save = st.session_state.get("map_label_updating", False)
    folium_key = folium_widget_key(upload_key)
    prior_map_state = st.session_state.get(folium_key)
    label_moved = False
    if isinstance(prior_map_state, dict):
        label_moved = sync_dragged_labels(prior_map_state, upload_key)

    label_positions = label_positions_from_session(
        marker_rows,
        lat_span,
        lon_span,
        marker_type,
        show_name,
        show_values,
        show_total,
    )

    m, map_view = build_interactive_map(
        df,
        lat_col,
        lon_col,
        upload_key,
        map_style=map_style,
        show_legend=show_legend,
        legend_items=legend_items,
    )
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
        force_compare_total_tooltip=force_compare_total_tooltip,
        map_style=map_style,
        draggable_labels=True,
        drag_locked=completing_save,
        unlock_after_save=completing_save,
    )
    map_state = st_folium(
        m,
        height=INTERACTIVE_MAP_HEIGHT_BOOTSTRAP,
        use_container_width=True,
        center=(map_view["center_lat"], map_view["center_lon"]),
        zoom=None,
        key=folium_key,
        returned_objects=["last_object_clicked_tooltip"],
    )

    sync_live_map_view(map_state, upload_key)
    post_sync_moved = sync_dragged_labels(map_state, upload_key)
    label_moved = label_moved or post_sync_moved
    if label_moved:
        st.session_state["map_label_updating"] = True
    elif completing_save:
        st.session_state["map_label_updating"] = False
