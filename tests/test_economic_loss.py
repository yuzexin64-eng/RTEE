"""Tests for the RTEE manuscript-aligned illustrative economic module."""

import importlib.util
import math
from pathlib import Path
import unittest

import pandas as pd

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "01_run_economic_loss_demo.py"
spec = importlib.util.spec_from_file_location("rtee_economic", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def city_base(cities):
    return pd.DataFrame({
        "city": cities,
        "transport_storage_postal_value_added_rmb_2023": [365_000_000.0] * len(cities),
    })


class EconomicLossTests(unittest.TestCase):
    def test_single_route_exact_manuscript_equations(self):
        od = pd.DataFrame({"origin_city": ["A"], "destination_city": ["B"],
                           "q_normal": [100.0], "q_rain": [80.0]})
        cities, routes = module.compute_economic_disturbance(od, city_base(["B"]))
        dlnq = math.log(81.0 / 101.0)
        alpha = 57080.2 / 134758.9
        expected = alpha * 1_000_000.0 * (1 - math.exp(dlnq / 4.5))
        self.assertAlmostEqual(routes.loc[0, "baseline_od_weight"], 1.0)
        self.assertAlmostEqual(routes.loc[0, "delta_ln_transport_cost"], -dlnq / 4.5)
        self.assertAlmostEqual(cities.loc[0, "delta_ln_welfare"], dlnq / 4.5)
        self.assertAlmostEqual(cities.loc[0, "output_disturbance_rmb_per_day"], expected)
        self.assertAlmostEqual(cities.loc[0, "output_disturbance_rmb_event"], 4 * expected)

    def test_weights_normalized_across_all_routes_and_by_destination(self):
        od = pd.DataFrame({"origin_city": ["A", "C"], "destination_city": ["B", "B"],
                           "q_normal": [30.0, 70.0], "q_rain": [15.0, 70.0]})
        cities, routes = module.compute_economic_disturbance(od, city_base(["B"]))
        self.assertAlmostEqual(routes["baseline_od_weight"].sum(), 1.0)
        expected_welfare = 0.3 * math.log(16.0 / 31.0) / 4.5
        self.assertAlmostEqual(cities.loc[0, "delta_ln_welfare"], expected_welfare)

    def test_increased_flow_is_signed_gain_not_clipped(self):
        od = pd.DataFrame({"origin_city": ["A"], "destination_city": ["B"],
                           "q_normal": [10.0], "q_rain": [20.0]})
        cities, _ = module.compute_economic_disturbance(od, city_base(["B"]))
        self.assertLess(cities.loc[0, "output_disturbance_rmb_per_day"], 0)

    def test_missing_destination_gdp_rejected(self):
        od = pd.DataFrame({"origin_city": ["A"], "destination_city": ["B"],
                           "q_normal": [10.0], "q_rain": [9.0]})
        with self.assertRaisesRegex(ValueError, "Missing economic-base"):
            module.compute_economic_disturbance(od, city_base(["A"]))

    def test_duplicate_od_rejected(self):
        od = pd.DataFrame({"origin_city": ["A", "A"], "destination_city": ["B", "B"],
                           "q_normal": [10.0, 10.0], "q_rain": [9.0, 9.0]})
        with self.assertRaisesRegex(ValueError, "exactly one row"):
            module.compute_economic_disturbance(od, city_base(["B"]))

    def test_negative_and_nan_flows_rejected(self):
        for q in (-1, float("nan")):
            with self.subTest(q=q):
                od = pd.DataFrame({"origin_city": ["A"], "destination_city": ["B"],
                                   "q_normal": [10.0], "q_rain": [q]})
                with self.assertRaisesRegex(ValueError, "finite, nonnegative"):
                    module.compute_economic_disturbance(od, city_base(["B"]))

    def test_zero_baseline_route_has_zero_weight(self):
        od = pd.DataFrame({"origin_city": ["A", "C"], "destination_city": ["B", "B"],
                           "q_normal": [0.0, 10.0], "q_rain": [20.0, 8.0]})
        _, routes = module.compute_economic_disturbance(od, city_base(["B"]))
        self.assertEqual(routes.loc[0, "baseline_od_weight"], 0.0)
        self.assertEqual(routes.loc[0, "weighted_transport_cost_shock"], 0.0)

    def test_theta_sensitivity(self):
        od = pd.DataFrame({"origin_city": ["A"], "destination_city": ["B"],
                           "q_normal": [100.0], "q_rain": [80.0]})
        low_theta, _ = module.compute_economic_disturbance(od, city_base(["B"]), theta=3.0)
        high_theta, _ = module.compute_economic_disturbance(od, city_base(["B"]), theta=6.0)
        self.assertGreater(low_theta.loc[0, "output_disturbance_rmb_per_day"],
                           high_theta.loc[0, "output_disturbance_rmb_per_day"])


if __name__ == "__main__":
    unittest.main()
