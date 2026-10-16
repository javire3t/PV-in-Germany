"""Write the MaStR and NEP Excel workbooks from the prepared data, then verify them.

Replaces the earlier Node builder (code/excel_build, made with Codex) with the
same sheets, values and formatting, written with openpyxl:

    poetry run python main.py excel-workbooks

Inputs: data/processed/mastr/, nep_scenarios/, nep_estimates/ and the BKG
district boundaries. Outputs: results/excel/mastr_solar_capacity.xlsx,
nep_solar_capacity.xlsx and redispatch_curtailment.xlsx. Every cell is checked against the input tables after
writing; the run stops with an error on any mismatch.
"""

# Allow running this file directly from an editor or any working directory.
if __package__ in (None, ''):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
import math
import numbers
import re
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

from project_paths import BKG_GEOJSON, DATA, FINAL_EXCEL
from data_preparation.read_workbook import STATE_CODES

PROCESSED = DATA / 'processed'
MASTR_FILE = 'mastr_solar_capacity.xlsx'
NEP_FILE = 'nep_solar_capacity.xlsx'
REDISPATCH_FILE = 'redispatch_curtailment.xlsx'

# Sheets whose numeric column headers receive their unit, e.g. "ground_mounted (MWp)".
UNIT_SHEETS = {'District capacity', 'State capacity', 'District capacity EST', 'District density',
               'State density', 'District density EST', 'Annual commissioning'}
HEADER_FILL = PatternFill('solid', fgColor='FF1F4E78')
HEADER_FONT = Font(name='Arial', size=10, bold=True, color='FFFFFFFF')
BODY_FONT = Font(name='Arial', size=10)


# ---------------------------------------------------------------- sheet contents

def read(path):
    return pd.read_csv(PROCESSED / path, dtype={'AGS': str})


def sheet(name, frame):
    """A sheet as a header row plus value rows; missing values become empty cells."""
    rows = frame.astype(object).where(pd.notna(frame), None).values.tolist()
    return dict(name=name, rows=[list(frame.columns)] + rows)


def overview(rows):
    return sheet('Overview', pd.DataFrame(rows, columns=['Topic', 'Description']))


def flatten(value, prefix=''):
    if isinstance(value, dict):
        return [row for k, v in value.items() for row in flatten(v, f'{prefix}.{k}' if prefix else k)]
    if isinstance(value, list):
        return [row for i, v in enumerate(value) for row in flatten(v, f'{prefix}[{i}]')]
    return [[prefix, value]]


def audit(name, path):
    """A JSON validation file flattened into Field / Value rows."""
    values = flatten(json.loads((PROCESSED / path).read_text(encoding='utf-8')))
    return sheet(name, pd.DataFrame(values, columns=['Field', 'Value']))


def wide(frame, index, column, value):
    return frame.pivot(index=index, columns=column, values=value).reset_index()


def additions_by_size(annual):
    """Capacity (MWp) and units commissioned per year and size class, with yearly totals."""
    capacity = annual.pivot_table(index='year', columns='power_band_kWp', values='capacity_MWp', aggfunc='sum')
    units = annual.pivot_table(index='year', columns='power_band_kWp', values='unit_count', aggfunc='sum')
    bands = ['<=10', '>10-30', '>30-100', '>100-1000', '>1000']
    table = pd.concat([capacity[bands].add_suffix(' kW (MWp)'), units[bands].add_suffix(' kW (units)')], axis=1)
    table.insert(len(bands), 'total (MWp)', capacity[bands].sum(axis=1))
    table['total (units)'] = units[bands].sum(axis=1)
    return table.reset_index()


def eeg_exit_table():
    """Both size classifications in one long table, with cumulative values and capacity share."""
    validation = json.loads((PROCESSED / 'mastr/eeg_exit_validation.json').read_text(encoding='utf-8'))
    frames = []
    for classes, path in (('MaStR series', 'mastr/pv_eeg_exit_by_year_power.csv'),
                          ('PwC chart', 'mastr/pv_eeg_exit_by_year_power_pwc_classes.csv')):
        frame = read(path).drop(columns='snapshot_date')
        frame.insert(1, 'size_classes', classes)
        group = frame.groupby('power_band_kWp', sort=False)
        frame['cumulative_unit_count'] = group.unit_count.cumsum()
        frame['cumulative_capacity_MWp'] = group.capacity_MWp.cumsum()
        frames.append(frame)
    table = pd.concat(frames, ignore_index=True)
    table['cumulative_share_of_operating_capacity_percent'] = (
        table.cumulative_capacity_MWp / validation['operating_capacity_MWp'] * 100)
    return table


