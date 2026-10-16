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

from project_paths import FINAL_OUTPUTS, INTERMEDIATE_OUTPUTS
from figures.shared.plot_helpers import figure_name
from figures.shared.source_credits import add_source_footer


OUT = FINAL_OUTPUTS
WORK = INTERMEDIATE_OUTPUTS / "external_figures"
SOURCE = "Energy-Charts.info; values checked against the selected chart view"

MIX_TOTAL = 497.5
MIX = [
    ("Waste renewable", 4.23, "#513000"), ("Hydro run-of-river", 15.43, "#1409cc"),
    ("Biomass grid feed-in", 36.06, "#2c962a"), ("Biomass self-consumption", 4.36, "#4cc75c"),
    ("Wind offshore", 26.07, "#9daf90"), ("Wind onshore", 105.10, "#c3d6b6"),
    ("Solar EEG grid feed-in", 67.94, "#facc5b"), ("Solar self-consumption", 19.84, "#fcea66"),
    ("Lignite grid feed-in", 67.13, "#978168"), ("Hard coal grid feed-in", 26.16, "#323232"),
    ("Coal-derived gas", 4.15, "#dcc37b"), ("Gas grid feed-in", 49.49, "#f29543"),
    ("Gas industrial own production", 29.84, "#fac778"), ("Other", 9.42, "#9882b3"),
    ("Waste non-renewable", 4.70, "#523202"), ("Import balance", 18.81, "#78197f"),
]

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
FULL = {2022: 13.1, 2023: 13.1, 2024: 12.8, 2025: 12.6, 2026: 12.3}
RETAIL = {2000: 13.9, 2001: 14.3, 2002: 16.1, 2003: 17.2, 2004: 18.0,
          2005: 18.7, 2006: 19.5, 2007: 20.6, 2008: 21.7, 2009: 23.2,
          2010: 23.7, 2011: 25.2, 2012: 25.9, 2013: 28.8, 2014: 29.1,
          2015: 28.7, 2016: 28.8, 2017: 29.3, 2018: 29.5, 2019: 30.5,
          2020: 31.8, 2021: 32.2, 2022: 37.9, 2023: 45.7, 2024: 40.9,
          2025: 39.6, 2026: 37.0}

YIELD = 2 * 850
MV_LOW, MV_MID, MV_HIGH = 4.51 - .715, 4.0, 4.51 - .358


