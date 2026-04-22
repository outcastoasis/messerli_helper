from app.models.preferences import AppPreferences


def test_preferences_round_trip_preserves_tutorial_completed() -> None:
    preferences = AppPreferences(tutorial_completed=True)

    loaded = AppPreferences.from_dict(preferences.to_dict())

    assert loaded.tutorial_completed is True


def test_preferences_default_tutorial_completed_is_false() -> None:
    loaded = AppPreferences.from_dict({})

    assert loaded.tutorial_completed is False
