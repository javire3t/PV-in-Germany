import json

import pytest

from project_paths import ROOT, WORKBOOK, BKG_GEOJSON
from data_preparation.read_workbook import read_data, select, match_geometry


def test_paths_do_not_depend_on_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert ROOT.is_absolute()
    assert WORKBOOK == ROOT / 'results/excel/energy-charts_solar_capacity.xlsx'
    assert BKG_GEOJSON.parent == ROOT / 'data/raw/boundaries'


def test_duplicate_district_names_require_state():
    records = [dict(state=s, name='Example', id=str(i)) for i, s in enumerate(['Bavaria', 'Thuringia'])]
    with pytest.raises(ValueError, match='2 matches'):
        select(records, [], ['Example'])
    assert select(records, [], ['Bayern:Example']) == [records[0]]


@pytest.mark.skipif(not WORKBOOK.exists() or not BKG_GEOJSON.exists(), reason='Local data is not shipped with the package')
def test_official_boundaries_match_existing_regional_data():
    records, years = read_data(WORKBOOK, 'capacity')
    geojson = json.loads(BKG_GEOJSON.read_text(encoding='utf-8'))
    assert geojson['boundary_date'] == '2025-12-31'
    assert len(match_geometry(select(records, ['Bayern'], []), geojson)) == 96
    assert len(match_geometry(select(records, ['Thuringia'], []), geojson)) == 22
    assert len(match_geometry(select(records, ['Saxony-Anhalt'], []), geojson)) == 14
    assert len(match_geometry(records, geojson)) == 400
    assert {record['id'] for record in records} == {feature['properties']['AGS'] for feature in geojson['features']}
    assert years[0] == 1999


@pytest.mark.skipif(not WORKBOOK.exists() or not BKG_GEOJSON.exists(), reason='Local data is not shipped with the package')
def test_group_totals_and_area_weighted_density():
    from data_preparation.read_workbook import group_data, state_data
    from data_preparation.read_workbook import STATE_CODES
    expected, _, _, _ = state_data(WORKBOOK,list(STATE_CODES))
    total = sum(record['values'][2026] for record in expected)
    for definition in ('east-west','south-north'):
        capacity,density,years,geometry = group_data(WORKBOOK,definition)
        assert sum(record['values'][2026] for record in capacity) == pytest.approx(total)
        assert sum(len(record['members']) for record in capacity) == 16
        for record, density_record in zip(capacity,density):
            assert density_record['values'][2026] == pytest.approx(record['values'][2026]*1000/record['area_km2'])
