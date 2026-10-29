# Extreme Rainfalls Increase Economic and Environmental Costs of Highway Freight

This repository accompanies the study applying the rainfall–transport–economy–environment (RTEE) framework to assess the effects of extreme rainfall on highway freight in China. It provides runnable Python workflows, configuration files, example input tables, variable definitions, and example output tables.

## Repository contents

- `scripts/00_run_demo.py`: processes GPS-point samples, assigns event windows, estimates vehicle movement and CO₂ emissions, and aggregates activity by projected 10 km × 10 km grid cells.
- `scripts/01_run_economic_loss_demo.py`: derives city-level freight activity and speed changes and calculates a direct economic-loss proxy.
- `config/`: workflow settings and scenario parameters.
- `data/demo/`: sample GPS-point and vehicle-attribute tables used by the scripts.
- `data/metadata/data_dictionary.csv`: variable definitions for the input and output tables.
- `outputs/demo/`: example tables produced by the workflows.

## Requirements

Python 3.11 is recommended.

Create the conda environment:

```bash
conda env create -f environment.yml
conda activate rtee
```

Alternatively, install the dependencies in an existing Python environment:

```bash
python -m pip install -r requirements.txt
```

## Run the workflows

Generate the grid-level summary:

```bash
python scripts/00_run_demo.py --config config/demo_config.yaml
```

Output: `outputs/demo/grid_daily_summary.csv`. The demo uses a local Transverse Mercator projection centered at 113.9°E, 34.7°N and assigns points to 10,000 m × 10,000 m cells in projected coordinates. This projection is intended for the supplied local demo data; choose an appropriate projected CRS when applying the workflow to another study area.

Generate the city-level direct-loss table:

```bash
python scripts/01_run_economic_loss_demo.py --config config/demo_config.yaml
```

Output: `outputs/demo/city_economic_loss.csv`.

## Repository structure

```text
.
├── README.md
├── CITATION.cff
├── LICENSE
├── requirements.txt
├── environment.yml
├── config/
│   ├── demo_config.yaml
│   └── scenario_config.yaml
├── data/
│   ├── demo/
│   │   ├── gps_points_sample.csv
│   │   └── vehicle_static_sample.csv
│   └── metadata/
│       └── data_dictionary.csv
├── scripts/
│   ├── 00_run_demo.py
│   └── 01_run_economic_loss_demo.py
└── outputs/
    └── demo/
        ├── city_economic_loss.csv
        └── grid_daily_summary.csv
```

## Citation

Please cite the associated article when using this code or adapting the workflows. Repository citation metadata are provided in `CITATION.cff`.

## License

The MIT license applies to the code and example files in this repository.
