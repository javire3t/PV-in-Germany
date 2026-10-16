"""Figure settings: the one file to edit for everyday changes.

Change a value here, then run `poetry run python main.py all-figures`
(or a single figure task) to regenerate the figures.

States use their English names (e.g. "Bavaria", "Thuringia"); districts use
their exact name in the workbook's District column (e.g. "Burgenlandkreis").
"""

# ---------------------------------------------------------------- comparisons

# Two federal states shown in the static capacity and density comparison.
# Set to None to pick the highest- and lowest-density states automatically
# (city states included, so this usually gives Berlin and Bremen).
STATES_TO_COMPARE = ["Saxony-Anhalt", "Thuringia"]

# Two districts shown in the static capacity and density comparison.
DISTRICTS_TO_COMPARE = ["Saale-Holzland-Kreis", "Burgenlandkreis"]

# Further state pairs that get only a static map comparison.
EXTRA_STATE_COMPARISONS = [
    ["Bavaria", "Baden-Württemberg"],
]


# ---------------------------------------------------------------- years

# First year of the historical series (the workbook starts in 1999).
FIRST_YEAR = 1999

# The national map animation starts later because Germany is almost blank
# at the start; 1999 adds an empty frame.
GERMANY_ANIMATION_FIRST_YEAR = 2000

# The last year is always the latest year in the workbook.

# ---------------------------------------------------------------- maps

# Fixed top of the green national density scale, in kWp/km².
# Districts above it use the darkest colour but keep their printed value.
GERMANY_DENSITY_SCALE_MAX = 780.0

# States (and optional single districts) drawn by the `district-maps` task.
DISTRICT_MAP_STATES = ["Thuringia"]
DISTRICT_MAP_DISTRICTS = []

# ---------------------------------------------------------------- scatter charts

# True leaves Berlin, Hamburg and Bremen out of the capacity-density scatter.
EXCLUDE_CITY_STATES = False

# True draws the capacity-density scatter with both axes logarithmic.
USE_LOG_LOG_FOR_CAPACITY_DENSITY = False
