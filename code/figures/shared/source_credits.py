"""One source-footer style, with the actual sources used by each figure."""
from datetime import datetime
from functools import lru_cache
import json
import re
from matplotlib.font_manager import FontProperties

from project_paths import ENERGY_CHARTS, BKG_GEOJSON, DATA

RETRIEVED = '16.10.2026'


@lru_cache(maxsize=1)
def chart_metadata():
    path = ENERGY_CHARTS / 'chart_text.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def data_update(year):
    """Energy-Charts 'Last Update' date of one year's map, or None if unknown."""
    source = chart_metadata().get(str(year), {}).get('source', '')
    update = re.search(r'Last Update:\s*(\d{2}/\d{2}/\d{4})', source)
    return datetime.strptime(update.group(1), '%m/%d/%Y') if update else None


def is_partial_year(year):
    """Determine incomplete reporting years independently of their displayed label."""
    update = data_update(year)
    return update is not None and update.year == int(year)


def history_source(reference_year=None):
    return f'Data: Energy-Charts.info (retrieved {RETRIEVED})'


def mastr_source():
    return f'Data: Marktstammdatenregister (retrieved {RETRIEVED})'


def source_lines(kind='history', reference_year=None, boundaries=False, geojson=None, areas=False):
    lines = ['Visualization: EIFER']
    if kind in {'history', 'nep_scenarios'}:
        lines.append(history_source(reference_year))
    if kind == 'nep_scenarios':
        lines[-1] = f'Data: NEP 2025, second draft (retrieved {RETRIEVED})'
    elif kind == 'nep_estimates':
        lines.append(f'Data: NEP 2025, first draft (retrieved {RETRIEVED})')
    elif kind == 'mastr':
        lines.append(mastr_source())
    return lines


def add_source_footer(fig, lines, center=.5, line_spacing=.022, bottom=.030, fontsize=None,
                      title=None, show_footer=True):
    """Add the one shared title / visualisation / data block to a figure.

    The geometry is fixed relative to the full canvas, rather than to the
    plotted axes.  This keeps every exported block vertically aligned.
    """
    if title is None:
        if fig._suptitle is not None and fig._suptitle.get_visible():
            title = fig._suptitle.get_text()
            fig._suptitle.set_visible(False)
        else:
            for ax in fig.axes:
                if ax.get_title() and (ax.get_xlabel() or len(ax.get_title()) > 20):
                    title = ax.get_title()
                    ax.set_title('')
                    break
    # The footer is deliberately one fixed three-line block.  Some plotting
    # modules use a newline in their internal title; collapse it here so that
    # the exported figures do not acquire figure-specific footer heights.
    if title:
        title = re.sub(r'\s+', ' ', title).strip()
    # Keep the figure footer enabled by default: every exported figure carries
    # the same compact title / visualisation / data block.
    if not show_footer:
        return []

    # One fixed, compact three-line block for every generated figure.
    # The text is deliberately built here, rather than separately in each
    # figure module, so title/source/data typography stays harmonised.
    fig.subplots_adjust(bottom=max(fig.subplotpars.bottom, .14))
    visualization = next((line for line in lines if line.startswith('Visualization:')), 'Visualization: EIFER')
    data = next((line for line in lines if line.startswith('Data:')), 'Data: source not specified')
    # A common cap prevents maps and animation frames from acquiring oversized
    # footer text merely because their plotting canvas is physically large.
    detail_size = min(fontsize if fontsize is not None else 8, 8)
    title_size = detail_size * 1.25
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    visible_axes = [ax for ax in fig.axes if ax.get_visible()]
    if visible_axes:
        content_bottom_px = min(ax.get_tightbbox(renderer).y0 for ax in visible_axes)
        content_bottom_fig = fig.transFigure.inverted().transform((0, content_bottom_px))[1]
        # Keep a small one-line safety gap between the plotted content and
        # the compact three-line footer; do not alter the footer's internal spacing.
        footer_y = max(0.02, content_bottom_fig - .065)
    else:
        footer_y = bottom
    available = fig.get_figwidth() * fig.dpi * .90
    title_props = FontProperties(family='DejaVu Sans', size=title_size, weight='bold')
    detail_props = FontProperties(family='DejaVu Sans', size=detail_size, weight='normal')
    title_width = renderer.get_text_width_height_descent(title or '', title_props, False)[0]
    detail_width = max(renderer.get_text_width_height_descent(line, detail_props, False)[0]
                        for line in (visualization, data))
    if title_width > available:
        title_size *= available / title_width
    if detail_width > available:
        detail_size *= available / detail_width

    # Pack the rows from the data line upwards using the measured glyph
    # heights.  This leaves only a small, constant pixel gap—never an
    # accidental blank line caused by a module-specific title.
    title_props = FontProperties(family='DejaVu Sans', size=title_size, weight='bold')
    detail_props = FontProperties(family='DejaVu Sans', size=detail_size, weight='normal')
    title_h = renderer.get_text_width_height_descent(title or '', title_props, False)[1]
    source_h = renderer.get_text_width_height_descent(visualization, detail_props, False)[1]
    data_h = renderer.get_text_width_height_descent(data, detail_props, False)[1]
    gap_px = max(5, round(fig.dpi * .004))
    fig_h_px = fig.get_figheight() * fig.dpi
    gap = gap_px / fig_h_px
    data_y = footer_y
    source_y = data_y + (data_h + source_h) / (2 * fig_h_px) + gap
    title_y = source_y + (source_h + title_h) / (2 * fig_h_px) + gap
    if visible_axes:
        block_top = title_y + title_h / (2 * fig_h_px)
        allowed_top = content_bottom_fig - .006
        if block_top >= allowed_top:
            shift = block_top - allowed_top
            title_y -= shift
            source_y -= shift
            data_y -= shift

    texts = []
    if title:
        caption = fig.text(center, title_y, title, ha='center', va='center', fontsize=title_size,
                           fontfamily='DejaVu Sans', fontweight='bold', color='#17372C')
        caption.set_gid('figure_caption')
        texts.append(caption)
    for y, line in ((source_y, visualization), (data_y, data)):
        credit = fig.text(center, y, line, ha='center', va='center', fontsize=detail_size,
                          fontfamily='DejaVu Sans', fontweight='normal', color='#555555')
        credit.set_gid('source_credit')
        texts.append(credit)
    return texts
