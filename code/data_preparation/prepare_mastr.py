"""Aggregate the complete MaStR solar export by district; retain exclusions in QA."""
if __package__ in (None, ''):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
import csv
import gzip
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
from pyproj import Transformer

from data_preparation.read_workbook import normalize
from project_paths import RAW, DATA, BKG_GEOJSON

GROUPS = ('ground_mounted', 'building', 'balcony', 'other_unknown')
STATE_NAMES = ['Schleswig-Holstein', 'Hamburg', 'Niedersachsen', 'Bremen',
               'Nordrhein-Westfalen', 'Hessen', 'Rheinland-Pfalz', 'Baden-Württemberg',
               'Bayern', 'Saarland', 'Berlin', 'Brandenburg', 'Mecklenburg-Vorpommern',
               'Sachsen', 'Sachsen-Anhalt', 'Thüringen']
# Administrative mergers already represented in the BKG 2025 boundaries.
DISTRICT_MERGERS = {'16056': '16063', '03152': '03159', '03156': '03159'}


def classify(label):
    return {'Freiflächensolaranlage': 'ground_mounted',
            'Gebäudesolaranlage': 'building',
            'Steckerfertige Solaranlage (sog. Balkonkraftwerk)': 'balcony'}.get(label, 'other_unknown')


def units(path):
    """Clear processed records; retain only empty nodes until each file closes."""
    with gzip.open(path, 'rb') as stream:
        iterator = ET.iterparse(stream, events=('end',))
        for _, element in iterator:
            if element.tag.rsplit('}', 1)[-1] == 'EinheitSolar':
                yield {child.tag.rsplit('}', 1)[-1]: child.text or '' for child in element}
                element.clear()


