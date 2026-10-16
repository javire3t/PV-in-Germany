"""External labels for paired geographic maps."""
import numpy as np


def external_label_positions(matched):
    """Put the northern region above and the southern one below the map."""
    centers=[]
    for record,geometry in matched:
        polygons=[geometry['coordinates']] if geometry['type']=='Polygon' else geometry['coordinates']
        points=np.asarray([point for polygon in polygons for ring in polygon for point in ring])
        centers.append((points.min(axis=0)+points.max(axis=0))/2)
    north=int(np.argmax([center[1] for center in centers]))
    positions=[]
    for i,(record,_) in enumerate(matched):
        # East and West stay outside too, offset toward their respective sides.
        x=.75 if record['name']=='East' else (.25 if record['name']=='West' else .5)
        positions.append(((x,1.02 if i==north else -.04),'bottom' if i==north else 'top'))
    return positions


def add_external_map_labels(ax,matched,labels,colors,fontsize=12):
    """Keep names and densities outside the silhouette without white label boxes."""
    artists=[]
    for (position,vertical),label,color in zip(external_label_positions(matched),labels,colors):
        artists.append(ax.text(*position,label,transform=ax.transAxes,ha='center',va=vertical,
                               fontsize=fontsize,color=color,clip_on=False))
    return artists
