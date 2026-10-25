"""Official SMARD regional reductions; no inference from raster-map colours."""
if __package__ in (None, ''):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import csv
import json
import textwrap
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
from matplotlib.patches import Patch
from project_paths import DATA, FINAL_OUTPUTS, RESULTS, WORKBOOK
from data_preparation.read_workbook import STATE_CODES, state_data
from figures.germany.redispatch_maps import polygons, label_point, export
from figures.shared.plot_helpers import polygon_patch, add_polygon
from figures.shared.redispatch_regions import regional_totals, outline_regions, state_percent
from figures.shared.source_credits import add_source_footer

SOURCE = 'https://www.smard.de/resource/blob/217306/-/data-csv-data.csv'
STATE_PAGE = 'https://www.smard.de/page/home/topic-article/211972/213254/netzengpassmanagement-je-bundesland-und-anrainerstaaten'
TECH_PAGE = 'https://www.smard.de/page/home/topic-article/211816/213384'
CODES = ['BW', 'BY', 'BE', 'BB', 'HB', 'HH', 'HE', 'MV', 'NI', 'NW', 'RP', 'SL', 'SN', 'ST', 'SH', 'TH']
TECH = ['Wind offshore', 'Wind onshore', 'Lignite', 'Photovoltaics', 'Hard coal', 'Natural gas',
        'Nuclear', 'Biomass', 'Pumped storage', 'Hydropower', 'Other renewables',
        'Other conventional', 'Unknown / exchange']
PROCESSED = DATA / 'processed/redispatch'


def annual(rows, series, columns):
    selected = [r for r in rows if r[0].lstrip('\ufeff') == series]
    assert selected and all(len(r) == len(columns) + 2 for r in selected)
    frame = pd.DataFrame([[r[1], *map(float, r[2:])] for r in selected], columns=['date', *columns])
    frame['date'] = pd.to_datetime(frame.date)
    assert not frame.date.duplicated().any()
    assert np.isfinite(frame[columns]).all().all()
    frame['year'] = frame.date.dt.year
    counts = frame.groupby('year').date.count()
    complete = counts[counts.eq(12)].index
    result = frame[frame.year.isin(complete)].groupby('year')[columns].sum()
    assert {2023, 2024, 2025}.issubset(result.index)
    return result


def credit(fig, note):
    fig.text(.5, .13, note, ha='center', fontsize=10, color='#283E45')
    fig.text(.5, .045, 'Source: Bundesnetzagentur / SMARD, monthly data summed over January-December; retrieved 15 Oct 2026\n'
             'Regional series: s-nepm_nepm_ba-1-1 | All 16 states included; neighbouring countries and unallocated volumes excluded from map shares\n'
             'Visualization: EIFER | Boundaries: (c) BKG 2026, VG250, dl-de/by-2-0',
             ha='center', fontsize=8.5, linespacing=1.6, color='#59666B')


def main():
    with (DATA / 'raw/redispatch/smard_chart_data.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.reader(f, delimiter=';'))
    regions = annual(rows, 's-nepm_nepm_ba-1-1', CODES + ['Neighbouring countries', 'Unallocated'])
    technologies = annual(rows, 's-nepm_re_et-1-1', TECH)
    regions.to_csv(PROCESSED / 'smard_reductions_by_state_annual_GWh.csv')
    technologies.to_csv(PROCESSED / 'smard_reductions_by_technology_annual_GWh.csv')
    names = {code: name for name, code in STATE_CODES.items()}
    included = CODES
    common = regions.loc[[2023, 2025], included].notna().all(axis=0)
    mapped = regions[included].copy()
    mapped.loc[:, ~common] = np.nan
    shares = mapped.div(mapped.sum(axis=1), axis=0) * 100
    shares.to_csv(PROCESSED / 'smard_reductions_by_state_annual_share.csv')
    assert np.allclose(shares.sum(axis=1), 100)
    summaries = {year: regional_totals(mapped.loc[year].rename(index=names), year, '2023-2025')
                 for year in [2023, 2025]}
    pd.DataFrame([row for rows in summaries.values() for row in rows]).to_csv(
        PROCESSED / 'north_south_2023-2025.csv', index=False)
    _, _, _, matched = state_data(WORKBOOK, list(STATE_CODES))
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11})
    table, vmax, unit = mapped, 5000, 'Generation reductions (GWh/year)'
    fig, axes = plt.subplots(1, 2, figsize=(14, 10), dpi=300)
    fig.subplots_adjust(left=.025, right=.975, top=.94, bottom=.23, wspace=.12)
    norm = Normalize(0, vmax)
    cmap = plt.get_cmap('YlOrRd')
    for ax, year in zip(axes, [2023, 2025]):
        for record, geometry in matched:
            state = record['state']
            code = STATE_CODES[state]
            value = table.loc[year, code]
            for rings in polygons(geometry):
                patch = polygon_patch(rings, '#E0E0E0' if pd.isna(value) else cmap(norm(value)))
                patch.set_edgecolor('#737D80')
                patch.set_linewidth(.55)
                add_polygon(ax, patch)
            if code in {'BE', 'HB', 'HH'}:
                continue
            x, y = label_point(state, geometry)
            label = '\n'.join(textwrap.wrap(state, 16))
            label += '\n' + state_percent(shares.loc[year, code])
            ax.text(x, y, label, ha='center', va='center', fontsize=8,
                    path_effects=[pe.withStroke(linewidth=2.4, foreground='white')], color='#1C2E35')
        ax.autoscale_view()
        ax.set_aspect('equal')
        ax.set_axis_off()
        ax.set_title(str(year), fontsize=18, weight='bold', pad=10)
        outline_regions(ax, matched)
    cax = fig.add_axes([.27, .18, .46, .018])
    fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation='horizontal', label=unit)
    add_source_footer(fig,
                      ["Visualization: EIFER", "Data: SMARD (retrieved 16.10.2026)"],
                      fontsize=15,
                      title="Redispatch reductions by state, GWh")
    export(fig, 'Figure_redispatch-reductions-gwh_germany_2023-2025')

    lines = ['# Redispatch: resultados de la extraccion oficial', '',
             'Fecha de descarga: 15 de octubre de 2026.', '',
             '## Alcance', '',
             'Los mapas comparan reducciones de generacion de todas las tecnologias en 2023 y 2025. '
             'No representan exclusivamente curtailment renovable. Se eligio 2023 por ser el primer ano completo '
             'de la serie mensual, que empieza en julio de 2022. Los 16 estados, incluido BW, se incluyen en mapas y denominadores; '
             'no se modifica el dato original. Los estados urbanos se incluyen aunque sus nombres no se rotulan.', '',
             'La tabla publica no cruza estado y tecnologia. No se puede derivar de ella un mapa exacto '
             'de curtailment renovable por estado para compararlo con 2021. No se han estimado valores ausentes.', '',
             '## Resultados regionales (todas las tecnologias)', '',
             '| Ano | Baviera GWh | Baviera %* | NI + SH GWh | NI + SH %* |',
             '| --- | ---: | ---: | ---: | ---: |']
    for year in [2023, 2024, 2025]:
        lines.append(f'| {year} | {regions.loc[year,"BY"]:.2f} | {shares.loc[year,"BY"]:.2f} | '
                     f'{regions.loc[year,["NI","SH"]].sum():.2f} | {shares.loc[year,["NI","SH"]].sum():.2f} |')
    print(regions.loc[[2023, 2025], ['BY', 'NI', 'SH']].to_string())


if __name__ == '__main__':
    main()
