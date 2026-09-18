"""Checks for the approved exports and planner interactions; no database needed."""
import sys
import unittest
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dashboard"))
from components.planner_scores import load_scores, monthly_explorer_scores, adjusted_scores


class PlannerScoresTests(unittest.TestCase):
    def test_export_periods_and_totals(self):
        for period, count in [("Monthly", 12), ("Weekly", 51), ("Daily", 365)]:
            with self.subTest(period=period):
                frame = load_scores(period)
                self.assertEqual(len(frame), count)
                column = "score_date" if period == "Daily" else "start_date"
                frequency = {"Monthly": "MS", "Weekly": "W-MON", "Daily": "D"}[period]
                start = "2025-01-06" if period == "Weekly" else "2025-01-01"
                expected = pd.date_range(start, periods=count, freq=frequency)
                self.assertEqual(frame[column].tolist(), expected.tolist())
                recalculated = (frame.capacity * .30 + frame.fiscal * .30
                                + frame.air_quality * .15 + frame.weather * .15
                                + frame.energy * .10)
                self.assertTrue((recalculated - frame.suitability).abs().le(.011).all())

    def test_zero_adjustment_preserves_exported_totals(self):
        scores = monthly_explorer_scores(load_scores("Monthly"))
        values, weights = adjusted_scores(scores, 0)
        pd.testing.assert_series_equal(values, scores["Baseline score"])
        self.assertAlmostEqual(sum(weights.values()), 1)
        for adjustment in [-15, -10, 10, 15]:
            values, weights = adjusted_scores(scores, adjustment)
            self.assertAlmostEqual(sum(weights.values()), 1)
            self.assertTrue(values.between(0, 100).all())
        scores.loc[0, "Energy"] = float("nan")
        self.assertTrue(pd.isna(adjusted_scores(scores, 10)[0].iloc[0]))

    def test_page_renders_and_updates(self):
        script = "from pages.convention_planner import render_convention_planner\nrender_convention_planner()"
        app = AppTest.from_string(script).run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual([tab.label for tab in app.tabs], ["Monthly", "Weekly", "Daily", "Scoring method"])
        self.assertIn("65.08", [metric.value for metric in app.metric])
        self.assertIn("59.80", [metric.value for metric in app.metric])
        app.select_slider(key="explorer_adjustment").set_value(10).run()
        self.assertEqual(len(app.exception), 0)
        app.selectbox(key="explorer_month").select("February").run()
        self.assertEqual(len(app.exception), 0)
        app.select_slider(key="explorer_adjustment").set_value(0).run()
        self.assertEqual(len(app.exception), 0)
        adjusted = next(metric for metric in app.metric if metric.label == "Adjusted score")
        self.assertEqual(adjusted.value, "25.24")


if __name__ == "__main__":
    unittest.main()
