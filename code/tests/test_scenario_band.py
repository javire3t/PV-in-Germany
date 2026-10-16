import numpy as np

from figures.regions.nep_scenarios import scenario_envelope


def test_envelope_uses_all_scenarios_even_when_their_order_changes():
    future = {'A': [[3, 5]], 'B': [[6, 1]], 'C': [[4, 2]]}
    lower, upper, scenario_b = scenario_envelope(future, 0, 7)
    np.testing.assert_array_equal(lower, [7, 3, 1])
    np.testing.assert_array_equal(upper, [7, 6, 5])
    np.testing.assert_array_equal(scenario_b, [7, 6, 1])
