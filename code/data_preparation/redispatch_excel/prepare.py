"""Prepare typed workbook tables; preserve raw observations and paired coverage separately."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / 'data/processed/redispatch'
WORK = ROOT / 'data/work'


def table(name, frame):
    frame = frame.replace([np.inf, -np.inf], np.nan)
    return {'name': name, 'rows': [list(frame.columns), *json.loads(frame.to_json(orient='values', force_ascii=False))]}


def main():
    history = pd.read_csv(DATA / 'curtailment_2016-2021_by_state_OFFICIAL.csv')
    recent = pd.read_csv(DATA / 'smard_reductions_by_state_annual_GWh.csv').set_index('year')
    historic_pair = history.pivot(index='state', columns='year', values='curtailment_GWh')[[2016, 2021]]
    historic_pair.columns = ['source_2016_GWh', 'source_2021_GWh']
    historic_pair['included'] = historic_pair.notna().all(axis=1)
    for year in [2016, 2021]:
        historic_pair[f'map_{year}_GWh'] = historic_pair[f'source_{year}_GWh'].where(historic_pair.included)
        historic_pair[f'map_{year}_share'] = historic_pair[f'map_{year}_GWh'] / historic_pair[f'map_{year}_GWh'].sum()
    historic_pair['reason'] = np.where(historic_pair.included, 'Data in both years', 'No data in one or both years')
    codes = ['BW', 'BY', 'BE', 'BB', 'HB', 'HH', 'HE', 'MV', 'NI', 'NW', 'RP', 'SL', 'SN', 'ST', 'SH', 'TH']
    recent_pair = recent.loc[[2023, 2025], codes].T
    recent_pair.columns = ['source_2023_GWh', 'source_2025_GWh']
    recent_pair['included'] = recent_pair.notna().all(axis=1)
    for year in [2023, 2025]:
        recent_pair[f'map_{year}_GWh'] = recent_pair[f'source_{year}_GWh'].where(recent_pair.included)
        recent_pair[f'map_{year}_share'] = recent_pair[f'map_{year}_GWh'] / recent_pair[f'map_{year}_GWh'].sum()
    recent_pair['reason'] = np.where(recent_pair.included, 'Data in both years', 'No data in one or both years')
    meta = pd.DataFrame([
        ['Coverage rule', 'Compare only regions with data in both periods. Others are grey in both panels.'],
        ['Missing values', 'Blank source cells are missing. Only source data determine availability; small numbers remain valid data.'],
        ['Historic comparison', f'2016 and 2021: {int(historic_pair.included.sum())} of 16 states included; EEG/CHP EinsMan scope.'],
        ['Recent comparison', f'2023 and 2025: {int(recent_pair.included.sum())} of 16 states included; all generation technologies.'],
        ['Percentage denominator', 'Only common states; neighbouring countries and unallocated volumes excluded.'],
        ['North and south', 'South: BY, BW, HE, RP, SL, TH. North: SH, HH, NI, HB, NW, BB, BE, MV, SN, ST.'],
        ['Method change', 'Historical renewable/CHP data are not spliced with recent all-technology data.'],
        ['SMARD source', 'https://www.smard.de/resource/blob/217306/-/data-csv-data.csv'],
        ['SMARD definitions', 'https://www.smard.de/page/home/topic-article/211972/213254/netzengpassmanagement-je-bundesland-und-anrainerstaaten'],
        ['Data snapshot', '15 October 2026. Historical source URLs and PDF pages are included beside each observation.'],
    ], columns=['Item', 'Description'])
    sheets = [table('Overview', meta), table('Compare 2016-2021', historic_pair.reset_index()),
              table('Compare 2023-2025', recent_pair.rename_axis('state_code').reset_index()),
              table('North and South', pd.concat([pd.read_csv(DATA / 'north_south_2016-2021.csv'),
                                                pd.read_csv(DATA / 'north_south_2023-2025.csv')], ignore_index=True)),
              table('Historic source 2016-2021', history), table('SMARD annual source', recent.reset_index()),
              table('SMARD technology source', pd.read_csv(DATA / 'smard_reductions_by_technology_annual_GWh.csv'))]
    assert 0 < int(historic_pair.included.sum()) <= 16
    assert historic_pair.loc[~historic_pair.included, ['map_2016_GWh', 'map_2021_GWh']].isna().all().all()
    assert recent_pair.included.all()
    assert np.allclose(recent_pair[['map_2023_share', 'map_2025_share']].sum(), 1)
    (WORK / 'redispatch_excel_tables.json').write_text(json.dumps(sheets, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    print(f'Historic common states: {historic_pair.included.sum()}; recent: {recent_pair.included.sum()}')


if __name__ == '__main__':
    main()
    import sys
    if '--export' in sys.argv:
        import subprocess
        subprocess.run(['node', str(Path(__file__).with_name('export.mjs'))], check=True)
