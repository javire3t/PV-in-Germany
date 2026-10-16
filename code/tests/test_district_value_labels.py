import numpy as np

from figures.germany.labeled_map import contains_points, label_anchor


def test_label_anchor_is_on_land_and_avoids_an_interior_hole():
    geometry = {'type':'Polygon','coordinates':[
        [[0,0],[10,0],[10,10],[0,10],[0,0]],
        [[3,3],[7,3],[7,7],[3,7],[3,3]],
    ]}
    anchor = label_anchor(geometry)
    assert contains_points(geometry, [anchor])[0]
    assert not (3 <= anchor[0] <= 7 and 3 <= anchor[1] <= 7)


def test_multipart_label_uses_largest_part_instead_of_offshore_island():
    geometry = {'type':'MultiPolygon','coordinates':[
        [[[0,0],[1,0],[1,1],[0,1],[0,0]]],
        [[[20,20],[30,20],[30,30],[20,30],[20,20]]],
    ]}
    anchor = label_anchor(geometry)
    assert np.all(anchor > 20) and np.all(anchor < 30)
