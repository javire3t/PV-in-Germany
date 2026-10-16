"""Read every year's district solar capacity and density from Energy-Charts and build the workbook.

Run with `poetry run python main.py update-data`. Values are read from the map data in
the web page (no screenshots). Output: results/excel/energy-charts_solar_capacity.xlsx.
"""
from __future__ import annotations

# Allow running this file directly from an editor or any working directory.
if __package__ in (None, ''):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


import json
from pathlib import Path
import re

from datetime import date

from project_paths import ENERGY_CHARTS, WORKBOOK
from data_preparation.read_workbook import STATE_AREA_KM2

from openpyxl import Workbook
from openpyxl.styles import Font


# ============================================================
# DOWNLOAD FOLDER
# ============================================================

OUTPUT_FOLDER = ENERGY_CHARTS

# Title, national total and source text (with the provider's "Last Update"
# date) of every year, read from the page (see extract_chart_text). Figures
# use the update date for their credits and year-to-date labels; the MaStR
# comparison uses the national totals.
TEXT_DATA_FILE = OUTPUT_FOLDER / "chart_text.json"

# District values of every downloaded year, so completed years can be reused
# without opening their maps again.
REGIONAL_DATA_FILE = OUTPUT_FOLDER / "regional_series.json"
ENGLISH_EXCEL_OUTPUT_FILE = WORKBOOK


# ============================================================
# YEARS TO DOWNLOAD
# ============================================================

FIRST_YEAR = 1999
# The current year is year-to-date; figures label it as partial.
LAST_YEAR = date.today().year


# ============================================================
# ENERGY-CHARTS URL
#
# The script replaces the year and reads the per-area map
# (solar_per_area) and the absolute map (solar_total).
# ============================================================

CHART_URL = (
    "https://www.energy-charts.info/charts/installed_power_map/chart.htm"
    "?l=en"
    "&c=DE"
    "&year=1999"
    "&expansion=solar_per_area"
    "&show_map_labels=0"
    "&linear_color_scale=1"
)


# ============================================================
# BROWSER SETTINGS
# ============================================================

HEADLESS = True

PAGE_TIMEOUT_MS = 90_000
WAIT_AFTER_LOADING_MS = 5_000

BROWSER_WIDTH = 1600
BROWSER_HEIGHT = 1200


# Completed years already downloaded are reused from the cache; the current
# year is always read again. Set to True to read every year again, e.g. after
# Energy-Charts revises earlier years.
FORCE_REDOWNLOAD = False


def set_query_param(url: str, key: str, value: object) -> str:
    """Set (or replace) a single query parameter in the URL."""

    pattern = rf"([?&]){re.escape(key)}=[^&]*"

    if re.search(pattern, url):
        return re.sub(
            pattern,
            rf"\1{key}={value}",
            url,
        )

    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{key}={value}"


def replace_year(url: str, year: int) -> str:
    """Replace the year parameter in the Energy-Charts URL."""

    return set_query_param(url, "year", year)


def accept_cookies(page: Page) -> None:
    """Accept or close the cookie banner when it is visible."""

    button_patterns = [
        re.compile(r"accept all", re.IGNORECASE),
        re.compile(r"accept", re.IGNORECASE),
        re.compile(r"allow all", re.IGNORECASE),
        re.compile(r"alle akzeptieren", re.IGNORECASE),
        re.compile(r"akzeptieren", re.IGNORECASE),
        re.compile(r"zustimmen", re.IGNORECASE),
    ]

    for pattern in button_patterns:
        try:
            buttons = page.get_by_role(
                "button",
                name=pattern,
            )

            for index in range(buttons.count()):
                button = buttons.nth(index)

                if button.is_visible():
                    button.click()
                    page.wait_for_timeout(500)
                    return

        except Exception:
            continue


def wait_for_chart(page: Page, year: int) -> None:
    """Wait until the annual map has finished rendering."""

    try:
        page.wait_for_selector(
            ".highcharts-container",
            state="visible",
            timeout=PAGE_TIMEOUT_MS,
        )

    except PlaywrightTimeoutError as error:
        raise RuntimeError(
            f"The chart did not load for year {year}."
        ) from error

    page.wait_for_timeout(WAIT_AFTER_LOADING_MS)


