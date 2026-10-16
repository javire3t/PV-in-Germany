import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pytest

import figures.shared.source_credits as credits
from figures.shared.plot_helpers import figure_name, selection_slug, slug


def test_figure_name_orders_type_or_metric_before_scale():
    assert figure_name('states', 'saxony-anhalt-vs-thuringia', 'capacity-and-density', 'comparison', '1999-2026') == \
        'Figure_comparison_states_saxony-anhalt-vs-thuringia_1999-2026.png'
    assert figure_name('states', 'all', 'capacity', 'timeseries', '1999-2026') == \
        'Figure_capacity_states_1999-2026.png'
    assert figure_name('regions', 'east-vs-west', 'density', 'timeseries', '1999-2045', 'nep-abc') == \
        'Figure_density_regions_east-vs-west_1999-2045_NEP-ABC.png'
    assert figure_name('germany', 'all', 'density', 'map-animation', '2000-2026', suffix='.gif') == \
        'Animation_density_germany_2000-2026.gif'
    with pytest.raises(KeyError):
        figure_name('country', 'all', 'density', 'map', 2026)


def test_names_are_english_ascii_and_alphabetical():
    assert slug('Baden-Württemberg') == 'baden-wurttemberg'
    assert slug('Burgenlandkreis') == 'burgenland'
    assert slug('Saale-Holzland-Kreis') == 'saale-holzland'
    assert selection_slug(['Thuringia', 'Saxony-Anhalt']) == 'saxony-anhalt-vs-thuringia'
    assert selection_slug(['South', 'North']) == 'north-vs-south'


@pytest.fixture
def metadata(monkeypatch):
    data = {'2025': {'source': 'Energy-Charts.info; Last Update: 03/31/2026, 9:33 AM GMT+2'},
            '2026': {'source': 'Energy-Charts.info; Last Update: 09/17/2026, 9:10 PM GMT+2'}}
    monkeypatch.setattr(credits, 'chart_metadata', lambda: data)


def test_year_to_date_detection_is_preserved_with_retrieval_credits(metadata):
    assert credits.is_partial_year(2026)
    assert not credits.is_partial_year(2025)
    assert credits.history_source(2026) == 'Data: Energy-Charts.info (retrieved 16.10.2026)'
    assert credits.history_source(2025) == 'Data: Energy-Charts.info (retrieved 16.10.2026)'


def test_trend_axis_labels_partial_year_and_hollow_point(metadata):
    from figures.states.charts import plot_years
    years = [str(year) for year in range(1999, 2027)]
    fig, ax = plt.subplots()
    line = plot_years(ax, years, range(len(years)))
    labels = [tick.get_text() for tick in ax.get_xticklabels()]
    assert labels == ['2000', '2005', '2010', '2015', '2020', '2026']
    assert list(line.get_markevery()) == list(range(len(years) - 1))
    assert ax.lines[-1].get_markerfacecolor() == 'white'
    plt.close(fig)
