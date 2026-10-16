"""Draw new vector maps from digitized NEP estimates, explicitly labelled as estimates."""

# Allow running this file directly from an editor or any working directory.
if __package__ in (None, ''):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import json

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.cm import ScalarMappable
import numpy as np
import pandas as pd

from project_paths import FINAL_OUTPUTS, NEP_ESTIMATES, BKG_GEOJSON
from figures.shared.plot_helpers import polygon_patch, figure_name, add_polygon
from figures.shared.source_credits import source_lines, add_source_footer
from figures.shared.crop_exports import save_cropped


def source_color_scale(legend):
    """Preserve the PDF colorbar mapping used to decode district estimates."""
    values = np.asarray(legend['legend_values'], dtype=float)
    colors = np.asarray(legend['colors'], dtype=float) / 255
    order = np.argsort(values, kind='stable')
    values, indices = np.unique(values[order], return_index=True)
    colors = colors[order][indices]
    maximum = float(values[-1])
    positions = values / maximum
    stops = list(zip(positions, colors))
    if positions[0] > 0:
        stops.insert(0, (0., colors[0]))
    cmap = LinearSegmentedColormap.from_list('nep_source', stops, N=4096)
    return cmap, Normalize(vmin=0, vmax=maximum, clip=True)


def comparison_color_scale():
    """One linear scale for both technologies: equal colours mean equal densities."""
    cmap=LinearSegmentedColormap.from_list('nep_shared',
        ['#FFFFFF','#FFF4CC','#FFE69A','#FFD15A','#F2AA24','#D78011'],N=4096)
    return cmap,Normalize(vmin=0,vmax=4.6,clip=True)


def main():
    output = NEP_ESTIMATES
    figures = FINAL_OUTPUTS
    figures.mkdir(parents=True, exist_ok=True)
    table = pd.read_csv(output/'nep_pv_district_density_ESTIMATED_2024_B2037_B2045.csv', dtype={'AGS':str})
    features = json.loads(BKG_GEOJSON.read_text(encoding='utf-8'))['features']
    plt.rcParams.update({'font.family':'DejaVu Sans','text.color':'#18384A',
                         'axes.labelcolor':'#18384A','xtick.color':'#18384A','ytick.color':'#18384A'})
    cmap,norm=comparison_color_scale()
    fig=plt.figure(figsize=(10.5,11),facecolor='none')
    for row,(technology,title) in enumerate([('ground_mounted','Ground-mounted photovoltaic'),('rooftop','Rooftop photovoltaic')]):
        bottom=.54 if row==0 else .16
        fig.text(.45,bottom+.34,title,ha='center',fontsize=18,weight='bold')
        for index, scenario in enumerate(['2024','B2037','B2045']):
            estimates = table[(table.technology==technology)&(table.scenario==scenario)].set_index('AGS')
            ax=fig.add_axes([.01+index*.295,bottom,.29,.31])
            for feature in features:
                value=estimates.loc[feature['properties']['AGS'],'estimated_MW_per_km2']
                color=cmap(norm(value)) if np.isfinite(value) else '#cccccc'
                geometry=feature['geometry']
                polygons=[geometry['coordinates']] if geometry['type']=='Polygon' else geometry['coordinates']
                for polygon in polygons:
                    patch=polygon_patch(polygon,color)
                    patch.set_edgecolor('#000000')
                    patch.set_linewidth(.26)
                    add_polygon(ax, patch)
            ax.autoscale_view()
            ax.set_aspect('equal')
            ax.set_axis_off()
            # Same place and size as the labels in the source figures (NEP 2025,
            # 1st draft, p. 45): centred 59.4% across the country from the west,
            # 1.5% below its northern tip, with a 9 pt font on a 190.6 pt map.
            box = ax.dataLim
            ax.apply_aspect()
            map_height_pt = (ax.transData.transform((0, box.ymax))[1]
                             - ax.transData.transform((0, box.ymin))[1]) * 72 / fig.dpi
            ax.text(box.xmin + .594 * box.width, box.ymax - .015 * box.height,
                    scenario.replace('B', 'B '), ha='center', va='center',
                    fontsize=map_height_pt * 9 / 190.6, weight='bold', clip_on=False)
    cax=fig.add_axes([.895,.22,.022,.58])
    cb=fig.colorbar(ScalarMappable(norm=norm,cmap=cmap),cax=cax,ticks=[0,1,2,3,4,4.6])
    cb.ax.tick_params(labelsize=15,width=0,length=0,pad=8)
    cb.ax.set_title('MW/km²',fontsize=16,pad=14)
    cb.outline.set_visible(False)
    lines=source_lines('nep_estimates',boundaries=True)
    lines[0]='Visualization: EIFER · Adapted to a single colour scale and shared colourbar'
    add_source_footer(fig,lines,title='Ground-mounted and rooftop photovoltaic\nEstimated installed capacity per land area · Scenario B',fontsize=11)
    target=figures/figure_name('germany','all','ground-and-rooftop-density','map','2024-2037-2045','nep-b')
    save_cropped(fig,target,dpi=350)
    print(target)
    plt.close(fig)


if __name__=='__main__':
    main()