def extract_chart_text(page: Page) -> dict[str, str | float]:
    """
    Read the title, "Total" subtitle, and source-credit text straight
    from the DOM. These are plain page elements, not Highcharts'
    native (empty, unused) title/subtitle: #pagetitle, #pagesubheading
    and the SVG .highcharts-caption element.

    Also computes the total installed capacity as a plain number (the
    sum of the map's per-region values), the same figure the
    subtitle's formatted "Total: X MWp" text shows - but usable for
    math (e.g. "% of peak"), since that formatted text uses "." as a
    thousands separator and can't be parsed back reliably.
    """

    return page.evaluate(
        """
        () => {
            const text = (selector) => {
                const el = document.querySelector(selector);
                return el ? el.textContent.replace(/\\s+/g, " ").trim() : "";
            };
            const series = (typeof maps !== "undefined"
                && typeof mapSourceURL !== "undefined"
                && maps[mapSourceURL])
                ? maps[mapSourceURL].series
                : [];
            const total = series
                .map(s => s.value)
                .filter(v => typeof v === "number" && isFinite(v))
                .reduce((a, b) => a + b, 0);
            return {
                title: text("#pagetitle"),
                subtitle: text("#pagesubheading"),
                source: text(".highcharts-caption"),
                total: total,
            };
        }
        """
    )


def extract_map_series(page: Page) -> list[dict[str, object]]:
    """Return the regional values currently loaded in the Energy-Charts map."""

    return page.evaluate(
        """
        () => {
            const charts = (typeof Highcharts !== "undefined"
                && Array.isArray(Highcharts.charts))
                ? Highcharts.charts : [];
            const rawSeries = (typeof maps !== "undefined"
                && typeof mapSourceURL !== "undefined"
                && maps[mapSourceURL])
                ? maps[mapSourceURL].series : [];
            const mapChart = charts.find(chart => chart
                && chart.series
                && chart.series.some(series => series.type === "map"));
            if (mapChart) {
                const points = mapChart.series.flatMap(series =>
                    (series.points || []).map((point, index) => ({
                        id: rawSeries[index]?.id ?? rawSeries[index]?.code
                            ?? rawSeries[index]?.key ?? point.options?.id
                            ?? point.id ?? "",
                        name: point.name ?? point.options?.name ?? "",
                        value: (typeof point.value === "number"
                            && isFinite(point.value)) ? point.value : null
                    }))
                ).filter(item => item.value !== null);
                if (points.length) return points;
            }

            const series = (typeof maps !== "undefined"
                && typeof mapSourceURL !== "undefined"
                && maps[mapSourceURL])
                ? maps[mapSourceURL].series
                : [];
            return series.map(s => {
                const object = (s && typeof s === "object") ? s : {};
                const properties = object.properties ?? object.options?.custom ?? {};
                const strings = Object.values(object)
                    .filter(v => typeof v === "string" && v.trim());
                const numericId = strings.find(v => /^\\d{5}$/.test(v.trim()));
                return {
                    id: object.id ?? object.code ?? object.key
                        ?? object["hc-key"] ?? object.region_id
                        ?? properties.id ?? properties.AGS ?? numericId ?? "",
                    name: object.name ?? object.label ?? object.region_name
                        ?? properties.name ?? object.options?.name
                        ?? strings.find(v => !/^\\d{5}$/.test(v.trim())) ?? "",
                    value: (typeof object.value === "number" && isFinite(object.value))
                        ? object.value
                        : null
                };
            });
        }
        """
    )


