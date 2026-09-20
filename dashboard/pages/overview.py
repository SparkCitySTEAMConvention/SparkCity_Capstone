"""Landing-page UI only. Navigation cards and future team-result slots."""
import base64
import io
from functools import lru_cache
from html import escape
from pathlib import Path

import streamlit as st
from PIL import Image

from components.shared import STYLES_PATH, open_page, read_css
from components.planner_scores import load_scores

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
HERO_IMAGE_PATH = ASSETS_DIR / "updated_hero.png"  # hero background swapped from city.png (2026-09-19); city.png itself is untouched
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
            img = img.resize(
                (DOMAIN_IMAGE_MAX_WIDTH, new_height),
                Image.Resampling.LANCZOS
            )
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
    {"title": "Mobility & Traffic", "description": "Understand how people move through New York Digital City.", "icon": "🚘", "accent": "#337bc0", "destination": "Mobility & Traffic", "image": "mobility_traffic.png"},
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
    # Corner radius rounded 14px->20px (2026-09-17) to match reference image; border
    # color/thickness stay each card's own accent, unchanged.
    # Resting box-shadow scaled back down (2026-09-17) from a bright neon-style glow
    # to a subtle neutral depth shadow, per request; border color (not the shadow)
    # now carries each card's accent identity.
    card_wrapper_css = "".join(
        f".st-key-domain_card_{i} {{border:1.5px solid {c['accent']};border-radius:20px;overflow:hidden;background:#182430;"
        f"box-shadow:0 4px 14px rgba(16,41,68,.10);"
        f"transition:transform .2s ease, box-shadow .2s ease, border-color .2s ease;}}\n"
        f".st-key-domain_card_{i}:hover {{transform:translateY(-5px);box-shadow:0 14px 30px rgba(16,41,68,.2);"
        f"border-color:color-mix(in srgb,{c['accent']} 70%, black);}}\n"
        # Explore-button footer recolored from Streamlit's default gray to a pale
        # per-card accent tint (2026-09-17, per request; tint strengthened 14%->24%
        # same day after it read too faint). !important beats Streamlit's own button
        # theme rule, which otherwise outweighs the plain .st-key-overview_domains
        # button selector below. Parent's overflow:hidden + border-radius already clips
        # this into the matching rounded bottom corners, so no radius needed here.
        f".st-key-domain_card_{i} [data-testid='stElementContainer']:has(button),"
        f".st-key-domain_card_{i} button {{background:color-mix(in srgb,{c['accent']} 24%,#182430) !important;}}\n"
        for i, c in enumerate(DOMAINS)
    )
    # The hero rule needs the runtime hero image data URI, so it can't live in the
    # static styles.css file. It's combined with the static "overview" section and
    # injected in exactly one st.markdown call: each such call is its own zero-height
    # flex sibling in the surrounding layout, so more calls than the original single
    # style block would silently reintroduce gaps between the real page sections.
    # Hero's margin-bottom cut 24px->6px (2026-09-17, per request) to close the
    # excessive gap above "Explore SparkCity"; see the matching h2#explore-sparkcity
    # padding-top cut in styles.css's "overview" section for the other half of it.
    # Compact pass (2026-09-17, same day): padding 64px->36px top/bottom (56px
    # left/right unchanged, so width/horizontal layout is untouched) and
    # min-height 460px->340px. Background image/size/position, overlay gradient,
    # rounded corners are unchanged. Hero no longer pulls up under the navbar
    # (margin-top:-32px -> 0) and its top corners are now fully rounded
    # (border-radius:0 0 18px 18px -> 18px) now that Overview's navbar uses
    # the same shared geometry as every other page instead of a flush,
    # zero-margin fusion with the hero.
    with st.container(key="overview_hero"):
        # Style block deliberately lives inside this container, as its first
        # child, rather than before it (2026-09-18): keeps this hero as
        # sparkcity_page_content's first-and-only top-level child on refresh,
        # with no style-only sibling ahead of it consuming a shared-container
        # gap — same structural pattern Environment already uses successfully.
        # CSS scoping is selector-based, not position-based, so this changes
        # nothing about what's styled, only which gap this element consumes.
        st.markdown(f'''<style>
{read_css(STYLES_PATH, section="overview")}
.st-key-overview_hero {{position:relative;margin-top:0;background:linear-gradient(90deg,rgba(6,14,30,.90) 0%,rgba(6,14,30,.78) 26%,rgba(6,14,30,.42) 50%,rgba(6,14,30,.12) 70%,rgba(6,14,30,0) 85%),url('{_hero_image_data_uri()}');background-size:cover;background-position:center;background-repeat:no-repeat;border-radius:18px;padding:36px 56px;min-height:340px;margin-bottom:6px;color:white;overflow:hidden;}}
{card_wrapper_css}
</style>''', unsafe_allow_html=True)
        intro, mission = st.columns([1.8, 1], gap="large")
        with intro:
            st.markdown('<span class="overview-eyebrow">WELCOME TO</span>', unsafe_allow_html=True)
            # Hero title "SparkCity" -> "New York Digital City" (2026-09-19); same white + blue-accent split.
            st.markdown('<h1>New York <span class="title-accent">Digital City</span></h1>', unsafe_allow_html=True)
            st.subheader("Data-Driven Decisions for a Stronger Tomorrow")
            st.write("Explore real city data to plan a successful and sustainable STEAM convention.")
            st.markdown('<div class="overview-actions"><a href="#explore-sparkcity">Explore the Data →</a><a href="#about-the-data">Learn More</a></div>', unsafe_allow_html=True)
        with mission:
            st.markdown('<div class="overview-mission"><h3>Our Mission</h3><p>Use real city data to support events that bring people, innovation, and opportunity to New York Digital City.</p></div>', unsafe_allow_html=True)
    st.header("Explore New York Digital City", anchor="explore-sparkcity")
    st.write("Dive into key aspects of the city to understand opportunities and plan the best STEAM convention.")
    with st.container(key="overview_domains"):
        for index, (column, card) in enumerate(zip(st.columns(4), DOMAINS)):
            with column:
                render_domain_card(index, card)
    render_suitability()
    # "About the Data" expander (+ its #about-the-data anchor spacer) removed (2026-09-19); page now ends after the footer.
    st.markdown('<footer class="overview-footer"><div><strong>New York Digital City</strong><br>People • Innovation • Opportunity</div><div>“Data today. A brighter tomorrow.”</div></footer>', unsafe_allow_html=True)


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
    """Display the team's final convention recommendation using planner results."""

    try:
        monthly = load_scores("Monthly")

        november = monthly.loc[
            monthly["start_date"].dt.month == 11
        ].iloc[0]

        alternative_months = monthly.loc[
            monthly["start_date"].dt.month != 11
        ]

        alternative = alternative_months.loc[
            alternative_months["suitability"].idxmax()
        ]

        recommended_month = "November"
        alternative_month = alternative["start_date"].strftime("%B")
        recommended_score = float(november["suitability"])

    except (OSError, ValueError, KeyError, IndexError):
        recommended_month = "Unavailable"
        alternative_month = "Unavailable"
        recommended_score = None

    with st.container(key="overview_plan"):
        intro, slots = st.columns([1.1, 2], gap="large")

        with intro:
            st.markdown(
                '<div class="plan-heading">'
                '<span class="plan-icon">📅</span>'
                '<h3>Plan the STEAM Convention</h3>'
                '</div>',
                unsafe_allow_html=True,
            )

            st.write(
                "Combine insights from across New York Digital City to identify "
                "the best time and strategy for a successful STEAM convention."
            )

            st.button(
                "Go to Convention Planner →",
                on_click=open_page,
                args=("Convention Planner",),
                width="stretch",
            )

            st.markdown(
                '''<div class="plan-highlights">
<span class="plan-highlight-item">
<span class="plan-highlight-icon plan-highlight-icon-blue">📊</span>Data-driven insights
</span>
<span class="plan-highlight-item">
<span class="plan-highlight-icon plan-highlight-icon-lavender">👥</span>Cross-domain analysis
</span>
<span class="plan-highlight-item">
<span class="plan-highlight-icon plan-highlight-icon-yellow">💡</span>Smarter planning
</span>
</div>''',
                unsafe_allow_html=True,
            )

        with slots:
            score_display = (
                f"{recommended_score:.2f}"
                if recommended_score is not None
                else "Unavailable"
            )

            cards = [
                (
                    "🏆",
                    "Recommended Month",
                    recommended_month,
                    "Team Recommendation",
                    "gold",
                ),
                (
                    "📅",
                    "Alternative Month",
                    alternative_month,
                    "Next Best Option",
                    "mint",
                ),
                (
                    "📊",
                    f"{recommended_month} Suitability Score",
                    score_display,
                    "0–100 Scale",
                    "lavender",
                ),
            ]

            for column, (icon, title, value, status, tint) in zip(
                st.columns(3), cards
            ):
                with column:
                    st.markdown(
                        f'''<div class="plan-card plan-card-{tint}">
<span class="plan-card-icon">{icon}</span>
<div class="plan-card-title">{title}</div>
<div class="plan-card-value">{value}</div>
<span class="plan-card-status">{status}</span>
</div>''',
                        unsafe_allow_html=True,
                    )


def render_pending(destination):
    st.title(destination)
    st.info("Team analysis integration pending.")
    st.write("The responsible teammates' validated components will be integrated here. No domain findings or recommendations are published yet.")
