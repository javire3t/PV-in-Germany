"""When operating PV units leave EEG payments, by exit year and unit size, from the MaStR export.

An EEG-paid unit receives payments in its EEG commissioning year and the following
20 calendar years; it enters the year after that without EEG payments:

    exit year = EEG commissioning year + 21

Units commissioned before 2000 were paid until the end of 2020 under the EEG 2000
transition, so they exit in 2021. Counted units: located in Germany, currently in
operation, positive gross capacity, linked to an EEG record that does not state "no EEG
payment". The payment field (InanspruchnahmeZahlungNachEeg) is mostly empty, and empty
for almost all units since 2023, so only an explicit "0" excludes a unit. When the EEG
commissioning date is missing, the unit's own commissioning date is used.

Output (data/processed/mastr/): pv_eeg_exit_by_year_power.csv (size classes of the MaStR annual
series), pv_eeg_exit_by_year_power_pwc_classes.csv (PwC size classes) and eeg_exit_validation.json.
Run after `main.py mastr-download` (needs EinheitenSolar and AnlagenEegSolar).
"""
if __package__ in (None, ''):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
import pandas as pd

from data_preparation.prepare_mastr import units
from data_preparation.prepare_mastr_annual import BANDS
from project_paths import RAW, DATA

EEG_YEARS = 20
EEG_START = 2000


# Two size classifications: the one of the MaStR annual series and the pv magazine chart,
# and the one of the PwC chart. Boundary values belong to the lower class.
SIZE_SCHEMES = {
    'mastr': ((10, 30, 100, 1000), list(BANDS)),
    'pwc': ((5, 10, 40, 750), ['<=5', '>5-10', '>10-40', '>40-750', '>750']),
}
SCHEME_FILES = {'mastr': 'pv_eeg_exit_by_year_power.csv', 'pwc': 'pv_eeg_exit_by_year_power_pwc_classes.csv'}


def exit_table(exit_year, kw, bins, labels, first, last, snapshot):
    """Units and capacity per exit year and size class, with every combination present."""
    classes = np.array(labels)[np.searchsorted(np.array(bins), kw, side='left')]
    frame = pd.DataFrame(dict(exit_year=exit_year, power_band_kWp=classes, kw=kw))
    table = (frame.groupby(['exit_year', 'power_band_kWp']).kw.agg(['size', 'sum']).reset_index()
             .rename(columns={'size': 'unit_count', 'sum': 'capacity_kW'}))
    full = pd.MultiIndex.from_product([range(first, last + 1), labels], names=['exit_year', 'power_band_kWp'])
    table = table.set_index(['exit_year', 'power_band_kWp']).reindex(full, fill_value=0).reset_index()
    table['capacity_MWp'] = table.pop('capacity_kW') / 1000
    table['snapshot_date'] = snapshot
    return table


def eeg_key(number):
    """EEG MaStR numbers are 'EEG' plus 12 digits; keep the digits as an integer key."""
    return int(number[3:]) if number.startswith('EEG') and number[3:].isdigit() else -1


def eeg_records(path):
    """EEG number, EEG commissioning year and payment claim of every record in one file."""
    keys, years, paid = [], [], []
    with gzip.open(path, 'rb') as stream:
        for _, element in ET.iterparse(stream, events=('end',)):
            if element.tag.rsplit('}', 1)[-1] != 'AnlageEegSolar':
                continue
            fields = {child.tag.rsplit('}', 1)[-1]: child.text or '' for child in element}
            element.clear()
            date = fields.get('EegInbetriebnahmedatum', '')
            keys.append(eeg_key(fields.get('EegMaStRNummer', '')))
            years.append(int(date[:4]) if date[:4].isdigit() else -1)
            # 1 = claims EEG payment, 0 = explicitly no payment, -1 = not stated.
            paid.append({'1': 1, '0': 0}.get(fields.get('InanspruchnahmeZahlungNachEeg'), -1))
    return np.array(keys, np.int64), np.array(years, np.int16), np.array(paid, np.int8)


