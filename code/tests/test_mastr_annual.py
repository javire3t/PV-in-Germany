from datetime import date
import gzip
import pytest
from data_preparation.prepare_mastr_annual import power_band, use_category, aggregate_file

def test_power_band_boundaries():
    assert [power_band(p) for p in (10,10.01,30,30.01,100,100.01,1000,1000.01)] == ['<=10','>10-30','>10-30','>30-100','>30-100','>100-1000','>100-1000','>1000']
    for power in (0,-1,float('nan'),float('inf')):
        with pytest.raises(ValueError):
            power_band(power)

def test_ground_overrides_use_and_missing_is_not_assumed_household():
    lookup = {'852':'Freiflächensolaranlage','713':'Haushalt','718':'Sonstige'}
    assert use_category({'ArtDerSolaranlage':'852','Nutzungsbereich':'713'},lookup) == 'ground_mounted'
    assert use_category({'Nutzungsbereich':'713'},lookup) == 'household'
    assert use_category({'Nutzungsbereich':'718'},lookup) == 'other_uses'
    assert use_category({'ArtDerSolaranlage':'2961'},lookup) == 'no_information'

def test_retired_included_planned_excluded_and_commissioning_date_used(tmp_path):
    def unit(status, commissioned):
        return f'<EinheitSolar><Land>84</Land><EinheitBetriebsstatus>{status}</EinheitBetriebsstatus><Inbetriebnahmedatum>{commissioned}</Inbetriebnahmedatum><Registrierungsdatum>2025-01-01</Registrierungsdatum><Bruttoleistung>10</Bruttoleistung><Nutzungsbereich>713</Nutzungsbereich></EinheitSolar>'
    path = tmp_path/'solar.xml.gz'
    with gzip.open(path,'wt') as stream:
        stream.write('<EinheitenSolar>'+unit('35','2001-01-01')+unit('38','2001-01-01')+unit('37','2002-01-01')+unit('31','2003-01-01')+unit('35','2026-12-01')+unit('35','1999-01-01')+'</EinheitenSolar>')
    lookup = {'84':'Deutschland','35':'In Betrieb','38':'Endgültig stillgelegt','37':'Vorübergehend stillgelegt','31':'In Planung','713':'Haushalt'}
    counts, capacity, audit, statuses = aggregate_file((path,lookup,date(2026,10,13)))
    assert counts[(2001,'<=10','household')] == 2
    assert capacity[(2001,'<=10','household')] == 20
    assert audit['included_units'] == 3
    assert audit['future_commissioning_date'] == audit['commissioned_before_2000'] == 1
    assert audit['excluded_status_In Planung'] == 1
    assert statuses['Endgültig stillgelegt'] == statuses['Vorübergehend stillgelegt'] == 1
