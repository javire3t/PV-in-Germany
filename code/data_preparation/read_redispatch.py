"""Curtailment of renewables by state (2021) and redispatch share by district (2025).

2021: BNetzA/Bundeskartellamt Monitoringbericht 2022, Abbildung 60 "Regionale Verteilung der
Ausfallarbeit im Jahr 2021" (GWh of curtailed EEG feed-in by state), read from the PDF text.

2025: enervis for Green Planet Energy (2026), "Auswirkung des Redispatchvorbehalts", page 4
map "Anteil Redispatch an gesamter Stromerzeugung" (the map reproduced by BEE). No table is
published, so the raster map is aligned with the BKG district boundaries (through the district
lines drawn on it) and each district is read from its colours against the map legend:
<2 %, 2-3 %, 3 %, >3 %. Grey districts, and districts under only the pale glow at the edge of
the heat map, have no data (227 districts with data; enervis reports 224). The source is a smoothed heat map, so a
district's class is an approximation, not a published value.

Outputs (data/processed/redispatch/): curtailment_2021_by_state.csv,
redispatch_share_2025_by_district_ESTIMATED.csv, enervis_alignment.json and
enervis_alignment_check.png. Source PDFs are in data/raw/redispatch/.
"""
if __package__ in (None, ''):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
import re

import cv2
import numpy as np
import pandas as pd
import pymupdf
from PIL import Image
from pyproj import Transformer
from scipy.ndimage import map_coordinates
from scipy.optimize import minimize
from scipy.spatial import cKDTree

from project_paths import BKG_GEOJSON, DATA, RAW
from data_preparation.estimate_nep_districts import image_array, polygons
from data_preparation.read_workbook import STATE_AREA_KM2, STATE_CODES

SOURCES = RAW / 'redispatch'
OUTPUT = DATA / 'processed' / 'redispatch'
MONITORING_REPORT = SOURCES / 'bnetza_monitoringbericht_2022.pdf'
ENERVIS = SOURCES / 'enervis_redispatchvorbehalt_2026.pdf'
# German state names in the report -> English names used in the project.
GERMAN_NAMES = {
    'Baden-Württemberg': 'Baden-Württemberg', 'Bayern': 'Bavaria', 'Berlin': 'Berlin',
    'Brandenburg': 'Brandenburg', 'Bremen': 'Bremen', 'Hamburg': 'Hamburg', 'Hessen': 'Hesse',
    'Mecklenburg-Vorpommern': 'Mecklenburg-Western Pomerania', 'Niedersachsen': 'Lower Saxony',
    'Nordrhein-Westfalen': 'North Rhine-Westphalia', 'Rheinland-Pfalz': 'Rhineland-Palatinate',
    'Saarland': 'Saarland', 'Sachsen': 'Saxony', 'Sachsen-Anhalt': 'Saxony-Anhalt',
    'Schleswig-Holstein': 'Schleswig-Holstein', 'Thüringen': 'Thuringia'}
CLASSES = ['<2%', '2-3%', '3%', '>3%']
MIN_STRONG_SHARE = .3


def curtailment_2021():
    """State curtailment (GWh) from the bar chart text of Abbildung 60, with MWh per km²."""
    document = pymupdf.open(MONITORING_REPORT)
    page = next(p for p in document if 'Regionale Verteilung der Ausfallarbeit im Jahr 2021' in p.get_text()
                and 'in GWh' in p.get_text())
    lines = [line.strip() for line in page.get_text().splitlines() if line.strip()]
    names = [line for line in lines if line in GERMAN_NAMES]
    numbers = [line for line in lines if re.fullmatch(r'[\d.]+', line)]
    # The chart lists its 16 values, smallest first, followed by the 16 state names in the same order.
    values = [float(n.replace('.', '')) for n in numbers[-len(names):]]
    if len(names) != 16 or len(values) != 16:
        raise ValueError('Could not read the 16 state values of Abbildung 60')
    table = pd.DataFrame(dict(state=[GERMAN_NAMES[n] for n in names], state_de=names, curtailment_GWh=values))
    table['area_km2'] = table.state.map(STATE_AREA_KM2)
    table['curtailment_MWh_per_km2'] = table.curtailment_GWh * 1000 / table.area_km2
    table['source'] = f'BNetzA Monitoringbericht 2022, Abbildung 60 (PDF page {page.number + 1})'
    return table.sort_values('curtailment_GWh', ascending=False)


