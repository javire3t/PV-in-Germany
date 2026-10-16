"""Canvas, year axis and export shared by the state and district charts."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from project_paths import FINAL_OUTPUTS
from figures.shared.source_credits import source_lines, add_source_footer, is_partial_year
from figures.shared.crop_exports import save_cropped
OUTPUT_FOLDER = FINAL_OUTPUTS


CHART_SIZE = (10, 7.15)
CHART_DPI = 180


def chart():
    """Use the same canvas and typography for all capacity analysis figures."""
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 12,
                         'axes.labelsize': 14, 'xtick.labelsize': 12,
                         'ytick.labelsize': 12, 'legend.fontsize': 12})
    return plt.subplots(figsize=CHART_SIZE, dpi=CHART_DPI)


def save_chart(fig, target, areas=False, **kwargs):
    """Add the source footer (with Destatis areas for state densities) and export."""
    for ax in fig.axes:
        ax.grid(True, which='major', color='#BCCAD0', alpha=.4, linewidth=.7)
        ax.grid(True, which='minor', color='#DDE5E9', alpha=.3, linewidth=.45)
    if 'scatter' in target.name:
        fig.canvas.draw()
        renderer=fig.canvas.get_renderer()
        for ax in fig.axes:
            labels=[text for text in ax.texts if text.get_text()]
            boxes=[text.get_window_extent(renderer).padded(2) for text in labels]
            for i,box in enumerate(boxes):
                if any(box.overlaps(other) for other in boxes[i+1:]):
                    raise ValueError(f'Overlapping scatter labels in {target.name}: {labels[i].get_text()}')
    add_source_footer(fig, source_lines(areas=areas), fontsize=11)
    save_cropped(fig, target, **kwargs)


def year_axis(ax, years):
    """Tick every fifth year plus the last one."""
    last = int(years[-1])
    ticks = [i for i, year in enumerate(years) if int(year) % 5 == 0 and last - int(year) >= 3]
    ticks.append(len(years) - 1)
    ax.set_xticks(ticks, [str(years[i]) for i in ticks])


def mark_partial_year(ax, years, lines):
    """Draw the year-to-date point of each line as a hollow marker."""
    if not is_partial_year(years[-1]):
        return
    for line in lines:
        line.set_markevery(range(len(years) - 1))
        x, y = line.get_xdata(), line.get_ydata()
        ax.plot(x[-1:], y[-1:], linestyle='none', marker=line.get_marker(),
                markersize=line.get_markersize(), markerfacecolor='white',
                markeredgecolor=line.get_color(), markeredgewidth=1.6, zorder=line.get_zorder() + 1)


def plot_years(ax, years, values, **style):
    """Year series on a categorical axis; the year-to-date point is hollow."""
    line, = ax.plot(years, values, marker="o", **style)
    mark_partial_year(ax, years, [line])
    year_axis(ax, years)
    return line
