"""Read the fixed Energy-Charts workbook and match official BKG geometry."""
import json
import re
import unicodedata
from openpyxl import load_workbook
from project_paths import BKG_GEOJSON, BOUNDARIES

ALIASES = {'bayern': 'Bavaria', 'thuringen': 'Thuringia', 'thueringen': 'Thuringia',
           'bw': 'Baden-Württemberg', 'badenwurttemberg': 'Baden-Württemberg'}
STATE_CODES = dict(zip(
    ['Schleswig-Holstein', 'Hamburg', 'Lower Saxony', 'Bremen', 'North Rhine-Westphalia',
     'Hesse', 'Rhineland-Palatinate', 'Baden-Württemberg', 'Bavaria', 'Saarland',
     'Berlin', 'Brandenburg', 'Mecklenburg-Western Pomerania', 'Saxony', 'Saxony-Anhalt', 'Thuringia'],
    ['SH', 'HH', 'NI', 'HB', 'NW', 'HE', 'RP', 'BW', 'BY', 'SL', 'BE', 'BB', 'MV', 'SN', 'ST', 'TH']))

# The only copy of the state areas: the workbook's State density sheet is written
# from it, and figures read the areas back from that sheet.
# Source: German Federal Statistical Office (Destatis), Bodenfläche nach
# Nutzungsarten und Bundesländern, reference date 31.12.2024.
# https://www.destatis.de/DE/Themen/Branchen-Unternehmen/Landwirtschaft-Forstwirtschaft-Fischerei/Flaechennutzung/Tabellen/bodenflaeche-laender.html
STATE_AREA_KM2 = {
    'Schleswig-Holstein': 15804, 'Hamburg': 755, 'Lower Saxony': 47710, 'Bremen': 420,
    'North Rhine-Westphalia': 34112, 'Hesse': 21116, 'Rhineland-Palatinate': 19858,
    'Baden-Württemberg': 35748, 'Bavaria': 70542, 'Saarland': 2572, 'Berlin': 891,
    'Brandenburg': 29654, 'Mecklenburg-Western Pomerania': 23294, 'Saxony': 18450,
    'Saxony-Anhalt': 20555, 'Thuringia': 16202}


REGION_GROUPS = {
    'east-west': {
        'East': ['Brandenburg', 'Mecklenburg-Western Pomerania', 'Saxony', 'Saxony-Anhalt', 'Thuringia', 'Berlin'],
        'West': ['Schleswig-Holstein', 'Hamburg', 'Lower Saxony', 'Bremen', 'North Rhine-Westphalia',
                 'Hesse', 'Rhineland-Palatinate', 'Baden-Württemberg', 'Bavaria', 'Saarland'],
    },
    'south-north': {
        # Listed North first so legends, titles and file names share alphabetical order.
        'North': ['Schleswig-Holstein', 'Hamburg', 'Lower Saxony', 'Bremen', 'North Rhine-Westphalia',
                  'Brandenburg', 'Berlin', 'Mecklenburg-Western Pomerania', 'Saxony', 'Saxony-Anhalt'],
        'South': ['Bavaria', 'Baden-Württemberg', 'Hesse', 'Rhineland-Palatinate', 'Saarland', 'Thuringia'],
    },
}


def normalize(value):
    value = str(value)
    if 'Ã' in value or 'Â' in value:
        for encoding in ('latin1', 'cp1252'):
            try:
                value = value.encode(encoding).decode('utf-8')
                break
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
    value = unicodedata.normalize('NFKD', str(value)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]', '', value)

