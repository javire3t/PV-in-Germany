# Sources for the national PV animation

Visualization and animation: EIFER. District values are read from the project's Energy-Charts workbook, matched to official AGS district codes, and drawn on BKG land geometries. The color scale is fixed at 0–780 kWp/km² across all years; values above 780 use the darkest green.

## PV data

Source: [Energy-Charts installed solar power map](https://energy-charts.info/charts/installed_power_map/chart.htm?l=en&c=DE&source=solar).

The saved source metadata for 2026 reports its last update as **17 September 2026, 21:10 GMT+2**. This is the provider's update timestamp, not the date this animation was generated or downloaded. The 2026 value represents a partial year. Earlier years retain their own source update timestamps in `data/raw/energy_charts/chart_text.json`.

## Map boundaries

BKG is the **Bundesamt für Kartographie und Geodäsie**, Germany's Federal Agency for Cartography and Geodesy: [official website](https://www.bkg.bund.de/EN/Home/home.html).

Dataset: [VG250 administrative areas, 31 December edition](https://gdz.bkg.bund.de/index.php/default/digitale-geodaten/verwaltungsgebiete/verwaltungsgebiete-1-250-000-stand-31-12-vg250-31-12.html), at 1:250,000 scale. The local delivery's `dokumentation/aktualitaet.txt` confirms the boundary date **31 December 2025**.

Attribution: **© BKG 2026 · dl-de/by-2-0**. See the [Data Licence Germany attribution 2.0](https://www.govdata.de/dl-de/by-2-0) and the [VG250 data-source notice](https://sgx.geodatenzentrum.de/web_public/gdz/datenquellen/datenquellen_vg_nuts.pdf).

Modifications: land geometries selected, grouped by AGS and converted to GeoJSON; PV values and colors added by EIFER. The same 2025 boundary geometry is used for every historical frame.
