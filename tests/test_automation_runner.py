import ctypes

from app.automation.runner import Input, _requires_unicode_input, _utf16_code_units


def test_ascii_text_can_be_typed_directly() -> None:
    assert _requires_unicode_input("Individuelle Abklaerung") is False


def test_umlaut_text_uses_unicode_input() -> None:
    assert _requires_unicode_input("Individuelle Abklärung") is True


def test_unicode_input_uses_utf16_code_units() -> None:
    assert _utf16_code_units("ä") == [0x00E4]


def test_windows_input_structure_has_native_size() -> None:
    expected_size = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
    assert ctypes.sizeof(Input) == expected_size
