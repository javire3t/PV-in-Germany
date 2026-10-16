"""Independent raw XML national totals and commissioning-date diagnostics."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from project_paths import ROOT, VALIDATION_RESULTS
import gzip,json,math
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from xml.etree import ElementTree as ET
from data_preparation.prepare_mastr import units

FOLDER=ROOT/'data/raw/mastr/Gesamtdatenexport_20261013_26.2'

def scan(payload):
    path,lookup=payload
    c=Counter()
    for u in units(path):
        c['records']+=1
        if lookup.get(u.get('Land'))!='Deutschland' or lookup.get(u.get('EinheitBetriebsstatus'))!='In Betrieb':continue
        date=u.get('Inbetriebnahmedatum','')[:10]
        try:p=float(u.get('Bruttoleistung',''))
        except ValueError:continue
        if not date or date>'2026-10-13' or not math.isfinite(p) or p<=0:continue
        c['active_units']+=1
        c['gross_kWp']+=p
        c['gross_kWp_'+lookup.get(u.get('ArtDerSolaranlage'),'unknown')]+=p
        if date>'2026-09-17':
            c['commissioned_since_ec_kWp']+=p
            c['commissioned_since_ec_units']+=1
        else:c['commissioned_by_ec_kWp']+=p
        reg=u.get('Registrierungsdatum','')[:10]
        if reg>'2026-09-17':c['registered_since_ec_kWp']+=p
    return c

if __name__=='__main__':
    with gzip.open(FOLDER/'Katalogwerte.xml.gz','rb') as f:
        lookup={e.findtext('Id'):e.findtext('Wert') for e in ET.parse(f).getroot()}
    manifest=json.loads((FOLDER/'manifest.json').read_text())
    files=[FOLDER/(Path(e['name']).name+'.gz') for e in manifest['files'] if 'EinheitenSolar' in e['name']]
    assert all(p.exists() for p in files)
    total=Counter()
    with ProcessPoolExecutor(max_workers=3) as pool:
        for i,c in enumerate(pool.map(scan,[(p,lookup) for p in files]),1):
            total.update(c)
            print(f'{i}/{len(files)} files',flush=True)
    qa=json.loads((ROOT/'data/processed/mastr/validation.json').read_text())
    assert total['records']==qa['records']['records_read']
    assert total['active_units']==sum(qa['national_units'].values())
    assert math.isclose(total['gross_kWp']/1000,sum(qa['national_capacity_MWp'].values()),abs_tol=1e-6)
    (VALIDATION_RESULTS / 'mastr_energy_charts'/'xml_audit.json').write_text(json.dumps(dict(total),indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(dict(total),indent=2,ensure_ascii=True),flush=True)
