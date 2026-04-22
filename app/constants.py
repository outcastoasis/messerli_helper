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
    "Admin": "#A3B2C6",
    "Projektleitung": "#6F89AD",
    "Meeting": "#486583",
    "Fahrt": "#2FAF98",
    "Sys. AVOR": "#8CB2E3",
    "Sys. Installation": "#5C8FD5",
    "Sys. Rückbau": "#2F63AC",
    "Event Aufbau": "#E38DAA",
    "Event Abbau": "#D76088",
    "Event Betreuung": "#B93D68",
    "Mittag": "#D62839",
    "Pause": "#9C6644",
    "Kompensation": "#2A9D8F",
}

PROJECT_BADGE_COLORS = [
    "#BFDBFE",
    "#BBF7D0",
    "#FDE68A",
    "#FBCFE8",
    "#C4B5FD",
    "#A5F3FC",
    "#FDBA74",
    "#FECACA",
]

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
TIMELINE_START_HOUR = 0
TIMELINE_END_HOUR = 24
TIMELINE_PRIMARY_START_HOUR = 6
TIMELINE_PRIMARY_END_HOUR = 18
TIMELINE_DEFAULT_VISIBLE_HOUR = 6
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
