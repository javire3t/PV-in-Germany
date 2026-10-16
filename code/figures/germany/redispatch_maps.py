"""Curtailment of renewables by state in 2021 next to the redispatch share by district in 2025."""

# Allow running this file directly from an editor or any working directory.
if __package__ in (None, ''):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.patches import Patch

from project_paths import BKG_GEOJSON, DATA, FINAL_OUTPUTS, WORKBOOK
from data_preparation.read_workbook import STATE_CODES, state_data
from figures.shared.plot_helpers import add_polygon, figure_name, polygon_patch
from figures.shared.source_credits import add_source_footer
from figures.shared.crop_exports import save_cropped

REDISPATCH = DATA / 'processed/redispatch'
NO_DATA_COLOR = '#E3E3E3'
CITY_STATES = {'Berlin', 'Hamburg', 'Bremen'}
# Label positions that would otherwise fall on a neighbouring state (fraction of the bounding box).
LABEL_SHIFT = {'Brandenburg': (.80, .35), 'Hesse': (.5, .55)}


def polygons(geometry):
    return [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates']


def label_point(state, geometry):
    """Centroid of the largest polygon, or a fixed spot inside the bounding box where needed."""
    rings = [np.asarray(p[0]) for p in polygons(geometry)]
    if state in LABEL_SHIFT:
        points = np.concatenate(rings)
        low, high = points.min(axis=0), points.max(axis=0)
        return low + (high - low) * np.array(LABEL_SHIFT[state])
    ring = max(rings, key=lambda r: abs(np.dot(r[:-1, 0], r[1:, 1]) - np.dot(r[1:, 0], r[:-1, 1])))
    x, y = ring[:-1, 0], ring[:-1, 1]
    cross = x * np.roll(y, -1) - np.roll(x, -1) * y
    area = cross.sum() / 2
    return np.array([((x + np.roll(x, -1)) * cross).sum(), ((y + np.roll(y, -1)) * cross).sum()]) / (6 * area)


def draw_map(ax, shapes, colors, title):
    for geometry, color in zip(shapes, colors):
        for rings in polygons(geometry):
            patch = polygon_patch(rings, color)
            patch.set_edgecolor('#C8C8C8' if isinstance(color, str) and color == NO_DATA_COLOR else '#FFFFFF')
            patch.set_linewidth(.35)
            add_polygon(ax, patch)
    ax.autoscale_view()
    ax.set_aspect('equal')
    ax.set_axis_off()
    ax.set_title(title, fontsize=13, pad=10, color='#263238')


def export(fig, stem):
    target = FINAL_OUTPUTS / (stem + '.png')
    save_cropped(fig, target)
    plt.close(fig)
    print(target)


def footer(fig, extra):
    fig.text(.5, .075, extra, ha='center', fontsize=10, color='#36454F')
    fig.text(.5, .025,
             'Visualization: EIFER | 2021: BNetzA, Monitoringbericht 2022, Fig. 60 | '
             '2025: enervis / Green Planet Energy (2026), p. 4\n'
             '2025 classes estimated from source-map colours; no published district values. '
             'Boundaries: (c) BKG 2026, VG250, dl-de/by-2-0',
             ha='center', fontsize=8, color='#606970', linespacing=1.6)


def main():
    # Numeric-source comparison supersedes the earlier raster-colour estimates.
    from figures.germany.redispatch_official import main as official_main
    official_main()


if __name__ == '__main__':
    main()
