"""Extract official historical EinsMan state tables without bridging the Redispatch 2.0 break."""
if __package__ in (None, ''):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import pymupdf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
from matplotlib.patches import Patch
from project_paths import DATA, RESULTS, WORKBOOK
from data_preparation.read_redispatch import GERMAN_NAMES
from data_preparation.read_workbook import state_data, STATE_CODES
from figures.germany.redispatch_maps import polygons, label_point, export
from figures.shared.plot_helpers import add_polygon, polygon_patch
from figures.shared.redispatch_regions import regional_totals, outline_regions, state_percent
from figures.shared.source_credits import add_source_footer

SOURCES = [
    (2017, 28, 'https://www.bundesnetzagentur.de/SharedDocs/Mediathek/Berichte/2018/Quartalsbericht_Q4_Gesamt_2017.pdf?__blob=publicationFile&v=4'),
    (2019, 19, 'https://www.bundesnetzagentur.de/SharedDocs/Mediathek/Berichte/2020/Quartalszahlen_Gesamtjahr_2019.pdf?__blob=publicationFile&v=1'),
    (2021, 19, 'https://www.bundesnetzagentur.de/SharedDocs/Downloads/DE/Sachgebiete/Energie/Unternehmen_Institutionen/Versorgungssicherheit/Engpassmanagement/Zahlen%20Ganzes%20Jahr2021.pdf?__blob=publicationFile&v=4'),
]


def number(token):
    return np.nan if token == '-' else float(token.replace('.', '').replace(',', '.'))


def main():
    rows = []
    checks = []
    for report_year, page_index, url in SOURCES:
        with pymupdf.open(DATA / f'raw/redispatch/bnetza_nem_{report_year}.pdf') as document:
            page = document[page_index]
            lines = [t.strip() for t in page.get_text().splitlines() if t.strip()]
            assert 'Ausfallarbeit' in lines and 'Bundesland' in lines
            positions = sorted((lines.index(name), name) for name in GERMAN_NAMES)
            total_pos = lines.index('Gesamt')
            assert len(positions) == 16
            for index, (pos, name) in enumerate(positions):
                end = positions[index + 1][0] if index + 1 < 16 else total_pos
                cells = ' '.join(lines[pos + 1:end]).split()
                assert len(cells) == 8, (report_year, name, cells)
                for offset, year in [(0, report_year), (4, report_year - 1)]:
                    token = cells[offset]
                    rows.append(dict(year=year, state=GERMAN_NAMES[name], state_de=name,
                                     curtailment_GWh=number(token), source_token=token,
                                     status='dash in source; not imputed' if token == '-' else 'reported number',
                                     scope='EinsMan: EEG and CHP plants', source_url=url,
                                     pdf_page=page_index + 1, report_year=report_year))
            totals = ' '.join(lines[total_pos + 1:total_pos + 9]).split()
            for offset, year in [(0, report_year), (4, report_year - 1)]:
                official = number(totals[offset])
                subtotal = sum(r['curtailment_GWh'] for r in rows if r['year'] == year and np.isfinite(r['curtailment_GWh']))
                # Values are rounded to integer GWh in the 2021 report.
                assert abs(official - subtotal) < (8 if report_year == 2021 else .1), (year, official, subtotal)
                checks.append(dict(year=year, reported_total_GWh=official, sum_numeric_states_GWh=subtotal))
            if report_year == 2017:
                page.get_pixmap(matrix=pymupdf.Matrix(1.4, 1.4)).save(DATA / 'work/redispatch_2017_table_check.png')
    frame = pd.DataFrame(rows).sort_values(['year', 'state'])
    assert len(frame) == 96 and not frame.duplicated(['year', 'state']).any()
    target = DATA / 'processed/redispatch/curtailment_2016-2021_by_state_OFFICIAL.csv'
    frame.to_csv(target, index=False, encoding='utf-8-sig')
    paired = frame.pivot(index='state', columns='year', values='curtailment_GWh')[[2016, 2021]]
    common_states = paired.index[paired.notna().all(axis=1)]
    comparison = paired.rename(columns={2016: 'raw_2016_GWh', 2021: 'raw_2021_GWh'})
    comparison['included'] = comparison.index.isin(common_states)
    for year in [2016, 2021]:
        comparison[f'mapped_{year}_GWh'] = comparison[f'raw_{year}_GWh'].where(comparison.included)
        comparison[f'mapped_{year}_share'] = comparison[f'mapped_{year}_GWh'] / comparison[f'mapped_{year}_GWh'].sum()
    comparison.to_csv(DATA / 'processed/redispatch/comparison_2016-2021_common_states.csv')
    summaries = {year: regional_totals(paired[year].where(paired.index.isin(common_states)), year, '2016-2021')
                 for year in [2016, 2021]}
    pd.DataFrame([row for rows in summaries.values() for row in rows]).to_csv(
        DATA / 'processed/redispatch/north_south_2016-2021.csv', index=False)
    pd.DataFrame(checks).sort_values('year').to_csv(DATA / 'processed/redispatch/curtailment_history_total_checks.csv', index=False)
    _, _, _, matched = state_data(WORKBOOK, list(STATE_CODES))
    plt.rcParams.update({'font.family': 'DejaVu Sans'})
    fig, axes = plt.subplots(1, 2, figsize=(14, 10), dpi=300)
    fig.subplots_adjust(left=.025, right=.975, top=.94, bottom=.23, wspace=.12)
    # Shared scale with the separate redispatch figure so the two maps are
    # directly comparable, while remaining separate figures.
    cmap, norm = plt.get_cmap('YlOrRd'), Normalize(0, 5000)
    for ax, year in zip(axes, [2016, 2021]):
        table = frame[frame.year.eq(year)].set_index('state')
        for record, geometry in matched:
            state = record['state']
            value = table.loc[state, 'curtailment_GWh'] if state in common_states else np.nan
            for rings in polygons(geometry):
                patch = polygon_patch(rings, '#DFDFDF' if pd.isna(value) else cmap(norm(value)))
                patch.set_edgecolor('#788084')
                patch.set_linewidth(.55)
                add_polygon(ax, patch)
            if STATE_CODES[state] in {'BE', 'HB', 'HH'}:
                continue
            x, y = label_point(state, geometry)
            names = {'Mecklenburg-Western Pomerania': 'Mecklenburg-\nWestern Pomerania',
                     'Baden-Württemberg': 'Baden-\nWürttemberg', 'North Rhine-Westphalia': 'North Rhine-\nWestphalia'}
            label = names.get(state, state) + '\n' + state_percent(comparison.loc[state, f'mapped_{year}_share'] * 100)
            ax.text(x, y, label, ha='center', va='center', fontsize=8,
                    path_effects=[pe.withStroke(linewidth=2.4, foreground='white')], color='#20333C')
        ax.autoscale_view()
        ax.set_aspect('equal')
        ax.set_axis_off()
        ax.set_title(str(year), fontsize=19, weight='bold', pad=10)
        outline_regions(ax, matched)
    cax = fig.add_axes([.27, .18, .46, .018])
    fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation='horizontal', label='Curtailed energy (GWh/year)')
    add_source_footer(fig,
                      ['Visualization: EIFER', 'Data: Bundesnetzagentur (retrieved 16.10.2026)'],
                      fontsize=15,
                      title='Historical renewable and CHP curtailment by state')
    export(fig, 'Figure_curtailment-einsman_germany_2016-2021')
    print(frame[frame.state.eq('Bavaria')][['year', 'curtailment_GWh']].to_string(index=False))


if __name__ == '__main__':
    main()
