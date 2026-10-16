"""Static comparisons: historical installed capacity beside latest-year map density."""
import argparse
import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from matplotlib.ticker import MaxNLocator

from project_paths import settings, WORKBOOK, BKG_GEOJSON, FINAL_OUTPUTS
from data_preparation.read_workbook import (read_data, select, match_geometry, state_data,
                                             group_data, REGION_GROUPS, ALIASES, STATE_CODES,
                                             normalize)
from figures.shared.plot_helpers import polygon_patch, add_polygon, COLORS, figure_name, selection_slug
from figures.shared.map_labels import add_external_map_labels
from figures.shared.source_credits import source_lines, add_source_footer, is_partial_year
from figures.shared.crop_exports import save_cropped


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--districts',nargs=2,default=settings.DISTRICTS_TO_COMPARE)
    parser.add_argument('--states',nargs=2)
    parser.add_argument('--groups',choices=REGION_GROUPS)
    parser.add_argument('--start',type=int,default=settings.FIRST_YEAR)
    parser.add_argument('--end',type=int)
    parser.add_argument('--output',type=Path,default=FINAL_OUTPUTS)
    parser.add_argument('--workbook',type=Path,default=WORKBOOK)
    args=parser.parse_args()
    if args.groups and args.states:parser.error('Use either --groups or --states.')
    geojson=json.loads(BKG_GEOJSON.read_text(encoding='utf-8'))
    if args.groups:
        records,densities,available,matched=group_data(args.workbook,args.groups)
        _,map_densities,_,map_matched=state_data(args.workbook,list(STATE_CODES))
        scale='regions'
    elif args.states:
        names=[ALIASES.get(normalize(name),name) for name in args.states]
        records,densities,available,matched=state_data(args.workbook,names)
        map_densities,map_matched=densities,matched
        scale='states'
    else:
        records,available=read_data(args.workbook,'capacity')
        records=select(records,[],args.districts)
        densities,_=read_data(args.workbook,'density')
        densities=select(densities,[],args.districts)
        matched=match_geometry(records,geojson)
        map_densities,map_matched=densities,matched
        scale='districts'
    if len(records)!=2 or records[0]['name']==records[1]['name']:parser.error('Choose two distinct regions.')
    years=[y for y in available if args.start<=y<=(args.end or max(available))]
    if len(years)<2:parser.error('Select at least two historical years.')
    year=years[-1]
    values=np.asarray([[r['values'][y] for y in years] for r in records],dtype=float)
    if not np.isfinite(values).all():raise ValueError('Incomplete historical capacity values.')
    density_by_name={r['name']:r['values'][year] for r in densities}
    final_density=np.asarray([density_by_name[r['name']] for r in records],dtype=float)
    if not np.isfinite(final_density).all():raise ValueError('Incomplete map density values.')
    factor=1000 if values.max()>=1000 else 1
    unit='GWp' if factor==1000 else 'MWp'
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'axes.labelsize':14,'text.color':'#263238'})
    fig=plt.figure(figsize=(14,7.15),dpi=180,facecolor='none')
    ax=fig.add_axes([.075,.28,.57,.64])
    map_ax=fig.add_axes([.71,.31,.23,.57])
    for i,r in enumerate(records):
        ax.plot(years,values[i]/factor,color=COLORS[i],lw=2.3,label=r['name'])
        if is_partial_year(year):
            ax.plot(year,values[i,-1]/factor,'o',mfc='white',mec=COLORS[i],mew=1.4,ms=5)
    ticks=[y for y in years if y%5==0 and year-y>=3]+[year]
    ax.set_xticks(ticks,[str(y) for y in ticks])
    ax.set(xlabel='Year',ylabel=f'Installed capacity ({unit})',xlim=(years[0]-.5,year+.5),ylim=(0,(values/factor).max()*1.12))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=6))
    ax.grid(color='#CFD8DC',alpha=.5,lw=.7)
    ax.legend(loc='upper left',frameon=False)
    # Use the national density-map palette and fixed ceiling for every static
    # comparison. The comparison colours remain reserved for the outlines,
    # chart lines and external labels.
    cmap=plt.get_cmap('BuGn')
    norm=Normalize(0,780,clip=True)
    record_index={r['name']:i for i,r in enumerate(records)}
    region_index={state:i for i,record in enumerate(records) for state in record.get('members', [])}
    map_density_by_name={r['name']:r['values'][year] for r in map_densities}
    for r,geometry in map_matched:
        i=region_index.get(r['name'], record_index.get(r['name']))
        color=cmap(norm(map_density_by_name[r['name']])) if args.groups else cmap(norm(final_density[i]))
        polygons=[geometry['coordinates']] if geometry['type']=='Polygon' else geometry['coordinates']
        for rings in polygons:
            patch=polygon_patch(rings,color)
            patch.set_edgecolor(COLORS[i]);patch.set_linewidth(.55)
            add_polygon(map_ax,patch)
    map_ax.autoscale_view();map_ax.set_aspect('equal');map_ax.set_axis_off();map_ax.margins(.05)
    labels=[f"{r['name']}\n{density_by_name[r['name']]:,.1f} kWp/km²" for r,_ in matched]
    add_external_map_labels(map_ax,matched,labels,[COLORS[record_index[r['name']]] for r,_ in matched],fontsize=12)
    map_ax.set_title(f'Map: capacity density\n{year}',fontsize=12,pad=48)
    cax=fig.add_axes([.958,.36,.012,.43])
    bar=fig.colorbar(ScalarMappable(norm=norm,cmap=cmap),cax=cax)
    bar.ax.set_title('kWp/km²',fontsize=10,pad=10);bar.ax.tick_params(labelsize=10)
    title='Installed photovoltaic capacity — '+' vs '.join(r['name'] for r in records)
    add_source_footer(fig,source_lines(reference_year=year,boundaries=True,geojson=geojson,areas=bool(args.states or args.groups)),
                      title=title+'\nHistorical capacity and latest-year map density',fontsize=11)
    args.output.mkdir(parents=True,exist_ok=True)
    target=args.output/figure_name(scale,selection_slug(r['name'] for r in records),'capacity-and-density','comparison',f'{years[0]}-{year}')
    save_cropped(fig,target);plt.close(fig);print(target)


if __name__=='__main__':main()
