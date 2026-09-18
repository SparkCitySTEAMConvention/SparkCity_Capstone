"""Illustrated current-weather scene for the Environment page."""

from html import escape

import streamlit as st


def render_weather_scene(description: str) -> None:
    """Show a compact animated scene matching the modeled condition."""
    condition = description.lower()
    if "thunder" in condition:
        kind, label = "storm", "Storm clouds with rain"
    elif "snow" in condition:
        kind, label = "snow", "Clouds with falling snow"
    elif "rain" in condition or "shower" in condition:
        kind, label = "rain", "Clouds with falling rain"
    elif "cloud" in condition:
        kind, label = "cloudy", "Sun behind drifting clouds"
    else:
        kind, label = "clear", "Glowing sun"

    drops = "".join("<i></i>" for _ in range(12))
    st.html(
        f"""
        <style>
          .environment-scene {{
            position: relative; height: 150px; overflow: hidden;
            border-radius: 16px;
            background: linear-gradient(145deg, #294966, #5c809b 70%, #a6bbca);
          }}
          .environment-scene .sun {{
            position: absolute; left: 49%; top: 23px;
            width: 70px; height: 70px; border-radius: 50%;
            background: radial-gradient(circle at 35% 35%, #fff4b5, #f8a52c 72%);
            box-shadow: 0 0 34px 15px #ffd27088;
            animation: env-glow 3s ease-in-out infinite alternate;
          }}
          .environment-scene .cloud {{
            position: absolute; left: 42%; top: 88px;
            width: 130px; height: 36px; border-radius: 25px;
            background: #edf3f8;
            filter: drop-shadow(0 8px 10px #20385055);
            animation: env-drift 5s ease-in-out infinite alternate;
          }}
          .environment-scene .cloud::before,
          .environment-scene .cloud::after {{
            content: ""; position: absolute; border-radius: 50%;
            background: inherit;
          }}
          .environment-scene .cloud::before {{
            width: 65px; height: 65px; left: 19px; top: -35px;
          }}
          .environment-scene .cloud::after {{
            width: 51px; height: 51px; right: 19px; top: -26px;
          }}
          .environment-scene .horizon {{
            position: absolute; bottom: -28px; left: -5%;
            width: 110%; height: 52px; border-radius: 50%;
            background: #304d69;
          }}
          .environment-scene .precipitation {{
            position: absolute; left: 43%; top: 113px;
            display: flex; gap: 8px;
          }}
          .environment-scene .precipitation i {{
            display: block; width: 2px; height: 12px;
            border-radius: 4px; background: #d3eeff;
            animation: env-fall 1.1s linear infinite;
          }}
          .environment-scene .precipitation i:nth-child(3n) {{
            animation-delay: -.5s;
          }}
          .environment-scene .precipitation i:nth-child(3n + 1) {{
            animation-delay: -.8s;
          }}
          .environment-scene.snow .precipitation i {{
            width: 5px; height: 5px; border-radius: 50%;
            background: white; animation-duration: 2s;
          }}
          .environment-scene.clear .cloud,
          .environment-scene.clear .precipitation,
          .environment-scene.cloudy .precipitation {{
            display: none;
          }}
          .environment-scene.rain .sun,
          .environment-scene.snow .sun,
          .environment-scene.storm .sun {{
            display: none;
          }}
          .environment-scene.storm {{ background: #283c59; }}
          .environment-scene.storm .cloud {{ background: #aab9cb; }}
          @keyframes env-glow {{
            to {{ transform: scale(1.07); box-shadow: 0 0 42px 22px #ffd270aa; }}
          }}
          @keyframes env-drift {{ to {{ transform: translateX(16px); }} }}
          @keyframes env-fall {{
            to {{ transform: translateY(20px); opacity: 0; }}
          }}
          @media (prefers-reduced-motion: reduce) {{
            .environment-scene *, .environment-scene *::before,
            .environment-scene *::after {{ animation: none !important; }}
          }}
        </style>
        <div class="environment-scene {kind}" role="img"
             aria-label="{escape(label)}">
          <span class="sun"></span>
          <span class="cloud"></span>
          <span class="precipitation">{drops}</span>
          <span class="horizon"></span>
        </div>
        """
    )
