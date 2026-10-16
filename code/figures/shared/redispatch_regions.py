"""North/south shares of observed energy, using the project's state grouping."""
import numpy as np
import pandas as pd
import cv2
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from data_preparation.read_workbook import REGION_GROUPS, STATE_CODES

GROUPS = REGION_GROUPS['south-north']
REGION_COLORS = {'North': '#2466B0', 'South': '#C83246'}


def outline_regions(ax, matched):
    def parts(geometry):
        return [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates']
    all_points = np.concatenate([np.asarray(p[0]) for _, g in matched for p in parts(g)])
    low, high = all_points.min(axis=0), all_points.max(axis=0)
    scale = 3000 / (high - low).max()
    size = np.ceil((high - low) * scale).astype(int) + 5
    for region, states in GROUPS.items():
        mask = np.zeros((size[1], size[0]), np.uint8)
        for record, geometry in matched:
            if record['state'] in states:
                for rings in parts(geometry):
                    cv2.fillPoly(mask, [np.rint((np.asarray(ring) - low) * scale + 2).astype(np.int32)
                                        for ring in rings], 255)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            points = (contour[:, 0, :] - 2) / scale + low
            points = np.vstack([points, points[0]])
            ax.plot(points[:, 0], points[:, 1], color=REGION_COLORS[region], lw=1.35, zorder=4)


def map_legend(fig, y=.12):
    fig.legend(handles=[Line2D([0], [0], color=REGION_COLORS['North'], lw=2, label='North'),
                        Line2D([0], [0], color=REGION_COLORS['South'], lw=2, label='South'),
                        Patch(facecolor='#DFDFDF', label='ND')],
               loc='center', bbox_to_anchor=(.5, y), ncol=3, frameon=False, fontsize=10)


def state_percent(value):
    if pd.isna(value):
        return 'ND'
    return f'{value:.2f}%' if 0 < value < .1 else f'{value:.1f}%'


def regional_totals(values, year, comparison):
    """Values are a Series keyed by English state name; excluded values must be NaN."""
    total = values.sum(min_count=1)
    rows = []
    for region, states in GROUPS.items():
        selected = values.reindex(states)
        energy = selected.sum(min_count=1)
        rows.append(dict(comparison=comparison, year=year, region=region,
                         included_states=int(selected.notna().sum()), energy_GWh=energy,
                         common_total_GWh=total, share=energy / total,
                         states=', '.join(STATE_CODES[s] for s in states if pd.notna(values.get(s)))))
    if all(pd.notna(r['share']) for r in rows):
        assert np.isclose(sum(r['share'] for r in rows), 1)
    return rows


