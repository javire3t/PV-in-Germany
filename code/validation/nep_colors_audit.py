"""Check source palette fidelity and sensitivity to district interior sampling."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from project_paths import ROOT, VALIDATION_RESULTS, NEP_SOURCES
import json
import cv2
import numpy as np
import pandas as pd
import pymupdf
from pyproj import Transformer
from scipy.spatial import cKDTree
from data_preparation.estimate_nep_districts import image_array, silhouette, polygons
from figures.germany.nep_b_maps import source_color_scale

P=VALIDATION_RESULTS / 'nep_colors'
S=ROOT/'data/processed/nep_estimates'
fit=json.loads((S/'alignment.json').read_text())
affine=np.asarray(fit['affine']).reshape(2,3)
transformer=Transformer.from_crs(25832,fit['epsg'],always_xy=True)
features=json.loads((ROOT/'data/raw/boundaries/germany_districts_bkg_2025.geojson').read_text())['features']
table=pd.read_csv(S/'nep_pv_district_density_ESTIMATED_2024_B2037_B2045.csv',dtype={'AGS':str})
doc=pymupdf.open(NEP_SOURCES/'NEP_2037_2045_V2025_1_Entwurf_0.pdf')
maps=sorted([i for i in doc[44].get_image_info(xrefs=True) if i['width']>100],key=lambda i:(i['bbox'][1],i['bbox'][0]))
_,baseedge=silhouette(image_array(doc,maps[0]['xref']))
base_low,base_high=baseedge.min(axis=0),baseedge.max(axis=0)
rows=[]
palette=[]
for ti,technology in enumerate(['ground_mounted','rooftop']):
    legend=json.loads((S/f'{technology}_legend.json').read_text())
    colors=np.asarray(legend['colors'])
    values=np.asarray(legend['legend_values'])
    tree=cKDTree(colors)
    cmap,norm=source_color_scale(legend)
    error=np.linalg.norm(cmap(norm(values))[:,:3]*255-colors,axis=1)
    palette.append(dict(technology=technology,mean_RGB_error=float(error.mean()),p95_RGB_error=float(np.percentile(error,95))))
    for si,scenario in enumerate(['2024','B2037','B2045']):
        rgb=image_array(doc,maps[ti*3+si]['xref'])
        _,edge=silhouette(rgb)
        low,high=edge.min(axis=0),edge.max(axis=0)
        scale=(high-low)/(base_high-base_low)
        subset=table[(table.technology==technology)&(table.scenario==scenario)].set_index('AGS')
        for f in features:
            region=np.zeros(rgb.shape[:2],dtype='uint8')
            for poly in polygons(f['geometry']):
                rings=[]
                for ring in poly:
                    points=np.asarray(ring)
                    x,y=transformer.transform(points[:,0],points[:,1])
                    normalized=(np.column_stack([x,y])-fit['low'])/(np.asarray(fit['high'])-fit['low'])
                    projected=normalized@affine[:,:2].T+affine[:,2]
                    rings.append(np.rint((projected-base_low)*scale+low).astype('int32'))
                cv2.fillPoly(region,rings,255)
            distance=cv2.distanceTransform(region,cv2.DIST_L2,3)
            pixels=rgb[distance>=max(1,float(distance.max())*.5)]
            if not len(pixels):continue
            valid=(np.ptp(pixels,axis=1)>5)|(pixels.min(axis=1)>240)
            pixels=pixels[valid]
            if not len(pixels):continue
            errors,indices=tree.query(pixels.astype(float))
            accepted=errors<=12
            if not accepted.any():continue
            core=float(np.median(values[indices[accepted]]))
            ags=f['properties']['AGS']
            original=float(subset.loc[ags,'estimated_MW_per_km2'])
            rows.append(dict(AGS=ags,district=f['properties']['GEN'],technology=technology,scenario=scenario,
                saved_estimate=original,core_estimate=core,absolute_difference=abs(original-core),core_pixels=int(accepted.sum())))
        print(technology,scenario,flush=True)
d=pd.DataFrame(rows)
d.to_csv(P/'district_sampling_check.csv',index=False,encoding='utf-8-sig')
summary=dict(source_palette=palette,checked_rows=len(d),median_sampling_difference=float(d.absolute_difference.median()),
    p95_sampling_difference=float(d.absolute_difference.quantile(.95)),rows_above_0_1=int((d.absolute_difference>.1).sum()),
    largest_sampling_differences=d.nlargest(10,'absolute_difference').to_dict('records'))
(P/'audit.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=True,indent=2))
