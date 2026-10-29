"""Run the RTEE direct economic-loss workflow.

The script joins GPS-point samples with vehicle attributes, derives freight
activity and speed changes across event windows, and calculates a city-level
direct economic-loss proxy.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


def resolve(root: Path, p: str) -> Path:
    return root / p


def load_config(path: Path) -> dict:
    if yaml is not None:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    text = path.read_text(encoding="utf-8").splitlines()
    values = {}
    section = None
    for line in text:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and line.rstrip().endswith(":"):
            section = line.strip()[:-1]
            values[section] = {}
            continue
        if section and ":" in line:
            key, value = line.strip().split(":", 1)
            value = value.strip()
            if value:
                values[section][key] = value
    return {
        "input_files": {
            "gps_points": values["input_files"]["gps_points"],
            "vehicle_static": values["input_files"]["vehicle_static"],
        },
        "output_files": {
            "city_economic_loss": values["output_files"].get("city_economic_loss", "outputs/demo/city_economic_loss.csv"),
        },
        "event_windows": {
            "pre_event": {"start": "2023-09-18 00:00:00", "end": "2023-09-18 23:59:59"},
            "rainfall_period": {"start": "2023-09-19 00:00:00", "end": "2023-09-19 23:59:59"},
        },
    }


def assign_event_window(df: pd.DataFrame, cfg: dict) -> pd.Series:
    result = pd.Series("outside_window", index=df.index)
    for name, window in cfg["event_windows"].items():
        start = pd.to_datetime(window["start"])
        end = pd.to_datetime(window["end"])
        result.loc[df["timestamp_rounded"].between(start, end, inclusive="both")] = name
    return result


def haversine_scalar(lon1, lat1, lon2, lat2):
    radius = 6371.0088
    lon1, lat1, lon2, lat2 = [math.radians(float(v)) for v in [lon1, lat1, lon2, lat2]]
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(min(1, math.sqrt(max(0, a))))


def prepare_segments(gps: pd.DataFrame, static: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    df = gps.merge(static, on="plate_id_hash", how="left", validate="many_to_one")
    df["timestamp_rounded"] = pd.to_datetime(df["timestamp_rounded"])
    df["event_window"] = assign_event_window(df, cfg)
    df = df[df["event_window"].isin(["pre_event", "rainfall_period"])].copy()
    df = df.sort_values(["plate_id_hash", "timestamp_rounded"]).reset_index(drop=True)
    df["prev_lon"] = df.groupby(["plate_id_hash", "event_window"])["longitude_jittered"].shift(1)
    df["prev_lat"] = df.groupby(["plate_id_hash", "event_window"])["latitude_jittered"].shift(1)
    df["prev_time"] = df.groupby(["plate_id_hash", "event_window"])["timestamp_rounded"].shift(1)
    df["distance_km"] = [
        0.0 if pd.isna(plon) else haversine_scalar(plon, plat, lon, lat)
        for plon, plat, lon, lat in zip(df["prev_lon"], df["prev_lat"], df["longitude_jittered"], df["latitude_jittered"])
    ]
    df["duration_min"] = (df["timestamp_rounded"] - df["prev_time"]).dt.total_seconds().div(60).fillna(0).clip(lower=0)
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/demo_config.yaml")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    cfg = load_config(resolve(root, args.config))

    gps = pd.read_csv(resolve(root, cfg["input_files"]["gps_points"]))
    static = pd.read_csv(resolve(root, cfg["input_files"]["vehicle_static"]))
    seg = prepare_segments(gps, static, cfg)

    activity = (
        seg.groupby(["city_code_masked", "event_window"], as_index=False)
        .agg(
            vehicle_count=("plate_id_hash", "nunique"),
            point_count=("plate_id_hash", "count"),
            activity_distance_km=("distance_km", "sum"),
            activity_duration_min=("duration_min", "sum"),
            mean_speed_kmh=("speed_kmh", "mean"),
        )
    )

    wide = activity.pivot(index="city_code_masked", columns="event_window")
    wide.columns = [f"{metric}_{window}" for metric, window in wide.columns]
    wide = wide.reset_index()

    # Example baseline transport-GDP values used by the city-level workflow.
    demo_gdp = {
        "CN_DEMO_4101": 12_000_000.0,
        "CN_DEMO_4102": 9_000_000.0,
        "CN_DEMO_4103": 6_000_000.0,
    }
    wide["baseline_transport_gdp_demo"] = wide["city_code_masked"].map(demo_gdp).fillna(5_000_000.0)

    pre_distance = wide["activity_distance_km_pre_event"].replace(0, pd.NA)
    rain_distance = wide["activity_distance_km_rainfall_period"]
    pre_speed = wide["mean_speed_kmh_pre_event"].replace(0, pd.NA)
    rain_speed = wide["mean_speed_kmh_rainfall_period"]

    wide["freight_activity_change_pct_demo"] = (rain_distance - pre_distance) / pre_distance
    wide["speed_change_pct_demo"] = (rain_speed - pre_speed) / pre_speed
    wide["freight_activity_reduction_demo"] = (-wide["freight_activity_change_pct_demo"]).clip(lower=0).fillna(0)
    wide["speed_reduction_demo"] = (-wide["speed_change_pct_demo"]).clip(lower=0).fillna(0)
    wide["direct_loss_shock_index_demo"] = 0.7 * wide["freight_activity_reduction_demo"] + 0.3 * wide["speed_reduction_demo"]
    wide["direct_economic_loss_proxy_demo"] = wide["baseline_transport_gdp_demo"] * wide["direct_loss_shock_index_demo"]

    out_path = resolve(root, cfg["output_files"]["city_economic_loss"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wide.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Wrote {out_path}")
    print(wide.to_string(index=False))


if __name__ == "__main__":
    main()
