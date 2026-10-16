# Methods, sources and figure conventions

Reference details behind the figures and their reproducibility. Keep this file at the repository root; `results/` contains shareable outputs and `validation/` contains internal audit artifacts. For everyday use see [README.md](README.md).

## Contents

1. [Sources and dates](#sources-and-dates)
2. [Year-to-date data and units](#year-to-date-data-and-units)
3. [Energy-Charts workbook](#energy-charts-workbook)
4. [Regional groups](#regional-groups)
5. [NEP scenarios and estimates](#nep-scenarios-and-estimates)
6. [MaStR register data](#mastr-register-data)
7. [Figure conventions](#figure-conventions)
8. [Individual figures](#individual-figures)
9. [Code map and tests](#code-map-and-tests)

## Sources and dates

| Source | Used for | Date | Licence |
| --- | --- | --- | --- |
| [Energy-Charts](https://www.energy-charts.info) installed-power maps | District and state history 1999–2026 | Last update 1 Oct 2026 (2026 values) | Credit "Energy-Charts.info" |
| BKG VG250 boundaries | Every map | 31 Dec 2025 | © BKG 2026, dl-de/by-2-0 |
| Destatis land area by state | Every state and regional density | 31 Dec 2024 | Credit Destatis |
| NEP 2025, 2nd draft, Figures 13–18 (PDF pp. 55–60) | NEP A/B/C state tables | — | German TSOs |
| NEP 2025, 1st draft, Figures 10–11 (PDF p. 45) | NEP B district maps | — | CC BY 4.0 (adapted) |
| [MaStR](https://www.marktstammdatenregister.de/MaStR/Datendownload) full export, rev. 26.2 | MaStR workbook and checks | 13 Oct 2026 | Datenlizenz Deutschland – Namensnennung 2.0 (Bundesnetzagentur / Marktstammdatenregister) |

Source PDFs are in `data/raw/nep/`; links and geometry notes for the national map are in [code/figures/germany/sources.md](code/figures/germany/sources.md).

## Year-to-date data and units

The latest Energy-Charts year is **year-to-date**, not a full year. Figures display only the year (for example, 2026) to keep labels compact. The source credits give the provider update date and how far the year runs, e.g. "Last update 01.10.26 · 2026 up to October". The current-year point is hollow on historical comparison lines. Annual additions cover only part of that year and are not comparable with complete years.

- Capacity: MWp (GWp in large-scale charts).
- Density: kWp/km² for every density computed in this project. The two NEP B maps keep the source document's MW/km².
- State density = state capacity × 1000 / Destatis state area. The areas are defined once, as `STATE_AREA_KM2` in [read_workbook.py](code/data_preparation/read_workbook.py), written to the workbook and read back from it by the figures.
- Regional group density = total group capacity / total group area (not an average of state densities).

## Energy-Charts workbook

`results/excel/energy-charts_solar_capacity.xlsx` is built by `poetry run python main.py update-data`, which drives a browser (Playwright) over the Energy-Charts maps. Completed years already downloaded are reused; their district values are cached in `data/raw/energy_charts/regional_series.json`. The current year is always refreshed. Set `FORCE_REDOWNLOAD = True` in [download_energy_charts.py](code/data_preparation/download_energy_charts.py) to fetch every year again. The first run after the cache was introduced downloads every year once.

Sheets: district and state capacity, district and state density, and an Overview sheet describing the method. District values sum exactly to the state values for every year, and the state total row is compared with the national Energy-Charts total.

All 400 districts match the BKG 2025 boundaries uniquely by official AGS code. The same 2025 geometry is used for every historical year.

## Regional groups

Each partition contains all 16 states exactly once.

- **East**: Berlin, Brandenburg, Mecklenburg-Western Pomerania, Saxony, Saxony-Anhalt, Thuringia. **West**: the other ten states.
- **South**: Bavaria, Baden-Württemberg, Hesse, Rhineland-Palatinate, Saarland, Thuringia. **North**: the other ten states. South–North is an illustrative division.


## NEP scenarios and estimates

**Regional comparisons (A/B/C).** `poetry run python main.py nep-tables` extracts the published state tables of the 2nd draft. Forecast figures show two aligned panels sharing the year axis: installed capacity in GWp above and density in kWp/km² below. Each region uses its own total Destatis area to convert historical capacity and all NEP scenarios into density. Both panels show the A–C band (outlined in the region colour so overlapping ranges stay readable), the dashed scenario B line and the forecast shading. The map beside the panels is drawn by Land: each Land is coloured from its own NEP B 2045 capacity divided by its own area, using a common 0–1,400 kWp/km² green scale; regional colours remain in the outlines and labels. Regions are listed in alphabetical order (East/West, North/South) in legends, titles and file names. A translucent band covers the minimum and maximum of the three scenarios at each published year; a dashed line shows scenario B. The band is the range of published scenarios, not a confidence interval. Straight segments connect the last historical year with 2037 and 2045; they are not additional published forecasts. Historical-only comparison figures show each Land's latest-year density with the common 0–780 kWp/km² green scale and regional outlines.

**District maps (B).** The NEP publishes no district numbers. `poetry run python main.py nep-extract` aligns the 1st-draft map images with the BKG boundaries and reads each district's colour back against the source legend. The result is an **estimate** and is labelled as such in the figure subtitle. Ground-mounted and rooftop maps are presented together with one linear 0–4.6 MW/km² scale and a single shared colourbar. Equal colours represent equal densities across both technologies. This approved visual adaptation does not alter the digitized values. EIFER credits explicitly identify the shared-scale adaptation. Year labels sit where the source places them: centred 59% across the country from the west, just below its northern tip, at the same size relative to the map. The alignment check is `data/processed/nep_estimates/alignment_check.png`; the colour audit is in `validation/nep_colors/`.

## MaStR register data

**District baseline.** `poetry run python main.py mastr-download` fetches only the solar tables and lookup tables of the official export (about 1.13 GB of the 3.23 GB ZIP, by HTTP range requests) into `data/raw/mastr/`. `poetry run python main.py mastr-prepare` reads the XML incrementally and keeps German units **in operation**, commissioned no later than the snapshot, with positive gross capacity (`Bruttoleistung`). Categories come from the export's own lookup tables: ground-mounted, building-mounted (roofs and facades; not "rooftop only"), balcony, and other/unknown.

Municipal AGS codes identify the district; the Eisenach/Wartburgkreis and Göttingen/Osterode mergers are translated to BKG 2025 codes. A missing code falls back to an exact district name within the same state, only when unique. Result for the 13 Oct 2026 snapshot: 6,570,255 records; 46,881.5 MWp ground-mounted, 82,284.8 MWp building-mounted, 1,676.7 MWp balcony, 58.2 MWp other. 99.998% of capacity is assigned to districts; 2.0 MWp in "Kassel" cannot be split between city and district and stays unassigned. Densities use BKG land areas computed in equal-area EPSG:3035.

**Annual commissioning.** `poetry run python main.py mastr-annual` builds `pv_commissioning_by_year_power_use_2000_2026.csv`: 27 years × 5 power bands (≤10, >10–30, >30–100, >100–1000, >1000 kWp; boundaries belong to the lower band) × 8 use categories. The commissioning date sets the year; operating and shut-down units are included, planned units are not. These are **cohorts reconstructed from today's register** (current capacity and use), not historical annual statistics; 2026 runs to 13 October.

**Workbooks.** `poetry run python main.py excel-workbooks` writes `results/excel/mastr_solar_capacity.xlsx` and `nep_solar_capacity.xlsx` from the prepared tables ([excel_workbooks.py](code/data_preparation/excel_workbooks.py)), then re-reads every cell and checks it against its input; the MaStR district total must equal `validation.json`. Run it after `mastr-prepare`, `mastr-annual`, `nep-tables` or `nep-extract`. (It replaces an earlier Node builder made with Codex; the Python output was checked cell by cell and style by style against the Codex files: identical except the renamed header `density_kWp_per_km2`.)

MaStR and Energy-Charts totals differ slightly because of dates, registration delays and definitions; nothing is rescaled. The comparison outputs are in `validation/mastr_energy_charts/` (`comparison.json`, `comparison.png`, and the state and district CSV tables).

**Annual additions by unit size.** `Figure_additions-by-size_germany_2000-2025` (task `mastr-additions`) stacks the capacity commissioned each year by unit size (<10, 10–30, 30–100, 100–1,000 kW, >1 MW), from the annual commissioning table. It updates the pv magazine chart of the 2000s; for 2000–2009 the MaStR values reproduce that chart within about ±3%.

**Exit from EEG payments.** `poetry run python main.py mastr-eeg-exit` links every operating unit to its EEG record (`AnlagenEegSolar`, downloaded with `mastr-download`). A unit is paid in its EEG commissioning year and the following 20 calendar years, so it is without EEG payment from *EEG year + 21*; units from before 2000 exit in 2021 (EEG 2000 transition). Only an explicit "no EEG payment" excludes a unit: the payment field is empty for most records and for almost all units since 2023. The presentation uses `Figure_eeg-exit_germany_2021-2037`; the PwC classification is retained in the workbook as an alternative analysis, not as a presentation figure. Both classifications show cumulative unit counts (top) and capacity (bottom; right axis as a share of capacity in operation at the snapshot). The series stops in 2037 (cohorts to 2016), because for recent cohorts paid and unpaid units cannot be told apart. Counts cover units still in operation; units already shut down are not counted. Result: about 1.3 million units and 33 GW by 2033 (25% of today's capacity), 1.6 million units and 40 GW by 2037 (31%). Totals are in `data/processed/mastr/eeg_exit_validation.json`. The annual and cumulative tables of both classifications, and the additions by size, are also in `results/excel/mastr_solar_capacity.xlsx` (sheets *Additions by size*, *EEG exit*, *EEG exit validation*).

## Curtailment and redispatch: published numeric tables

The finished maps and `results/excel/redispatch_curtailment.xlsx` use published numeric tables only. Values inferred from raster colours have been retired from finished outputs. `redispatch-maps` and `redispatch-official` generate the official 2023/2025 maps. `redispatch-excel` saves source observations, comparison inputs and coverage flags.

Historical 2016-2021 observations come from BNetzA full-year reports 2017 (PDF p. 29), 2019 (p. 20) and 2021 (p. 20). The 2016/2021 pair covers EEG and CHP EinsMan and includes 11 states with numeric observations in both years. Source dashes stay missing. Recent SMARD series `s-nepm_nepm_ba-1-1` covers reductions of all generation technologies; twelve monthly records are summed per complete year. Its 2023/2025 pair includes all 16 states. These scopes are not spliced.

Only states with observations in both periods are compared. Missing comparison values are grey and labelled ND. Small published numbers remain valid observations, including BW. Percentage labels use the common-state total; colours use the shared scale stated below the maps. Original values remain intact in Excel. Blue and red contours delimit the existing project North/South grouping. No overall titles or regional legends are added.

Checks cover source cell counts, unique observations, annual completeness, rounding reconciliation, percentage totals and exported Excel cells.

## Figure conventions

- **Names**: `Figure_<type-or-metric>_<scope>[_<selection>][_<qualifier>]_<period>[_NEP-<scenario>]` for PNGs and `Animation_<metric>_<scope>_<period>` for GIFs. Comparisons start with `comparison`; other figures start with their metric. Redundant `all`, `map`, `timeseries` and `scatter` fields are omitted. Distinguishing qualifiers include `labeled` and `logx`. NEP scenarios are explicit uppercase `NEP-B` or `NEP-ABC`. Built by `figure_name` in `code/figures/shared/plot_helpers.py`; subject pairs are alphabetical ASCII names.
- **Folder**: every finished figure goes flat into `results/figures/`. Animation frames, annual district maps and export checks go to `data/work/` and can be deleted. Rerunning a task overwrites its figures.
- **Cropping**: PNGs and GIFs are cropped to their content with a margin of 1.2% of the shorter side (at least 8 px), so they drop cleanly into Word or PowerPoint. All GIF frames share one crop box.
- **Background**: transparent PNG and GIF canvases; GIFs clear each frame before the next.
- **Caption**: a bold dark-green title below the content, directly above the source credits. GIF captions stay fixed; the year is shown separately.
- **Credits**: [source_credits.py](code/figures/shared/source_credits.py) writes one centred footer. The first line is always `Visualization: EIFER`; the following lines list only the sources used by that figure (Energy-Charts with its update date, Destatis areas, NEP draft, BKG boundaries).
- **Scatter canvas**: state capacity–density scatters use 10 × 8.58 in (20% taller), with 14 pt axis labels and 12 pt ticks. Annotation boxes are checked for overlaps. Comparison layouts use a chart and geographic map together.

## Individual figures

**National animation** (`Animation_density_germany_…gif`). Districts from 2000 to the latest year (set in `settings.py`), one second per year, 2.5 s on the last frame, playing once. Fixed green scale 0–780 kWp/km² (`GERMANY_DENSITY_SCALE_MAX`); higher values use the darkest green. The text above the map gives the year, the share of the latest year's national capacity, and the total in MWp.

**Labelled national map** (`Figure_density_germany_labeled_…png`). Same 400 districts and scale, lighter `BuGn` palette, bold values. Labels sit on land in the largest part of each district; larger districts have priority and a value is shown only if its box does not overlap another, so about 340 of 400 districts are labelled. Label positions and unrounded values are logged in `data/work/district_value_maps/`.

**Static comparisons** (`Figure_comparison_states_…`, `Figure_comparison_districts_…`, `Figure_comparison_regions_…`). Complete historical capacity lines are retained, with latest-year density on the map. No comparison GIFs or secondary density axes are generated. Every Land in a regional comparison keeps its own observed capacity-per-area value; the common 0–780 kWp/km² green scale encodes density, while regional outlines and labels identify East/West or North/South.

**Capacity–density scatters** (`Figure_capacity-vs-density_states_……`). All-state, city-state and non-city-state views remain as the requested analytical diagrams. Map-free pair time series, annual additions, capacity shares, district-pair scatter and trajectories have been removed.

## Code map and tests

| Folder | Contents |
| --- | --- |
| `code/project_paths.py` | Every folder path; loads `settings.py` |
| `code/data_preparation/` | Downloads, workbook reading and region matching, MaStR and NEP extraction |
| `code/figures/germany/` | `animation.py`, `labeled_map.py`, `nep_b_maps.py` (all national figures) |
| `code/figures/regions/` | `nep_scenarios.py` (`Figure_capacity-and-density_regions_…_NEP-ABC`) |
| `code/figures/states/` | `charts.py` (state capacity–density scatters) |
| `code/figures/districts/` | `maps.py` (extra annual district maps) |
| `code/figures/shared/` | `comparison.py` (static historical capacity and density maps), `map_labels.py` (interior geographic labels), `charts.py` (chart canvas and year axis), `plot_helpers.py` (figure names, map drawing), `source_credits.py` (footers and the year-to-date note), `crop_exports.py` |
| `code/validation/` | MaStR XML audit and report, NEP colour audit |
| `code/tests/` | Automated tests: `poetry run python main.py tests` |

Tests cover working-directory-independent paths, ambiguous district names, boundary matching, group totals and densities, published NEP totals, figure names, the year-to-date credit, cropping, captions, credits and GIF transparency.


