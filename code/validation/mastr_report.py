"""Write the MaStR reconciliation diagnostic plot."""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from project_paths import VALIDATION_RESULTS
P = VALIDATION_RESULTS / 'mastr_energy_charts'
d = pd.read_csv(P/'district_comparison.csv', dtype={'AGS': str})
fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
x, y = d.energy_charts_MWp, d.mastr_MWp
axes[0].scatter(x, y, s=15, alpha=.6, color='#246A8A')
limit = max(x.max(), y.max())*1.03
axes[0].plot([0, limit], [0, limit], color='black', lw=1, label='Equality')
axes[0].set(xlabel='Energy-Charts (MWp), updated 17 Sep 2026', ylabel='MaStR (MWp), snapshot 13 Oct 2026', title='Capacity in 400 districts')
axes[0].legend(frameon=False)
axes[1].hist(d.difference_pct, bins=30, color='#246A8A', edgecolor='white')
axes[1].axvline(0, color='black', lw=1)
axes[1].set(xlabel='100 × (MaStR / Energy-Charts − 1) [%]', ylabel='Number of districts', title='Relative difference by district')
fig.tight_layout()
fig.savefig(P/'comparison.png', dpi=180)
plt.close(fig)
print(P/'comparison.png')
