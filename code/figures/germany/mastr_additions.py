"""Annual PV additions in Germany by unit size, from the MaStR register (MWp per year)."""

# Allow running this file directly from an editor or any working directory.
if __package__ in (None, ''):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import MultipleLocator

from project_paths import DATA, FINAL_OUTPUTS
from figures.shared.plot_helpers import figure_name
from figures.shared.source_credits import source_lines, add_source_footer
from figures.shared.crop_exports import save_cropped

ANNUAL = DATA / 'processed/mastr/pv_commissioning_by_year_power_use_2000_2026.csv'
FIRST_YEAR, LAST_YEAR = 2000, 2025
# Same size classes and colour order as the pv magazine chart of the 2000s.
BANDS = ['<=10', '>10-30', '>30-100', '>100-1000', '>1000']
LABELS = ['< 10 kW', '10 to 30 kW', '30 to 100 kW', '100 to 1,000 kW', '> 1 MW']
SIZE_COLORS = ['#1F3D99', '#F5A623', '#E8562A', '#A7AAAE', '#8B1A1A']


def main():
    table = pd.read_csv(ANNUAL)
    table = table[(table.year >= FIRST_YEAR) & (table.year <= LAST_YEAR)]
    additions = table.pivot_table(index='year', columns='power_band_kWp', values='capacity_MWp',
                                  aggfunc='sum')[BANDS] / 1000
    years = additions.index.to_numpy()

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 12})
    fig, ax = plt.subplots(figsize=(14, 6.5), dpi=180, facecolor='none')
    bottom = np.zeros(len(years))
    for band, label, color in zip(BANDS, LABELS, SIZE_COLORS):
        ax.bar(years, additions[band], bottom=bottom, width=.72, color=color, label=label,
               edgecolor='white', linewidth=.4, zorder=3)
        bottom += additions[band].to_numpy()
    for year, total in zip(years, bottom):
        ax.text(year, total + bottom.max() * .012, f'{total:.1f}', ha='center', va='bottom',
                fontsize=9, color='#455A64')
    ax.set_xticks(years, [str(y) if y % 5 == 0 or y == years[-1] else f"'{y % 100:02d}" for y in years])
    ax.set_xlim(years[0] - .6, years[-1] + .6)
    ax.set_ylim(0, bottom.max() * 1.1)
    ax.set_ylabel('Added capacity (GWp per year)', fontsize=14)
    ax.yaxis.set_major_locator(MultipleLocator(2))
    ax.grid(axis='y', color='#CFD8DC', alpha=.6, linewidth=.7, zorder=0)
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    ax.legend(ncol=5, loc='upper left', frameon=False, fontsize=11, title='Unit size',
              title_fontsize=11, alignment='left')
    fig.tight_layout()
    add_source_footer(fig, source_lines('mastr'), fontsize=11,
                      title='Annual photovoltaic additions in Germany by unit size\n'
                            'Capacity of units commissioned each year, as recorded in the MaStR register')
    target = FINAL_OUTPUTS / figure_name('germany', 'all', 'additions-by-size', 'timeseries',
                                         f'{FIRST_YEAR}-{LAST_YEAR}')
    save_cropped(fig, target)
    plt.close(fig)
    print(target)


if __name__ == '__main__':
    main()