def area_km2(geometry):
    """Area of BKG land polygons in equal-area ETRS89 / LAEA Europe (EPSG:3035)."""
    transform = Transformer.from_crs(25832, 3035, always_xy=True)
    polygons = [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates']
    total = 0
    for polygon in polygons:
        for index, ring in enumerate(polygon):
            points = np.asarray(ring)
            x, y = transform.transform(points[:, 0], points[:, 1])
            x, y = np.asarray(x)-x[0], np.asarray(y)-y[0]
            area = abs(np.sum(x*np.roll(y, -1)-y*np.roll(x, -1)))/2
            total += area if index == 0 else -area
    return total/1e6


def aggregate_file(payload):
    path, lookup, boundaries, names, cutoff = payload
    totals, counts = Counter(), Counter()
    audit, audit_kw, unresolved = Counter(), Counter(), Counter()
    active_kw, active_count = Counter(), Counter()
    for unit in units(path):
        audit['records_read'] += 1
        if lookup.get(unit.get('Land')) != 'Deutschland':
            audit['outside_germany'] += 1
            continue
        if lookup.get(unit.get('EinheitBetriebsstatus')) != 'In Betrieb':
            audit['not_in_operation'] += 1
            continue
        commissioned = unit.get('Inbetriebnahmedatum', '')
        if not commissioned or commissioned[:10] > cutoff:
            audit['missing_or_future_commissioning_date'] += 1
            continue
        try:
            power = float(unit.get('Bruttoleistung', ''))
        except ValueError:
            audit['invalid_power'] += 1
            continue
        if not np.isfinite(power) or power <= 0:
            audit['invalid_power'] += 1
            continue
        group = classify(lookup.get(unit.get('ArtDerSolaranlage')))
        active_kw[group] += power
        active_count[group] += 1
        raw_ags = unit.get('Gemeindeschluessel', '')
        ags = raw_ags[:5] if len(raw_ags) == 8 and raw_ags.isdigit() else ''
        ags = DISTRICT_MERGERS.get(ags, ags)
        if ags not in boundaries:
            state = lookup.get(unit.get('Bundesland'))
            prefix = f'{STATE_NAMES.index(state)+1:02}' if state in STATE_NAMES else ''
            candidates = names.get((prefix, normalize(unit.get('Landkreis', ''))), [])
            if len(candidates) == 1:
                ags = candidates[0]
                audit['district_name_fallback'] += 1
            else:
                audit['unmatched_district'] += 1
                audit_kw['unmatched_district'] += power
                unresolved[f"{raw_ags}|{state}|{unit.get('Landkreis', '')}"] += power
                continue
        totals[(ags, group)] += power
        counts[(ags, group)] += 1
    return totals, counts, audit, audit_kw, unresolved, active_kw, active_count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, default=RAW/'mastr'/'Gesamtdatenexport_20261013_26.2')
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    manifest = json.loads((args.folder/'manifest.json').read_text(encoding='utf-8'))
    expected = [Path(e['name']).name+'.gz' for e in manifest['files'] if 'EinheitenSolar' in e['name']]
    if not expected or any(not (args.folder/n).exists() for n in expected):
        raise RuntimeError('Complete solar export required; finish download_mastr.py first')
    catalogue = ET.parse(gzip.open(args.folder/'Katalogwerte.xml.gz')).getroot()
    lookup = {e.findtext('Id'): e.findtext('Wert') for e in catalogue}
    features = json.loads(BKG_GEOJSON.read_text(encoding='utf-8'))['features']
    boundaries = {f['properties']['AGS']: f for f in features}
    names = defaultdict(list)
    for ags, feature in boundaries.items():
        names[(ags[:2], normalize(feature['properties']['GEN']))].append(ags)
    totals, counts = defaultdict(float), Counter()
    audit, audit_kw, unresolved = Counter(), Counter(), Counter()
    active_kw, active_count = Counter(), Counter()
    date = Path(manifest['source_url']).stem.split('_')[1]
    cutoff = f'{date[:4]}-{date[4:6]}-{date[6:]}'
    payloads = [(args.folder/name, lookup, set(boundaries), names, cutoff) for name in expected]
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        for index, values in enumerate(executor.map(aggregate_file, payloads), 1):
            for target_counter, partial in zip((totals, counts, audit, audit_kw, unresolved, active_kw, active_count), values):
                for key, value in partial.items():
                    target_counter[key] += value
            print(f'[{index}/{len(expected)}] processed {expected[index-1]}', flush=True)
    output = DATA/'processed'/'mastr'
    output.mkdir(parents=True, exist_ok=True)
    target = output/f'pv_by_district_{date[:4]}.csv'
    with target.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=['AGS', 'district', 'technology', 'units', 'capacity_MWp', 'area_km2', 'density_MWp_per_km2', 'snapshot_date'])
        writer.writeheader()
        for ags, feature in sorted(boundaries.items()):
            area = area_km2(feature['geometry'])
            for group in GROUPS:
                capacity = totals[(ags, group)]/1000
                writer.writerow(dict(AGS=ags, district=feature['properties']['GEN'], technology=group,
                                     units=counts[(ags, group)], capacity_MWp=capacity, area_km2=area,
                                     density_MWp_per_km2=capacity/area, snapshot_date=cutoff))
    qa = dict(snapshot_date=cutoff, source_url=manifest['source_url'], filters='Germany; in operation; commissioned by snapshot; positive gross power',
              category_definition='building includes roofs and facades; balcony and other/unknown retained separately',
              density_area='BKG VG250 31 Dec 2025 land polygons, equal-area EPSG:3035',
              records=dict(audit), national_capacity_MWp={k:v/1000 for k,v in active_kw.items()},
              national_units=dict(active_count), mapped_capacity_MWp=sum(totals.values())/1000,
              unmatched_capacity_MWp=audit_kw['unmatched_district']/1000,
              unmatched_locations_MWp={k:v/1000 for k,v in unresolved.most_common()})
    (output/'validation.json').write_text(json.dumps(qa, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(qa, indent=2, ensure_ascii=False), flush=True)
    print(target, flush=True)


if __name__ == '__main__':
    main()
