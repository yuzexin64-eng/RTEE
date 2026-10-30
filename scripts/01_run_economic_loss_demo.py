"""Reproduce the *methodological chain* of the RTEE short-run economic module.

This script is a transparent, executable illustration of the equations in the
RTEE manuscript (economic module) and Supplementary Note 6. It does NOT
reproduce the article's numerical results: the bundled OD flows and GDP values
are synthetic, and rainfall/control sample selection is an upstream step.

Inputs (preprocessed by the analyst):
  - One row per intercity OD pair, with mean daily freight flows in the matched
    normal/control period and in the rainfall event period.
  - Annual 2023 city value added for transport, storage and postal services,
    denominated in RMB (not in 10^4 or 10^8 RMB).

Equations:
  dlnq_od   = ln[(q_rain_od + 1)/(q_normal_od + 1)]
  dln_tau   = -dlnq_od / theta
  phi_od    = q_normal_od / sum_all_OD(q_normal_od)
  dln_u_c   = -sum_{OD with destination c}(phi_od * dln_tau_od)
  GDProad_c = alpha_road * GDP_transport_storage_postal_c
  Ldaily_c  = (GDProad_c / 365) * (1 - exp(dln_u_c))
  Levent_c  = event_days * Ldaily_c

The manuscript's route-to-city rule is 'o -> d = c' (destination city).
Signed negative values are retained for routes/cities with increased flows;
this script does not silently truncate gains to zero.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

OD_COLUMNS = ("origin_city", "destination_city", "q_normal", "q_rain")
GDP_COLUMNS = ("city", "transport_storage_postal_value_added_rmb_2023")


def _require_columns(df: pd.DataFrame, required: tuple[str, ...], name: str) -> None:
    missing = sorted(set(required).difference(df.columns))
    if missing:
        raise ValueError(f"{name} is missing required columns: {missing}")


def _numeric_nonnegative(df: pd.DataFrame, column: str, name: str) -> None:
    values = pd.to_numeric(df[column], errors="coerce")
    if values.isna().any() or not np.isfinite(values.to_numpy()).all() or (values < 0).any():
        raise ValueError(f"{name}.{column} must contain finite, nonnegative values")
    df[column] = values.astype(float)


def compute_economic_disturbance(
    od: pd.DataFrame,
    city_economy: pd.DataFrame,
    *,
    theta: float = 4.5,
    road_revenue_100m_rmb: float = 57080.2,
    sector_revenue_100m_rmb: float = 134758.9,
    event_days: int = 4,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return city-level monetary disturbances and OD-level diagnostics.

    q_normal and q_rain MUST be matched mean daily OD flows, after upstream
    rainfall-mask, time-window, and rain-free control selection. Missing OD
    observations must be resolved upstream; missing does not mean zero.

    The normal-flow shares are normalized across ALL supplied OD pairs, so
    inference for a national network requires the full relevant OD universe.
    """
    if not np.isfinite(theta) or theta <= 0:
        raise ValueError("theta must be finite and strictly positive")
    if not np.isfinite(road_revenue_100m_rmb) or road_revenue_100m_rmb <= 0:
        raise ValueError("road_revenue_100m_rmb must be finite and positive")
    if not np.isfinite(sector_revenue_100m_rmb) or sector_revenue_100m_rmb <= 0:
        raise ValueError("sector_revenue_100m_rmb must be finite and positive")
    if road_revenue_100m_rmb > sector_revenue_100m_rmb:
        raise ValueError("road-transport revenue cannot exceed total sector revenue")
    if isinstance(event_days, bool) or int(event_days) != event_days or event_days <= 0:
        raise ValueError("event_days must be a positive integer")

    routes = od.copy()
    cities = city_economy.copy()
    _require_columns(routes, OD_COLUMNS, "OD table")
    _require_columns(cities, GDP_COLUMNS, "city economic-base table")
    if routes.empty or cities.empty:
        raise ValueError("Both input tables must be nonempty")

    for col in ("origin_city", "destination_city"):
        if routes[col].isna().any() or routes[col].astype(str).str.strip().eq("").any():
            raise ValueError(f"OD table contains missing {col} values")
        routes[col] = routes[col].astype(str).str.strip()
    if cities["city"].isna().any() or cities["city"].astype(str).str.strip().eq("").any():
        raise ValueError("City economic-base table contains missing city values")
    cities["city"] = cities["city"].astype(str).str.strip()

    if routes.duplicated(["origin_city", "destination_city"]).any():
        raise ValueError("OD table must contain exactly one row per origin-destination pair")
    if (routes["origin_city"] == routes["destination_city"]).any():
        raise ValueError("Only intercity OD pairs are supported (origin != destination)")
    if cities["city"].duplicated().any():
        raise ValueError("City economic-base table must contain one row per city")

    for col in ("q_normal", "q_rain"):
        _numeric_nonnegative(routes, col, "OD table")
    gdp_col = "transport_storage_postal_value_added_rmb_2023"
    _numeric_nonnegative(cities, gdp_col, "city economic-base table")

    # Paper: baseline OD share is computed across the whole reference network.
    total_normal_flow = routes["q_normal"].sum()
    if not np.isfinite(total_normal_flow) or total_normal_flow <= 0:
        raise ValueError("The total normal-period OD flow must be positive")

    missing_dest = sorted(set(routes["destination_city"]) - set(cities["city"]))
    if missing_dest:
        raise ValueError(f"Missing economic-base values for destination cities: {missing_dest}")

    routes["delta_ln_q"] = np.log1p(routes["q_rain"]) - np.log1p(routes["q_normal"])
    routes["delta_ln_transport_cost"] = -routes["delta_ln_q"] / theta
    routes["baseline_od_weight"] = routes["q_normal"] / total_normal_flow
    routes["weighted_transport_cost_shock"] = (
        routes["baseline_od_weight"] * routes["delta_ln_transport_cost"]
    )

    # Manuscript: Δln(u_c) = -Σ_{o→d=c} φ_od Δln(τ_od).
    city_shocks = (
        routes.groupby("destination_city", as_index=False)["weighted_transport_cost_shock"]
        .sum()
        .rename(columns={"destination_city": "city"})
    )
    city_shocks["delta_ln_welfare"] = -city_shocks["weighted_transport_cost_shock"]

    result = cities[["city", gdp_col]].merge(
        city_shocks[["city", "delta_ln_welfare"]], on="city", how="left", validate="one_to_one"
    )
    # Cities with no incoming routes have zero shock in this reduced-form rule.
    result["delta_ln_welfare"] = result["delta_ln_welfare"].fillna(0.0)
    alpha_road = road_revenue_100m_rmb / sector_revenue_100m_rmb
    result["road_transport_revenue_share"] = alpha_road
    result["road_transport_value_added_rmb_2023"] = result[gdp_col] * alpha_road
    result["road_transport_value_added_rmb_per_day"] = (
        result["road_transport_value_added_rmb_2023"] / 365.0
    )
    # Signed short-run gross output disturbance; do not clip gains to zero.
    result["output_disturbance_rmb_per_day"] = (
        result["road_transport_value_added_rmb_per_day"]
        * (-np.expm1(result["delta_ln_welfare"]))
    )
    result["output_disturbance_rmb_event"] = (
        result["output_disturbance_rmb_per_day"] * event_days
    )
    result["theta"] = float(theta)
    result["event_days"] = int(event_days)

    return result.sort_values("city").reset_index(drop=True), routes.sort_values(
        ["origin_city", "destination_city"]
    ).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/economic_loss_config.yaml")
    parser.add_argument("--theta", type=float, default=None, help="Override configured elasticity")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    cfg_path = Path(args.config)
    if not cfg_path.is_absolute():
        cfg_path = root / cfg_path
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    inputs = cfg["input_files"]
    settings = cfg["economic_module"]
    od = pd.read_csv(root / inputs["od_period_mean_flows"])
    city_economy = pd.read_csv(root / inputs["city_economic_base"])
    theta = settings["theta"] if args.theta is None else args.theta
    cities, routes = compute_economic_disturbance(
        od,
        city_economy,
        theta=float(theta),
        road_revenue_100m_rmb=float(settings["road_revenue_100m_rmb_2023"]),
        sector_revenue_100m_rmb=float(settings["sector_revenue_100m_rmb_2023"]),
        event_days=int(settings["event_days"]),
    )
    city_out = root / cfg["output_files"]["city_economic_disturbance"]
    od_out = root / cfg["output_files"]["od_diagnostics"]
    city_out.parent.mkdir(parents=True, exist_ok=True)
    od_out.parent.mkdir(parents=True, exist_ok=True)
    cities.to_csv(city_out, index=False, encoding="utf-8-sig")
    routes.to_csv(od_out, index=False, encoding="utf-8-sig")
    print(f"Wrote {city_out}")
    print(f"Wrote {od_out}")
    print(f"Illustrative signed daily total (RMB): {cities['output_disturbance_rmb_per_day'].sum():,.2f}")
    print(f"Illustrative signed event total (RMB): {cities['output_disturbance_rmb_event'].sum():,.2f}")
    print("Synthetic demo outputs are NOT the paper's empirical estimates.")


if __name__ == "__main__":
    main()
