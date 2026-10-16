"""Keep map colors consistent with the source legend used for digitization."""
import numpy as np
import pytest
from figures.germany.nep_b_maps import source_color_scale


def test_source_palette_preserves_low_values_without_gamma_enhancement():
    legend = {'legend_values': [2., 1., 0.],
              'colors': [[255, 190, 0], [255, 230, 128], [255, 255, 255]]}
    cmap, norm = source_color_scale(legend)
    assert norm(.1) == pytest.approx(.05)
    np.testing.assert_allclose(np.asarray(cmap(norm(1.)))[:3]*255,
                               legend['colors'][1], atol=.2)
    np.testing.assert_allclose(np.asarray(cmap(norm(0.)))[:3]*255,
                               [255, 255, 255], atol=.01)


def test_source_palette_handles_repeated_zero_values_and_white_extension():
    cmap, norm = source_color_scale({'legend_values': [2., 0., 0.],
                                    'colors': [[255,190,0], [255,255,255], [255,255,255]]})
    assert np.isfinite(cmap(norm(.5))).all()
    cmap, norm = source_color_scale({'legend_values': [2., .001],
                                    'colors': [[255,190,0], [255,255,255]]})
    np.testing.assert_allclose(np.asarray(cmap(norm(0.)))[:3], [1,1,1])
