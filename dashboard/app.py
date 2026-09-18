"""Streamlit entry point: shared setup and page routing."""
from pathlib import Path
import sys

import streamlit as st
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
load_dotenv(PROJECT_ROOT / "secrets" / ".env")

st.set_page_config(page_title="SparkCity | Convention Planning", page_icon="🏙️", layout="wide")

from components.shared import render_navigation

destination = render_navigation()

from pages.overview import render_overview, render_pending
from pages.convention_planner import render_convention_planner #MCC added

if destination == "Overview":
    render_overview()

elif destination == "Convention Planner": #MCC added
    render_convention_planner()
else:
    # Teammates: import your domain renderer here and route its destination to
    # that function. Mobility & Traffic is Leigh's; it stays on the neutral
    # render_pending() placeholder below until her page is wired in.
    render_pending(destination)
