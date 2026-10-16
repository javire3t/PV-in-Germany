import gzip

import pytest

from data_preparation.prepare_mastr import classify, units, area_km2, aggregate_file


def test_types_do_not_merge_balcony_or_unknown_into_buildings():
    assert classify('Gebäudesolaranlage') == 'building'
    assert classify('Freiflächensolaranlage') == 'ground_mounted'
    assert classify('Steckerfertige Solaranlage (sog. Balkonkraftwerk)') == 'balcony'
    assert classify(None) == classify('Sonstige Solaranlage') == 'other_unknown'


def test_stream_reads_each_unit_without_retaining_previous_fields(tmp_path):
    path = tmp_path/'solar.xml.gz'
    with gzip.open(path, 'wt') as file:
        file.write('<EinheitenSolar><EinheitSolar><Bruttoleistung>5.2</Bruttoleistung><ArtDerSolaranlage>853</ArtDerSolaranlage></EinheitSolar><EinheitSolar><Bruttoleistung>8.4</Bruttoleistung></EinheitSolar></EinheitenSolar>')
    assert list(units(path)) == [{'Bruttoleistung':'5.2', 'ArtDerSolaranlage':'853'}, {'Bruttoleistung':'8.4'}]


def test_area_subtracts_holes_and_sums_islands():
    outer = [[500000,5500000],[501000,5500000],[501000,5501000],[500000,5501000],[500000,5500000]]
    hole = [[500100,5500100],[500300,5500100],[500300,5500300],[500100,5500300],[500100,5500100]]
    full = area_km2({'type':'Polygon','coordinates':[outer]})
    inner = area_km2({'type':'Polygon','coordinates':[hole]})
    cut = area_km2({'type':'Polygon','coordinates':[outer,hole]})
    assert cut == pytest.approx(full-inner)
    multi = area_km2({'type':'MultiPolygon','coordinates':[[outer],[hole]]})
    assert multi == pytest.approx(full+inner)
    assert full == pytest.approx(1, rel=.002)


def test_aggregation_filters_and_reports_unmapped_capacity(tmp_path):
    def unit(**changes):
        fields = dict(Land='84', EinheitBetriebsstatus='35', Inbetriebnahmedatum='2026-01-01',
                      Bruttoleistung='1000', ArtDerSolaranlage='852', Gemeindeschluessel='16056000')
        fields.update(changes)
        return '<EinheitSolar>'+''.join(f'<{k}>{v}</{k}>' for k,v in fields.items())+'</EinheitSolar>'
    records = [unit(), unit(ArtDerSolaranlage='853', Bruttoleistung='500'),
               unit(ArtDerSolaranlage='2961', Bruttoleistung='1'),
               unit(EinheitBetriebsstatus='38'), unit(Inbetriebnahmedatum='2027-01-01'),
               unit(Land='99'), unit(Bruttoleistung='-5'), unit(Gemeindeschluessel='99999000')]
    path = tmp_path/'solar.xml.gz'
    with gzip.open(path, 'wt', encoding='utf-8') as stream:
        stream.write('<EinheitenSolar>'+''.join(records)+'</EinheitenSolar>')
    lookup = {'84':'Deutschland','35':'In Betrieb','38':'Endgültig stillgelegt',
              '852':'Freiflächensolaranlage','853':'Gebäudesolaranlage',
              '2961':'Steckerfertige Solaranlage (sog. Balkonkraftwerk)'}
    totals, counts, audit, audit_kw, unresolved, national, _ = aggregate_file((path, lookup, {'16063'}, {}, '2026-10-13'))
    assert totals[('16063','ground_mounted')] == 1000
    assert totals[('16063','building')] == 500
    assert totals[('16063','balcony')] == 1
    assert audit['records_read'] == 8
    assert audit['not_in_operation'] == audit['outside_germany'] == audit['invalid_power'] == 1
    assert audit['missing_or_future_commissioning_date'] == audit['unmatched_district'] == 1
    assert sum(national.values()) == sum(totals.values()) + audit_kw['unmatched_district']