def read_data(path, metric):
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook['District capacity' if metric == 'capacity' else 'District density']
        rows = iter(sheet.values)
        headers = next(rows)
        columns = {int(str(h).split()[0]): i for i, h in enumerate(headers)
                   if re.match(r'^\d{4}\b', str(h))}
        id_col = headers.index('District ID') if 'District ID' in headers else None
        records = [dict(state=r[0], name=r[1], id=str(r[id_col] or '') if id_col is not None else '',
                        values={year: r[col] for year, col in columns.items()}) for r in rows]
        if BKG_GEOJSON.exists():
            features = json.loads(BKG_GEOJSON.read_text(encoding='utf-8'))['features']
            state_names = {code: state for state, code in STATE_CODES.items()}
            indexed = {}
            for feature in features:
                props = feature['properties']
                key = (normalize(props['GEN']), props['BEZ'] in ('Kreisfreie Stadt','Stadtkreis'))
                indexed.setdefault(key, []).append(props)
            for record in records:
                plain = re.sub(r'\s*\((?:Kreisfreie Stadt|Stadtkreis|Landkreis|Kreis|Regionalverband)\)\s*$', '', record['name'], flags=re.IGNORECASE)
                plain = re.sub(r'^Landkreis\s+', '', plain)
                plain = plain.replace('Oldenburg (Oldenburg)', 'Oldenburg (Oldb)')
                city = any(word in record['name'].lower() for word in ('kreisfreie stadt','stadtkreis'))
                matches = indexed.get((normalize(plain), city), [])
                if len(matches)==1:
                    props = matches[0]
                    record['state'] = state_names[props['bundesland'].removeprefix('DE.')]
                    record['id'] = props['AGS']
        return records, sorted(columns)
    finally:
        workbook.close()

def select(records, states, districts):
    states = [ALIASES.get(normalize(s), s) for s in states]
    selected = []
    for state in states:
        matches = [r for r in records if normalize(r['state']) == normalize(state)]
        if not matches:
            raise ValueError(f'Unknown state: {state}. Use --list.')
        selected.extend(matches)
    for district in districts:
        # Qualify ambiguous names as State:District; IDs are also accepted.
        state, name = district.split(':', 1) if ':' in district else ('', district)
        state = ALIASES.get(normalize(state), state)
        matches = [r for r in records if
                   (normalize(r['name']) == normalize(name) or r['id'] == name)
                   and (not state or normalize(r['state']) == normalize(state))]
        if len(matches) != 1:
            raise ValueError(f'District {district!r}: {len(matches)} matches. Use --list and State:District.')
        selected.extend(matches)
    unique = {(r['state'], r['name'], r['id']): r for r in selected}
    if not unique:
        raise ValueError('Select at least one state or district.')
    return list(unique.values())

