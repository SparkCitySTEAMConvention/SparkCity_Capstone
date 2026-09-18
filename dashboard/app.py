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
from pages.capacity_utilization import render_capacity_utilization
from pages.mobility_traffic import render_mobility_traffic

if destination == "Overview":
    render_overview()
elif destination == "Convention Planner": #MCC added
    render_convention_planner()
elif destination == "Environment":
    from environment_app import render_environment_page

    render_environment_page()
elif destination == "Capacity & Utilization":
    render_capacity_utilization()
elif destination == "Mobility & Traffic":
    render_mobility_traffic()
else:
    render_pending(destination)
