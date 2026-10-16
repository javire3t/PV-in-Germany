"""Extract published Land PV capacities and compare all NEP scenarios with history."""

# Allow running this file directly from an editor or any working directory.
if __package__ in (None, ''):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import csv
import json

import matplotlib.pyplot as plt
import numpy as np
import shapefile
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable

from project_paths import DATA, FINAL_OUTPUTS, BOUNDARIES
from data_preparation.read_workbook import group_data, REGION_GROUPS, STATE_CODES, state_areas
from figures.shared.plot_helpers import COLORS, figure_name, selection_slug, polygon_patch, add_polygon
from figures.shared.map_labels import add_external_map_labels
from project_paths import WORKBOOK
from figures.shared.source_credits import source_lines, add_source_footer
from figures.shared.crop_exports import save_cropped



def scenario_envelope(future, region, historical_value):
    """Published scenario range; B is preserved even if it is not the middle case."""
    values = np.array([[historical_value, *future[scenario][region]] for scenario in 'ABC'])
    return values.min(axis=0), values.max(axis=0), values[1]


def main(definitions=None, workbook_path=WORKBOOK, metric='capacity', output=None, scenario_style='band_b',
         band_edges=True):
    if metric != 'capacity':
        raise ValueError('Forecast charts show installed capacity.')
    if scenario_style not in {'lines', 'band_b', 'band', 'band_lines'}:
        raise ValueError('Unknown scenario presentation style')
    destination = DATA / 'processed/nep_scenarios'
    table = destination / 'pv_by_land_ABC_2037_2045.csv'
    with table.open(encoding='utf-8-sig', newline='') as file:
        rows = list(csv.DictReader(file))
    for row in rows:
        row['year'] = int(row['year'])
        row['capacity_GW'] = float(row['capacity_GW'])
    areas = state_areas(workbook_path)
    land_density_2045_b = {
        row['state']: row['capacity_GW'] * 1e6 / areas[row['state']]
        for row in rows if row['scenario'] == 'B' and row['year'] == 2045
    }
    checks = json.loads((destination / 'validation.json').read_text(encoding='utf-8'))
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':14,'text.color':'#263238',
                         'axes.labelcolor':'#263238'})
    for definition in definitions or REGION_GROUPS:
        records, density, years, shapes = group_data(workbook_path,definition)
        historical_end = max(years)
        history = np.array([[r['values'][year] for year in years] for r in (density if metric=='density' else records)])
        if metric=='capacity':
            history = history / 1000
        unit = 'GWp'
        future = {}
        exported = []
        for scenario in 'ABC':
            values = []
            for record in records:
                capacities = [sum(row['capacity_GW'] for row in rows if row['scenario']==scenario
                                  and row['year']==year and row['state'] in record['members']) for year in (2037,2045)]
                values.append(np.array(capacities)*1e6/record['area_km2'] if metric=='density' else np.array(capacities))
                for year, capacity in zip((2037,2045), capacities):
                    exported.append(dict(region=record['name'],scenario=scenario,year=year,
                                         capacity_GW=round(capacity,3),area_km2=record['area_km2'],
                                         density_kWp_per_km2=capacity*1e6/record['area_km2']))
            future[scenario] = np.array(values)
        with (destination/f'{definition}_ABC.csv').open('w',encoding='utf-8-sig',newline='') as file:
            writer=csv.DictWriter(file,fieldnames=list(exported[0])); writer.writeheader(); writer.writerows(exported)
        fig=plt.figure(figsize=(14,9.5),dpi=180,facecolor='none')
        axes = fig.subplots(2, 1, sharex=True)
        fig.subplots_adjust(left=.085, right=.70, bottom=.23, top=.96, hspace=.13)
        # Map beside the panels: 2045 scenario-B density in green, with the
        # comparison colours retained only for region outlines and labels.
        region_map = fig.add_axes([.73, .36, .26, .48])
        density_cmap = plt.get_cmap('BuGn')
        density_norm = Normalize(0, 1400, clip=True)
        region_index = {state: i for i, record in enumerate(records) for state in record['members']}
        state_reader = shapefile.Reader(str(BOUNDARIES / 'BKG_VG250/vg250_ebenen_1231/VG250_LAN.shp'))
        try:
            for item in state_reader.iterShapeRecords():
                properties = item.record.as_dict()
                if properties.get('GF') != 4:
                    continue
                state = next((name for name, code in STATE_CODES.items()
                              if code == properties.get('LKZ')), None)
                if state is None or state not in region_index:
                    continue
                i = region_index[state]
                density_2045 = land_density_2045_b[state]
                geometry = item.shape.__geo_interface__
                polygons = ([geometry['coordinates']] if geometry['type'] == 'Polygon'
                            else geometry['coordinates'])
                for rings in polygons:
                    patch = polygon_patch(rings, density_cmap(density_norm(density_2045)))
                    patch.set_edgecolor(COLORS[i])
                    patch.set_linewidth(.45)
                    add_polygon(region_map, patch)
        finally:
            state_reader.close()
        region_map.autoscale_view()
        region_map.set_aspect('equal')
        region_map.set_axis_off()
        add_external_map_labels(region_map, shapes, [r['name'] for r, _ in shapes], COLORS, fontsize=14)
        scalar_map = ScalarMappable(norm=density_norm, cmap=density_cmap)
        scalar_map.set_array([])
        colorbar = fig.colorbar(scalar_map, ax=region_map, fraction=.035, pad=.02,
                                ticks=[0, 700, 1400])
        colorbar.set_label('PV density, 2045 NEP B\n(kWp/km²)', fontsize=9)
        colorbar.ax.tick_params(labelsize=8)
        chart = axes[0]
        for panel in axes:
            panel.axvspan(historical_end,2045.5,color='#FFF4E6',alpha=.18,zorder=0)
        forecast_note = {'band_b': 'Forecast: NEP A–C range\nDashed line: scenario B',
                         'band': 'Forecast: NEP A–C range',
                         'lines': 'Forecast: NEP A / B / C',
                         'band_lines': 'Forecast: NEP A–C range and scenario lines'}[scenario_style]
        chart.text(2035.5,.97,forecast_note,transform=chart.get_xaxis_transform(),
                   ha='center',va='top',fontsize=11)
        for density_panel, chart in enumerate(axes):
            for i,record in enumerate(records):
                factor = 1e6 / record['area_km2'] if density_panel else 1.0
                panel_history = history[i] * factor
                panel_future = {key: values * factor for key, values in future.items()}
                chart.plot(years,panel_history,color=COLORS[i],linewidth=2.4,label=record['name'])
                projection_years = [historical_end,2037,2045]
                if scenario_style != 'lines':
                    lower, upper, scenario_b = scenario_envelope(panel_future, i, panel_history[-1])
                    chart.fill_between(projection_years, lower, upper, color=COLORS[i],
                                       alpha=.10 if band_edges else .16, linewidth=0, zorder=2)
                    if band_edges:
                        # Outline each A–C range so overlapping bands stay distinguishable.
                        for bound in (lower, upper):
                            chart.plot(projection_years, bound, color=COLORS[i], linewidth=1.1,
                                       alpha=.75, zorder=3)
                    if scenario_style == 'band_b':
                        chart.plot(projection_years, scenario_b, color=COLORS[i],
                                   linestyle='--', linewidth=.9)
                if scenario_style in {'lines', 'band_lines'}:
                    for scenario in 'ABC':
                        chart.plot(projection_years,[panel_history[-1],*panel_future[scenario][i]],
                                   color=COLORS[i],linestyle=':',linewidth=1.8)
            if not density_panel:
                chart.legend(loc='upper left',frameon=False,fontsize=12)
            maximum = max(max(history[i].max(), max(v[i].max() for v in future.values()))
                          * (1e6 / record['area_km2'] if density_panel else 1.0)
                          for i, record in enumerate(records))
            chart.set(xlim=(years[0]-.5,2045.5),ylim=(0,maximum*1.17),xlabel='Year' if density_panel else '',
                      ylabel='PV density (kWp/km²)' if density_panel else 'Installed PV capacity (GWp)')
            chart.set_xticks([2000,2008,2016,historical_end,2037,2045])
            chart.grid(color='#CFD8DC',alpha=.5,linewidth=.7)
            chart.tick_params(labelsize=12)
            chart.xaxis.label.set_size(14)
            chart.yaxis.label.set_size(14)
        title = ('Photovoltaic capacity and density — ' + ' vs '.join(r['name'] for r in records) +
                 '\nHistorical data and NEP forecast')
        add_source_footer(fig, source_lines('nep_scenarios', reference_year=historical_end, areas=True, boundaries=True),
                          title=title, fontsize=11)
        folder=output or FINAL_OUTPUTS; folder.mkdir(parents=True,exist_ok=True)
        target=folder/figure_name('regions',selection_slug(r['name'] for r in records),'capacity-and-density',
                                  'timeseries',f'{years[0]}-2045','nep-abc')
        save_cropped(fig,target); plt.close(fig); print(target)
    print(json.dumps(checks,indent=2))

if __name__ == '__main__':
    main()
