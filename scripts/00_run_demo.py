"""Run the RTEE trajectory aggregation workflow.

The script assigns event windows to GPS-point samples and summarizes
vehicle movement and CO2 emissions by projected 10 km grid cell.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import CRS, Transformer

try:
    import yaml
except ModuleNotFoundError:  # Keep the public demo runnable before users create the conda env.
    yaml = None


def resolve(root: Path, p: str) -> Path:
    return root / p


def load_config(path: Path) -> dict:
    if yaml is not None:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    # Minimal fallback parser for config/demo_config.yaml.
    # It intentionally supports only the small demo config shipped here.
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
            "grid_daily_summary": values["output_files"]["grid_daily_summary"],
            "city_economic_loss": values["output_files"].get("city_economic_loss", "outputs/demo/city_economic_loss.csv"),
        },
        "event_windows": {
            "pre_event": {"start": "2023-09-18 00:00:00", "end": "2023-09-18 23:59:59"},
            "rainfall_period": {"start": "2023-09-19 00:00:00", "end": "2023-09-19 23:59:59"},
        },
    }


def assign_event_window(df: pd.DataFrame, cfg: dict) -> pd.Series:
    result = pd.Series("outside_window", index=df.index)
    windows = cfg.get("event_windows") or {
        "pre_event": {"start": "2023-09-18 00:00:00", "end": "2023-09-18 23:59:59"},
        "rainfall_period": {"start": "2023-09-19 00:00:00", "end": "2023-09-19 23:59:59"},
    }
    for name, window in windows.items():
        start = pd.to_datetime(window["start"])
        end = pd.to_datetime(window["end"])
        mask = df["timestamp_rounded"].between(start, end, inclusive="both")
        result.loc[mask] = name
    return result


def haversine_km(lon1, lat1, lon2, lat2):
    radius = 6371.0088
    lon1, lat1, lon2, lat2 = map(pd.to_numeric, [lon1, lat1, lon2, lat2])
    phi1 = lon1 * 0 + lat1.map(lambda x: x * 3.141592653589793 / 180.0)
    phi2 = lon2 * 0 + lat2.map(lambda x: x * 3.141592653589793 / 180.0)
    dphi = (lat2 - lat1) * 3.141592653589793 / 180.0
    dlambda = (lon2 - lon1) * 3.141592653589793 / 180.0
    a = (dphi / 2).map(lambda x: __import__("math").sin(x) ** 2) + phi1.map(__import__("math").cos) * phi2.map(__import__("math").cos) * (dlambda / 2).map(lambda x: __import__("math").sin(x) ** 2)
    return 2 * radius * a.map(lambda x: __import__("math").asin(min(1, __import__("math").sqrt(max(0, x)))))


def demo_emission_factor_g_per_km(row):
    # Estimate a demonstration emission factor from fuel type and gross vehicle weight.
    fuel = str(row.get("fuel_type", "")).lower()
    gross = float(row.get("gross_weight_kg", 0) or 0)
    if "lng" in fuel:
        base = 620.0
    else:
        base = 820.0
    if gross >= 35000:
        return base * 1.12
    if gross >= 18000:
        return base
    return base * 0.72


def assign_10km_grid(df: pd.DataFrame) -> pd.Series:
    """Assign GPS points to 10 km x 10 km cells in a local projected CRS."""
    local_crs = CRS.from_proj4(
        "+proj=tmerc +lat_0=34.7 +lon_0=113.9 +k=1 "
        "+x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
    )
    transformer = Transformer.from_crs("EPSG:4326", local_crs, always_xy=True)
    x, y = transformer.transform(
        pd.to_numeric(df["longitude_jittered"]).to_numpy(),
        pd.to_numeric(df["latitude_jittered"]).to_numpy(),
    )

    grid_x = np.floor(np.asarray(x) / 10_000).astype(int)
    grid_y = np.floor(np.asarray(y) / 10_000).astype(int)
    return pd.Series(
        [f"G_X{ix}_Y{iy}" for ix, iy in zip(grid_x, grid_y)],
        index=df.index,
        dtype="string",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/demo_config.yaml")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    cfg = load_config(resolve(root, args.config))

    gps = pd.read_csv(resolve(root, cfg["input_files"]["gps_points"]))
    static = pd.read_csv(resolve(root, cfg["input_files"]["vehicle_static"]))
    df = gps.merge(static, on="plate_id_hash", how="left", validate="many_to_one")
    df["timestamp_rounded"] = pd.to_datetime(df["timestamp_rounded"])
    df = df.sort_values(["plate_id_hash", "timestamp_rounded"]).reset_index(drop=True)
    df["event_window"] = assign_event_window(df, cfg)
    df = df[df["event_window"].isin(["pre_event", "rainfall_period"])].copy()
    df["prev_lon"] = df.groupby(["plate_id_hash", "event_window"])["longitude_jittered"].shift(1)
    df["prev_lat"] = df.groupby(["plate_id_hash", "event_window"])["latitude_jittered"].shift(1)
    df["prev_time"] = df.groupby(["plate_id_hash", "event_window"])["timestamp_rounded"].shift(1)
    df["distance_km"] = haversine_km(
        df["prev_lon"].fillna(df["longitude_jittered"]),
        df["prev_lat"].fillna(df["latitude_jittered"]),
        df["longitude_jittered"],
        df["latitude_jittered"],
    )
    df["duration_min"] = (df["timestamp_rounded"] - df["prev_time"]).dt.total_seconds().div(60).fillna(0).clip(lower=0)
    df["emission_factor_g_per_km_demo"] = df.apply(demo_emission_factor_g_per_km, axis=1)
    df["co2_g_demo"] = df["distance_km"] * df["emission_factor_g_per_km_demo"]
    df["grid_id_10km"] = assign_10km_grid(df)
    summary = (
        df.groupby(["grid_id_10km", "event_window"], as_index=False)
        .agg(
            demo_vehicle_count=("plate_id_hash", "nunique"),
            demo_point_count=("plate_id_hash", "count"),
            demo_distance_km=("distance_km", "sum"),
            demo_duration_min=("duration_min", "sum"),
            demo_co2_g=("co2_g_demo", "sum"),
            mean_speed_kmh=("speed_kmh", "mean"),
        )
        .sort_values(["grid_id_10km", "event_window"])
    )

    out_path = resolve(root, cfg["output_files"]["grid_daily_summary"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Wrote {out_path}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
