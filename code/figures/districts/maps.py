"""Annual maps for selected states or districts."""

# Allow running this file directly from an editor or any working directory.
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
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
from matplotlib.ticker import MaxNLocator
from project_paths import settings, WORKBOOK, BKG_GEOJSON, FINAL_OUTPUTS, INTERMEDIATE_OUTPUTS
from data_preparation.read_workbook import read_data, select, match_geometry
from figures.shared.plot_helpers import polygon_patch, number, slug, figure_name, add_polygon
from figures.shared.source_credits import source_lines, add_source_footer
from figures.shared.crop_exports import save_cropped


# Default selection comes from settings.py in the project root.
SELECTED_STATES = settings.DISTRICT_MAP_STATES
SELECTED_DISTRICTS = settings.DISTRICT_MAP_DISTRICTS

def save_maps(records, years, unit, output, metric, boundary_path, vmax, scope):
    geojson = json.loads(boundary_path.read_text(encoding='utf-8'))
    matched = match_geometry(records, geojson)
    finite = [number(r['values'].get(y)) for r in records for y in years
              if isinstance(r['values'].get(y), (int, float))]
    if not finite:
        raise ValueError('No numeric values in selected years.')
    norm = Normalize(0, vmax if vmax is not None else max(max(finite), 1))
    cmap = plt.get_cmap('YlOrRd')
    selection = ', '.join(sorted({r['state'] for r in records}))
    for year in years:
        fig, ax = plt.subplots(figsize=(8, 8))
        for record, geometry in matched:
            value = record['values'].get(year)
            color = cmap(norm(value)) if isinstance(value, (int, float)) else '#cccccc'
            polygons = [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates']
            for rings in polygons:
                add_polygon(ax, polygon_patch(rings, color))
        ax.autoscale_view()
        ax.set_aspect('equal')
        ax.set_axis_off()
        ax.set_title(f'Photovoltaic {metric} — {year}\n{selection}', fontsize=13)
        fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), ax=ax, shrink=.65, label=unit,
                     extend='max' if vmax is not None and max(finite) > vmax else 'neither')
        fig.tight_layout(rect=(0,.15,1,1))
        add_source_footer(fig, source_lines(reference_year=max(years), boundaries=True, geojson=geojson))
        save_cropped(fig, output / figure_name('districts', scope, metric, 'map', year), dpi=180)
        plt.close(fig)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--states', nargs='*', help='State names, e.g. Bayern Thüringen')
    parser.add_argument('--districts', nargs='*', help='District names, IDs, or State:District')
    parser.add_argument('--start', type=int, default=settings.FIRST_YEAR)
    parser.add_argument('--end', type=int, help='Default: latest year in the workbook')
    parser.add_argument('--metric', choices=['capacity', 'density'], default='density')
    parser.add_argument('--boundaries', type=Path, default=BKG_GEOJSON)
    parser.add_argument('--vmax', type=float, help='Fixed map color-scale maximum')
    parser.add_argument('--workbook', type=Path, default=WORKBOOK)
    parser.add_argument('--output', type=Path, help='Explicit destination; annual maps otherwise go to data/work/district_maps')
    parser.add_argument('--list', action='store_true', help='List available State:District names and IDs')
    args = parser.parse_args()
    records, available = read_data(args.workbook, args.metric)
    if args.list:
        for r in records:
            print(f"{r['state']}:{r['name']}  {r['id']}")
        return
    explicit = args.states is not None or args.districts is not None
    selected = select(records, args.states or ([] if explicit else SELECTED_STATES),
                      args.districts or ([] if explicit else SELECTED_DISTRICTS))
    end = args.end if args.end is not None else max(available)
    years = [y for y in available if args.start <= y <= end]
    if not years:
        parser.error('No workbook years fall within the selected range.')
    if args.vmax is not None and args.vmax <= 0:
        parser.error('--vmax must be positive.')
    scope = '-'.join(sorted(slug(x) for x in {r['state'] for r in selected}))
    if args.districts or (not explicit and SELECTED_DISTRICTS):
        scope += '-' + '-'.join(sorted(slug(r['name']) + '-' + r['id'] for r in selected))
    unit = 'Installed capacity (MWp)' if args.metric == 'capacity' else 'Installed capacity density (kWp/km²)'
    output = args.output or INTERMEDIATE_OUTPUTS/'district_maps'
    output.mkdir(parents=True, exist_ok=True)
    save_maps(selected, years, unit, output, args.metric, args.boundaries, args.vmax, scope)
    print(f'Exported {len(selected)} districts, {years[0]}–{years[-1]}: {output}')

if __name__ == '__main__':
    main()
