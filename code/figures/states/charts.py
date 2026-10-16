"""State capacity-versus-density scatter diagrams."""

# Allow running this file directly from an editor or any working directory.
if __package__ in (None, ''):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import (
    AutoMinorLocator,
    FixedLocator,
    FuncFormatter,
    MaxNLocator,
    NullFormatter,
    StrMethodFormatter,
)


from project_paths import WORKBOOK, settings
from data_preparation.read_workbook import state_areas
from figures.shared.plot_helpers import figure_name
from figures.shared.charts import OUTPUT_FOLDER, chart as base_chart, save_chart, plot_years


# What is compared comes from settings.py in the project root.
EXCLUDE_CITY_STATES = settings.EXCLUDE_CITY_STATES
USE_LOG_LOG_FOR_CAPACITY_DENSITY = settings.USE_LOG_LOG_FOR_CAPACITY_DENSITY
CITY_STATES = {"Berlin", "Hamburg", "Bremen"}
STATE_ABBREVIATIONS = {
    "Schleswig-Holstein": "SH", "Hamburg": "HH", "Lower Saxony": "NI",
    "Bremen": "HB", "North Rhine-Westphalia": "NW", "Hesse": "HE",
    "Rhineland-Palatinate": "RP", "Baden-Württemberg": "BW",
    "Bavaria": "BY", "Saarland": "SL", "Berlin": "BE",
    "Brandenburg": "BB", "Mecklenburg-Western Pomerania": "MV",
    "Saxony": "SN", "Saxony-Anhalt": "ST", "Thuringia": "TH",
}
SNAPSHOT_LABEL_OFFSETS = {
    "Saxony-Anhalt": (5, 12),
    "Rhineland-Palatinate": (5, -13),
    "North Rhine-Westphalia": (7, 12),
    "Baden-Württemberg": (7, -14),
    "Saxony": (-8, 10),
    "Hesse": (8, -10),
    "Schleswig-Holstein": (-7, 8),
}


def chart():
    """Increase scatter height by 20% without scaling text or changing width."""
    fig, ax = base_chart()
    fig.set_size_inches(10, 7.15 * 1.2)
    return fig, ax


def create_non_city_state_snapshot(capacity=None, density=None, year=None):
    """Draw the existing roadmap scatter plot with text readable on slides."""
    if capacity is None:
        data = pd.read_excel(WORKBOOK, sheet_name="State capacity")
        data = data[data.iloc[:, 0].isin(STATE_ABBREVIATIONS)].set_index(data.columns[0])
        columns = {int(str(column).split()[0]): column for column in data.columns
                   if str(column).split()[0].isdigit()}
        year = max(columns)
        capacity = data[columns[year]]
        areas = state_areas(WORKBOOK)
        density = pd.Series({land: capacity[land]*1000/areas[land] for land in capacity.index})
    states = [land for land in capacity.index if land not in CITY_STATES]
    fig, ax = chart()
    label_offsets = {
        "Saxony": (-8, 10),
        "Hesse": (8, -10),
        "North Rhine-Westphalia": (7, 12),
        "Baden-Württemberg": (7, -15),
        "Schleswig-Holstein": (-6, 9),
        "Rhineland-Palatinate": (6, -12),
        "Saxony-Anhalt": (6, 12),
    }
    annotations = []
    for land in states:
        ax.scatter(capacity[land], density[land], s=65, color="#C45100", zorder=3)
        dx, dy = label_offsets.get(land, (6, 7))
        annotations.append(ax.annotate(
            STATE_ABBREVIATIONS[land], (capacity[land], density[land]),
            xytext=(dx, dy), textcoords="offset points", fontsize=11.5,
            color="#263238", ha="right" if dx < 0 else "left", va="center"))
    ax.set_xscale("log")
    ax.set_title(f"Capacity and density excluding city states in {year}", fontsize=16, pad=14)
    ax.set_xlabel("Installed capacity (MWp, logarithmic scale)", fontsize=14, labelpad=10)
    ax.set_ylabel("Installed capacity density (kWp/km²)", fontsize=14, labelpad=10)
    ax.tick_params(axis="both", labelsize=12)
    ax.xaxis.set_major_locator(FixedLocator([100,200,500,1000,2000,5000,10000,20000,40000]))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda value, position: f"{value:,.0f}"))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.yaxis.set_major_locator(MaxNLocator(nbins=6))
    ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    ax.margins(x=.09, y=.09)
    ax.set_axisbelow(True)
    ax.grid(True, which="major", color="#BCCAD0", alpha=.4, linewidth=.7)
    ax.minorticks_on()
    ax.grid(True, which="minor", color="#DDE5E9", alpha=.35, linewidth=.45)
    fig.tight_layout(rect=(0,.17,1,1))
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    boxes = [label.get_window_extent(renderer).padded(2) for label in annotations]
    for index, box in enumerate(boxes):
        if any(box.overlaps(other) for other in boxes[index+1:]):
            raise ValueError("State labels overlap in the roadmap scatter plot")
        if box.x0 < ax.bbox.x0 or box.x1 > ax.bbox.x1 or box.y0 < ax.bbox.y0 or box.y1 > ax.bbox.y1:
            raise ValueError("State label extends outside the plotting area")
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
    target = OUTPUT_FOLDER / figure_name('states', 'excl-city-states', 'capacity-vs-density', 'scatter-logx', year)
    save_chart(fig, target, areas=True)
    plt.close(fig)
    print(f"Updated existing scatter plot: {target}")


