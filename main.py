"""Single entry point: update data, make figures, run checks.

    poetry run python main.py                 numbered menu
    poetry run python main.py all-figures     regenerate every finished figure
    poetry run python main.py <task> --help   options of one task

What the figures compare is set in settings.py.
"""
import importlib
import runpy
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
# All project code lives in code/.
sys.path.insert(0, str(ROOT / "code"))


def run(module, *args, function="main"):
    """Run one script's entry point as if called from the command line."""
    saved = sys.argv
    sys.argv = [module, *args]
    try:
        getattr(importlib.import_module(module), function)()
    finally:
        sys.argv = saved


def run_script(path, *args):
    """Run a script that has no main() function."""
    saved = sys.argv
    sys.argv = [str(path), *args]
    try:
        runpy.run_path(str(ROOT / path), run_name="__main__")
    finally:
        sys.argv = saved


def pair_comparisons(*args):
    from project_paths import settings
    states = settings.STATES_TO_COMPARE
    for pair in ([states] if states else []) + settings.EXTRA_STATE_COMPARISONS:
        run("figures.shared.comparison", "--states", *pair, *args)
    run("figures.shared.comparison", "--districts", *settings.DISTRICTS_TO_COMPARE, *args)


def region_comparisons(*args):
    for groups in ("east-west", "south-north"):
        run("figures.shared.comparison", "--groups", groups, *args)


FIGURE_TASKS = ["germany-animation", "germany-labeled-map", "nep-b-maps", "mastr-additions", "eeg-exit", "redispatch-maps", "redispatch-official",
                "redispatch-history", "regions-nep", "region-definition-maps", "region-comparisons", "state-charts", "pair-comparisons", "external-figures"]


def all_figures(*args):
    times = {}
    for name in FIGURE_TASKS:
        print(f"\n=== {name} ===", flush=True)
        start = time.perf_counter()
        TASKS[name][2](*args)
        times[name] = time.perf_counter() - start
    print("\nTime per task:")
    for name, seconds in times.items():
        print(f"  {name:22} {seconds:6.0f} s")
    print(f"  {'total':22} {sum(times.values()):6.0f} s")


