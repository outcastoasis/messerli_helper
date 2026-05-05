from app.models.preferences import AppPreferences


def test_preferences_round_trip_preserves_tutorial_completed() -> None:
    preferences = AppPreferences(
        tutorial_completed=True,
        feature_tutorial_seen_version="1.0.3",
    )

    loaded = AppPreferences.from_dict(preferences.to_dict())

    assert loaded.tutorial_completed is True
    assert loaded.feature_tutorial_seen_version == "1.0.3"


def test_preferences_default_tutorial_completed_is_false() -> None:
    loaded = AppPreferences.from_dict({})

    assert loaded.tutorial_completed is False
    assert loaded.feature_tutorial_seen_version == ""