def strokes_distance(rgb):
    """Distance to the thin district lines drawn on the map (dark relative to their surroundings)."""
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    closed = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    strokes = ((closed.astype(np.int16) - gray.astype(np.int16)) > 18).astype(np.uint8)
    return cv2.distanceTransform(1 - strokes, cv2.DIST_L2, 3), strokes.astype(bool)


def align(rgb, features):
    """Affine map from BKG coordinates (EPSG:3035) to image pixels, fitted to the district lines."""
    distance, _ = strokes_distance(rgb)
    to3035 = Transformer.from_crs(25832, 3035, always_xy=True)
    rings = []
    for feature in features:
        for polygon in polygons(feature['geometry']):
            ring = np.asarray(polygon[0])
            x, y = to3035.transform(ring[:, 0], ring[:, 1])
            rings.append(np.column_stack([x, y]))
    low, high = np.concatenate(rings).min(axis=0), np.concatenate(rings).max(axis=0)
    sample = (np.concatenate([r[::max(1, len(r) // 60)] for r in rings]) - low) / (high - low)

    def project(parameters, points):
        affine = np.asarray(parameters).reshape(2, 3)
        return points @ affine[:, :2].T + affine[:, 2]

    def loss(parameters):
        pixels = project(parameters, sample)
        d = map_coordinates(distance, [pixels[:, 1], pixels[:, 0]], order=1, mode='constant', cval=30)
        return float(np.mean(np.minimum(d, 8) ** 2))

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    ys, xs = np.where(gray < 245)
    initial = np.array([xs.max() - xs.min(), 0, xs.min(), 0, -(ys.max() - ys.min()), ys.max()], float)
    best = None
    # The heat-map glow extends beyond the borders, so try slightly smaller starting extents.
    for scale in (1.0, .97, .94, .91):
        for shift in (-6, 0, 6):
            start = initial.copy()
            start[[0, 4]] *= scale
            start[2] += shift + (1 - scale) * initial[0] / 2
            start[5] += (1 - scale) * initial[4] / 2
            fitted = minimize(loss, start, method='Powell', options={'maxiter': 4000, 'xtol': .01, 'ftol': 1e-4})
            if best is None or fitted.fun < best.fun:
                best = fitted
    pixels = project(best.x, sample)
    error = map_coordinates(distance, [pixels[:, 1], pixels[:, 0]], order=1, mode='constant', cval=30)
    fit = dict(epsg=3035, low=low.tolist(), high=high.tolist(), affine=best.x.tolist(),
               median_px=float(np.median(error)), p90_px=float(np.percentile(error, 90)))
    if fit['p90_px'] > 2:
        raise ValueError(f"enervis map alignment too uncertain: p90 {fit['p90_px']:.1f} px")

    def transform(ring):
        x, y = to3035.transform(np.asarray(ring)[:, 0], np.asarray(ring)[:, 1])
        return project(best.x, (np.column_stack([x, y]) - low) / (high - low))
    return fit, transform


def redispatch_2025():
    """Redispatch-share class of every district read from the enervis heat map."""
    document = pymupdf.open(ENERVIS)
    page = next(p for p in document if 'Anteil Redispatch an gesamter Stromerzeugung' in p.get_text())
    images = sorted(page.get_image_info(xrefs=True), key=lambda i: i['width'] * i['height'])
    legend_info = next(i for i in images if i['width'] < 40 and i['height'] > 60)
    map_info = images[-1]
    rgb = image_array(document, map_info['xref'])
    legend = image_array(document, legend_info['xref'])
    colors = legend[:, legend.shape[1] // 2 - 3:legend.shape[1] // 2 + 4].mean(axis=1)
    # Class boundaries lie halfway between the legend labels (top: >3 %, bottom: <2 %).
    spans = [s for b in page.get_text('dict')['blocks'] for l in b.get('lines', []) for s in l['spans']]
    top, bottom = legend_info['bbox'][1], legend_info['bbox'][3]
    centres = []
    for label in ('>3%', '3%', '2-3%', '< 2%'):
        span = next(s for s in spans if s['text'].strip() == label and s['bbox'][0] < 120)
        centres.append(((span['bbox'][1] + span['bbox'][3]) / 2 - top) / (bottom - top))
    edges = [(a + b) / 2 for a, b in zip(centres, centres[1:])]
    position_from_top = np.linspace(0, 1, len(colors))
    tree = cKDTree(colors)

    features = json.loads(BKG_GEOJSON.read_text(encoding='utf-8'))['features']
    fit, transform = align(rgb, features)
    _, strokes = strokes_distance(rgb)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    grey = (hsv[..., 1] < 25) & (hsv[..., 2] > 170)
    state_names = {'DE.' + code: state for state, code in STATE_CODES.items()}
    rows, overlay = [], rgb.copy()
    for feature in features:
        region = np.zeros(rgb.shape[:2], np.uint8)
        for polygon in polygons(feature['geometry']):
            cv2.fillPoly(region, [np.rint(transform(ring)).astype(np.int32) for ring in polygon], 255)
            cv2.polylines(overlay, [np.rint(transform(polygon[0])).astype(np.int32)], True, (0, 60, 200), 1)
        inside = (cv2.erode(region, np.ones((3, 3), np.uint8)) > 0) & ~strokes
        if inside.sum() < 5:
            inside = (region > 0) & ~strokes
        props = feature['properties']
        row = dict(AGS=props['AGS'], district=props['GEN'], state=state_names[props['bundesland']],
                   pixels=int(inside.sum()))
        grey_share = float(grey[inside].mean()) if inside.any() else 1.0
        strong_share = float((hsv[..., 1][inside] >= 150).mean()) if inside.any() else 0.0
        row.update(grey_share=round(grey_share, 3), strong_colour_share=round(strong_share, 3))
        # The heat map fades out as a pale, translucent glow over grey no-data districts. Districts
        # with data are mostly covered by saturated colour (HSV saturation >= 150), even where green.
        if strong_share < MIN_STRONG_SHARE:
            row.update(covered=False, legend_position=None, share_class=None, colour_error=None)
        else:
            pixels = rgb[inside & ~grey].astype(float)
            errors, index = tree.query(pixels)
            position = float(np.median(1 - position_from_top[index]))  # 0 = bottom (<2 %), 1 = top (>3 %)
            share_class = CLASSES[int(np.searchsorted([1 - e for e in edges[::-1]], position))]
            row.update(covered=True, legend_position=round(position, 3), share_class=share_class,
                       colour_error=round(float(np.median(errors)), 1))
        rows.append(row)
    table = pd.DataFrame(rows)
    table['source'] = f'enervis/Green Planet Energy 2026, page {page.number + 1} map; inferred from raster colours'
    # The legend itself (first row is the white frame), so figures can reuse its colour gradient.
    legend_colours = dict(colours_top_to_bottom=colors[1:].round().tolist(),
                          label_positions_from_bottom=dict(zip(CLASSES[::-1], [round(1 - c, 3) for c in centres])),
                          class_edges_from_bottom=[round(1 - e, 3) for e in edges[::-1]])
    return table, fit, overlay, legend_colours


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    states = curtailment_2021()
    states.to_csv(OUTPUT / 'curtailment_2021_by_state.csv', index=False, encoding='utf-8-sig')
    print(states[['state', 'curtailment_GWh', 'curtailment_MWh_per_km2']].round(1).to_string(index=False))
    print('Total:', states.curtailment_GWh.sum(), 'GWh')
    districts, fit, overlay, legend_colours = redispatch_2025()
    (OUTPUT / 'enervis_legend.json').write_text(json.dumps(legend_colours, indent=2), encoding='utf-8')
    districts.to_csv(OUTPUT / 'redispatch_share_2025_by_district_ESTIMATED.csv', index=False, encoding='utf-8-sig')
    (OUTPUT / 'enervis_alignment.json').write_text(json.dumps(fit, indent=2), encoding='utf-8')
    Image.fromarray(overlay).save(OUTPUT / 'enervis_alignment_check.png')
    print('Alignment error (px): median', round(fit['median_px'], 2), 'p90', round(fit['p90_px'], 2))
    print('Districts with data:', int(districts.covered.sum()), 'of', len(districts))
    print(districts[districts.covered].share_class.value_counts().reindex(CLASSES).to_dict())


if __name__ == '__main__':
    main()
