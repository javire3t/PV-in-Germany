"""Maps showing the project's explicit East/West and North/South definitions."""

# Allow running this file directly from an editor or any working directory.
if __package__ in (None, ''):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import argparse
import textwrap

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np
from matplotlib.colors import to_rgb
from matplotlib.patches import Patch

from data_preparation.read_workbook import REGION_GROUPS, STATE_CODES, state_data
from figures.shared.crop_exports import save_cropped
from figures.shared.plot_helpers import COLORS, add_polygon, polygon_patch
from figures.shared.source_credits import add_source_footer
from project_paths import FINAL_OUTPUTS, WORKBOOK


DEFINITIONS = {
    'east-west': {
        'title': 'East–West regional definition used in this project',
        'filename': 'Figure_definition_east-vs-west_germany.png',
    },
    'south-north': {
        'title': 'North–South regional definition used in this project',
        'filename': 'Figure_definition_north-vs-south_germany.png',
    },
}


def polygons(geometry):
    return [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates']


def label_point(state, geometry):
    """Return a stable interior-ish label point for a state geometry."""
    rings = [np.asarray(p[0], dtype=float) for p in polygons(geometry)]
    if state == 'Brandenburg':
        points = np.concatenate(rings)
        low, high = points.min(axis=0), points.max(axis=0)
        return low + (high - low) * np.array([.80, .35])
    if state == 'Hesse':
        points = np.concatenate(rings)
        low, high = points.min(axis=0), points.max(axis=0)
        return low + (high - low) * np.array([.50, .55])
    ring = max(rings, key=lambda r: abs(np.dot(r[:-1, 0], r[1:, 1]) -
                                         np.dot(r[1:, 0], r[:-1, 1])))
    x, y = ring[:-1, 0], ring[:-1, 1]
    cross = x * np.roll(y, -1) - np.roll(x, -1) * y
    area = cross.sum() / 2
    return np.array([((x + np.roll(x, -1)) * cross).sum(),
                     ((y + np.roll(y, -1)) * cross).sum()]) / (6 * area)


def light_color(color, white_amount=.72):
    """Blend the existing project colour with white for large map fills."""
    rgb = np.asarray(to_rgb(color))
    return tuple(rgb * (1 - white_amount) + white_amount)


def label_text(state):
    replacements = {
        'Mecklenburg-Western Pomerania': 'Mecklenburg–\nWestern Pomerania',
        'North Rhine-Westphalia': 'North Rhine–\nWestphalia',
        'Rhineland-Palatinate': 'Rhineland–\nPalatinate',
        'Baden-Württemberg': 'Baden–\nWürttemberg',
        'Schleswig-Holstein': 'Schleswig–\nHolstein',
    }
    return replacements.get(state, '\n'.join(textwrap.wrap(state, 16)))


def draw_map(definition, output=FINAL_OUTPUTS, dpi=300):
    if definition not in DEFINITIONS:
        raise ValueError(f'Unknown definition: {definition}')

    groups = REGION_GROUPS[definition]
    states = [state for members in groups.values() for state in members]
    if set(states) != set(STATE_CODES) or len(states) != len(set(states)):
        raise ValueError(f'{definition} must partition all 16 states exactly once')

    _, _, _, matched = state_data(WORKBOOK, states)
    group_by_state = {state: group for group, members in groups.items() for state in members}
    group_names = list(groups)
    group_base = {group: COLORS[index] for index, group in enumerate(group_names)}
    group_fill = {group: light_color(group_base[group]) for group in group_names}

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11})
    fig = plt.figure(figsize=(10.5, 10.2), dpi=dpi, facecolor='none')
    ax = fig.add_axes([.055, .20, .89, .66], facecolor='none')

    for record, geometry in matched:
        group = group_by_state[record['state']]
        for rings in polygons(geometry):
            patch = polygon_patch(rings, group_fill[group])
            patch.set_edgecolor('#FFFFFF')
            patch.set_linewidth(.85)
            add_polygon(ax, patch)

    ax.autoscale_view()
    ax.set_aspect('equal')
    ax.set_axis_off()
    ax.margins(.02)

    for record, geometry in matched:
        state = record['state']
        x, y = label_point(state, geometry)
        ax.text(x, y, label_text(state), ha='center', va='center',
                fontsize=8.4, color='#263238', linespacing=1.03, zorder=5,
                path_effects=[pe.withStroke(linewidth=2.4, foreground='white')])

    handles = [Patch(facecolor=group_fill[group], edgecolor=group_base[group],
                     linewidth=1.0, label=group) for group in group_names]
    ax.legend(handles=handles, loc='upper center', bbox_to_anchor=(.5, -.07),
              ncol=len(handles), frameon=False, fontsize=13,
              handlelength=1.4, handleheight=1.0, columnspacing=2.0,
              borderaxespad=0)

    add_source_footer(
        fig,
        ['Visualization: EIFER',
         'Data: Project regional definition; boundaries: (c) BKG 2025, VG250'],
        title=DEFINITIONS[definition]['title'],
        fontsize=11,
    )

    output.mkdir(parents=True, exist_ok=True)
    target = output / DEFINITIONS[definition]['filename']
    save_cropped(fig, target)
    plt.close(fig)
    print(target)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--definition', choices=[*DEFINITIONS, 'all'], default='all')
    args = parser.parse_args()
    definitions = DEFINITIONS if args.definition == 'all' else {args.definition: DEFINITIONS[args.definition]}
    for definition in definitions:
        draw_map(definition)


if __name__ == '__main__':
    main()
