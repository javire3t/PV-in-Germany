"""Digitize approximate district PV density from NEP map colors, with alignment QA."""

# Allow running this file directly from an editor or any working directory.
if __package__ in (None, ''):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import io
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import pymupdf
import shapefile
from PIL import Image
from pyproj import Transformer
from scipy.optimize import minimize
from scipy.spatial import cKDTree

from project_paths import BOUNDARIES, BKG_GEOJSON, NEP_ESTIMATES, NEP_SOURCES


def image_array(document, xref):
    return np.array(Image.open(io.BytesIO(document.extract_image(xref)['image'])).convert('RGB'))


def silhouette(rgb):
    binary = (rgb.min(axis=2) < 240).astype('uint8') * 255
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((3, 3), 'uint8'))
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    mask = np.zeros(binary.shape, 'uint8')
    for contour in contours:
        if cv2.contourArea(contour) > 5:
            cv2.drawContours(mask, [contour], -1, 255, -1)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    return mask, np.concatenate([c[:, 0, :] for c in contours if cv2.contourArea(c) > 5])


def polygons(geometry):
    return [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates']


def fit_country(rgb, country):
    mask, edge = silhouette(rgb)
    target = edge[::max(1, len(edge) // 1800)].astype(float)
    projections = []
    raw = np.concatenate([np.array(poly[0]) for poly in polygons(country)])
    raw = raw[::max(1, len(raw) // 3500)]
    for epsg in (25832, 3035, 3857, 4326):
        transformer = Transformer.from_crs(25832, epsg, always_xy=True)
        x, y = transformer.transform(raw[:, 0], raw[:, 1])
        points = np.column_stack([x, y])
        low, high = points.min(axis=0), points.max(axis=0)
        normalized = (points - low) / (high - low)
        min_px, max_px = target.min(axis=0), target.max(axis=0)
        initial = [max_px[0]-min_px[0], 0, min_px[0], 0, -(max_px[1]-min_px[1]), max_px[1]]
        def transformed(parameters, points=normalized):
            return points @ np.array(parameters).reshape(2, 3)[:, :2].T + np.array(parameters).reshape(2, 3)[:, 2]
        target_tree = cKDTree(target)
        def loss(parameters):
            predicted = transformed(parameters)
            forward = target_tree.query(predicted)[0]
            backward = cKDTree(predicted).query(target)[0]
            return np.mean(np.minimum(forward, 15)**2) + np.mean(np.minimum(backward, 15)**2)
        fitted = minimize(loss, initial, method='Powell', options={'maxiter': 120, 'xtol': .01})
        predicted = transformed(fitted.x)
        distances = cKDTree(predicted).query(target)[0]
        projections.append(dict(epsg=epsg, low=low, high=high, affine=fitted.x,
                                median=float(np.median(distances)), p90=float(np.percentile(distances, 90)), loss=float(fitted.fun)))
    best = min(projections, key=lambda fit: fit['loss'])
    print('Alignment candidates:', [(f['epsg'], round(f['median'], 2), round(f['p90'], 2)) for f in projections])
    if best['p90'] > 8:
        raise ValueError(f'Alignment is too uncertain: 90th-percentile boundary error {best["p90"]:.1f} pixels')
    def transform(points):
        points = np.asarray(points)
        transformer = Transformer.from_crs(25832, best['epsg'], always_xy=True)
        x, y = transformer.transform(points[:, 0], points[:, 1])
        normalized = (np.column_stack([x, y]) - best['low']) / (best['high'] - best['low'])
        affine = np.array(best['affine']).reshape(2, 3)
        return normalized @ affine[:, :2].T + affine[:, 2]
    return best, transform, mask


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', type=Path, default=NEP_SOURCES / 'NEP_2037_2045_V2025_1_Entwurf_0.pdf')
    args = parser.parse_args()
    document = pymupdf.open(args.pdf)
    page = next(p for p in document if 'Abbildung 10: Flächen' in p.get_text() and len(p.get_images()) >= 4)
    # Higher-resolution source has both figures on one page.
    image_info = page.get_image_info(xrefs=True)
    if len(image_info) < 8:
        raise ValueError('Use the first-draft PDF with both figures on page 45; it has higher-resolution maps.')
    maps = sorted([i for i in image_info if i['width'] > 100], key=lambda i: (i['bbox'][1], i['bbox'][0]))
    bars = sorted([i for i in image_info if i['width'] < 100], key=lambda i: i['bbox'][1])
    reader = shapefile.Reader(str(BOUNDARIES / 'BKG_VG250/vg250_ebenen_1231/VG250_STA.shp'))
    parts = []
    for item in reader.iterShapeRecords():
        if item.record.as_dict()['GF'] == 4:
            parts.extend(polygons(item.shape.__geo_interface__))
    reader.close()
    source_rgb = image_array(document, maps[0]['xref'])
    fit, transform, country_mask = fit_country(source_rgb, {'type': 'MultiPolygon', 'coordinates': parts})
    output = NEP_ESTIMATES
    output.mkdir(parents=True, exist_ok=True)
    features = json.loads(BKG_GEOJSON.read_text(encoding='utf-8'))['features']
    spans = [s for b in page.get_text('dict')['blocks'] if 'lines' in b for l in b['lines'] for s in l['spans']]
    rows = []
    overlay = source_rgb.copy()
    for technology_index, technology in enumerate(['ground_mounted', 'rooftop']):
        bar_info = bars[technology_index]
        gradient = image_array(document, bar_info['xref'])
        colors = gradient[:, gradient.shape[1] // 2 - 2:gradient.shape[1] // 2 + 3].mean(axis=1)
        y0, y1 = bar_info['bbox'][1], bar_info['bbox'][3]
        ticks = [(float(s['text'].replace(',', '.')), (s['bbox'][1]+s['bbox'][3])/2)
                 for s in spans if 510 < s['bbox'][0] < 530 and y0-6 < s['bbox'][1] < y1+6
                 and s['text'].strip().replace(',', '.').replace('.', '', 1).isdigit()]
        ticks.sort(key=lambda t: t[1])
        positions = [(y-y0)/(y1-y0)*(len(colors)-1) for value, y in ticks]
        legend_values = np.interp(np.arange(len(colors)), positions, [v for v,y in ticks])
        # Tick labels do not always reach the ends of the colorbar (notably rooftop PV).
        tick_values = np.array([v for v, y in ticks])
        pixel_rows = np.arange(len(colors))
        above = pixel_rows < positions[0]
        below = pixel_rows > positions[-1]
        legend_values[above] = tick_values[0] + (pixel_rows[above]-positions[0]) * (tick_values[1]-tick_values[0])/(positions[1]-positions[0])
        legend_values[below] = tick_values[-1] + (pixel_rows[below]-positions[-1]) * (tick_values[-1]-tick_values[-2])/(positions[-1]-positions[-2])
        legend_values = np.maximum(0, legend_values)
        tree = cKDTree(colors)
        for scenario_index, scenario in enumerate(['2024', 'B2037', 'B2045']):
            rgb = image_array(document, maps[technology_index*3+scenario_index]['xref'])
            height, width = rgb.shape[:2]
            # Each embedded map can have different white padding and pixel dimensions.
            _, panel_edge = silhouette(rgb)
            base_y, base_x = np.where(country_mask > 0)
            base_low = np.array([base_x.min(), base_y.min()])
            base_high = np.array([base_x.max(), base_y.max()])
            panel_low, panel_high = panel_edge.min(axis=0), panel_edge.max(axis=0)
            panel_scale = (panel_high-panel_low)/(base_high-base_low)
            for feature in features:
                region = np.zeros((height, width), 'uint8')
                for polygon in polygons(feature['geometry']):
                    rings = [np.rint((transform(ring)-base_low)*panel_scale+panel_low).astype('int32') for ring in polygon]
                    cv2.fillPoly(region, rings, 255)
                    if technology_index == scenario_index == 0:
                        cv2.polylines(overlay, [rings[0]], True, (0, 100, 180), 1)
                inside = cv2.erode(region, np.ones((5, 5), 'uint8')) > 0
                pixels = rgb[inside]
                small = len(pixels) < 12
                if small:
                    distances = cv2.distanceTransform(region, cv2.DIST_L2, 3)
                    pixels = rgb[distances >= max(1, float(distances.max())*.7)]
                if not len(pixels):
                    continue
                # Reject dark gray boundary strokes; preserve nearly white zero-valued fills.
                pixels = pixels[(pixels.max(axis=1)-pixels.min(axis=1) > 5) | (pixels.min(axis=1)>240)]
                errors, indices = tree.query(pixels.astype(float)) if len(pixels) else (np.array([]), np.array([],dtype=int))
                keep = errors <= 12
                decoded = legend_values[indices[keep]]
                accepted = len(decoded)/max(len(pixels),1)
                estimate = float(np.median(decoded)) if len(decoded) else None
                p10, p90 = (np.percentile(decoded,[10,90]).tolist() if len(decoded) else [None,None])
                quality = 'low' if small or accepted<.7 or not len(decoded) else ('mixed' if p90-p10>.2 else 'usable')
                props = feature['properties']
                rows.append(dict(AGS=props['AGS'], district=props['GEN'], state=props['bundesland'],
                                 technology=technology, scenario=scenario,
                                 estimated_MW_per_km2=round(estimate,2) if estimate is not None else None,
                                 pixel_p10=round(p10,3) if p10 is not None else None,
                                 pixel_p90=round(p90,3) if p90 is not None else None,accepted_pixel_fraction=round(accepted,3),
                                 sample_pixels=int(len(decoded)),quality=quality,
                                 upper_scale_saturation=bool(estimate is not None and estimate >= legend_values.max()-.01),
                                 source='NEP 2025 first draft, figure 10/11; inferred from raster colors'))
        metadata = dict(technology=technology, colors=colors.tolist(), legend_values=legend_values.tolist(),
                        source_pdf=str(args.pdf), source_page=page.number+1,
                        note='Approximate values inferred from compressed raster colors; not official numeric data.')
        (output/f'{technology}_legend.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    pd.DataFrame(rows).to_csv(output/'nep_pv_district_density_ESTIMATED_2024_B2037_B2045.csv',index=False,encoding='utf-8-sig')
    Image.fromarray(overlay).save(output/'alignment_check.png')
    serializable = {k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in fit.items()}
    (output/'alignment.json').write_text(json.dumps(serializable,indent=2),encoding='utf-8')
    print('Estimated rows:',len(rows),'; quality:',pd.DataFrame(rows)['quality'].value_counts().to_dict())
    print(output)


if __name__ == '__main__':
    main()
