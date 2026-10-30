## Manuscript-aligned economic module (illustrative data)

```bash
python scripts/01_run_economic_loss_demo.py --config config/economic_loss_config.yaml
python scripts/01_run_economic_loss_demo.py --config config/economic_loss_config.yaml --theta 3.0
python scripts/01_run_economic_loss_demo.py --config config/economic_loss_config.yaml --theta 6.0
python -m unittest discover -s tests -v
```

**Input contracts** (the bundled CSVs are synthetic, not research data):

- `data/demo/od_period_mean_flows_sample.csv`: `origin_city`, `destination_city`,
  `q_normal`, `q_rain`. The last two are mean *daily* OD freight flows for
  the matched normal/control and rainstorm periods, not point counts or
  truck-kilometres. Each OD pair appears once. Explicit observed zeros are
  allowed; unknown/missing flow must not be coded as zero.
- `data/demo/city_economic_base_sample.csv`: `city`,
  `transport_storage_postal_value_added_rmb`, annual city value added
  in RMB.

**Important upstream prerequisites:** The supplied OD means must be derived
from the actual event (26–29 August 2023) and properly matched control days
(the seven days before and after), with daily rainfall masks, the event-period
union of rainfall-affected areas, and **rain-free** control eligibility applied
before this economic script. This script does not infer rainfall exposure from
GPS points and does not silently treat unobserved OD days as zero.

**Economic equations** (main manuscript economic module; Supplementary Note 6):

1. `delta_ln_q = log1p(q_rain) - log1p(q_normal)`.
2. `delta_ln_transport_cost = -delta_ln_q / theta` (baseline `theta=4.5`,
   alternatives `3.0` and `6.0`).
3. `baseline_od_weight = q_normal / sum_all_OD(q_normal)` (the **global**
   baseline OD denominator, not within-destination normalization).
4. `delta_ln_welfare_c = -sum_{o->d=c}(baseline_od_weight * delta_ln_transport_cost)`.
5. `road_transport_value_added_c = alpha_road * annual_transport_storage_postal_value_added_c`,
   where `alpha_road = 57080.2 / 134758.9` (2023 sector revenue share).
6. `daily_disturbance_c = road_transport_value_added_c / 365 * (1 - exp(delta_ln_welfare_c))`.
7. `event_disturbance_c = event_days * daily_disturbance_c` (4 days in the
   bundled example).

Outputs: `outputs/demo/city_economic_disturbance.csv` and
`outputs/demo/od_cost_shock_diagnostics.csv`. Signed disturbances are retained;
negative values indicate a gain under this reduced-form proxy.

**Scope and scientific limitations:**

- The synthetic demonstration does **not** reproduce the published
  `RMB 0.832 million` event estimate or the full 261-million-GPS analysis.
- Baseline route shares are normalized over the supplied OD table. National
  interpretation requires the complete relevant national OD network; a small
  demonstration network cannot substitute for that denominator.
- The transport-cost shock is inferred from OD flow changes assuming constant
  elasticity, not independently observed transport prices.
- The output is a *short-run gross output disturbance proxy* based on sector
  value added and fixed short-run structures, not a measured causal welfare
  loss or downstream supply-chain loss.
- The road-transport revenue ratio is applied to value added as a calibration
  proxy; it does not establish an observed city-level road-freight value-added
  share and may include passenger and support activities.
- The standalone GPS/grid/emissions demo (`00_run_demo.py`) is separate and
  remains illustrative; its formulas are not used in this economic module.
