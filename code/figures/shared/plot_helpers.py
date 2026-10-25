"""Small drawing helpers shared by the figure scripts."""
import re
import unicodedata
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.path import Path as PlotPath
from matplotlib.patches import PathPatch
from PIL import Image

COLORS = ['#B85C00', '#246A8A']

# Geographic scopes accepted by the naming convention.
SCALE_ORDER = {'germany': 1, 'regions': 2, 'states': 3, 'districts': 4}


def slug(name):
    """ASCII, lowercase, hyphenated name without the German district word 'Kreis'."""
    plain = unicodedata.normalize('NFKD', str(name)).encode('ascii', 'ignore').decode().lower()
    plain = re.sub(r'[^a-z0-9]+', '-', plain).strip('-')
    return re.sub(r'^(land)?kreis-|-?kreis$', '', plain) or plain


def selection_slug(names):
    """Compared regions in alphabetical order, e.g. 'saxony-anhalt-vs-thuringia'."""
    return '-vs-'.join(sorted(slug(name) for name in names))


def figure_name(scale, subject, metric, kind, period, scenario=None, suffix='.png'):
    """Use short names with type or metric, scope, selection and optional NEP scenario."""
    if scale not in SCALE_ORDER:
        raise KeyError(scale)
    prefix = 'Animation' if suffix.lower() == '.gif' or 'animation' in kind else 'Figure'
    parts = [prefix, 'comparison' if kind == 'comparison' else metric, scale]
    if subject != 'all':
        parts.append(subject)
    # Keep only qualifiers that distinguish otherwise identical outputs.
    qualifier = {'map-labeled': 'labeled', 'scatter-logx': 'logx',
                 'scatter-loglog': 'loglog'}.get(kind)
    if qualifier:
        parts.append(qualifier)
    parts.append(str(period))
    if scenario:
        parts.append(scenario.upper() if scenario.lower().startswith('nep-') else scenario)
    return '_'.join(parts) + suffix

def number(value):
    return float(value) if isinstance(value, (int, float)) else float('nan')

def polygon_patch(rings, color):
    vertices, codes = [], []
    for ring in rings:
        vertices.extend(ring)
        codes.extend([PlotPath.MOVETO] + [PlotPath.LINETO] * (len(ring) - 2) + [PlotPath.CLOSEPOLY])
    return PathPatch(PlotPath(vertices, codes), facecolor=color, edgecolor='white', linewidth=.5)


def add_polygon(ax, patch):
    """Add a map polygon quickly.

    Axes.add_patch measures every Bezier segment to update the data limits,
    which takes most of the run time with full-resolution BKG boundaries.
    The polygons are straight-line paths, so their vertices give the same limits.
    """
    ax.add_artist(patch)
    ax.update_datalim(patch.get_path().vertices)
    return patch


def gif_palette(images):
    """Build one palette from representative samples of every animation frame.

    A palette made from only the final frame can quantize earlier maps poorly,
    especially when the spatial distribution changes over time.  Small samples
    keep palette construction cheap while preserving the colours used across
    the whole animation.
    """
    if isinstance(images, Image.Image):
        images = [images]
    samples = []
    for image in images:
        sample = image.convert('RGB').copy()
        sample.thumbnail((256, 256), Image.Resampling.BILINEAR)
        samples.append(sample)
    width = max(image.width for image in samples)
    contact = Image.new('RGB', (width, sum(image.height for image in samples)), 'white')
    y = 0
    for sample in samples:
        contact.paste(sample, (0, y))
        y += sample.height
    palette = contact.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    colors = palette.getpalette()
    palette.putpalette(colors[:765] + colors[:3])
    return palette


def gif_frame(image, palette):
    """Use binary GIF transparency without erasing opaque black artwork."""
    rgba = image.convert('RGBA')
    frame = rgba.convert('RGB').quantize(palette=palette, dither=Image.Dither.NONE)
    frame = frame.point(lambda index: 0 if index == 255 else index)
    frame.paste(255, mask=rgba.getchannel('A').point(lambda alpha: 255 if alpha < 128 else 0))
    frame.info['transparency'] = 255
    return frame
