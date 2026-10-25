"""Energy-Charts and BNetzA PV figures used by the project.

Run with ``python main.py external-figures``.
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.path import Path

from project_paths import FINAL_OUTPUTS, INTERMEDIATE_OUTPUTS
from figures.shared.plot_helpers import figure_name
from figures.shared.source_credits import add_source_footer


OUT = FINAL_OUTPUTS
WORK = INTERMEDIATE_OUTPUTS / "external_figures"
SOURCE = "Energy-Charts.info; values checked against the selected chart view"

MIX_TOTAL = 497.5
# Energy-Charts' 2025 total view reports an energetically corrected total of
# 497.5 TWh.  The displayed source series sum to 494.68 TWh; the difference
# is included in the explicit Others slice rather than left as an unnamed
# residual.  Others contains the small source categories listed below.
MIX = [
    ("Waste renewable", 4.23, "#513000"), ("Hydro run-of-river", 15.43, "#1409cc"),
    ("Biomass grid feed-in", 36.06, "#2c962a"), ("Biomass self-consumption", 4.36, "#4cc75c"),
    ("Wind offshore", 26.07, "#9daf90"), ("Wind onshore", 105.10, "#c3d6b6"),
    ("Solar EEG grid feed-in", 67.94, "#facc5b"), ("Solar self-consumption", 19.84, "#fcea66"),
    ("Lignite grid feed-in", 67.19, "#978168"), ("Hard coal grid feed-in", 26.60, "#323232"),
    ("Coal-derived gas", 4.15, "#dcc37b"), ("Gas grid feed-in", 49.54, "#f29543"),
    ("Gas industrial own production", 29.78, "#fac778"),
    ("Waste non-renewable", 4.70, "#523202"), ("Import balance", 18.81, "#78197f"),
]

# Small official Energy-Charts series omitted from the main labels.  The
# total-view correction is included so the plotted slices sum exactly to the
# official 497.5 TWh centre value.
MIX.append((
    "Other",
    round(MIX_TOTAL - sum(v for _, v, _ in MIX), 2),
    "#e3e3e3",
))

POWER = [
    ("Hydro", 5.3, "#0000ae"), ("Hydro pumped storage", 9.9, "#afc8ff"),
    ("Battery storage", 21.4, "#bebbda"), ("Biomass", 9.1, "#009631"),
    ("Lignite", 14.8, "#977d64"), ("Hard coal", 15.1, "#313131"),
    ("Oil", 3.5, "#7e644b"), ("Gas", 35.3, "#fb964b"),
    ("Other non-renewable", 2.4, "#957daf"), ("Wind offshore", 11.4, "#9bb091"),
    ("Wind onshore", 71.3, "#c3d8b9"), ("Solar AC", 118.6, "#ffcd64"),
]

# Official BNetzA anchor rates: first published small-rooftop fixed-feed rate
# for each year.  These are not annual averages; 2012 onward has several
# within-year tariff steps, so the source period is retained in the notes.
FIT = {2010: 39.14, 2011: 28.74, 2012: 24.43, 2013: 17.016,
       2014: 13.683, 2015: 12.954, 2016: 12.697, 2017: 12.30,
       2018: 12.20, 2019: 11.09, 2020: 9.87, 2021: 8.16,
       2022: 7.14, 2023: 8.20, 2024: 8.11, 2025: 7.94, 2026: 7.78}
RETAIL = {2000: 13.9, 2001: 14.3, 2002: 16.1, 2003: 17.2, 2004: 18.0,
          2005: 18.7, 2006: 19.5, 2007: 20.6, 2008: 21.7, 2009: 23.2,
          2010: 23.7, 2011: 25.2, 2012: 25.9, 2013: 28.8, 2014: 29.1,
          2015: 28.7, 2016: 28.8, 2017: 29.3, 2018: 29.5, 2019: 30.5,
          2020: 31.8, 2021: 32.2, 2022: 37.9, 2023: 45.7, 2024: 40.9,
          2025: 39.6, 2026: 37.0}

MV_LOW, MV_MID, MV_HIGH = 4.51 - .715, 4.0, 4.51 - .358


def _save(fig, metric, period, *, dpi=300):
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / figure_name("germany", "all", metric, "chart", period)
    temporary = target.with_name(target.name + ".tmp")
    fig.savefig(temporary, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
    temporary.replace(target)
    plt.close(fig)
    return target


def electricity_mix():
    rows = MIX
    # Give the labels room horizontally while keeping the footer compact.
    fig, ax = plt.subplots(figsize=(15.2, 6.65), dpi=300)
    values = [v for _, v, _ in rows]
    colors = [c for _, _, c in rows]
    wedges, _ = ax.pie(values, colors=colors, startangle=90, counterclock=False,
                       radius=1.17, wedgeprops={"width": .38, "edgecolor": "white", "linewidth": 1.2})

    groups = {
        "Renewables": {"Waste renewable", "Hydro run-of-river", "Biomass grid feed-in",
                       "Biomass self-consumption", "Wind offshore", "Wind onshore",
                       "Solar EEG grid feed-in", "Solar self-consumption"},
        "Fossil": {"Lignite grid feed-in", "Hard coal grid feed-in", "Coal-derived gas",
                   "Gas grid feed-in", "Gas industrial own production", "Waste non-renewable"},
        "Imports": {"Import balance"},
        "Other": {"Other"},
    }
    group_colors = {"Renewables": "#2f8f5b", "Fossil": "#8b6f55",
                    "Imports": "#7b3f91", "Other": "#b6b6b6"}
    group_values = [sum(v for n, v, _ in rows if n in names) for names in groups.values()]
    ax.pie(group_values, colors=[group_colors[n] for n in groups], startangle=90,
           counterclock=False, radius=.77,
           wedgeprops={"width": .13, "edgecolor": "white", "linewidth": 1.0})

    labels = {1: [], -1: []}
    # Keep every technology title on one line; the wide layout provides room.
    display_names = {}
    for wedge, (name, value, color) in zip(wedges, rows):
        angle = np.deg2rad((wedge.theta1 + wedge.theta2) / 2)
        x, y = np.cos(angle), np.sin(angle)
        labels[1 if x >= 0 else -1].append((y, x, name, value, color))
    for side, items in labels.items():
        items.sort(key=lambda item: item[0], reverse=True)
        label_positions = np.linspace(1.34, -1.22, len(items))
        for y_label, (y, x, name, value, color) in zip(label_positions, items):
            text_x = 1.68 * side
            # Use one smooth Bézier curve whose initial tangent is radial, so
            # each connector leaves its wedge perpendicularly without showing
            # a visible elbow before turning toward the text block.
            start_x, start_y = 1.17 * x, 1.17 * y
            radial_x, radial_y = 1.39 * x, 1.39 * y
            curve = Path(
                [(start_x, start_y),
                 (radial_x, radial_y),
                 (text_x - .24 * side, y_label),
                 (text_x - .02 * side, y_label)],
                [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4],
            )
            ax.add_patch(PathPatch(curve, fill=False, color=color, linewidth=1.0,
                                   capstyle="round", joinstyle="round"))
            label = display_names.get(name, name)
            name_lines = label.count("\n") + 1
            # Keep the value line at a consistent distance from the last
            # technology-name line, whether the name is one or two lines.
            name_y = y_label + .040 + (name_lines - 1) * .040
            value_y = y_label - .060
            ax.text(text_x, name_y, label,
                    ha="left" if side > 0 else "right", va="center", fontsize=8.7,
                    color="#4d4d4d", fontweight="bold", linespacing=1.05)
            ax.text(text_x, value_y,
                    f"{value / MIX_TOTAL * 100:.1f} % · {value:.1f} TWh",
                    ha="left" if side > 0 else "right", va="center", fontsize=8.2,
                    color="#8a8a8a")
    ax.text(0, .12, f"{MIX_TOTAL:.1f}", ha="center", va="center", fontsize=39, color="#555555")
    ax.text(0, -.18, "TWh", ha="center", va="center", fontsize=32, color="#555555")
    # Compact, centered footer legend: the four summaries should read as one
    # grouped legend rather than four widely separated blocks.
    # Center the complete legend beneath the donut instead of stretching it
    # across the full canvas.
    aggregator_x = [.33, .48, .63, .78]
    for x_pos, (name, value) in zip(aggregator_x, zip(groups, group_values)):
        fig.patches.append(Rectangle((x_pos - .083, .023), .029, .040,
                                     transform=fig.transFigure, facecolor=group_colors[name],
                                     edgecolor="none", clip_on=False))
        fig.text(x_pos - .044, .052, name, ha="left", va="center",
                 fontsize=16.0, color="#333333", fontweight="bold")
        fig.text(x_pos - .044, .011, f"{value / MIX_TOTAL * 100:.1f} % · {value:.1f} TWh",
                 ha="left", va="center", fontsize=13.0, color="#888888")
    ax.set(aspect="equal", xlim=(-2.15, 2.15), ylim=(-1.48, 1.48)); ax.axis("off")
    fig.subplots_adjust(bottom=.065)
    footer_texts = add_source_footer(
        fig,
        ["Visualization: EIFER", "Data: Energy-Charts.info (retrieved 16.10.2026)"],
        title="Electricity mix in Germany · 497.5 TWh")
    # Keep the existing donut and aggregator legend untouched; place the
    # shared footer below that legend instead of between the chart and legend.
    for text, y in zip(footer_texts, (-.035, -.065, -.095)):
        text.set_position((.5, y))
    fig.subplots_adjust(bottom=.065)
    target = _save(fig, "electricity-mix", "497-5-TWh", dpi=300)
    WORK.mkdir(parents=True, exist_ok=True)
    with (WORK / "electricity_mix.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle); writer.writerow(["source", "TWh", "share"])
        writer.writerows((n, v, v / MIX_TOTAL) for n, v, _ in rows)
    return target


def installed_power():
    # Preserve the installed-capacity figure supplied by the project.
    # Do not regenerate it: regeneration changes the user's original artwork.
    preserved = OUT / "Figure_installed-power_germany_2026.png"
    if preserved.exists():
        print(f"Preserved existing installed-power figure: {preserved}")
        return preserved

    fig, ax = plt.subplots(figsize=(12, 8), dpi=300)
    names = [n for n, _, _ in POWER][::-1]; values = [v for _, v, _ in POWER][::-1]
    colors = [c for _, _, c in POWER][::-1]
    bars = ax.barh(names, values, color=colors, zorder=3)
    for bar, value in zip(bars, values):
        ax.text(value + 1.2, bar.get_y() + bar.get_height() / 2, f"{value:.1f}", va="center")
    ax.set_xlim(0, 132); ax.set_xlabel("Installed capacity (GW)"); ax.set_title("Net installed electricity generation capacity in Germany, 2026")
    ax.grid(axis="x", alpha=.25, zorder=0)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    add_source_footer(fig, ["Visualization: EIFER", "Data: Energy-Charts.info (retrieved 16.10.2026)"],
                      title="Installed electricity capacity by technology, Germany, 2026")
    target = _save(fig, "installed-power", "2026", dpi=300)
    with (WORK / "installed_power_2025.csv").open("w", newline="", encoding="utf-8") as handle:
        WORK.mkdir(parents=True, exist_ok=True)
        writer = csv.writer(handle); writer.writerow(["technology", "GW", "year"]); writer.writerows((n, v, 2026) for n, v, _ in POWER)
    return target


def selling_vs_consuming():
    years = np.array(sorted(FIT))
    fig, (ax, gap) = plt.subplots(2, 1, figsize=(10.5, 8), sharex=True, dpi=300, gridspec_kw={"height_ratios": [2.2, 1]})
    all_years = years
    retail = np.array([RETAIL[y] for y in years])
    sell = np.array([FIT[y] for y in years])
    ax.plot(years, retail, "o-", color="#2f78b7",
            label="Household electricity price")
    ax.plot(years, sell, "o-", color="#2ca02c",
            label="PV selling tariff")
    ax.set_ylabel("ct/kWh"); ax.grid(alpha=.3); ax.legend(fontsize=8)
    diff = retail - sell; gap.bar(all_years, diff, color=np.where(diff >= 0, "#4a90d9", "#7fb519")); gap.axhline(0, color="black", lw=.8); gap.set(xlabel="Year", ylabel="Retail − selling\n[ct/kWh]"); gap.set_xticks(np.arange(2010, 2027, 2)); gap.grid(alpha=.2)
    add_source_footer(fig, ["Visualization: EIFER", "Data: Bundesnetzagentur (retrieved 16.10.2026)"],
                      title="Household electricity price and PV selling tariff")
    target = _save(fig, "selling-vs-consuming", "2010-2026")
    return [target]


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    targets = [electricity_mix(), installed_power(), *selling_vs_consuming()]
    print("Updated external figure imports:")
    for target in targets:
        print(f"  {target}")


if __name__ == "__main__":
    main()