def match_geometry(records, geojson):
    features = geojson['features']
    matched = []
    for record in records:
        candidates = []
        for feature in features:
            props = feature['properties']
            if props.get('bundesland') and props['bundesland'] != 'DE.' + STATE_CODES.get(record['state'], ''):
                continue
            ids = [str(props.get(k, '')) for k in ('hc-key', 'id', 'AGS', 'RS')]
            raw_id = record['id']
            numeric_id = re.search(r'(\d{5})(?:000)?$', raw_id)
            if numeric_id:
                raw_id = numeric_id.group(1)
            if raw_id and raw_id in ids:
                candidates.append(feature)
                continue
            name = props.get('GEN', props.get('name', ''))
            # Keep city/rural qualifiers: removing these can silently merge different districts.
            plain_name = re.sub(r'\s*\((?:Kreisfreie Stadt|Stadtkreis|Landkreis|Kreis)\)\s*$', '', record['name'], flags=re.IGNORECASE)
            if normalize(name) == normalize(plain_name):
                if props.get('BEZ'):
                    city = any(x in record['name'].lower() for x in ('kreisfreie stadt', 'stadtkreis'))
                    boundary_city = props['BEZ'] in ('Kreisfreie Stadt', 'Stadtkreis')
                    if city != boundary_city:
                        continue
                candidates.append(feature)
        if len(candidates) > 1 and record['state'] == 'Bavaria':
            # Bavarian independent cities use district codes 61–63; rural districts 71+.
            city = 'stadt' in record['name'].lower()
            candidates = [f for f in candidates if
                          (int(f['properties']['hc-key'].split('-')[-1][3:5]) < 70) == city]
        if len(candidates) != 1:
            raise ValueError(f"Boundary match for {record['state']}:{record['name']}: "
                             f'{len(candidates)} matches. Supply compatible boundaries with exact IDs/names. '
                             'No partial map was generated.')
        geometry = candidates[0]['geometry']
        if record['state'] == 'Thuringia' and record['name'] == 'Wartburgkreis':
            eisenach = [f for f in features if f['properties'].get('hc-key') == 'de-th-16056000']
            if eisenach and not any(r['state'] == 'Thuringia' and r['name'].startswith('Eisenach') for r in records):
                def polygons(g):
                    return [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']
                geometry = {'type': 'MultiPolygon', 'coordinates': polygons(geometry) + polygons(eisenach[0]['geometry'])}
        matched.append((record, geometry))
    return matched

def state_data(workbook_path, states):
    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    result = []
    for sheet_name in ('State capacity', 'State density'):
        rows = iter(workbook[sheet_name].values)
        headers = next(rows)
        columns = {int(str(h).split()[0]): i for i, h in enumerate(headers)
                   if re.match(r'^\d{4}\b', str(h))}
        indexed = {row[0]: row for row in rows}
        records = []
        for state in states:
            if state not in indexed:
                raise ValueError(f'State not found: {state}')
            row = indexed[state]
            values = {y: row[i] for y, i in columns.items()}
            if sheet_name == 'State density':
                capacity = next(r for r in result[0] if r['state'] == state)
                area = row[headers.index('Area (km²)')]
                values = {y: value if isinstance(value, (int, float)) else
                          (capacity['values'][y] * 1000 / area if isinstance(capacity['values'][y], (int, float)) else None)
                          for y, value in values.items()}
            records.append(dict(name=state, state=state, values=values))
        result.append(records)
    workbook.close()
    import shapefile
    reader = shapefile.Reader(str(BOUNDARIES / 'BKG_VG250/vg250_ebenen_1231/VG250_LAN.shp'))
    matched = []
    for record in result[0]:
        polygons = []
        for item in reader.iterShapeRecords():
            props = item.record.as_dict()
            if props['GF'] == 4 and props['LKZ'] == STATE_CODES[record['state']]:
                geometry = item.shape.__geo_interface__
                polygons.extend([geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates'])
        if not polygons:
            raise ValueError(f'No official state geometry for {record["state"]}')
        matched.append((record, {'type': 'MultiPolygon', 'coordinates': polygons}))
    reader.close()
    return result[0], result[1], sorted(columns), matched

def state_areas(workbook_path):
    """State land areas (km²) as stored in the workbook's State density sheet."""
    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        return {row[0]: row[1] for row in workbook['State density'].iter_rows(min_row=2, values_only=True)
                if row[0] in STATE_CODES}
    finally:
        workbook.close()

def group_data(workbook_path, definition):
    groups = REGION_GROUPS[definition]
    states = [state for members in groups.values() for state in members]
    if len(states) != len(set(states)) or set(states) != set(STATE_CODES):
        raise ValueError('Groups must partition all 16 states exactly once.')
    capacity, _, years, geometries = state_data(workbook_path, states)
    capacities = {record['state']: record for record in capacity}
    shapes = {record['state']: geometry for record, geometry in geometries}
    areas = state_areas(workbook_path)
    grouped, density, matched = [], [], []
    for name, members in groups.items():
        area = sum(areas[state] for state in members)
        values = {}
        for year in years:
            inputs = [capacities[state]['values'].get(year) for state in members]
            values[year] = sum(inputs) if all(isinstance(value,(int,float)) for value in inputs) else None
        record = dict(name=name,state=name,values=values,members=members,area_km2=area)
        grouped.append(record)
        density.append(dict(name=name,state=name,values={year: value*1000/area if value is not None else None
                                                        for year,value in values.items()}))
        matched.append((record,{'type':'MultiPolygon','coordinates':[
            polygon for state in members for polygon in shapes[state]['coordinates']]}))
    return grouped,density,years,matched
