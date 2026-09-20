"""Streamlit entry point: shared setup and page routing."""
from pathlib import Path
import sys

import streamlit as st
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
load_dotenv(PROJECT_ROOT / "secrets" / ".env")

st.set_page_config(page_title="New York Digital City | Convention Planning", page_icon="🏙️", layout="wide")

from components.shared import render_navigation

destination = render_navigation()

from pages.fiscal_impact import render_fiscal_impact
from pages.overview import render_overview, render_pending
from pages.mobility_traffic import render_mobility_traffic
from pages.convention_planner import render_convention_planner
from pages.capacity_utilization import render_capacity_utilization

# The page-content min-height only needs to exist from this session's second
# script run onward: it stops the container collapsing when swapping between
# two already-rendered destinations, but on the very first run there is no
# prior content to protect against collapsing, so reserving it immediately
# just shows as a large empty region under the navbar before the destination
# has produced anything to fill it (2026-09-18, refresh-reflow investigation).
if st.session_state.get("_sparkcity_content_rendered_once"):
    st.markdown(
        "<style>.st-key-sparkcity_page_content {min-height:70vh;}</style>",
        unsafe_allow_html=True,
    )
st.session_state["_sparkcity_content_rendered_once"] = True

# Identity for the inner, destination-specific content wrapper below. This is
# deliberately NOT the same key as sparkcity_page_content itself: that outer
# container's key never changes, so it keeps its own persisted identity (and
# its min-height reservation) across every rerun regardless of destination.
# This inner key DOES change with the destination, so React treats a
# destination switch as a brand-new component instance at this position
# rather than an update to the previous one -- the previous destination's
# whole subtree (e.g. Fiscal Impact's hero image) is unmounted atomically
# instead of being incrementally reconciled/patched, which is what let stale
# content from the previous destination remain visible while the next one
# was still streaming in (2026-09-19, stale-subtree-flash investigation).
_destination_key = (
    destination.lower().replace(" & ", "_and_").replace(" ", "_")
)

with st.container(key="sparkcity_page_content"):
    with st.container(key=f"sparkcity_destination_{_destination_key}"):
        if destination == "Overview":
            render_overview()
        elif destination == "Convention Planner":
            render_convention_planner()
        elif destination == "Mobility & Traffic":
            render_mobility_traffic()
        elif destination == "Environment":
            from environment_app import render_environment_page

            render_environment_page()
        elif destination == "Capacity & Utilization":
            render_capacity_utilization()
        elif destination == "Fiscal Impact":
            render_fiscal_impact()
        else:
            render_pending(destination)
