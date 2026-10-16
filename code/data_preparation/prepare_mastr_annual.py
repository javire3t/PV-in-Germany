"""Reconstruct solar commissioning cohorts by year, power band and building use."""
if __package__ in (None, ''):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import csv
from datetime import date
import gzip
import json
import math
from pathlib import Path
from xml.etree import ElementTree as ET

from data_preparation.prepare_mastr import units
from project_paths import RAW, DATA

BANDS = ('<=10', '>10-30', '>30-100', '>100-1000', '>1000')
USES = ('household', 'commerce_services', 'industry', 'agriculture',
        'public_building', 'other_uses', 'ground_mounted', 'no_information')
USE_LABELS = dict(zip(('Haushalt', 'Gewerbe, Handel und Dienstleistungen', 'Industrie',
                     'Landwirtschaft', 'Öffentliches Gebäude', 'Sonstige'), USES[:6]))
STATUSES = ('In Betrieb', 'Vorübergehend stillgelegt', 'Endgültig stillgelegt')


def power_band(power):
    if not math.isfinite(power) or power <= 0:
        raise ValueError('Positive finite gross capacity required')
    for index, upper in enumerate((10, 30, 100, 1000)):
        if power <= upper:
            return BANDS[index]
    return BANDS[-1]


def use_category(unit, lookup):
    if lookup.get(unit.get('ArtDerSolaranlage')) == 'Freiflächensolaranlage':
        return 'ground_mounted'
    # Do not infer household use from small size or balcony type.
    return USE_LABELS.get(lookup.get(unit.get('Nutzungsbereich')), 'no_information')


def aggregate_file(payload):
    path, lookup, cutoff = payload
    counts, capacity, audit, by_status = Counter(), Counter(), Counter(), Counter()
    for unit in units(path):
        audit['records_read'] += 1
        if lookup.get(unit.get('Land')) != 'Deutschland':
            audit['outside_germany'] += 1
            continue
        status = lookup.get(unit.get('EinheitBetriebsstatus'), 'unknown')
        if status not in STATUSES:
            audit['excluded_status_'+status] += 1
            continue
        try:
            commissioned = date.fromisoformat(unit.get('Inbetriebnahmedatum', '')[:10])
        except ValueError:
            audit['missing_invalid_commissioning_date'] += 1
            continue
        if commissioned > cutoff:
            audit['future_commissioning_date'] += 1
            continue
        try:
            power = float(unit.get('Bruttoleistung', ''))
            band = power_band(power)
        except ValueError:
            audit['invalid_capacity'] += 1
            continue
        if commissioned.year < 2000:
            audit['commissioned_before_2000'] += 1
            continue
        key = (commissioned.year, band, use_category(unit, lookup))
        counts[key] += 1
        capacity[key] += power
        by_status[status] += 1
        audit['included_units'] += 1
    return counts, capacity, audit, by_status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, default=RAW/'mastr'/'Gesamtdatenexport_20261013_26.2')
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    manifest = json.loads((args.folder/'manifest.json').read_text(encoding='utf-8'))
    stamp = Path(manifest['source_url']).stem.split('_')[1]
    cutoff = date.fromisoformat(f'{stamp[:4]}-{stamp[4:6]}-{stamp[6:]}')
    files = [args.folder/(Path(e['name']).name+'.gz') for e in manifest['files'] if 'EinheitenSolar' in e['name']]
    if not files or any(not p.exists() for p in files):
        raise RuntimeError('Complete solar export required')
    with gzip.open(args.folder/'Katalogwerte.xml.gz') as stream:
        lookup = {e.findtext('Id'):e.findtext('Wert') for e in ET.parse(stream).getroot()}
    counts, capacity, audit, by_status = Counter(), Counter(), Counter(), Counter()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for index, partials in enumerate(pool.map(aggregate_file, [(p, lookup, cutoff) for p in files]), 1):
            for combined, partial in zip((counts, capacity, audit, by_status), partials):
                combined.update(partial)
            print(f'[{index}/{len(files)}] processed', flush=True)
    output = DATA/'processed'/'mastr'
    output.mkdir(parents=True, exist_ok=True)
    target = output/f'pv_commissioning_by_year_power_use_2000_{cutoff.year}.csv'
    fields = ['year','power_band_kWp','use_category','unit_count','capacity_MWp','snapshot_date','partial_year']
    with target.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for year in range(2000, cutoff.year+1):
            for band in BANDS:
                for use in USES:
                    key = (year,band,use)
                    writer.writerow(dict(year=year,power_band_kWp=band,use_category=use,
                                         unit_count=counts[key],capacity_MWp=capacity[key]/1000,
                                         snapshot_date=cutoff.isoformat(),partial_year=year==cutoff.year and (cutoff.month,cutoff.day)!=(12,31)))
    summary = dict(source_url=manifest['source_url'],snapshot_date=cutoff.isoformat(),
                   records=dict(audit),included_units_by_current_status=dict(by_status),
                   total_capacity_MWp=sum(capacity.values())/1000,
                   capacity_MWp_by_use={u:sum(v for k,v in capacity.items() if k[2]==u)/1000 for u in USES},
                   years={str(y):dict(unit_count=sum(v for k,v in counts.items() if k[0]==y),
                                      capacity_MWp=sum(v for k,v in capacity.items() if k[0]==y)/1000)
                          for y in range(2000,cutoff.year+1)},
                   interpretation='Commissioning cohorts reconstructed from the current register, using current gross capacity and current building use; not original historical capacity or energy production. Retired units included, planned units excluded. Missing/deleted records and later expansions/reclassifications may affect cohorts. Counts refer to registered generating units, not users, owners or necessarily entire plants.')
    (output/'annual_validation.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    print(target,flush=True)
    print(json.dumps(summary,indent=2,ensure_ascii=False),flush=True)


if __name__ == '__main__':
    main()