def workbook_contents():
    """Sheets of both workbooks, built from the prepared CSV and JSON files."""
    nep = read('nep_scenarios/pv_by_land_ABC_2037_2045.csv')
    mastr = read('mastr/pv_by_district_2026.csv')
    areas = mastr.drop_duplicates('AGS').set_index('AGS').area_km2
    geo = json.loads(BKG_GEOJSON.read_text(encoding='utf-8'))
    state_codes = {f['properties']['AGS']: f['properties']['bundesland'] for f in geo['features']}
    names = {'DE.' + code: state for state, code in STATE_CODES.items()}
    # State area = sum of its BKG district areas (EPSG:3035), as in the MaStR preparation.
    state_area = {names[code]: sum(areas[ags] for ags, c in state_codes.items() if c == code)
                  for code in set(state_codes.values())}

    nep['case'] = nep.scenario + ' ' + nep.year.astype(str)
    nep_sheets = [overview([
        ['Contents', 'NEP photovoltaic capacity: scenarios A, B and C by state; district estimates for scenario B only.'],
        ['States', 'NEP 2025, second draft, figures 13–18. Published GW values converted to MWp.'],
        ['Districts', 'NEP 2025, first draft, figures 10–11. Densities inferred from map colours: estimates, not official tables.'],
        ['District years', '2024 is the reference year; B2037 and B2045 are scenario B projections.'],
        ['Technologies', 'ground_mounted: ground-mounted PV; rooftop: rooftop PV. MaStR building also includes facades.'],
        ['State density', 'Capacity divided by the sum of BKG district areas; kWp/km².'],
        ['District capacity', 'Estimated density × BKG area. Sums are not calibrated to official state totals.'],
        ['Area', 'BKG VG250, 31 December 2025; area calculated in EPSG:3035.'],
        ['Quality', 'District estimates retains quality indicators, pixel dispersion and saturation flags.'],
        ['Documents', 'NEP_2037_2045_V2025_2_Entwurf_2.pdf (states); NEP 2025 first draft (maps).'],
    ])]
    nep['capacity_MWp'] = nep.capacity_GW * 1000
    nep['density_kWp_per_km2'] = nep.apply(lambda r: r.capacity_MWp * 1000 / state_area[r.state], axis=1)
    nep_sheets += [
        sheet('State capacity', wide(nep, ['state', 'code'], 'case', 'capacity_MWp')
              .rename(columns=lambda c: c + ' (MWp)' if c[:1] in 'ABC' else c)),
        sheet('State density', wide(nep, ['state', 'code'], 'case', 'density_kWp_per_km2')
              .rename(columns=lambda c: c + ' (kWp/km²)' if c[:1] in 'ABC' else c)),
    ]
    est = read('nep_estimates/nep_pv_district_density_ESTIMATED_2024_B2037_B2045.csv')
    est['area_km2'] = est.AGS.map(areas)
    if est.area_km2.isna().any():
        raise ValueError('NEP district estimates contain districts without a BKG area.')
    est['estimated_capacity_MWp'] = est.estimated_MW_per_km2 * est.area_km2
    est['estimated_density_kWp_per_km2'] = est.estimated_MW_per_km2 * 1000
    district_index = ['state', 'district', 'AGS', 'technology']
    nep_sheets += [
        sheet('District capacity EST', wide(est, district_index, 'scenario', 'estimated_capacity_MWp')),
        sheet('District density EST', wide(est, district_index, 'scenario', 'estimated_density_kWp_per_km2')),
        sheet('State source ABC', nep.drop(columns=['case', 'capacity_MWp', 'density_kWp_per_km2'])),
        sheet('District estimates', est),
        sheet('East West ABC', read('nep_scenarios/east-west_ABC.csv')),
        sheet('South North ABC', read('nep_scenarios/south-north_ABC.csv')),
        audit('Validation', 'nep_scenarios/validation.json'),
    ]

    mastr['state'] = mastr.AGS.map(state_codes).map(names)
    if mastr.state.isna().any():
        raise ValueError('MaStR districts without a state in the BKG boundaries.')
    mastr_sheets = [overview([
        ['Snapshot', '13 October 2026; MaStR export Gesamtdatenexport_20261013_26.2.'],
        ['Source', 'https://download.marktstammdatenregister.de/Gesamtdatenexport_20261013_26.2.zip'],
        ['District capacity', 'Units in Germany, currently operating, commissioned by the snapshot date, with positive gross capacity.'],
        ['Units', 'Each record represents a generating unit, not an owner, household or necessarily an entire plant.'],
        ['Technologies', 'ground_mounted: ground-mounted PV; building: roofs and facades; balcony: balcony PV; other_unknown: other or unknown.'],
        ['Area and density', 'BKG VG250, 31 December 2025; EPSG:3035. Density in kWp/km².'],
        ['Annual series', 'Grouped by commissioning year, power band and current declared use; retired units included, planned units excluded.'],
        ['Annual interpretation', 'Reconstructed from the current register using current capacity and use; not historical installed stock or energy production.'],
        ['2026', 'Partial year through 13 October 2026.'],
        ['Geographic assignment', 'District mergers are adjusted. Missing valid codes are matched by district name and state when the match is unique.'],
        ['Validation', 'Validation retains exclusions and unmapped capacity; Annual validation contains checks for the annual series.'],
        ['Additions by size', 'Capacity and number of units commissioned each year by unit size (<10, 10-30, 30-100, 100-1,000 kW, >1 MW); retired units included.'],
        ['EEG exit', 'Operating units and capacity whose EEG payment ends, by year without payment (EEG commissioning year + 21; pre-2000 units: 2021) and size class, in two classifications: MaStR series and PwC chart. Annual and cumulative values; share of capacity in operation at the snapshot.'],
        ['EEG exit caveat', 'Only an explicit "no EEG payment" excludes a unit; the payment field is empty for most records and for almost all units since 2023, so exits after 2037 cannot be separated from unpaid units.'],
    ])]
    index = ['state', 'district', 'AGS']
    mastr_sheets += [
        sheet('District capacity', wide(mastr, index, 'technology', 'capacity_MWp')),
        sheet('District density', wide(mastr.assign(density_kWp_per_km2=mastr.density_MWp_per_km2 * 1000),
                                       index, 'technology', 'density_kWp_per_km2')),
    ]
    states = mastr.groupby(['state', 'technology'], as_index=False)[['capacity_MWp', 'units']].sum()
    states['density_kWp_per_km2'] = states.apply(lambda r: r.capacity_MWp * 1000 / state_area[r.state], axis=1)
    annual = read('mastr/pv_commissioning_by_year_power_use_2000_2026.csv')
    mastr_sheets += [
        sheet('State capacity', wide(states, ['state'], 'technology', 'capacity_MWp')),
        sheet('State density', wide(states, ['state'], 'technology', 'density_kWp_per_km2')),
        sheet('District detail', mastr),
        sheet('Annual commissioning', wide(annual, ['power_band_kWp', 'use_category'], 'year', 'capacity_MWp')),
        sheet('Annual detail', annual),
        audit('Validation', 'mastr/validation.json'),
        audit('Annual validation', 'mastr/annual_validation.json'),
        sheet('Additions by size', additions_by_size(annual)),
        sheet('EEG exit', eeg_exit_table()),
        audit('EEG exit validation', 'mastr/eeg_exit_validation.json'),
    ]
    redispatch_sheets = [overview([
        ['Contents', 'Curtailment of renewables by state in 2021 and the redispatch share by district in 2025.'],
        ['2021', 'BNetzA/Bundeskartellamt Monitoringbericht 2022, Abbildung 60: curtailed EEG feed-in (Einspeisemanagement) by state, GWh. Per area: divided by the Destatis state area (31 Dec 2024).'],
        ['2025', 'enervis for Green Planet Energy (2026), map "Anteil Redispatch an gesamter Stromerzeugung". No table is published: the classes were read from the map colours after aligning it with the BKG district boundaries. Estimates, not published values.'],
        ['Classes 2025', '<2 %, 2-3 %, 3 %, >3 % as in the source legend; legend_position is the position on the legend gradient (0 = bottom, 1 = top).'],
        ['No data 2025', 'Districts outside the networks of the ten distribution system operators analysed by enervis (covered = False).'],
    ])]
    redispatch_sheets += [
        sheet('Curtailment 2021', read('redispatch/curtailment_2021_by_state.csv')),
        sheet('Redispatch 2025', read('redispatch/redispatch_share_2025_by_district_ESTIMATED.csv')),
    ]
    if (PROCESSED / 'redispatch/curtailment_2016-2021_by_state_OFFICIAL.csv').exists():
        from data_preparation.redispatch_excel.prepare import main as prepare_redispatch
        prepare_redispatch()
        specs = json.loads((DATA / 'work/redispatch_excel_tables.json').read_text(encoding='utf-8'))
        redispatch_sheets = [sheet(spec['name'], pd.DataFrame(spec['rows'][1:], columns=spec['rows'][0]))
                             for spec in specs]
    return {NEP_FILE: nep_sheets, MASTR_FILE: mastr_sheets, REDISPATCH_FILE: redispatch_sheets}


