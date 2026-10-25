"""Cumulative PV units and capacity leaving EEG payments, by exit year and unit size (MaStR)."""

# Allow running this file directly from an editor or any working directory.
if __package__ in (None, ''):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import argparse
import json
from datetime import date

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter, MultipleLocator

from project_paths import DATA, FINAL_OUTPUTS
from figures.germany.mastr_additions import BANDS, LABELS, SIZE_COLORS
from figures.shared.plot_helpers import figure_name
from figures.shared.source_credits import source_lines, add_source_footer
from figures.shared.crop_exports import save_cropped

# Size classes of the MaStR annual series, as used by the project figure.
SCHEMES = {
    'mastr': dict(table=DATA / 'processed/mastr/pv_eeg_exit_by_year_power.csv', metric='eeg-exit',
                  classes=BANDS, labels=LABELS, colors=SIZE_COLORS),
}
VALIDATION = DATA / 'processed/mastr/eeg_exit_validation.json'
# Cohorts up to 2016 (exit 2037) almost all received EEG payments. For units commissioned
# since 2023 the payment field is empty, so later exits cannot be separated from unpaid units.
LAST_EXIT_YEAR = 2037


def draw(scheme):
    spec = SCHEMES[scheme]
    table = pd.read_csv(spec['table'])
    summary = json.loads(VALIDATION.read_text(encoding='utf-8'))
    snapshot = date.fromisoformat(summary['snapshot_date'])
    table = table[table.exit_year <= LAST_EXIT_YEAR]
    units = table.pivot(index='exit_year', columns='power_band_kWp', values='unit_count')[spec['classes']].cumsum() / 1e6
    capacity = table.pivot(index='exit_year', columns='power_band_kWp', values='capacity_MWp')[spec['classes']].cumsum() / 1000
    years = units.index.to_numpy()
    installed_gw = summary['operating_capacity_MWp'] / 1000

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 12})
    fig, (top, bottom) = plt.subplots(2, 1, sharex=True, figsize=(13, 10), dpi=300, facecolor='none')
    fig.subplots_adjust(left=.09, right=.90, bottom=.2, top=.97, hspace=.12)
    for ax, frame, ylabel in ((top, units, 'Units without EEG payment\n(million, cumulative)'),
                              (bottom, capacity, 'Capacity without EEG payment\n(GWp, cumulative)')):
        stack = np.zeros(len(years))
        for band, label, color in zip(spec['classes'], spec['labels'], spec['colors']):
            ax.bar(years, frame[band], bottom=stack, width=.72, color=color, label=label,
                   edgecolor='white', linewidth=.4, zorder=3)
            stack += frame[band].to_numpy()
        # Exits up to the snapshot year have already happened; later ones follow from the rule.
        ax.axvspan(years[0] - .6, snapshot.year + .5, color='#ECEFF1', alpha=.6, zorder=0, linewidth=0)
        ax.set_ylabel(ylabel, fontsize=13)
        ax.set_ylim(0, stack.max() * 1.22)
        ax.grid(axis='y', color='#CFD8DC', alpha=.6, linewidth=.7, zorder=1)
        ax.spines['top'].set_visible(False)
        for year in (2026, 2030, 2033, LAST_EXIT_YEAR):
            index = int(np.where(years == year)[0][0])
            text = f'{stack[index]:.2f} M' if ax is top else f'{stack[index]:.0f} GW'
            ax.text(year, stack[index] + stack.max() * .015, text, ha='center', va='bottom',
                    fontsize=10, color='#263238', weight='bold')
    top.text((years[0] + snapshot.year) / 2, top.get_ylim()[1] * .5, 'already\nwithout EEG',
             ha='center', va='center', fontsize=11, color='#607D8B')
    top.yaxis.set_major_locator(MultipleLocator(.25))
    bottom.yaxis.set_major_locator(MultipleLocator(20))
    # Same bars read as a share of the capacity in operation today.
    share = bottom.secondary_yaxis('right', functions=(lambda gw: gw / installed_gw * 100,
                                                       lambda pct: pct * installed_gw / 100))
    share.set_ylabel(f'% of capacity in operation\non {snapshot:%d.%m.%Y} ({installed_gw:.0f} GWp)', fontsize=12)
    share.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v:.0f}%'))
    bottom.set_xticks([y for y in years if y % 2 == 1])
    bottom.set_xlim(years[0] - .6, years[-1] + .6)
    bottom.set_xlabel('Year without EEG payment (20 years after the EEG commissioning year)', fontsize=13)
    top.legend(ncol=5, loc='upper left', bbox_to_anchor=(.12, 1), frameon=False, fontsize=11,
               title='Unit size', title_fontsize=11, alignment='left')
    add_source_footer(fig, source_lines('mastr'), fontsize=11,
                      title='Photovoltaic units leaving EEG payments in Germany\n'
                            'Units in operation whose 20-year EEG payment has ended, cumulative by year')
    target = FINAL_OUTPUTS / figure_name('germany', 'all', spec['metric'], 'timeseries',
                                         f'{years[0]}-{years[-1]}')
    save_cropped(fig, target)
    plt.close(fig)
    print(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--classes', choices=['mastr'], default='mastr',
                        help='Size classes of the MaStR series')
    args = parser.parse_args()
    draw(args.classes)


if __name__ == '__main__':
    main()