def land_from_ags(region_id: object) -> str:
    """Map the first two AGS digits of a Landkreis to its Bundesland."""

    raw_code = str(region_id or "").strip().lower()
    iso_lands = {
        "sh": "Schleswig-Holstein", "hh": "Hamburg", "ni": "Lower Saxony",
        "hb": "Bremen", "nw": "North Rhine-Westphalia", "he": "Hesse",
        "rp": "Rhineland-Palatinate", "bw": "Baden-Württemberg",
        "by": "Bavaria", "sl": "Saarland", "be": "Berlin",
        "bb": "Brandenburg", "mv": "Mecklenburg-Western Pomerania",
        "sn": "Saxony", "st": "Saxony-Anhalt", "th": "Thuringia",
    }
    iso_match = re.search(r"(?:^|-)de-([a-z]{2})-", raw_code)
    if iso_match and iso_match.group(1) in iso_lands:
        return iso_lands[iso_match.group(1)]

    code = re.sub(r"\D", "", raw_code)
    lands = {
        "01": "Schleswig-Holstein", "02": "Hamburg", "03": "Lower Saxony",
        "04": "Bremen", "05": "North Rhine-Westphalia", "06": "Hesse",
        "07": "Rhineland-Palatinate", "08": "Baden-Württemberg",
        "09": "Bavaria", "10": "Saarland", "11": "Berlin",
        "12": "Brandenburg", "13": "Mecklenburg-Western Pomerania",
        "14": "Saxony", "15": "Saxony-Anhalt", "16": "Thuringia",
    }
    return lands.get(code[:2], "Unknown")


def add_year_series(
    regional_data: dict[str, dict[str, list[dict[str, object]]]],
    year: int,
    metric: str,
    series: list[dict[str, object]],
) -> None:
    """Store valid regional values for one year and one map metric."""

    regional_data.setdefault(metric, {})[str(year)] = [
        {
            "id": item.get("id", ""),
            "name": item.get("name", ""),
            "land": land_from_ags(item.get("id", "")),
            "value": item["value"],
        }
        for item in series
        if item.get("value") is not None
    ]