# ---------------------------------------------------------------- writing

def is_number(value):
    return isinstance(value, numbers.Real) and not isinstance(value, (bool, np.bool_))


def add_units(spec):
    """Append the unit to numeric column headers of the capacity and density sheets."""
    rows = spec['rows']
    if spec['name'] not in UNIT_SHEETS:
        return rows
    unit = 'kWp/km²' if 'density' in spec['name'] else 'MWp'
    header = [f'{h} ({unit})' if is_number(rows[1][j]) and '(' not in str(h) else h
              for j, h in enumerate(rows[0])]
    return [header] + rows[1:]


def write_sheet(workbook, spec, table_name):
    ws = workbook.create_sheet(spec['name'])
    rows = add_units(spec)
    height, width = len(rows), len(rows[0])
    for row in rows:
        ws.append(row)
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = 'A2'
    for row in ws.iter_rows(min_row=1, max_row=height, max_col=width):
        for cell in row:
            cell.font = BODY_FONT
            cell.alignment = Alignment(vertical='center')
    for r in range(2, height + 1):
        ws.row_dimensions[r].height = 18
    for cell in ws[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    ws.row_dimensions[1].height = 38

    if spec['name'] == 'Overview':
        ws.column_dimensions['A'].width = 27
        ws.column_dimensions['B'].width = 110
        for r in range(2, height + 1):
            ws.cell(r, 2).alignment = Alignment(vertical='center', wrap_text=True)
            ws.row_dimensions[r].height = 44
        return

    for j in range(width):
        header = str(rows[0][j])
        values = [row[j] for row in rows[1:]]
        numeric = all(v is None or is_number(v) for v in values)
        letter = get_column_letter(j + 1)
        if numeric:
            whole = re.search(r'year|units|count|pixels|page|figure', header) or re.fullmatch(r'\d{4}', header)
            number_format = '#,##0' if whole else '#,##0.000'
        for r in range(2, height + 1):
            cell = ws.cell(r, j + 1)
            cell.alignment = Alignment(horizontal='right' if numeric else 'left', vertical='center')
            if numeric:
                cell.number_format = number_format
        ws.column_dimensions[letter].width = (
            65 if re.search(r'source|interpretation', header) else
            30 if re.search(r'district|state|use_category|technology|Field', header) else
            19 if numeric else 24)
    if 'alidation' in spec['name']:
        ws.column_dimensions['A'].width = 56
        ws.column_dimensions['B'].width = 100
        for r in range(2, height + 1):
            for c in (1, 2):
                ws.cell(r, c).alignment = Alignment(horizontal=ws.cell(r, c).alignment.horizontal,
                                                    vertical='center', wrap_text=True)
            ws.row_dimensions[r].height = 32
    table = Table(displayName=table_name, ref=f'A1:{get_column_letter(width)}{height}')
    table.tableStyleInfo = TableStyleInfo(name='TableStyleMedium2', showRowStripes=True)
    ws.add_table(table)


def write_workbook(path, sheets):
    workbook = Workbook()
    workbook.remove(workbook.active)
    prefix = 'T' + path.name.split('_')[0]
    for index, spec in enumerate(sheets):
        write_sheet(workbook, spec, f'{prefix}{index}')
    workbook.save(path)


# ---------------------------------------------------------------- verification

def verify_workbook(path, sheets):
    """Every sheet, header and cell of the written file must match its input table."""
    workbook = load_workbook(path, data_only=True)
    try:
        if workbook.sheetnames != [s['name'] for s in sheets]:
            raise AssertionError(f'{path.name}: sheet names differ')
        for spec in sheets:
            actual = list(workbook[spec['name']].values)
            expected = add_units(spec)
            if len(actual) != len(expected) or len(actual[0]) != len(expected[0]):
                raise AssertionError(f"{path.name} / {spec['name']}: size differs")
            if list(actual[0]) != expected[0]:
                raise AssertionError(f"{path.name} / {spec['name']}: headers differ")
            for want_row, got_row in zip(expected[1:], actual[1:]):
                for want, got in zip(want_row, got_row):
                    same = (math.isclose(want, got, rel_tol=1e-12, abs_tol=1e-10) if is_number(want) and is_number(got)
                            else want == got or (want in ('', None) and got is None))
                    if not same:
                        raise AssertionError(f"{path.name} / {spec['name']}: {want!r} written as {got!r}")
        if path.name == MASTR_FILE:
            rows = list(workbook['District capacity'].values)[1:]
            total = sum(v for row in rows for v in row[3:] if is_number(v))
            expected = json.loads((PROCESSED / 'mastr/validation.json').read_text(encoding='utf-8'))['mapped_capacity_MWp']
            if not math.isclose(total, expected, rel_tol=1e-12):
                raise AssertionError(f'MaStR district total {total} differs from validation.json {expected}')
            print(f'  MaStR district total matches validation.json: {total:,.3f} MWp')
    finally:
        workbook.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output', type=Path, default=FINAL_EXCEL)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for name, sheets in workbook_contents().items():
        path = args.output / name
        write_workbook(path, sheets)
        verify_workbook(path, sheets)
        cells = sum(len(s['rows']) * len(s['rows'][0]) for s in sheets)
        print(f'Written and verified: {path} ({len(sheets)} sheets, {cells:,} cells)')


if __name__ == '__main__':
    main()
