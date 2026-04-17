from app.utils.time_utils import format_duration_minutes, format_messerli_time


def test_format_messerli_time_examples() -> None:
    assert format_messerli_time("06:00") == "06.00"
    assert format_messerli_time("06:15") == "06.25"
    assert format_messerli_time("06:30") == "06.50"
    assert format_messerli_time("06:45") == "06.75"
    assert format_messerli_time("10:00") == "10.00"


def test_format_duration_minutes_examples() -> None:
    assert format_duration_minutes(0) == "0:00"
    assert format_duration_minutes(510) == "8:30"
    assert format_duration_minutes(-30) == "-0:30"
    assert format_duration_minutes(45, include_sign=True) == "+0:45"
