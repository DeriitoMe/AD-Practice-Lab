import itertools
import json
import unittest
from decimal import Decimal

from lab import metrics
from simulation import DEFAULT_CONFIG, simulate


class SimulationTests(unittest.TestCase):
    def test_deterministic_and_no_mutation(self):
        config = {**DEFAULT_CONFIG, "budget": "1250.37"}
        original = dict(config)
        a, b = simulate(config), simulate(config)
        self.assertEqual(a, b)
        self.assertEqual(config, original)
        self.assertEqual(a["metrics"], metrics(a["totals"]))
        self.assertEqual(json.loads(json.dumps(a, allow_nan=False)), a)

    def test_defaults_and_equivalent_budget_types(self):
        self.assertEqual(simulate({}), simulate(DEFAULT_CONFIG))
        for budget in (1000, 1000.0, "1000.00", Decimal("1000.00")):
            self.assertEqual(simulate({"budget": budget}), simulate({}))

    def test_all_strategy_boundaries_budget_and_funnel(self):
        for budget, audience, creative, landing, bid in itertools.product(
                (100, 100.01, 999.99, 50000), ("broad", "focused"),
                ("feature", "benefit", "story"), ("basic", "clear"),
                ("balanced", "reach")):
            config = dict(budget=budget, audience=audience, creative=creative,
                          landing=landing, bid=bid)
            with self.subTest(config=config):
                result = simulate(config)
                t = result["totals"]
                counts = [t[k] for k in ("impressions", "clicks", "landing_views", "purchases")]
                self.assertTrue(all(type(n) is int and n >= 0 for n in counts))
                self.assertEqual(counts, sorted(counts, reverse=True))
                self.assertLessEqual(Decimal(str(t["spend"])), Decimal(str(budget)))
                self.assertGreaterEqual(t["spend"], 0)
                self.assertLess(Decimal(str(budget)) - Decimal(str(t["spend"])),
                                Decimal(str(result["model"]["cpm"])) / 1000 + Decimal("0.01"))
                self.assertEqual(t["revenue"], t["purchases"] * 199)
                self.assertEqual(t["variable_cost"], t["purchases"] * 99)
                self.assertEqual([f["count"] for f in result["funnel"]], counts)

    def test_zero_purchase_is_not_zero_cpa(self):
        result = simulate(dict(budget=100, audience="broad", creative="story",
                               landing="basic", bid="reach"))
        self.assertEqual(result["totals"]["purchases"], 0)
        self.assertEqual(result["totals"]["revenue"], 0)
        self.assertEqual(result["totals"]["variable_cost"], 0)
        self.assertIsNone(result["metrics"]["cpa"])
        self.assertEqual(result["metrics"]["roas"], 0)
        self.assertTrue(any("不可计算" in note for note in result["insights"]))

    def test_teaching_tradeoffs_are_consistent(self):
        base = simulate({})["totals"]
        story = simulate({"creative": "story"})["totals"]
        reach = simulate({"bid": "reach"})["totals"]
        basic = simulate({"landing": "basic"})["totals"]
        self.assertGreater(story["clicks"], base["clicks"])
        self.assertLess(story["purchases"], base["purchases"])
        self.assertGreater(reach["impressions"], base["impressions"])
        self.assertLess(reach["purchases"], base["purchases"])
        self.assertLess(basic["landing_views"], base["landing_views"])
        self.assertLess(basic["purchases"], base["purchases"])

    def test_reject_invalid_budgets(self):
        invalid = (99.99, 50000.01, -1, 0, True, False, None, [], {}, "", "abc",
                   "100.001", float("nan"), float("inf"), float("-inf"),
                   "NaN", "Infinity", Decimal("NaN"), "1e10000")
        for budget in invalid:
            with self.subTest(budget=budget), self.assertRaises(ValueError):
                simulate({"budget": budget})

    def test_reject_unknown_keys_values_and_types(self):
        invalid = (None, [], "", {"unexpected": 1}, {"audience": "all"},
                   {"creative": "unknown"}, {"landing": "fast"},
                   {"bid": "cheap"}, {"audience": []}, {"creative": None},
                   {"landing": float("nan")}, {"bid": True})
        for config in invalid:
            with self.subTest(config=config), self.assertRaises(ValueError):
                simulate(config)

    def test_model_explains_fiction_and_formula(self):
        result = simulate({})
        self.assertIn("纯虚拟", result["label"])
        self.assertGreaterEqual(len(result["model_assumptions"]), 8)
        self.assertAlmostEqual(result["model"]["cpm"], 24)
        self.assertAlmostEqual(result["model"]["ctr"], .012 * 1.1)
        self.assertAlmostEqual(result["model"]["arrival_rate"], .92)
        self.assertAlmostEqual(result["model"]["purchase_rate_after_arrival"], .05 * 1.15)
        self.assertIsNone(result["funnel"][0]["rate_from_previous"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