# name: (group, description, function receiving the extra command-line arguments)
TASKS = {
    # 1. Update data
    "update-data": ("Update data", "Download the latest Energy-Charts maps and rebuild the main workbook",
                    lambda *a: run("data_preparation.download_energy_charts", *a, function="cli")),
    "mastr-download": ("Update data", "Download the solar tables of the official MaStR export (about 1.1 GB)",
                       lambda *a: run("data_preparation.download_mastr", *a)),
    "mastr-prepare": ("Update data", "Aggregate MaStR solar units by district",
                      lambda *a: run("data_preparation.prepare_mastr", *a)),
    "mastr-annual": ("Update data", "Build MaStR annual commissioning by power band and use",
                     lambda *a: run("data_preparation.prepare_mastr_annual", *a)),
    "mastr-eeg-exit": ("Update data", "Count MaStR units and capacity leaving EEG payments per year",
                       lambda *a: run("data_preparation.prepare_eeg_exit", *a)),
    "redispatch-data": ("Update data", "Read 2021 curtailment (BNetzA) and the 2025 redispatch map (enervis)",
                        lambda *a: run("data_preparation.read_redispatch", *a)),
    "excel-workbooks": ("Update data", "Write and verify the MaStR and NEP Excel workbooks",
                        lambda *a: run("data_preparation.excel_workbooks", *a)),
    "boundaries": ("Update data", "Convert the downloaded BKG boundary files to GeoJSON",
                   lambda *a: run("data_preparation.prepare_boundaries", *a)),
    "nep-tables": ("Update data", "Extract the NEP A/B/C state tables from the NEP PDF",
                   lambda *a: run("data_preparation.read_nep_scenarios", *a)),
    "nep-extract": ("Update data", "Estimate NEP B district values from the NEP map colours",
                    lambda *a: run("data_preparation.estimate_nep_districts", *a)),
    # 2. Figures
    "all-figures": ("Figures", "Regenerate every finished figure in results/figures/", all_figures),
    "germany-animation": ("Figures", "national density animation (GIF)",
                          lambda *a: run("figures.germany.animation", *a)),
    "germany-labeled-map": ("Figures", "national density map with district values",
                            lambda *a: run("figures.germany.labeled_map", *a)),
    "nep-b-maps": ("Figures", "NEP scenario B rooftop and ground-mounted maps",
                   lambda *a: run("figures.germany.nep_b_maps", *a)),
    "mastr-additions": ("Figures", "annual PV additions by unit size from MaStR (2000-2025)",
                        lambda *a: run("figures.germany.mastr_additions", *a)),
    "eeg-exit": ("Figures", "units and capacity leaving EEG payments, cumulative by year",
                 lambda *a: run("figures.germany.eeg_exit", *a)),
    "redispatch-maps": ("Figures", "curtailment 2021 by state next to redispatch 2025 by district",
                        lambda *a: run("figures.germany.redispatch_maps", *a)),
    "redispatch-official": ("Figures", "official SMARD state reductions and wind/solar totals, 2023-2025",
                            lambda *a: run("figures.germany.redispatch_official", *a)),
    "redispatch-history": ("Figures", "historical BNetzA renewable and CHP curtailment, 2016-2021",
                           lambda *a: run("data_preparation.read_redispatch_history", *a)),
    "redispatch-excel": ("Data outputs", "export redispatch sources, common coverage and map data to Excel",
                         lambda *a: run("data_preparation.redispatch_excel.prepare", "--export", *a)),
    "regions-nep": ("Figures", "East/West and North/South history with NEP A/B/C",
                    lambda *a: run("figures.regions.nep_scenarios", *a)),
    "region-definition-maps": ("Figures", "Maps of the project's East/West and North/South state definitions",
                               lambda *a: run("figures.regions.definition_maps", *a)),
    "region-comparisons": ("Figures", "Regional historical capacity and latest density maps", region_comparisons),
    "state-charts": ("Figures", "State capacity-versus-density scatter diagrams",
                     lambda *a: run("figures.states.charts", *a)),
    "pair-comparisons": ("Figures", "Static state and district capacity/density comparisons", pair_comparisons),
    "external-figures": ("Figures", "Imported electricity mix, installed power and feed-in revenue figures",
                         lambda *a: run("figures.germany.external_figures", *a)),
    "district-maps": ("Figures", "annual district maps of selected states (to data/work/)",
                      lambda *a: run("figures.districts.maps", *a)),
    # 3. Checks
    "tests": ("Checks", "Run the automated tests",
              lambda *a: sys.exit(__import__("pytest").main(
                  ["-q", "-c", str(ROOT / "pyproject.toml"), str(ROOT / "code/tests"), *a]))),
    "mastr-compare": ("Checks", "Compare MaStR with Energy-Charts by district and state",
                      lambda *a: run("data_preparation.compare_mastr_energy_charts", *a)),
    "mastr-report": ("Checks", "Write the MaStR reconciliation report (validation/)",
                     lambda *a: run_script("code/validation/mastr_report.py", *a)),
    "crop-figures": ("Checks", "Crop the finished figures to their content again",
                     lambda *a: run("figures.shared.crop_exports", *a)),
}


def choose():
    """Numbered menu grouped by purpose."""
    names, group = list(TASKS), None
    for number, name in enumerate(names, 1):
        if TASKS[name][0] != group:
            group = TASKS[name][0]
            print(f"\n{group}")
        print(f"  {number:2}. {name:22} {TASKS[name][1]}")
    try:
        number = int(input("\nTask number: "))
        if not 1 <= number <= len(names):
            raise ValueError
    except (ValueError, EOFError):
        sys.exit("Select a number from the list.")
    return names[number - 1]


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        for name, (group, description, _) in TASKS.items():
            print(f"  {name:22} {description}")
        return
    if len(sys.argv) > 1 and sys.argv[1] not in TASKS:
        sys.exit(f"Unknown task {sys.argv[1]!r}. Run without arguments for the menu, or with --help.")
    task = sys.argv[1] if len(sys.argv) > 1 else choose()
    TASKS[task][2](*sys.argv[2:])


if __name__ == "__main__":
    main()
