"""Shared application constants."""

from app.metadata import APP_DATA_DIR_NAME, APP_EXECUTABLE_NAME, APP_NAME

BLOCK_TYPE_WORK = "work"
BLOCK_TYPE_BREAK = "break"
BLOCK_TYPE_COMPENSATION = "compensation"

WORK_REMARKS = [
    "Admin",
    "Projektleitung",
    "Meeting",
    "Fahrt",
    "Sys. AVOR",
    "Sys. Installation",
    "Sys. Rückbau",
    "Event Aufbau",
    "Event Abbau",
    "Event Betreuung",
]

BREAK_REMARKS = [
    "Mittag",
    "Pause",
]

COMPENSATION_REMARK = "Kompensation"
COMPENSATION_REMARKS = [COMPENSATION_REMARK]

REMARK_COLORS = {
    "Admin": "#8D99AE",
    "Projektleitung": "#3A86FF",
    "Meeting": "#6366F1",
    "Fahrt": "#4CC9A6",
    "Sys. AVOR": "#4361EE",
    "Sys. Installation": "#F4A261",
    "Sys. Rückbau": "#E76F51",
    "Event Aufbau": "#EC4899",
    "Event Abbau": "#F97316",
    "Event Betreuung": "#14B8A6",
    "Mittag": "#D62839",
    "Pause": "#9C6644",
    "Kompensation": "#2A9D8F",
}

WORK_COST_TYPES = {
    "Admin": "30.01",
    "Projektleitung": "30.02",
    "Meeting": "30.03",
    "Fahrt": "30.04",
    "Sys. AVOR": "30.08",
    "Sys. Installation": "30.09",
    "Sys. Rückbau": "30.10",
    "Event Aufbau": "30.11",
    "Event Abbau": "30.12",
    "Event Betreuung": "30.13",
}

SLOT_MINUTES = 15
TIMELINE_START_HOUR = 6
TIMELINE_END_HOUR = 18
MAX_FAVORITE_PROJECTS = 6

DEFAULT_COUNTDOWN_SECONDS = 3
DEFAULT_TYPING_INTERVAL = 0.12
TARGET_PRODUCTIVE_MINUTES_BY_WEEKDAY = {
    0: 8 * 60 + 30,
    1: 8 * 60 + 30,
    2: 8 * 60 + 30,
    3: 8 * 60 + 30,
    4: 8 * 60,
    5: 0,
    6: 0,
}

MESSERLI_MINUTE_SUFFIX = {
    0: "00",
    15: "25",
    30: "50",
    45: "75",
}
