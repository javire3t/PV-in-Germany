# PV in Germany

Installed photovoltaic capacity and density in Germany, using Energy-Charts history, MaStR register data and NEP scenarios.

## Everyday use

| Task | Action |
| --- | --- |
| Find finished figures | Open [results/figures/](results/figures/) |
| Find Excel workbooks | Open [results/excel/](results/excel/) |
| Share the presentation | Open [results/pv_figures_presentation.pdf](results/pv_figures_presentation.pdf) |
| Change selected regions or years | Edit [settings.py](settings.py) |
| Regenerate the current figure set | `poetry run python main.py all-figures` |
| Generate one family or update inputs | `poetry run python main.py` |
| List all available tasks | `poetry run python main.py --help` |
| Run the automated checks | `poetry run python main.py tests` |
| Read methods and sources | [METHODS.md](METHODS.md) |

## Setup

This project uses [Poetry](https://python-poetry.org/) with Python 3.12--3.14. From the repository root:

```powershell
poetry install
poetry run python main.py --help
poetry run python main.py tests
```

Poetry is configured to create the virtual environment in `.venv/`; use `poetry run ...` for project commands rather than calling the environment's Python executable directly. `poetry.lock` pins the resolved dependency set.

## Structure

- `code/`: generators, data preparation, shared helpers, validation and tests.
- `data/raw/`: original downloads, source PDFs and boundaries.
- `data/processed/`: prepared tables; `data/work/`: regenerable intermediate files.
- `results/figures/`, `results/excel/`: shareable deliverables; `validation/`: internal audit outputs.
- `latex/`: Beamer source for the presentation.
- `settings.py`: daily configuration; `main.py`: task menu.

## Current figure families

- Redispatch comparisons use only states with data in both periods; excluded states are grey in both maps. `poetry run python main.py redispatch-excel` saves original observations, common coverage flags, mapped values and sources to [results/excel/redispatch_curtailment.xlsx](results/excel/redispatch_curtailment.xlsx). Historical 2016/2021 coverage is 11 states; recent 2023/2025 coverage is all 16 states. Original values outside the comparison remain in the workbook.

- Historical renewable/CHP curtailment: `poetry run python main.py redispatch-history` extracts official state tables for 2016-2021 and exports a shared-scale 2016/2021 map pair. All 16 states are retained; source dashes remain missing. The historical series remains separate from the all-technology 2023-2025 series; see `METHODS.md` for the scope distinction.

- Official redispatch comparison: `poetry run python main.py redispatch-official` uses downloaded SMARD monthly tables. Two state maps compare 2023 and 2025 with shared GWh and percentage scales; all 16 states, including BW, are included. These regional data include conventional generation. Only maps are exported; the numeric technology tables are retained. Scope and limitations are documented in `METHODS.md`.

- Capacity–density scatter diagrams are 20% taller (10 × 8.58 inches); state labels are checked for overlaps, including SN and HE.
- Static comparisons show installed capacity through the latest year on the chart and latest-year density on the map. In regional comparisons, each Land is coloured with its own observed capacity density using the common 0–780 kWp/km² scale; East/West or North/South are retained in the Land outlines and external labels. State, district and regional maps use a density colourbar.
- Historical data and NEP forecasts use two aligned panels: installed capacity (GWp) above and density (kWp/km²) below, with a shared year axis. The regional density lines use each region's total Destatis area. Forecast bands show the A–C scenario range with outlined edges; dashed lines show B. The forecast map is drawn at Land level: each Land uses its own NEP B 2045 capacity divided by its own area, with a common 0–1,400 kWp/km² green scale and regional outlines.
- The ground-mounted and rooftop NEP B maps share one six-panel figure, one palette, one linear scale (0–4.6 MW/km²) and one colourbar. Titles distinguish the technologies. Source credits explicitly identify the shared-scale adaptation by EIFER.
- Historical comparison animations and map-free pair comparisons have been removed from the code and finished outputs. Static comparisons retain the complete historical lines and final-year maps. The national Germany animation is retained.
- Energy-Charts and BNetzA figures are available with `poetry run python main.py external-figures`. This produces the electricity-mix, installed-power, tariff comparison, and tariff/revenue figures. Sources and semantics are documented in [external_figures_sources.md](code/figures/germany/external_figures_sources.md).
- 2026 values are year-to-date. Figure labels show only the year; the source credits give the update date and say how far the year runs (e.g. "2026 up to October").

## Names

`Figure_<type-or-metric>_<scope>[_<selection>][_<qualifier>]_<period>[_NEP-<scenario>].png`

`Animation_<metric>_<scope>_<period>.gif`

Names omit redundant fields such as `all`, `map`, `timeseries` and `scatter`. Comparisons start with `comparison`; other figures start with their metric. Scope is `germany`, `regions`, `states` or `districts`. Pair names are alphabetical and ASCII. Qualifiers such as `labeled` and `logx` distinguish variants. NEP figures explicitly end in `NEP-B` or `NEP-ABC`.

## Figure catalogue

| File | Task |
| --- | --- |
| [Animation_density_germany_2000-2026.gif](results/figures/Animation_density_germany_2000-2026.gif) | `germany-animation` |
| [Figure_comparison_districts_burgenland-vs-saale-holzland_1999-2026.png](results/figures/Figure_comparison_districts_burgenland-vs-saale-holzland_1999-2026.png) | `pair-comparisons` |
| [Figure_density_germany_labeled_2026.png](results/figures/Figure_density_germany_labeled_2026.png) | `germany-labeled-map` |
| [Figure_additions-by-size_germany_2000-2025.png](results/figures/Figure_additions-by-size_germany_2000-2025.png) | `mastr-additions` |
| [Figure_eeg-exit_germany_2021-2037.png](results/figures/Figure_eeg-exit_germany_2021-2037.png) | `eeg-exit` |
| [Figure_ground-and-rooftop-density_germany_2024-2037-2045_NEP-B.png](results/figures/Figure_ground-and-rooftop-density_germany_2024-2037-2045_NEP-B.png) | `nep-b-maps` |
| [Figure_comparison_regions_east-vs-west_1999-2026.png](results/figures/Figure_comparison_regions_east-vs-west_1999-2026.png) | `region-comparisons` |
| [Figure_capacity-and-density_regions_east-vs-west_1999-2045_NEP-ABC.png](results/figures/Figure_capacity-and-density_regions_east-vs-west_1999-2045_NEP-ABC.png) | `regions-nep` |
| [Figure_comparison_regions_north-vs-south_1999-2026.png](results/figures/Figure_comparison_regions_north-vs-south_1999-2026.png) | `region-comparisons` |
| [Figure_capacity-and-density_regions_north-vs-south_1999-2045_NEP-ABC.png](results/figures/Figure_capacity-and-density_regions_north-vs-south_1999-2045_NEP-ABC.png) | `regions-nep` |
| [Figure_capacity-vs-density_states_logx_2026.png](results/figures/Figure_capacity-vs-density_states_logx_2026.png) | `state-charts` |
| [Figure_capacity-vs-density_states_2026.png](results/figures/Figure_capacity-vs-density_states_2026.png) | `state-charts` |
| [Figure_comparison_states_baden-wurttemberg-vs-bavaria_1999-2026.png](results/figures/Figure_comparison_states_baden-wurttemberg-vs-bavaria_1999-2026.png) | `pair-comparisons` |
| [Figure_capacity-vs-density_states_city-states_2026.png](results/figures/Figure_capacity-vs-density_states_city-states_2026.png) | `state-charts` |
| [Figure_capacity-vs-density_states_excl-city-states_logx_2026.png](results/figures/Figure_capacity-vs-density_states_excl-city-states_logx_2026.png) | `state-charts` |
| [Figure_comparison_states_saxony-anhalt-vs-thuringia_1999-2026.png](results/figures/Figure_comparison_states_saxony-anhalt-vs-thuringia_1999-2026.png) | `pair-comparisons` |




Redispatch now uses only published numeric tables: valid BW and other state observations are displayed, however small. ND is reserved for missing observations in either comparison year. Historical 2016/2021 coverage is 11 states; recent 2023/2025 coverage is 16 states. The old raster-derived comparison is archived outside results; estimated district data are no longer included in the Excel deliverable. `redispatch-maps` now runs the official numeric comparison.
