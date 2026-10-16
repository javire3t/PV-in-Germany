import json

from figures.shared import source_credits


def test_history_footer_uses_project_retrieval_date(tmp_path, monkeypatch):
    metadata = {'2026': {'source': 'Energy-Charts.info; Last Update: 07/15/2026, 9:10 PM GMT+2'}}
    (tmp_path / 'chart_text.json').write_text(json.dumps(metadata), encoding='utf-8')
    monkeypatch.setattr(source_credits, 'ENERGY_CHARTS', tmp_path)
    line = source_credits.history_source(2026)
    assert line == 'Data: Energy-Charts.info (retrieved 16.10.2026)'
    assert 'Last update' not in line


def test_estimated_nep_footer_does_not_attribute_values_to_energy_charts():
    lines = source_credits.source_lines('nep_estimates', boundaries=True,
                                        geojson={'boundary_date': '2025-12-31'})
    text = '\n'.join(lines)
    assert lines[0] == 'Visualization: EIFER'
    assert 'NEP 2025, first draft' in text
    assert not any(line.startswith('Method:') for line in lines)
    assert 'Energy-Charts' not in text
