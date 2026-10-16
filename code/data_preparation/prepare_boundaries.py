"""Convert downloaded official BKG VG250 district shapefiles into map GeoJSON."""

# Allow running this file directly from an editor or any working directory.
if __package__ in (None, ''):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
from pathlib import Path
import shapefile

from project_paths import BOUNDARIES, BKG_GEOJSON

root = BOUNDARIES
source = root / 'BKG_VG250/vg250_ebenen_1231/VG250_KRS.shp'
def main():
    reader = shapefile.Reader(str(source))
    districts = {}
    for item in reader.iterShapeRecords():
        props = item.record.as_dict()
        if props['GF'] != 4:
            continue
        key = props['AGS']
        geometry = item.shape.__geo_interface__
        polygons = [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates']
        if key not in districts:
            districts[key] = {'type': 'Feature', 'properties': {
                'AGS': key, 'id': key, 'GEN': props['GEN'], 'name': props['GEN'],
                'BEZ': props['BEZ'], 'bundesland': 'DE.' + props['LKZ'],
            }, 'geometry': {'type': 'MultiPolygon', 'coordinates': []}}
        districts[key]['geometry']['coordinates'].extend(polygons)
    data = {'type': 'FeatureCollection', 'boundary_date': '2025-12-31',
            'source_url': 'https://daten.gdz.bkg.bund.de/produkte/vg/vg250_ebenen_1231/aktuell/vg250_12-31.utm32s.shape.ebenen.zip',
            'copyrightShort': '© BKG 2026 · dl-de/by-2-0 · VG250, 31 Dec 2025',
            'source_information': 'https://sgx.geodatenzentrum.de/web_public/gdz/datenquellen/datenquellen_vg_nuts.pdf',
            'modification': 'District land geometry selected and grouped by AGS; converted to GeoJSON.',
            'crs': {'type': 'name', 'properties': {'name': 'EPSG:25832'}},
            'features': list(districts.values())}
    target = BKG_GEOJSON
    target.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    print(f'Converted {len(districts)} official district boundaries: {target}')

if __name__ == "__main__":
    main()
