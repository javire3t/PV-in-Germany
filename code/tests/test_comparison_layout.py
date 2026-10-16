"""Regression checks for shared NEP density scales and geographic region labels."""
import numpy as np
from figures.shared.map_labels import external_label_positions
from figures.germany.nep_b_maps import comparison_color_scale


def test_common_nep_scale_is_linear_and_covers_both_technologies():
    cmap,norm=comparison_color_scale()
    assert norm.vmin==0 and norm.vmax==4.6
    assert np.isclose(norm(2.3),.5)
    assert np.allclose(cmap(norm(0))[:3],[1,1,1])


def test_region_labels_are_outside_the_map_and_keep_geographic_order():
    north={'type':'Polygon','coordinates':[[[0,5],[5,5],[5,10],[0,10],[0,5]]]}
    south={'type':'Polygon','coordinates':[[[0,0],[5,0],[5,4],[0,4],[0,0]]]}
    positions=external_label_positions([({'name':'North'},north),({'name':'South'},south)])
    assert positions[0][0][1]>1 and positions[0][1]=='bottom'
    assert positions[1][0][1]<0 and positions[1][1]=='top'
    east_west=external_label_positions([({'name':'East'},north),({'name':'West'},south)])
    assert east_west[1][0][0]<east_west[0][0][0]


def test_animation_prefix_survives_building_name_before_adding_extension():
    from figures.shared.plot_helpers import figure_name
    assert figure_name('germany','all','density','map-animation','2000-2026',suffix='').startswith('Animation_')