def write_excel_export(
    regional_data: dict[str, dict[str, list[dict[str, object]]]],
    national_totals: dict[str, float],
) -> None:
    """Write district values, source identifiers, and state totals in English."""

    workbook = Workbook()
    workbook.remove(workbook.active)

    overview_sheet = workbook.create_sheet("Overview")
    overview_sheet.column_dimensions["A"].width = 28
    overview_sheet.column_dimensions["B"].width = 28
    overview_sheet.column_dimensions["C"].width = 105
    overview_rows = [
        ("Workbook", "Purpose", "Dataset for analysing installed photovoltaic capacity and its spatial distribution in Germany."),
        ("Methodology", "Source", "Energy-Charts installed-power maps for Germany; values are extracted from regional map data."),
        ("Methodology", "Capacity metric", "Absolute installed solar capacity from the solar_total map, in MWp."),
        ("Methodology", "Density metric", "Installed solar capacity per area from the solar_per_area map, in kWp/km²."),
        ("Methodology", "Aggregation", "District values are assigned to states using the regional identifier and summed by state."),
        ("Methodology", "Interpretation", "Capacity measures total deployment; density normalises deployment by geographic area for comparison between states."),
        ("Workbook", "External figures", "The scripts in code/figures/ read this workbook and write the finished figures to results/figures/."),
        ("Methodology", "Latest year", "The latest year is year-to-date: it holds the values of the latest Energy-Charts update, not a full year."),
        ("Methodology", "Validation", "District and state capacity totals are compared with the national Energy-Charts total for every year."),
        ("Methodology", "Units and areas", "Capacity: MWp. Density: kWp/km². State areas are Destatis land-area totals at 31 December 2024."),
    ]
    overview_sheet.append(["Section", "Item", "Description"])
    for values in overview_rows:
        overview_sheet.append(values)
    for cell in overview_sheet[1]:
        cell.font = Font(bold=True)
    overview_sheet.freeze_panes = "A2"
    overview_sheet.append([
        "Methodology", "District identifiers",
        "District ID preserves the exact Energy-Charts region identifier as text. "
        "It may be a map-specific key rather than an official AGS; retain it "
        "when matching geographic boundaries. State and District remain in columns A and B.",
    ])

    capacity_sheet = workbook.create_sheet("District capacity")
    land_sheet = workbook.create_sheet("State capacity")
    density_sheet = workbook.create_sheet("District density")

    capacity_rows = regional_data.get("capacity", {})
    density_rows = regional_data.get("density", {})

    missing_names = [
        (year, record.get("id", ""))
        for rows in (capacity_rows, density_rows)
        for year, records in rows.items()
        for record in records
        if not record.get("name")
    ]
    if missing_names:
        raise RuntimeError(
            "Energy-Charts returned regional values without names; "
            f"first missing record: {missing_names[0]}"
        )

    unknown_lands = [
        (year, record.get("id", ""), record.get("name", ""))
        for year, records in capacity_rows.items()
        for record in records
        if record.get("land") == "Unknown"
    ]
    if unknown_lands:
        raise RuntimeError(
            "Could not map Landkreis identifiers to Länder; "
            f"first unknown record: {unknown_lands[0]}"
        )

    def make_matrix(rows, aggregate_lands=False, weighted_density=False):
        entries = {}
        for year, records in rows.items():
            for record in records:
                key = record["land"] if aggregate_lands else (
                    record["id"] or record["name"]
                )
                if not key:
                    continue
                if key not in entries:
                    entries[key] = {
                        "id": str(record.get("id", "")),
                        "name": record["name"] if not aggregate_lands else key,
                        "land": record["land"],
                        "values": {},
                    }
                if weighted_density:
                    capacity = next(
                        (
                            item["value"]
                            for item in capacity_rows.get(year, [])
                            if item.get("id") == record.get("id")
                        ),
                        None,
                    )
                    if record["value"] and capacity is not None:
                        numerator, area = entries[key]["values"].get(
                            year, (0, 0)
                        )
                        entries[key]["values"][year] = (
                            numerator + capacity * 1000,
                            area + capacity * 1000 / record["value"],
                        )
                else:
                    entries[key]["values"][year] = (
                        entries[key]["values"].get(year, 0) + record["value"]
                    )
        if weighted_density:
            for entry in entries.values():
                for year, pair in entry["values"].items():
                    numerator, area = pair
                    entry["values"][year] = numerator / area if area else None
        keys = sorted(entries, key=lambda k: (entries[k]["land"], entries[k]["name"]))
        years = sorted(set(rows), key=int)
        return entries, keys, years

    def write_matrix(sheet, rows, unit, aggregate_lands=False, weighted_density=False):
        entries, keys, years = make_matrix(
            rows, aggregate_lands, weighted_density
        )
        land_abbreviations = {
            "Schleswig-Holstein": "SH", "Hamburg": "HH",
            "Lower Saxony": "NI", "Bremen": "HB",
            "North Rhine-Westphalia": "NW", "Hesse": "HE",
            "Rhineland-Palatinate": "RP", "Baden-Württemberg": "BW",
            "Bavaria": "BY", "Saarland": "SL", "Berlin": "BE",
            "Brandenburg": "BB", "Mecklenburg-Western Pomerania": "MV",
            "Saxony": "SN", "Saxony-Anhalt": "ST", "Thuringia": "TH",
        }

        def display_name(key):
            entry = entries[key]
            if aggregate_lands:
                return entry["name"]
            name = re.sub(
                r"\s+\((?:Landkreis|Kreis)\)$",
                "",
                str(entry["name"]),
                flags=re.IGNORECASE,
            ).strip()
            return f'{name} {land_abbreviations.get(entry["land"], entry["land"])}'

        headers = [
            display_name(key)
            for key in keys
        ]
        unit_headers = [f"{year} ({unit})" for year in years]
        sheet.append(
            (["State", "District", "District ID"] if not aggregate_lands else ["State"])
            + unit_headers
        )
        headers_by_key = dict(zip(keys, headers))
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for key in keys:
            if aggregate_lands:
                row = [headers_by_key[key]]
            else:
                row = [
                    entries[key]["land"],
                    re.sub(
                        r"\s+\((?:Landkreis|Kreis)\)$",
                        "",
                        str(entries[key]["name"]),
                        flags=re.IGNORECASE,
                    ).strip(),
                    entries[key]["id"],
                ]
            sheet.append(
                row + [entries[key]["values"].get(year) for year in years]
            )
        sheet.freeze_panes = "B2" if aggregate_lands else "D2"
        if not aggregate_lands:
            for cell in sheet["C"][1:]:
                cell.number_format = "@"
        sheet.cell(1, 1).comment = __import__("openpyxl").comments.Comment(
            f"Values in {unit}. District values are taken directly from Energy-Charts.",
            "PV in Germany",
        )
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = min(
                32, max(12, max(len(str(cell.value or "")) for cell in column) + 2)
            )

    write_matrix(capacity_sheet, capacity_rows, "MWp", False)
    write_matrix(land_sheet, capacity_rows, "MWp", True)
    write_matrix(density_sheet, density_rows, "kWp/km²", False)

    # Add an immediately visible reconciliation to the Länder sheet.
    years = sorted(capacity_rows, key=int)
    first_land_row = 2
    last_land_row = land_sheet.max_row
    total_row = last_land_row + 1
    expected_row = total_row + 1
    difference_row = expected_row + 1
    status_row = difference_row + 1
    land_sheet.cell(total_row, 1, "Total (Excel SUM) (MWp)")
    land_sheet.cell(expected_row, 1, "Energy-Charts total (MWp)")
    land_sheet.cell(difference_row, 1, "Difference (MWp)")
    land_sheet.cell(status_row, 1, "Status")
    for row in range(total_row, status_row + 1):
        land_sheet.cell(row, 1).font = Font(bold=True)
    for column, year in enumerate(years, start=2):
        column_letter = land_sheet.cell(1, column).column_letter
        land_sheet.cell(
            total_row, column,
            f"=SUM({column_letter}{first_land_row}:{column_letter}{last_land_row})",
        )
        land_sheet.cell(expected_row, column, national_totals.get(year))
        land_sheet.cell(
            difference_row, column,
            f"={land_sheet.cell(total_row, column).coordinate}"
            f"-{land_sheet.cell(expected_row, column).coordinate}",
        )
        land_sheet.cell(
            status_row, column,
            f'=IF(ABS({land_sheet.cell(difference_row, column).coordinate})<=0.000001,"OK","CHECK")',
        )

    workbook.calculation.fullCalcOnLoad = True
    workbook.calculation.forceFullCalc = True
    workbook.calculation.calcMode = "auto"
    add_state_density_sheet(workbook)
    ENGLISH_EXCEL_OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(ENGLISH_EXCEL_OUTPUT_FILE)
    print(f"Excel export saved: {ENGLISH_EXCEL_OUTPUT_FILE}")