def operating_units(payload):
    """Operating German units: EEG key, gross capacity (kW) and audit counts of one file."""
    path, lookup = payload
    keys, power, years, audit = [], [], [], Counter()
    for unit in units(path):
        # Catalogue values can share a name across categories, so compare decoded values.
        if (lookup.get(unit.get('Land')) != 'Deutschland'
                or lookup.get(unit.get('EinheitBetriebsstatus')) != 'In Betrieb'):
            continue
        try:
            kw = float(unit.get('Bruttoleistung', ''))
        except ValueError:
            continue
        if not kw > 0:
            continue
        audit['operating_units'] += 1
        audit['operating_kW'] += kw
        key = eeg_key(unit.get('EegMaStRNummer', ''))
        if key < 0:
            audit['without_eeg_record'] += 1
            audit['without_eeg_record_kW'] += kw
            continue
        keys.append(key)
        power.append(kw)
        commissioned = unit.get('Inbetriebnahmedatum', '')[:4]
        years.append(int(commissioned) if commissioned.isdigit() else -1)
    return np.array(keys, np.int64), np.array(power), np.array(years, np.int16), audit


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--folder', type=Path, default=RAW / 'mastr' / 'Gesamtdatenexport_20261013_26.2')
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    manifest = json.loads((args.folder / 'manifest.json').read_text(encoding='utf-8'))
    names = [Path(e['name']).name + '.gz' for e in manifest['files']]
    unit_files = [args.folder / n for n in names if n.startswith('EinheitenSolar')]
    eeg_files = [args.folder / n for n in names if n.startswith('AnlagenEegSolar')]
    if not eeg_files or any(not p.exists() for p in unit_files + eeg_files):
        raise RuntimeError('Run main.py mastr-download first: unit and EEG tables are required.')
    with gzip.open(args.folder / 'Katalogwerte.xml.gz') as stream:
        lookup = {e.findtext('Id'): e.findtext('Wert') for e in ET.parse(stream).getroot()}
    stamp = Path(manifest['source_url']).stem.split('_')[1]
    snapshot = f'{stamp[:4]}-{stamp[4:6]}-{stamp[6:]}'

    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        parts = list(pool.map(eeg_records, eeg_files))
        print(f'EEG records read from {len(eeg_files)} files', flush=True)
        unit_parts = list(pool.map(operating_units, [(p, lookup) for p in unit_files]))
        print(f'Units read from {len(unit_files)} files', flush=True)

    eeg_keys = np.concatenate([p[0] for p in parts])
    eeg_years = np.concatenate([p[1] for p in parts])
    eeg_paid = np.concatenate([p[2] for p in parts])
    order = np.argsort(eeg_keys)
    eeg_keys, eeg_years, eeg_paid = eeg_keys[order], eeg_years[order], eeg_paid[order]
    if len(np.unique(eeg_keys)) != len(eeg_keys):
        raise ValueError('Duplicate EEG MaStR numbers in AnlagenEegSolar')

    unit_keys = np.concatenate([p[0] for p in unit_parts])
    unit_kw = np.concatenate([p[1] for p in unit_parts])
    unit_years = np.concatenate([p[2] for p in unit_parts])
    audit = Counter()
    for part in unit_parts:
        audit.update(part[3])

    position = np.clip(np.searchsorted(eeg_keys, unit_keys), 0, len(eeg_keys) - 1)
    linked = eeg_keys[position] == unit_keys
    claim = np.where(linked, eeg_paid[position], 0)
    paid = linked & (claim != 0)
    eeg_year = np.where(eeg_years[position] > 1900, eeg_years[position], unit_years)
    dated = paid & (eeg_year > 1900)
    start = np.maximum(eeg_year[dated], EEG_START)
    exit_year = start + EEG_YEARS + 1
    first, last = int(exit_year.min()), int(exit_year.max())
    tables = {scheme: exit_table(exit_year, unit_kw[dated], bins, labels, first, last, snapshot)
              for scheme, (bins, labels) in SIZE_SCHEMES.items()}
    output = DATA / 'processed' / 'mastr'
    for scheme, table in tables.items():
        table.to_csv(output / SCHEME_FILES[scheme], index=False, encoding='utf-8-sig')
    target = output / SCHEME_FILES['mastr']

    summary = dict(
        source_url=manifest['source_url'], snapshot_date=snapshot,
        rule=f'exit year = max(EEG commissioning year, {EEG_START}) + {EEG_YEARS + 1}',
        operating_units=int(audit['operating_units']),
        operating_capacity_MWp=audit['operating_kW'] / 1000,
        units_without_eeg_record=int(audit['without_eeg_record']),
        capacity_without_eeg_record_MWp=audit['without_eeg_record_kW'] / 1000,
        units_with_unmatched_eeg_number=int((~linked).sum()),
        units_stating_no_eeg_payment=int((linked & (claim == 0)).sum()),
        units_payment_field_empty=int((linked & (claim == -1)).sum()),
        units_eeg_date_from_unit_date=int((paid & (eeg_years[position] <= 1900)).sum()),
        units_without_any_date=int((paid & ~dated).sum()),
        counted_units=int(dated.sum()), counted_capacity_MWp=float(unit_kw[dated].sum() / 1000),
        eeg_records=int(len(eeg_keys)),
    )
    (output / 'eeg_exit_validation.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(target)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
