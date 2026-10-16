"""Extract and save the published NEP A/B/C state capacities."""

# Allow running this file directly from an editor or any working directory.
if __package__ in (None, ''):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import csv
import json
import re
import pymupdf
from project_paths import DATA, NEP_SOURCES
from data_preparation.read_workbook import STATE_CODES

SOURCE = NEP_SOURCES / 'NEP_2037_2045_V2025_2_Entwurf_2.pdf'

def extract_tables(source=SOURCE):
    code_to_state = {code: state for state, code in STATE_CODES.items()}
    rows, checks = [], []
    with pymupdf.open(source) as document:
        for index, page in enumerate(document):
            text = page.get_text()
            heading = re.search(r'Abbildung (\d+): Installierte Leistungen je Bundesland im Szenario ([ABC]) (2037|2045)', text)
            if not heading or 'Summe**' not in text:
                continue
            figure, scenario, year = heading.groups()
            tokens = [line.strip() for line in text.splitlines() if line.strip()]
            scenario_rows = []
            for code, state in code_to_state.items():
                positions = [i for i, token in enumerate(tokens) if token == code]
                if len(positions) != 1:
                    raise ValueError(f'Ambiguous table row: {scenario} {year} {code}')
                start = positions[0] + 1
                cells = tokens[start:start+15]
                if len(cells) != 15 or not all(re.fullmatch(r'\d+,\d+', cell) for cell in cells):
                    raise ValueError(f'Unexpected numeric row: {code} {cells}')
                pv = float(cells[2].replace(',', '.'))
                scenario_rows.append(dict(state=state, code=code, scenario=scenario,
                                          year=int(year), capacity_GW=pv,
                                          page=index+1, figure=int(figure), source=source.name))
            national = float(tokens[tokens.index('Summe**')+3].replace(',', '.'))
            total = sum(row['capacity_GW'] for row in scenario_rows)
            if abs(total-national) > .81:
                raise ValueError(f'PV column/national sum mismatch: {total} vs {national}')
            checks.append(dict(scenario=scenario,year=int(year),land_sum_GW=round(total,2),
                               published_total_GW=national, rounding_difference_GW=round(total-national,2)))
            rows.extend(scenario_rows)
    if len(rows) != 96 or {(r['scenario'],r['year']) for r in rows} != {(s,y) for s in 'ABC' for y in (2037,2045)}:
        raise ValueError('Expected all 16 states in all six cases')
    return rows, checks

def main():
    rows, checks = extract_tables()
    destination = DATA / 'processed/nep_scenarios'
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / 'pv_by_land_ABC_2037_2045.csv').open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (destination / 'validation.json').write_text(json.dumps(checks, indent=2), encoding='utf-8')
    print(destination)

if __name__ == '__main__':
    main()
