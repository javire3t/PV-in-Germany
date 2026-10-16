import pytest

from data_preparation.read_nep_scenarios import SOURCE, extract_tables


@pytest.mark.skipif(not SOURCE.exists(), reason='Local NEP document is not shipped')
def test_published_scenarios_cover_all_states_and_match_national_totals():
    rows, checks = extract_tables()
    assert len(rows) == 96
    assert len({(r['code'], r['scenario'], r['year']) for r in rows}) == 96
    assert len(checks) == 6
    assert all(abs(c['rounding_difference_GW']) <= .8 for c in checks)
    assert all(13 <= r['figure'] <= 18 for r in rows)
    assert all(r['capacity_GW'] >= 0 for r in rows)
