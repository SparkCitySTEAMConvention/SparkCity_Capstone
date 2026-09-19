"""Shared dashboard shell and helpers reused across pages.

Domain pages should add content, not restyle this shell. Page-specific UI
(hero, cards, footer, etc.) belongs in its own page module, not here.
"""
from pathlib import Path

import streamlit as st

STYLES_PATH = Path(__file__).resolve().parents[1] / "styles" / "styles.css"

DESTINATIONS = {
    "Overview": "🏠 Overview",
    "Convention Planner": "📅 Convention Planner",
    "Planner Exports": "📊 Planner Exports",
    "Mobility & Traffic": "🚗 Mobility & Traffic",
    "Environment": "🍃 Environment",
    "Capacity & Utilization": "🏢 Capacity & Utilization",
    "Fiscal Impact": "💰 Fiscal Impact",
    # "Sustainability" intentionally removed (2026-09-17) — no page was ever routed to it.
}


def read_css(path=STYLES_PATH, section=None):
    """Read a CSS file (or one of its "/* >>> name */"-delimited sections) as text.

    Pages that only make sense on one destination (e.g. the overview page)
    keep their rules in their own named section, so loading a *different*
    section elsewhere (e.g. the shared section on every page) never leaks
    page-specific, globally-scoped selectors onto another page.

    Returns plain text rather than injecting it, so a caller that also has its
    own dynamic, runtime-only CSS (e.g. a base64 image URL) can concatenate the
    two and inject everything in one st.markdown call. Streamlit gives every
    st.markdown call its own DOM element, and each such element becomes its own
    (zero-height but still gap-consuming) flex sibling in the surrounding
    layout; extra style-only calls therefore add extra visual gaps between the
    real widgets around them, so keep the number of calls per page constant.
    """
    text = Path(path).read_text()
    if section is not None:
        marker = f"/* >>> {section} */"
        start = text.index(marker) + len(marker)
        end = text.find("/* >>> ", start)
        text = text[start:] if end == -1 else text[start:end]
    return text


def load_css(path=STYLES_PATH, section=None):
    """Read and immediately inject a CSS file/section. See read_css()."""
    st.markdown(f"<style>{read_css(path, section)}</style>", unsafe_allow_html=True)


def open_page(destination):
    """Generic session-state navigation setter, reusable by any page's buttons."""
    st.session_state["dashboard_destination"] = destination


def render_navigation():
    # Shared/frozen contract: navigation, page width, palette, headers and existing
    # common card styles. Teammates should reuse them rather than redesign them.
    load_css(section="shared")
    with st.container(key="sparkcity_navigation"):
        # Landing-page branding only; keep the existing domain-page shell intact.
        if st.session_state.get("dashboard_destination", "Overview") == "Overview":
            st.markdown('<div class="sparkcity-brand"><div><strong>SparkCity</strong><br><small>Data for a Brighter Tomorrow</small></div><small>Smarter Data.<br>Stronger Communities.</small></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="sparkcity-brand"><strong>SparkCity</strong><small>SparkCity STEAM Convention<br>Data-Driven Planning Dashboard</small></div>', unsafe_allow_html=True)
        return st.radio(
            "SparkCity Navigation", list(DESTINATIONS),
            format_func=DESTINATIONS.get, horizontal=True,
            label_visibility="collapsed", key="dashboard_destination",
        )