def add_state_density_sheet(workbook) -> None:
    """Calculate state density using the same fixed areas as the figures."""
    if "State density" in workbook.sheetnames:
        del workbook["State density"]
    source = workbook["State capacity"]
    sheet = workbook.create_sheet("State density")
    sheet.append(["State", "Area (km²)"] + [
        str(cell.value).replace("MWp", "kWp/km²") for cell in source[1][1:]
    ])
    for source_row in range(2, source.max_row + 1):
        state = source.cell(source_row, 1).value
        if state not in STATE_AREA_KM2:
            continue
        sheet.append([state, STATE_AREA_KM2[state]])
        row = sheet.max_row
        for source_column in range(2, source.max_column + 1):
            if source.cell(source_row, source_column).value is not None:
                reference = source.cell(source_row, source_column).coordinate
                sheet.cell(row, source_column + 1,
                           f"='State capacity'!{reference}*1000/$B{row}")
                sheet.cell(row, source_column + 1).number_format = "0.00"
        sheet.cell(row, 2).number_format = "#,##0.00"
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    sheet.column_dimensions["A"].width = 32
    sheet.column_dimensions["B"].width = 18
    for column in range(3, sheet.max_column + 1):
        sheet.column_dimensions[sheet.cell(1, column).column_letter].width = 23
    sheet.freeze_panes = "C2"
    sheet.auto_filter.ref = sheet.dimensions
    overview = workbook["Overview"]
    for row in range(overview.max_row, 1, -1):
        if overview.cell(row, 2).value == "State density":
            overview.delete_rows(row)
    overview.append([
        "Methodology", "State density",
        "State capacity (MWp) × 1000 / fixed state area (km²), in kWp/km²; "
        "Destatis land areas at 31 December 2024 (STATE_AREA_KM2 in data_preparation/read_workbook.py).",
    ])


def update_existing_excel() -> None:
    """Add state density locally without downloading any maps."""
    from openpyxl import load_workbook
    workbook = load_workbook(ENGLISH_EXCEL_OUTPUT_FILE)
    add_state_density_sheet(workbook)
    ENGLISH_EXCEL_OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(ENGLISH_EXCEL_OUTPUT_FILE)
    print(f"Updated: {ENGLISH_EXCEL_OUTPUT_FILE}")


def load_regional_data() -> dict[str, dict[str, list[dict[str, object]]]]:
    """Load the district values saved by previous runs, if any."""

    if REGIONAL_DATA_FILE.exists():
        return json.loads(REGIONAL_DATA_FILE.read_text(encoding="utf-8"))

    return {"capacity": {}, "density": {}}


