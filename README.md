# Extreme Rainfalls Increase Economic and Environmental Costs of Highway Freight

This repository accompanies the RTEE study of extreme rainfall and road freight
in China. The public repository includes **illustrative** workflows and synthetic
sample data. It does not contain the restricted 261-million-record truck GPS
analysis or enough inputs to reproduce the published numerical estimates.

## Workflows

- `scripts/00_run_demo.py`: a separate illustrative GPS/grid/emissions workflow;
  its simplified emissions and grid calculations are **not** the paper's
  empirical emissions implementation.
- `scripts/01_run_economic_loss_demo.py`: the paper's *economic-module equation
  chain* applied to synthetic OD and city-sector inputs, without arbitrary
  `0.7/0.3` activity/speed weights.
- `README_ECONOMIC.md`: equations, data requirements, assumptions and limits for
  the economic workflow.

## Setup

Python 3.11 is recommended.

```bash
python -m pip install -r requirements.txt
```

## Run

```bash
# Manuscript-aligned economic equation chain, on synthetic inputs
python scripts/01_run_economic_loss_demo.py --config config/economic_loss_config.yaml
# Elasticity sensitivity checks (theta = 3, 4.5, 6)
python scripts/01_run_economic_loss_demo.py --theta 3.0
python scripts/01_run_economic_loss_demo.py --theta 6.0
# Run automated economic-module tests
python -m unittest discover -s tests -v
# Separate GPS/grid/emissions demonstration
python scripts/00_run_demo.py --config config/demo_config.yaml
```

The economic script writes `outputs/demo/city_economic_disturbance.csv` and
`outputs/demo/od_cost_shock_diagnostics.csv`. The GPS script writes
`outputs/demo/grid_daily_summary.csv` (despite the legacy filename, the
aggregation is by **grid and event window**, not by individual calendar date).
All outputs are generated when scripts run; the repository does not ship them.

## Scientific scope

The economic module needs precomputed mean daily **intercity OD flows** for
matched rainfall/control samples, plus annual 2023 city-level transport,
storage and postal-services value added in RMB. The event/control rainfall
masks, rain-free controls and spatial matching must be prepared upstream;
GPS-point speeds or truck-kilometres cannot substitute for OD flow inputs.
The supplied CSVs are **synthetic examples**. The code illustrates the equations,
not the article's published estimates or a causal validation of those equations.
See [`README_ECONOMIC.md`](README_ECONOMIC.md) for full details.

## Citation and license

Please cite the associated article when using or adapting these workflows.
Repository citation metadata are provided in `CITATION.cff`. The repository
uses the MIT license.
