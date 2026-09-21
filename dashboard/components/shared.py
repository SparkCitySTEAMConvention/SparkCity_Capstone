"""Shared dashboard shell and helpers reused across pages.

Domain pages should add content, not restyle this shell. Page-specific UI
(hero, cards, footer, etc.) belongs in its own page module, not here.
"""
import base64
from functools import lru_cache
from pathlib import Path

import streamlit as st

STYLES_PATH = Path(__file__).resolve().parents[1] / "styles" / "styles.css"
HEADER_IMAGE_PATH = Path(__file__).resolve().parents[1] / "assets" / "nav_city.png"  # NOT city.png (that is the sunset Overview hero image)
LINEART_IMAGE_PATH = Path(__file__).resolve().parents[1] / "assets" / "nav_lineart.png"

DESTINATIONS = {
    # Nav-label emojis removed (2026-09-19); keys (routing values) unchanged, only the displayed labels.
    "Overview": "Overview",
    "Convention Planner": "Convention Planner",
    "Mobility & Traffic": "Mobility & Traffic",
    "Environment": "Environment",
    "Capacity & Utilization": "Capacity & Utilization",
    "Fiscal Impact": "Fiscal Impact",
    # "Sustainability" intentionally removed (2026-09-17) — no page was ever routed to it.
}

LIGHT_PALETTE = {
    "#101820": "#F4F7FB",
    "#F3F6F9": "#172B46",
    "#182430": "#FFFFFF",
    "#34495A": "#D6E0EA",
    "#B8C4CF": "#526A82",
    "#8FA1B2": "#62758A",
    "#223342": "#EAF1F8",
    "#1E2D3A": "#F7FAFC",
    "#20373D": "#EAF5F1",
    "#1E332F": "#EAF5F1",
    "#36352C": "#FDF3E2",
}


def light_mode_enabled():
    """Return the session-scoped accessibility theme preference."""
    return bool(st.session_state.get("accessibility_light_mode", False))


def apply_accessible_palette(css):
    """Translate the shared dark design tokens while preserving accent colors."""
    if not light_mode_enabled():
        return css
    for dark, light in LIGHT_PALETTE.items():
        css = css.replace(dark, light)
    return css


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
    return apply_accessible_palette(text)


def load_css(path=STYLES_PATH, section=None):
    """Read and immediately inject a CSS file/section. See read_css()."""
    st.markdown(f"<style>{read_css(path, section)}</style>", unsafe_allow_html=True)


@lru_cache(maxsize=1)
def _header_image_data_uri():
    """Nav header background (2026-09-19): assets/nav_city.png (daytime civic image), embedded unmodified (raw bytes, no resize/re-encode). Only used off-Overview."""
    return "data:image/png;base64," + base64.b64encode(HEADER_IMAGE_PATH.read_bytes()).decode("ascii")


@lru_cache(maxsize=1)
def _lineart_data_uri():
    """Overview navbar decoration (2026-09-19): assets/nav_lineart.png embedded unmodified (raw bytes)."""
    return "data:image/png;base64," + base64.b64encode(LINEART_IMAGE_PATH.read_bytes()).decode("ascii")


def open_page(destination):
    """Generic session-state navigation setter, reusable by any page's buttons."""
    st.session_state["dashboard_destination"] = destination


def render_theme_overrides():
    """Apply runtime widget colors after destination styles have rendered."""
    if not light_mode_enabled():
        return
    st.markdown(
        """<style>
        .stApp,[data-testid="stAppViewContainer"] {background:#F4F7FB;color:#172B46;}
        [data-testid="stMainBlockContainer"] {color:#172B46;}
        [data-testid="stWidgetLabel"] p {color:#223B57;}
        [data-baseweb="input"] input,
        [data-baseweb="select"] > div,
        [data-baseweb="textarea"] textarea {background:#FFFFFF!important;color:#172B46!important;}
        [data-baseweb="popover"],[role="listbox"] {background:#FFFFFF!important;color:#172B46!important;}
        [role="option"] {color:#172B46!important;}
        [role="option"]:hover {background:#EAF1F8!important;}
        .stButton button,.stDownloadButton button {color:#172B46;}
        :is(a,button,input,textarea,[role="radio"],[role="checkbox"],[role="option"]):focus-visible {
            outline:3px solid #1769AA!important;outline-offset:3px!important;
        }
        .st-key-sparkcity_navigation [data-testid="stWidgetLabel"] p {color:#E5EEFB!important;}
        .st-key-overview_hero,.st-key-overview_hero h1,.st-key-overview_hero h3,
        .st-key-overview_hero p {color:white;}
        </style>""",
        unsafe_allow_html=True,
    )


def render_navigation():
    # Shared/frozen contract: navigation, page width, palette, headers and existing
    # common card styles. Teammates should reuse them rather than redesign them.
    # City-image header (2026-09-19): Overview keeps the original compact navbar
    # (shared CSS only); every other destination also gets the "navheader" CSS
    # section with city.png substituted straight into its background declaration.
    # NOT via a CSS custom property (fix 2026-09-19): the ~3MB data URI exceeded
    # Chrome's custom-property/var() size cap, so the whole declaration was dropped.
    # Still one style call and one st.radio.
    css = read_css(section="shared")
    if st.session_state.get("dashboard_destination", "Overview") != "Overview":
        css += read_css(section="navheader").replace("var(--sc-city,none)", f"url('{_header_image_data_uri()}')")
    else:
        # Overview-only decorative line-art background (2026-09-19); background layer, no layout effect.
        css += read_css(section="navlineart").replace("__NAV_LINEART__", _lineart_data_uri())
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    with st.container(key="sparkcity_navigation"):
        # One shared brand block on every page/destination; only the active nav
        # item (below) changes. Do not fork this per destination again.
        st.markdown('<div class="sparkcity-brand"><div><strong>New York Digital City</strong><br><small>Data for a Brighter Tomorrow</small></div><small>Smarter Data.<br>Stronger Communities.</small></div>', unsafe_allow_html=True)
        st.toggle(
            "Light mode",
            key="accessibility_light_mode",
            help="Use a brighter, high-contrast dashboard palette and daylight city scene.",
        )
        return st.radio(
            "New York Digital City Navigation", list(DESTINATIONS),
            format_func=DESTINATIONS.get, horizontal=True,
            label_visibility="collapsed", key="dashboard_destination",
        )
