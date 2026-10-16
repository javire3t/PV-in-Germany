"""Standalone German district density map with readable, non-overlapping labels."""

if __package__ in (None, ''):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import patheffects
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.path import Path as PlotPath
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

from data_preparation.read_workbook import read_data, match_geometry
from figures.shared.plot_helpers import polygon_patch, figure_name, add_polygon
from figures.shared.crop_exports import save_cropped
from figures.shared.source_credits import source_lines, add_source_footer
from project_paths import settings, WORKBOOK, BKG_GEOJSON, FINAL_OUTPUTS, INTERMEDIATE_OUTPUTS


SCALE_MAX = settings.GERMANY_DENSITY_SCALE_MAX


def polygons(geometry):
    return [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates']


def ring_area(ring):
    points = np.asarray(ring, dtype=float)
    points = points - points[0]
    following = np.roll(points, -1, axis=0)
    return abs(np.sum(points[:, 0]*following[:, 1] - following[:, 0]*points[:, 1]))/2


def contains_points(geometry, points):
    """Test land coverage, respecting interior holes and multipart districts."""
    result = np.zeros(len(points), dtype=bool)
    for rings in polygons(geometry):
        inside = PlotPath(np.asarray(rings[0])).contains_points(points)
        for hole in rings[1:]:
            inside &= ~PlotPath(np.asarray(hole)).contains_points(points)
        result |= inside
    return result


def label_anchor(geometry):
    """Find an interior point in the largest land part, away from its boundary."""
    rings = max(polygons(geometry), key=lambda polygon: ring_area(polygon[0]))
    outer = np.asarray(rings[0], dtype=float)
    low, high = outer.min(axis=0), outer.max(axis=0)
    xs = np.linspace(low[0], high[0], 33)[1:-1]
    ys = np.linspace(low[1], high[1], 33)[1:-1]
    x, y = np.meshgrid(xs, ys)
    candidates = np.column_stack([x.ravel(), y.ravel()])
    local_geometry = {'type': 'Polygon', 'coordinates': rings}
    candidates = candidates[contains_points(local_geometry, candidates)]
    if not len(candidates):
        raise ValueError('Could not find an interior district label point')
    # Densify long straight segments so distance is not measured only to corners.
    step = max(float((high-low).max())/80, 1e-6)
    boundary = []
    for ring in rings:
        points = np.asarray(ring, dtype=float)
        for a, b in zip(points, np.roll(points, -1, axis=0)):
            subdivisions = max(1, int(np.ceil(np.linalg.norm(b-a)/step)))
            fractions = np.arange(subdivisions)/subdivisions
            boundary.extend(a + fractions[:, None]*(b-a))
    distance, _ = cKDTree(np.asarray(boundary)).query(candidates)
    anchor = candidates[int(np.argmax(distance))]
    assert contains_points(geometry, [anchor])[0]
    return anchor


def geometry_area(geometry):
    return sum(ring_area(rings[0]) - sum(ring_area(hole) for hole in rings[1:])
               for rings in polygons(geometry))


def create_map(matched, anchors, year, output, geojson, scale_max, dpi):
    norm = Normalize(0, scale_max, clip=True)
    # Keep the upper end light enough for dark district values to stay readable.
    cmap = LinearSegmentedColormap.from_list(
        'BuGn_light', plt.get_cmap('BuGn')(np.linspace(.08, .65, 256)))
    plt.rcParams.update({'font.family': 'DejaVu Sans'})
    # Portrait composition follows the roadmap reference and gives numbers room.
    fig = plt.figure(figsize=(12, 15.75), dpi=dpi, facecolor='none')
    # Reserve a compact, dedicated area for the shared three-line footer.
    ax = fig.add_axes([.035,.10,.775,.82], facecolor='none')
    for record, geometry in matched:
        for rings in polygons(geometry):
            patch = polygon_patch(rings, cmap(norm(record['values'][year])))
            patch.set_edgecolor('#9CB6A7')
            patch.set_linewidth(.35)
            add_polygon(ax, patch)
    ax.autoscale_view()
    ax.set_aspect('equal')
    ax.set_axis_off()
    ax.margins(.015)
    cax = fig.add_axes([.865,.25,.022,.53], facecolor='none')
    ticks = [*range(0, int(scale_max), 200), scale_max]
    colorbar = fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=cax,
                           extend='max', extendfrac=.025, ticks=ticks)
    colorbar.outline.set_visible(False)
    colorbar.ax.tick_params(labelsize=16, length=0, pad=8, colors='#555555')
    colorbar.ax.set_title('kWp/km²', fontsize=16, color='#555555', pad=16)
    credits = source_lines(reference_year=year, boundaries=True, geojson=geojson)
    add_source_footer(fig, credits, title=f'Photovoltaic density by district · {year}')
    texts = []
    for index, (record, geometry) in enumerate(matched):
        text = ax.text(*anchors[index], f"{record['values'][year]:.0f}", ha='center',va='center',
                       fontsize=9.5, fontweight='bold',
                       color='#172820',zorder=5,
                       path_effects=[patheffects.withStroke(linewidth=.45,foreground='white')])
        texts.append(text)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    accepted, boxes = [], []
    priority = sorted(range(len(matched)), key=lambda i: (-geometry_area(matched[i][1]), matched[i][0]['id']))
    # Padding includes the halo, plus a small gap between adjacent numbers.
    padding = .8 * dpi / 72
    for index in priority:
        box = texts[index].get_window_extent(renderer).padded(padding)
        # Interior anchors identify the district; the full number need not
        # fit inside a small polygon. Keep a visible gap between numbers.
        if not any(box.overlaps(other) for other in boxes):
            accepted.append(index)
            boxes.append(box)
        else:
            texts[index].set_visible(False)
    assert all(not a.overlaps(b) for i, a in enumerate(boxes) for b in boxes[i+1:])
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    name = figure_name('germany', 'all', 'density', 'map-labeled', year)
    target = output / name
    save_cropped(fig, target)
    with Image.open(target) as image:
        assert image.mode == 'RGBA'
    plt.close(fig)
    print(f'{target}: {len(accepted)}/{len(matched)} labels',flush=True)
    return {
        'file': name, 'mode': 'readable', 'year': year, 'district_count': len(matched),
        'label_count': len(accepted), 'scale_min': 0, 'scale_max': scale_max,
        'labelled_districts': [dict(AGS=matched[i][0]['id'],name=matched[i][0]['name'],
                                    density=matched[i][0]['values'][year],
                                    position=anchors[i].tolist()) for i in accepted],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--year', type=int, help='Default: latest year in the workbook')
    parser.add_argument('--vmax', type=float, default=SCALE_MAX)
    parser.add_argument('--dpi', type=int, default=180)
    parser.add_argument('--output', type=Path, default=FINAL_OUTPUTS)
    parser.add_argument('--workbook', type=Path, default=WORKBOOK)
    parser.add_argument('--boundaries', type=Path, default=BKG_GEOJSON)
    args = parser.parse_args()
    records, available = read_data(args.workbook, 'density')
    args.year = args.year if args.year is not None else max(available)
    if args.year not in available or args.vmax <= 0 or args.dpi < 72:
        parser.error('Choose an available year, positive vmax and dpi >= 72.')
    if not all(np.isfinite(record['values'][args.year]) for record in records):
        raise ValueError('Missing district densities; no incomplete map generated')
    geojson = json.loads(args.boundaries.read_text(encoding='utf-8'))
    matched = match_geometry(records, geojson)
    if len(matched) != len(geojson['features']) or len({r['id'] for r in records}) != len(matched):
        raise ValueError('Every district must have a unique boundary match')
    print(f'Preparing interior label positions for {len(matched)} districts...',flush=True)
    anchors = [label_anchor(geometry) for record, geometry in matched]
    args.output.mkdir(parents=True, exist_ok=True)
    checks = [create_map(matched, anchors, args.year, args.output, geojson, args.vmax, args.dpi)]
    audit = INTERMEDIATE_OUTPUTS/'district_value_maps'/str(args.year)
    audit.mkdir(parents=True, exist_ok=True)
    (audit/'label_validation.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')


if __name__ == '__main__':
    main()