def main() -> None:
    """Create capacity–density scatter diagrams."""

    if not WORKBOOK.exists():
        raise FileNotFoundError(
            f"Missing {WORKBOOK}. Run data_preparation/download_energy_charts.py first."
        )

    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
    data = pd.read_excel(WORKBOOK, sheet_name="State capacity")
    data = data[data.iloc[:, 0].notna()]
    data = data[
        ~data.iloc[:, 0].astype(str).str.startswith(
            ("Total", "Summe", "Energy", "Differenz", "Difference", "Status")
        )
    ]
    years = [str(column).split(" ")[0] for column in data.columns[1:]]
    capacities = data.set_index(data.columns[0]).iloc[:, :len(years)]
    capacities.columns = years
    latest_year = years[-1]
    areas = state_areas(WORKBOOK)
    density = capacities.copy()
    for land in density.index:
        density.loc[land] = capacities.loc[land] * 1000 / areas[land]
    snapshot_states = [
        land for land in capacities.index
        if not EXCLUDE_CITY_STATES or land not in CITY_STATES
    ]
    snapshot_capacity = capacities.loc[snapshot_states, latest_year]
    snapshot_density = density.loc[snapshot_states, latest_year]
    fig, ax = chart()
    for land in snapshot_states:
        ax.scatter(
            snapshot_capacity[land],
            snapshot_density[land],
            s=65,
            color="#C45100",
        )
        ax.annotate(
            STATE_ABBREVIATIONS.get(land, land),
            (snapshot_capacity[land], snapshot_density[land]),
            xytext=SNAPSHOT_LABEL_OFFSETS.get(land, (3, 3)),
            textcoords="offset points",
            fontsize=11.5,
            ha="right" if SNAPSHOT_LABEL_OFFSETS.get(land, (3, 3))[0] < 0 else "left",
            va="center",
            bbox={"facecolor": "none", "edgecolor": "none", "alpha": 0.7, "pad": 0.4},
        )
    ax.set_title(f"Capacity–density relationship by federal state in {latest_year}")
    ax.set_xlabel("Installed capacity (MWp)")
    ax.set_ylabel("Installed capacity density (kWp/km²)")
    if USE_LOG_LOG_FOR_CAPACITY_DENSITY:
        ax.set_xscale("log")
        ax.set_yscale("log")
    ax.xaxis.set_major_locator(MaxNLocator(nbins=10))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=6))
    ax.xaxis.set_major_formatter(
        FuncFormatter(lambda value, position: f"{value:,.0f}")
    )
    ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    ax.grid(True, alpha=0.25)
    ax.minorticks_on()
    ax.xaxis.set_minor_locator(AutoMinorLocator(5))
    ax.yaxis.set_minor_locator(AutoMinorLocator(5))
    ax.grid(True, which="minor", alpha=0.25, linewidth=0.6)
    fig.tight_layout(rect=(0,.17,1,1))
    save_chart(fig, OUTPUT_FOLDER / figure_name('states', 'all', 'capacity-vs-density', 'scatter', latest_year), areas=True)
    plt.close(fig)

    city_states = [land for land in sorted(CITY_STATES) if land in capacities.index]
    fig, ax = chart()
    for land in city_states:
        ax.scatter(
            capacities.loc[land, latest_year],
            density.loc[land, latest_year],
            s=65,
            color="#C45100",
        )
        ax.annotate(
            STATE_ABBREVIATIONS[land],
            (capacities.loc[land, latest_year], density.loc[land, latest_year]),
            xytext=(4, 4),
            textcoords="offset points",
        )
    ax.set_title(f"City-state capacity and density in {latest_year}")
    ax.set_xlabel("Installed capacity (MWp)")
    ax.set_ylabel("Installed capacity density (kWp/km²)")
    ax.xaxis.set_major_locator(MaxNLocator(nbins=6))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=6))
    ax.xaxis.set_major_formatter(
        FuncFormatter(lambda value, position: f"{value:,.0f}")
    )
    ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    ax.grid(True, alpha=0.25)
    ax.minorticks_on()
    ax.yaxis.set_minor_locator(AutoMinorLocator(5))
    ax.grid(True, which="minor", alpha=0.25, linewidth=0.6)
    fig.tight_layout(rect=(0,.17,1,1))
    save_chart(fig, OUTPUT_FOLDER / figure_name('states', 'city-states', 'capacity-vs-density', 'scatter', latest_year), areas=True)
    plt.close(fig)

    fig, ax = chart()
    for land in snapshot_states:
        ax.scatter(
            snapshot_capacity[land],
            snapshot_density[land],
            s=65,
            color="#C45100",
        )
        ax.annotate(
            STATE_ABBREVIATIONS.get(land, land),
            (snapshot_capacity[land], snapshot_density[land]),
            xytext=SNAPSHOT_LABEL_OFFSETS.get(land, (3, 3)),
            textcoords="offset points",
            fontsize=11.5,
            ha="right" if SNAPSHOT_LABEL_OFFSETS.get(land, (3, 3))[0] < 0 else "left",
            va="center",
        )
    ax.set_xscale("log")
    ax.set_title(f"Capacity and density by federal state in {latest_year} (log capacity axis)")
    ax.set_xlabel("Installed capacity (MWp, logarithmic scale)")
    ax.set_ylabel("Installed capacity density (kWp/km²)")
    ax.xaxis.set_major_locator(
        FixedLocator([50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 40000])
    )
    ax.xaxis.set_major_formatter(
        FuncFormatter(lambda value, position: f"{value:,.0f}")
    )
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.yaxis.set_major_locator(MaxNLocator(nbins=6))
    ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    ax.grid(True, alpha=0.25)
    ax.minorticks_on()
    ax.grid(True, which="minor", alpha=0.25, linewidth=0.6)
    fig.tight_layout(rect=(0,.17,1,1))
    save_chart(fig, OUTPUT_FOLDER / figure_name('states', 'all', 'capacity-vs-density', 'scatter-logx', latest_year), areas=True)
    plt.close(fig)

    create_non_city_state_snapshot(snapshot_capacity, snapshot_density, latest_year)

    print(f"Figures saved in: {OUTPUT_FOLDER.resolve()}")


if __name__ == "__main__":
    main()
