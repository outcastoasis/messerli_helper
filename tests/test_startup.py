from app.startup import build_single_instance_key


def test_build_single_instance_key_sanitizes_invalid_characters() -> None:
    key = build_single_instance_key("Jascha Bucher/Messerli Helper")

    assert key == "Jascha-Bucher-Messerli-Helper-single-instance"


def test_build_single_instance_key_uses_fallback_for_empty_values() -> None:
    key = build_single_instance_key("   ")

    assert key == "messerli-helper-single-instance"
