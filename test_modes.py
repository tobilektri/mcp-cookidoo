"""Tests for modes.py and the mode support in thermomix.py. Run with: pytest test_modes.py"""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from modes import BUILTIN_CATALOG, device_from_tools, parse_editor_html
from thermomix import build_instruction, check_steps, describe_instructions

FIXTURES = Path(__file__).parent / "fixtures"


def _html(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# --- Catalog from the editor page --------------------------------------------------


@pytest.mark.parametrize("page", ["editor_tm6.html", "editor_tm7.html"])
def test_editor_page_gives_the_builtin_catalog(page):
    # The built-in list is a snapshot of exactly these pages.
    catalog = parse_editor_html(_html(page))
    assert catalog.source == "cookidoo"
    assert replace(catalog, source="builtin") == BUILTIN_CATALOG


def test_catalog_marks_tm7_only_modes():
    catalog = parse_editor_html(_html("editor_tm6.html"))
    assert catalog.tm7_only == {"browning", "steaming"}
    assert catalog.modes["rice_cooker"] == "Reis kochen"
    assert catalog.accessories["SimmeringBasket"] == "im Gareinsatz"
    assert catalog.browning_powers == {"Gentle": "Leicht", "Intense": "Intensiv"}


def test_page_without_modes_is_rejected():
    with pytest.raises(ValueError):
        parse_editor_html("<html><body>Bitte anmelden</body></html>")


def test_available_modes_per_device():
    assert set(BUILTIN_CATALOG.available_modes("TM6")) == {
        "dough", "turbo", "blend", "warm_up", "rice_cooker"
    }
    assert set(BUILTIN_CATALOG.available_modes("TM7")) == {
        "dough", "turbo", "blend", "warm_up", "rice_cooker", "steaming", "browning"
    }
    assert "varoma" in BUILTIN_CATALOG.tts_temperatures("TM6")
    assert "varoma" not in BUILTIN_CATALOG.tts_temperatures("TM7")
    assert "160" not in BUILTIN_CATALOG.tts_temperatures("TM6")


def test_device_from_recipe_tools():
    assert device_from_tools(["TM6"]) == "TM6"
    assert device_from_tools(["TM6", "TM7"]) == "TM7"
    assert device_from_tools(None) == "TM6"


# --- Ground truth: what the Cookidoo editor dialog produced -------------------------

CASES = json.loads((FIXTURES / "editor_modes.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["input"] for c in CASES])
def test_modes_reproduce_editor_output_exactly(case):
    assert build_instruction(case["input"], device=case["device"]) == case["expected"]
    assert check_steps([case["input"]], device=case["device"]) == []


@pytest.mark.parametrize("case", CASES, ids=[c["input"] for c in CASES])
def test_live_catalog_gives_the_same_result(case):
    catalog = parse_editor_html(_html(f"editor_{case['device'].lower()}.html"))
    result = build_instruction(case["input"], catalog=catalog, device=case["device"])
    assert result == case["expected"]


# --- Spellings ----------------------------------------------------------------------


def test_aliases_and_half_second_turbo():
    assert build_instruction("Teigstufe/3 Min.")["annotations"][0]["data"] == {"time": 180}
    turbo = build_instruction("Turbo/0,5 Sek.")
    assert turbo["text"] == "Turbo /0.5 Sek."
    assert turbo["annotations"][0]["data"] == {"time": 0.5}


def test_editor_text_with_glyph_is_accepted_again():
    text = "Teig kneten /2 Min. fertig."
    assert build_instruction(text)["text"] == text
    assert build_instruction(text)["annotations"][0]["name"] == "dough"


def test_varoma_as_steaming_accessory():
    instruction = build_instruction("Dampfgaren/20 Min./Stufe 1/Varoma", device="TM7")
    assert instruction["annotations"][0]["data"]["accessory"] == "Varoma"


def test_mode_defaults():
    steaming = build_instruction("Dampfgaren/20 Min./Stufe 1", device="TM7")
    assert steaming["annotations"][0]["data"]["accessory"] == "Varoma"
    browning = build_instruction("Anbraten/155°C", device="TM7")
    assert browning["annotations"][0]["data"] == {
        "time": 600, "temperature": {"value": "155", "unit": "C"}, "power": "Gentle"
    }
    warm_up = build_instruction("Erwärmen/60°C")
    assert warm_up["annotations"][0]["data"]["speed"] == "soft"


def test_bare_titles_in_prose_stay_text():
    for text in ("Den Reis kochen lassen.", "Reis kochen", "Turbo ist zu stark."):
        assert "annotations" not in build_instruction(text)


def test_mode_and_setting_in_one_step():
    instruction = build_instruction("Turbo/1 Sek. zerkleinern, dann 3 Min./100°C/Stufe 2 kochen.")
    kinds = [a["type"] for a in instruction["annotations"]]
    assert kinds == ["MODE", "TTS"]


# --- Validation ---------------------------------------------------------------------

INVALID = [
    ("TM6", "Turbo/3 Sek.", "Turbo time"),
    ("TM6", "Turbo/1 Sek./3x", "only available for the TM7"),
    ("TM6", "Pürieren/1 Min./Stufe 10", "speed must be"),
    ("TM6", "Pürieren/5 Sek./Stufe 8", "time must be"),
    ("TM6", "Teig kneten/30 Min.", "time must be"),
    ("TM6", "Teig kneten/2 Min./Stufe 3", "takes no speed"),
    ("TM6", "Erwärmen/100°C", "temperature must be"),
    ("TM6", "Dampfgaren/20 Min./Stufe 1", "not available for the TM6"),
    ("TM6", "Anbraten/160°C", "not available for the TM6"),
    ("TM7", "Anbraten/120°C", "temperature must be"),
    ("TM7", "20 Min./Varoma/Stufe 1", "not available for the TM7"),
    ("TM6", "1 Min./42°C/Stufe 1", "not a Thermomix temperature"),
    ("TM6", "1 Min./100°C/Stufe 8", "only possible up to speed 6"),
    ("TM6", "Pürieren/1 Min.", "needs speed"),
]


@pytest.mark.parametrize("device,text,reason", INVALID)
def test_invalid_modes_stay_text_with_a_reason(device, text, reason):
    assert "annotations" not in build_instruction(text, device=device)
    warnings = check_steps([text], device=device)
    assert len(warnings) == 1 and reason in warnings[0]


def test_time_off_the_editor_grid_is_built_but_warned():
    instruction = build_instruction("7 Min. 15 Sek./100°C/Stufe 1")
    assert instruction["annotations"][0]["data"]["time"] == 435
    assert "time grid" in check_steps(["7 Min. 15 Sek./100°C/Stufe 1"])[0]


def test_removed_mode_is_not_built():
    catalog = replace(
        BUILTIN_CATALOG,
        modes={k: v for k, v in BUILTIN_CATALOG.modes.items() if k != "turbo"},
    )
    assert "annotations" not in build_instruction("Turbo/1 Sek.", catalog=catalog)


def test_new_unknown_mode_is_reported_as_unsupported():
    catalog = replace(BUILTIN_CATALOG, modes={**BUILTIN_CATALOG.modes, "sous_vide": "Sous-vide"})
    assert catalog.unsupported_modes() == {"sous_vide": "Sous-vide"}
    assert "sous_vide" not in catalog.available_modes("TM7")


def test_renamed_mode_follows_the_catalog():
    catalog = replace(BUILTIN_CATALOG, modes={**BUILTIN_CATALOG.modes, "dough": "Kneten Plus"})
    instruction = build_instruction("Kneten Plus/2 Min.", catalog=catalog)
    assert instruction["text"] == "Kneten Plus /2 Min."


def test_describe_reports_modes():
    lines = describe_instructions(
        [build_instruction("Nüsse Turbo/1 Sek./3x", device="TM7"), build_instruction("[Reis kochen]")]
    )
    assert lines == ["Step 1: Turbo/1 Sek./3x", "Step 2: Reis kochen"]