def save_regional_data(
    regional_data: dict[str, dict[str, list[dict[str, object]]]],
) -> None:
    """Persist the district values of every downloaded year."""

    REGIONAL_DATA_FILE.write_text(
        json.dumps(regional_data, ensure_ascii=False),
        encoding="utf-8",
    )


def load_text_data() -> dict[str, dict[str, str]]:
    """Load the per-year text extracted from previous runs, if any."""

    if TEXT_DATA_FILE.exists():
        return json.loads(TEXT_DATA_FILE.read_text(encoding="utf-8"))

    return {}


def save_text_data(text_data: dict[str, dict[str, str]]) -> None:
    """Persist the per-year extracted text, sorted by year."""

    ordered = {
        year: text_data[year]
        for year in sorted(text_data, key=int)
    }

    TEXT_DATA_FILE.write_text(
        json.dumps(ordered, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def download_year(
    page: Page,
    year: int,
    text_data: dict[str, dict[str, str]],
    regional_data: dict[str, dict[str, list[dict[str, object]]]],
    national_totals: dict[str, float],
) -> None:
    """Read one year's district capacity and density values and the map text."""

    cached = (
        "total" in text_data.get(str(year), {})
        and all(str(year) in regional_data.get(metric, {})
                for metric in ("capacity", "density"))
    )
    if cached and year < LAST_YEAR and not FORCE_REDOWNLOAD:
        national_totals[str(year)] = text_data[str(year)]["total"]
        print(f"{year}: completed year, reusing the cached values")
        return

    print(f"{year}: reading the Energy-Charts maps")
    page_url = replace_year(CHART_URL, year)

    # Read the absolute national total from the absolute-capacity map.
    # It must not be calculated by summing Kreis density values.
    page.goto(
        set_query_param(page_url, "expansion", "solar_total"),
        wait_until="domcontentloaded",
        timeout=PAGE_TIMEOUT_MS,
    )
    accept_cookies(page)
    wait_for_chart(page, year)
    absolute_total = extract_chart_text(page)["total"]
    national_totals[str(year)] = absolute_total
    add_year_series(regional_data, year, "capacity", extract_map_series(page))

    page.goto(page_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
    accept_cookies(page)
    wait_for_chart(page, year)
    density_text = extract_chart_text(page)
    add_year_series(regional_data, year, "density", extract_map_series(page))
    # Keep the absolute national total; the density map's own "total" is per area.
    density_text["total"] = absolute_total
    text_data[str(year)] = density_text


def main() -> None:
    """Read every year's district values from Energy-Charts and rebuild the workbook."""
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
    global sync_playwright, PlaywrightTimeoutError
    from playwright.sync_api import (
        TimeoutError as PlaywrightTimeoutError,
        sync_playwright,
    )

    text_data = load_text_data()
    regional_data = load_regional_data()
    national_totals: dict[str, float] = {}
    failed = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            viewport={"width": BROWSER_WIDTH, "height": BROWSER_HEIGHT},
        )
        page = context.new_page()
        page.set_default_timeout(PAGE_TIMEOUT_MS)
        try:
            for year in range(FIRST_YEAR, LAST_YEAR + 1):
                try:
                    download_year(page, year, text_data, regional_data, national_totals)
                    save_text_data(text_data)
                    save_regional_data(regional_data)
                except Exception as error:
                    print(f"{year}: failed ({error}); continuing with the next year.")
                    failed.append(year)
        finally:
            context.close()
            browser.close()

    if failed:
        # Never write a workbook with missing years. Downloaded years are
        # cached, so a second run only retries the failed ones.
        raise SystemExit(f"Not updated: years {failed} failed. Run update-data again; "
                         "completed years are reused from the cache.")

    write_excel_export(regional_data, national_totals)
    print(f"Workbook rebuilt: {ENGLISH_EXCEL_OUTPUT_FILE}")


def cli() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--update-excel", action="store_true",
                        help="Add state density to the existing workbook without downloading")
    args = parser.parse_args()
    if args.update_excel:
        update_existing_excel()
    else:
        main()


if __name__ == "__main__":
    cli()
