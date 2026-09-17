"""Landing-page UI only. Navigation cards and future team-result slots."""
import base64
import io
from functools import lru_cache
from html import escape
from pathlib import Path

import streamlit as st
from PIL import Image

from components.shared import STYLES_PATH, open_page, read_css

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
HERO_IMAGE_PATH = ASSETS_DIR / "city.png"
DOMAIN_IMAGE_DIR = ASSETS_DIR / "domains"
DOMAIN_IMAGE_MAX_WIDTH = 480  # card image area is ~110px tall; source photos are far larger


@lru_cache(maxsize=1)
def _hero_image_data_uri():
    """Local asset only; never reads from outside the project."""
    encoded = base64.b64encode(HERO_IMAGE_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


@lru_cache(maxsize=None)
def _domain_image_data_uri(filename):
    """Drop a matching file into dashboard/assets/domains/ to upgrade a card
    from its placeholder to a real photo; no code change needed. Downscales to
    a card-sized thumbnail so six full-resolution photos don't bloat the page."""
    path = DOMAIN_IMAGE_DIR / filename
    if not path.exists():
        return None
    with Image.open(path) as img:
        img = img.convert("RGB")
        if img.width > DOMAIN_IMAGE_MAX_WIDTH:
            new_height = round(img.height * DOMAIN_IMAGE_MAX_WIDTH / img.width)
            img = img.resize((DOMAIN_IMAGE_MAX_WIDTH, new_height), Image.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=80)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"

# image/metric_value/metric_label/status are optional and unused today; wired in
# for teammates to attach a real photo or a KPI later without touching this shape.
# Weather and Energy cards are hidden for now (assets kept under assets/domains/
# for later reuse); reintroduce their dicts here to bring them back.
DOMAINS = [
    {"title": "Environment", "description": "Explore air quality and weather conditions.", "icon": "🍃", "accent": "#39846d", "destination": "Environment", "image": "environment.png"},
    {"title": "Mobility & Traffic", "description": "Understand how people move through SparkCity.", "icon": "🚘", "accent": "#337bc0", "destination": "Mobility & Traffic", "image": "mobility_traffic.png"},
    {"title": "Capacity & Utilization", "description": "Explore venue and accommodation capacity.", "icon": "▦", "accent": "#8767b1", "destination": "Capacity & Utilization", "image": "capacity_utilization.png"},
    {"title": "Fiscal Impact", "description": "Explore the economic impact of the convention.", "icon": "▤", "accent": "#428778", "destination": "Fiscal Impact", "image": "fiscal_impact.png"},
]


def render_overview(load_data=None):
    # Compatibility with app.py only: this presentation never calls load_data.
    # The card markdown and its Explore button live in separate stElementContainers,
    # so var(--accent) set inline on .explore-card can't reach the button, and a plain
    # class can't give the two of them one shared hover/border. Each render_domain_card
    # call is wrapped in its own st.container(key=f"domain_card_{i}") instead, so the
    # accent border, radius, shadow and hover all live on that one real wrapper element
    # that contains both the card and the button as a single visual/hoverable unit.
    card_wrapper_css = "".join(
        f".st-key-domain_card_{i} {{border:1.5px solid {c['accent']};border-radius:14px;overflow:hidden;background:white;"
        f"box-shadow:0 4px 14px #10294408;transition:transform .2s ease, box-shadow .2s ease, border-color .2s ease;}}\n"
        f".st-key-domain_card_{i}:hover {{transform:translateY(-5px);box-shadow:0 14px 30px rgba(16,41,68,.2);"
        f"border-color:color-mix(in srgb,{c['accent']} 70%, black);}}\n"
        for i, c in enumerate(DOMAINS)
    )
    # The hero rule needs the runtime hero image data URI, so it can't live in the
    # static styles.css file. It's combined with the static "overview" section and
    # injected in exactly one st.markdown call: each such call is its own zero-height
    # flex sibling in the surrounding layout, so more calls than the original single
    # style block would silently reintroduce gaps between the real page sections.
    st.markdown(f'''<style>
{read_css(STYLES_PATH, section="overview")}
.st-key-overview_hero {{position:relative;margin-top:-32px;background:linear-gradient(90deg,rgba(6,14,30,.90) 0%,rgba(6,14,30,.78) 26%,rgba(6,14,30,.42) 50%,rgba(6,14,30,.12) 70%,rgba(6,14,30,0) 85%),url('{_hero_image_data_uri()}');background-size:cover;background-position:center;background-repeat:no-repeat;border-radius:0 0 18px 18px;padding:64px 56px;min-height:460px;margin-bottom:24px;color:white;overflow:hidden;}}
{card_wrapper_css}
</style>''', unsafe_allow_html=True)
    with st.container(key="overview_hero"):
        intro, mission = st.columns([1.8, 1], gap="large")
        with intro:
            st.markdown('<span class="overview-eyebrow">WELCOME TO</span>', unsafe_allow_html=True)
            st.markdown('<h1>Spark<span class="title-accent">City</span></h1>', unsafe_allow_html=True)
            st.subheader("Data-Driven Decisions for a Stronger Tomorrow")
            st.write("Explore real city data to plan a successful and sustainable STEAM convention.")
            st.markdown('<div class="overview-actions"><a href="#explore-sparkcity">Explore the Data →</a><a href="#about-the-data">Learn More</a></div>', unsafe_allow_html=True)
        with mission:
            st.markdown('<div class="overview-mission"><h3>Our Mission</h3><p>Use real city data to support events that bring people, innovation, and opportunity to SparkCity.</p></div>', unsafe_allow_html=True)
    st.header("Explore SparkCity", anchor="explore-sparkcity")
    st.write("Dive into key aspects of the city to understand opportunities and plan the best STEAM convention.")
    with st.container(key="overview_domains"):
        for index, (column, card) in enumerate(zip(st.columns(4), DOMAINS)):
            with column:
                render_domain_card(index, card)
    render_suitability()
    st.markdown('<div id="about-the-data"></div>', unsafe_allow_html=True)
    with st.expander("About the Data"):
        st.caption("Mission statement describes the intended application. This Overview is a navigation UI: no metrics, suitability scores, or recommendations are calculated here. Team analysis integration is pending. Existing Traffic analysis uses simulated SparkCity data—not live municipal observations.")
    st.markdown('<footer class="overview-footer"><div><strong>SparkCity</strong><br>People • Innovation • Opportunity</div><div>“Data today. A brighter tomorrow.”</div></footer>', unsafe_allow_html=True)


def render_domain_card(index, card):
    """Renders one Explore SparkCity card. `card` accepts title, description, icon,
    accent, destination (required today) plus optional image, metric_value,
    metric_label, status for teammates to attach a photo or KPI later without
    changing this function's shape."""
    image_uri = _domain_image_data_uri(card["image"]) if card.get("image") else None
    image_style = f"background-image:url('{image_uri}');" if image_uri else ""
    image_glyph = "" if image_uri else card["icon"]

    kpi_html = ""
    if card.get("metric_value"):
        status = card.get("status")
        status_html = f'<span class="explore-card-status">{escape(str(status))}</span>' if status else ""
        label_html = f'<span class="kpi-label">{escape(str(card["metric_label"]))}</span>' if card.get("metric_label") else ""
        kpi_html = f'<div class="explore-card-kpi"><div><span class="kpi-value">{escape(str(card["metric_value"]))}</span>{label_html}</div>{status_html}</div>'

    with st.container(key=f"domain_card_{index}"):
        st.markdown(f'''<div class="explore-card" style="--accent:{card["accent"]}">
<div class="explore-card-image" style="{image_style}">{image_glyph}</div>
<span class="explore-card-icon">{card["icon"]}</span>
<div class="explore-card-body">
<h3>{escape(card["title"])}</h3>
<p>{escape(card["description"])}</p>
{kpi_html}
</div>
</div>''', unsafe_allow_html=True)
        st.button("Explore →", key=f"explore_card_{index}", help=f"Open {card['destination']}",
                  on_click=open_page, args=(card["destination"],), width="stretch")


def render_suitability():
    """Team integration point: replace each card's value/status only with approved
    results later (e.g. value="November", status="High Confidence") without
    changing this structure."""
    with st.container(key="overview_plan"):
        intro, slots = st.columns([1.1, 2], gap="large")
        with intro:
            st.markdown('<div class="plan-heading"><span class="plan-icon">📅</span><h3>Plan the STEAM Convention</h3></div>', unsafe_allow_html=True)
            st.write("Combine insights from across SparkCity to identify the best time and strategy for a successful STEAM convention.")
            st.button("Go to Convention Planner →", on_click=open_page, args=("Convention Planner",), width="stretch")
        with slots:
            cards = [
                ("🏆", "Recommended Month"),
                ("🎖", "High-Confidence Alternative"),
                ("📊", "Monthly Suitability Score"),
            ]
            for column, (icon, title) in zip(st.columns(3), cards):
                with column:
                    st.markdown(f'''<div class="plan-card">
<span class="plan-card-icon">{icon}</span>
<div class="plan-card-title">{title}</div>
<div class="plan-card-value">Team Analysis</div>
<span class="plan-card-status">Integration Pending</span>
</div>''', unsafe_allow_html=True)


def render_pending(destination):
    st.title(destination)
    st.info("Team analysis integration pending.")
    st.write("The responsible teammates' validated components will be integrated here. No domain findings or recommendations are published yet.")
