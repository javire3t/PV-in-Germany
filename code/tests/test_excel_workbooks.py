import pytest
from openpyxl import load_workbook

from project_paths import DATA, BKG_GEOJSON
from data_preparation import excel_workbooks as excel

PREPARED = [DATA / 'processed/mastr/pv_by_district_2026.csv',
            DATA / 'processed/nep_scenarios/pv_by_land_ABC_2037_2045.csv', BKG_GEOJSON]


def test_units_are_added_only_to_numeric_headers():
    spec = dict(name='District density', rows=[['state', 'building', 'note (x)'], ['Bavaria', 1.5, 2.0]])
    assert excel.add_units(spec)[0] == ['state', 'building (kWp/km²)', 'note (x)']
    assert excel.add_units(dict(name='Annual detail', rows=spec['rows']))[0] == spec['rows'][0]


@pytest.mark.skipif(not all(p.exists() for p in PREPARED), reason='Prepared data is not shipped')
def test_workbooks_are_written_and_verified(tmp_path):
    contents = excel.workbook_contents()
    for name, sheets in contents.items():
        path = tmp_path / name
        excel.write_workbook(path, sheets)
        excel.verify_workbook(path, sheets)
        workbook = load_workbook(path)
        header = workbook[sheets[1]['name']]['A1']
        assert header.fill.fgColor.rgb == 'FF1F4E78' and header.font.b
        assert workbook[sheets[1]['name']].freeze_panes == 'A2'
        workbook.close()
    assert set(contents) == {excel.MASTR_FILE, excel.NEP_FILE, excel.REDISPATCH_FILE}