def _save(fig, metric, period, *, dpi=180):
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / figure_name("germany", "all", metric, "chart", period)
    fig.savefig(target, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return target


def electricity_mix():
    # Preserve the approved final donut once exported.
    preserved = OUT / "Figure_electricity-mix_germany_497-5-TWh.png"
    if preserved.exists():
        print(f"Preserved existing electricity-mix figure: {preserved}")
        return preserved

    remainder = round(MIX_TOTAL - sum(v for _, v, _ in MIX), 2)
    rows = MIX + [("Unlabelled remainder", remainder, "#e3e3e3")]
    fig, ax = plt.subplots(figsize=(14, 9), dpi=180)
    wedges, _ = ax.pie([v for _, v, _ in rows], colors=[c for _, _, c in rows],
                       startangle=90, counterclock=False, radius=1,
                       wedgeprops={"width": .43, "edgecolor": "white", "linewidth": 1.5})
    labels = {1: [], -1: []}
    label_y = {
        "Import balance": 1.48,
        "Waste non-renewable": 1.02,
        "Other": .56,
        "Gas industrial own production": .10,
        "Gas grid feed-in": -.36,
        "Coal-derived gas": -.82,
        "Hard coal grid feed-in": -1.18,
        "Lignite grid feed-in": -1.54,
        "Solar self-consumption": -1.88,
        "Waste renewable": 1.48,
        "Hydro run-of-river": 1.08,
        "Biomass grid feed-in": .68,
        "Biomass self-consumption": .28,
        "Wind offshore": -.12,
        "Wind onshore": -.78,
        "Solar EEG grid feed-in": -1.58,
    }
    for wedge, (name, value, color) in zip(wedges, rows):
        if name == "Unlabelled remainder":
            continue
        angle = np.deg2rad((wedge.theta1 + wedge.theta2) / 2)
        x, y = np.cos(angle), np.sin(angle)
        labels[1 if x >= 0 else -1].append((y, x, name, value, color))
    for side, items in labels.items():
        items.sort(reverse=True)
        ys = [label_y[name] for _, _, name, _, _ in items]
        for y_label, (y, x, name, value, color) in zip(ys, items):
            ax.annotate(f"{name}\n{value:.2f} TWh | {value / MIX_TOTAL:.1%}",
                        xy=(x, y / 1.15), xytext=(1.35 * side, y_label),
                        ha="left" if side > 0 else "right", va="center", fontsize=9,
                        arrowprops={"arrowstyle": "-", "color": color})
    ax.text(0, .08, "497.5", ha="center", va="center", fontsize=38, color="#555")
    ax.text(0, -.12, "TWh", ha="center", va="center", fontsize=32, color="#555")
    ax.set(aspect="equal", xlim=(-2.35, 2.35), ylim=(-2.05, 2.05)); ax.axis("off")
    target = _save(fig, "electricity-mix", "497-5-TWh", dpi=250)
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

    fig, ax = plt.subplots(figsize=(12, 8), dpi=180)
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
    target = _save(fig, "installed-power", "2026", dpi=250)
    with (WORK / "installed_power_2025.csv").open("w", newline="", encoding="utf-8") as handle:
        WORK.mkdir(parents=True, exist_ok=True)
        writer = csv.writer(handle); writer.writerow(["technology", "GW", "year"]); writer.writerows((n, v, 2026) for n, v, _ in POWER)
    return target


def _revenue(value):
    return YIELD * value / 100


def revenue_figures():
    years = np.array(sorted(FIT)); fyears = np.array(sorted(FULL)); future = np.arange(2027, 2031)
    targets = []
    fig, (ax, gap) = plt.subplots(2, 1, figsize=(10.5, 8), sharex=True, dpi=180, gridspec_kw={"height_ratios": [2.2, 1]})
    all_years = np.arange(2010, 2031); sell = np.array([FIT[y] for y in years] + [MV_MID] * 4); retail = np.array([RETAIL[y] for y in years] + [RETAIL[2026]] * 4)
    ax.plot(years, [RETAIL[y] for y in years], "o-", label="Household electricity price")
    ax.plot(all_years[-5:], retail[-5:], "--", label="Price held constant")
    ax.plot(all_years, sell, "o-", label="Selling tariff / scenario")
    ax.set_ylabel("ct/kWh"); ax.grid(alpha=.3); ax.legend(fontsize=8)
    diff = retail - sell; gap.bar(all_years, diff, color=np.where(diff >= 0, "#4a90d9", "#7fb519")); gap.axhline(0, color="black", lw=.8); gap.set(xlabel="Year", ylabel="Retail − selling\n[ct/kWh]"); gap.grid(alpha=.2)
    add_source_footer(fig, ["Visualization: EIFER", "Data: Bundesnetzagentur (retrieved 16.10.2026)"],
                      title="Household electricity price and PV selling tariff")
    targets.append(_save(fig, "selling-vs-consuming", "2010-2030"))

    # Merge the tariff and revenue information into one figure.  Revenue is
    # calculated from the published tariff anchors; no flat post-support line
    # or forecast is introduced.
    revenue_years = np.array(sorted(FIT))
    partial_tariff = np.array([FIT[y] for y in revenue_years])
    partial_revenue = np.array([_revenue(v) for v in partial_tariff])
    full_years = np.array(sorted(FULL))
    full_tariff = np.array([FULL[y] for y in full_years])
    full_revenue = np.array([_revenue(v) for v in full_tariff])

    fig, (tariff_ax, revenue_ax) = plt.subplots(2, 1, figsize=(10.5, 8), sharex=True, dpi=180)
    tariff_ax.plot(revenue_years, partial_tariff, "o-", color="#2a6f97", lw=2, label="Partial feed-in tariff")
    tariff_ax.plot(full_years, full_tariff, "s--", color="#d1495b", lw=2, label="Full feed-in tariff")
    tariff_ax.set_ylabel("Tariff (ct/kWh)")
    tariff_ax.grid(alpha=.3); tariff_ax.legend(fontsize=8)
    revenue_ax.plot(revenue_years, partial_revenue, "o-", color="#2a6f97", lw=2, label="Partial feed-in revenue")
    revenue_ax.plot(full_years, full_revenue, "s--", color="#d1495b", lw=2, label="Full feed-in revenue")
    revenue_ax.set_xlabel("Year"); revenue_ax.set_ylabel("Annual revenue (EUR/year)")
    revenue_ax.grid(alpha=.3); revenue_ax.legend(fontsize=8)
    add_source_footer(fig, ["Visualization: EIFER", "Data: Bundesnetzagentur (retrieved 16.10.2026)"],
                      title="Photovoltaic tariff anchors and corresponding annual revenue")
    targets.append(_save(fig, "revenue-over-time", "2010-2026"))
    return targets


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    targets = [electricity_mix(), installed_power(), *revenue_figures()]
    print("Updated external figure imports:")
    for target in targets:
        print(f"  {target}")


if __name__ == "__main__":
    main()
