"""Annual district maps and animation for Germany."""

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
import numpy as np
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
from PIL import Image
from project_paths import settings, WORKBOOK, BKG_GEOJSON, FINAL_OUTPUTS, INTERMEDIATE_OUTPUTS
from data_preparation.read_workbook import read_data, match_geometry
from figures.shared.plot_helpers import polygon_patch, number, gif_frame, gif_palette, figure_name, add_polygon
from figures.shared.source_credits import source_lines, add_source_footer
from figures.shared.crop_exports import crop_file, save_animation_frame

COLOR_SCALE_MAX = settings.GERMANY_DENSITY_SCALE_MAX





def main():
    """Create annual district maps and a GIF for all Germany from local data."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', type=int, default=settings.GERMANY_ANIMATION_FIRST_YEAR)
    parser.add_argument('--end', type=int, help='Default: latest year in the workbook')
    parser.add_argument('--metric', choices=['density','capacity'], default='density')
    parser.add_argument('--duration', type=int, default=1000)
    parser.add_argument('--vmax', type=float, default=COLOR_SCALE_MAX)
    parser.add_argument('--output', type=Path,
                        help='Default: results/figures (finished GIF only)')
    parser.add_argument('--workbook', type=Path, default=WORKBOOK)
    parser.add_argument('--boundaries', type=Path, default=BKG_GEOJSON)
    args = parser.parse_args()
    args.output = args.output or FINAL_OUTPUTS
    records, available = read_data(args.workbook, args.metric)
    capacity, _ = read_data(args.workbook, 'capacity')
    end = args.end if args.end is not None else max(available)
    years = [year for year in available if args.start<=year<=end]
    if not years or args.duration<20 or args.vmax <= 0:
        parser.error('Select available years, a duration of at least 20 ms and a positive color-scale maximum.')
    geojson = json.loads(args.boundaries.read_text(encoding='utf-8'))
    matched = match_geometry(records, geojson)
    if len(matched)!=len(geojson['features']) or len({record['id'] for record in records})!=len(matched):
        raise ValueError('National maps require a unique match for every BKG district.')
    matrix = np.array([[number(record['values'].get(year)) for year in years] for record in records])
    if not np.isfinite(matrix).all():
        raise ValueError('National data contains missing values; no incomplete maps were generated.')
    norm = Normalize(0, args.vmax, clip=True)
    cmap = plt.get_cmap('BuGn')
    unit = 'kWp/km²' if args.metric=='density' else 'MWp'
    totals = {year:sum(number(record['values'].get(year)) for record in capacity) for year in available}
    reference_year = max(available)
    reference_total = totals[reference_year]
    if not np.isfinite(reference_total) or reference_total <= 0:
        raise ValueError('Reference-year capacity must be finite and positive.')
    args.output.mkdir(parents=True,exist_ok=True)
    filename_prefix = figure_name('germany', 'all', args.metric, 'map-animation', f'{years[0]}-{years[-1]}', suffix='')
    maps_folder = INTERMEDIATE_OUTPUTS/'germany'/filename_prefix
    maps_folder.mkdir(parents=True,exist_ok=True)
    fig = plt.figure(figsize=(19.2,10.5),dpi=100,facecolor='none')
    map_box, scale_left = [.275,.14,.45,.74], .69
    text_x, text_align, total_y, credits_x = .50, 'center', .915, .50
    # Leave a dedicated footer under the map for its credits.
    ax = fig.add_axes(map_box,facecolor='none')
    patches = []
    for _,geometry in matched:
        polygons = [geometry['coordinates']] if geometry['type']=='Polygon' else geometry['coordinates']
        district_patches=[]
        for rings in polygons:
            patch=polygon_patch(rings,'white')
            patch.set_edgecolor('#9CB6A7'); patch.set_linewidth(.22)
            add_polygon(ax, patch); district_patches.append(patch)
        patches.append(district_patches)
    ax.autoscale_view(); ax.set_aspect('equal'); ax.set_axis_off(); ax.margins(.005)
    cax=fig.add_axes([scale_left,.20,.018,.62],facecolor='none')
    cb=fig.colorbar(ScalarMappable(norm=norm,cmap=cmap),cax=cax,
                    orientation='vertical',extend='max',extendfrac=.025,
                    ticks=[*range(0, int(args.vmax), 200), args.vmax])
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=24,length=0,pad=10,colors='#666666')
    cb.ax.set_title(unit,fontsize=20,pad=20,color='#666666')
    year_label=fig.text(text_x,.96,'',ha=text_align,va='top',fontsize=18,color='#008D49')
    total_label=fig.text(text_x,total_y,'',ha=text_align,va='top',fontsize=23,color='#666666')
    add_source_footer(fig, source_lines(reference_year=reference_year, boundaries=True, geojson=geojson),
                      center=credits_x,
                      fontsize=16 * .94,
                      title='Photovoltaic density by district' if args.metric == 'density'
                      else 'Installed photovoltaic capacity by district')
    frame_paths=[]
    for index,year in enumerate(years):
        for district_index,district_patches in enumerate(patches):
            for patch in district_patches:
                patch.set_facecolor(cmap(norm(matrix[district_index,index])))
        share = '' if year == reference_year else f' · {totals[year]/reference_total:.0%} of the {reference_year} total'
        year_label.set_text(str(year) + share)
        total_label.set_text(f'Total: {totals[year]:.0f} MWp')
        target=maps_folder/f'germany_pv_{args.metric}_by_district_{year}.png'
        save_animation_frame(fig,target); frame_paths.append(target)
        print(f'Saved: {target}',flush=True)
    plt.close(fig)
    with Image.open(frame_paths[-1]) as image:
        palette=gif_palette(image)
    frames=[]
    for path in frame_paths:
        with Image.open(path) as image:
            frames.append(gif_frame(image,palette))
    gif=args.output/f'{filename_prefix}.gif'
    durations=[args.duration]*len(years); durations[-1]=2500
    frames[0].save(gif,save_all=True,append_images=frames[1:],duration=durations,
                   disposal=2,optimize=False,transparency=255,background=255)
    crop_file(gif)
    for path in frame_paths:
        crop_file(path)
    # Keep the PDF preview with the other finished figures, not in work/.
    preview = args.output / f'Figure_{args.metric}-animation_germany_{years[0]}-{years[-1]}.png'
    with Image.open(frame_paths[-1]) as image:
        image.save(preview)
    with Image.open(gif) as check:
        if check.n_frames!=len(years):
            raise ValueError('Unexpected GIF frame count')
        if 'loop' in check.info:
            raise ValueError('The GIF must play once and stop at its final year')
        if 'transparency' not in check.info:
            raise ValueError('GIF lost its transparent background')
    print(f'Saved {len(years)} maps, GIF: {gif}, and preview: {preview}',flush=True)

if __name__ == '__main__':
    main()
