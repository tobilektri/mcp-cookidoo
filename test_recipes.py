"""Tests for recipes.py (no network). Run with: pytest test_recipes.py"""

import datetime
from types import SimpleNamespace as NS

import pytest

from mcp_cookidoo.recipes import (
    format_catalog_recipe,
    format_custom_recipe,
    format_custom_recipes,
    format_search_result,
    format_week,
    is_custom_recipe_id,
    parse_day,
    split_recipe_ids,
    step_text,
)

TODAY = datetime.date(2026, 10, 20)


def test_recipe_id_kinds():
    assert is_custom_recipe_id("01M5A79NY53CEKEW6NKVYBFSTW")
    assert is_custom_recipe_id(" 01m5a79ny53cekew6nkvybfstw ")
    assert not is_custom_recipe_id("r59322")
    with pytest.raises(ValueError):
        is_custom_recipe_id("Curry")


def test_split_mixed_ids():
    catalog, custom = split_recipe_ids("r59322, 01m5a79ny53cekew6nkvybfstw;r1\nr2")
    assert catalog == ["r59322", "r1", "r2"]
    assert custom == ["01M5A79NY53CEKEW6NKVYBFSTW"]
    with pytest.raises(ValueError):
        split_recipe_ids(" , ")


def test_parse_day():
    assert parse_day("", TODAY) == TODAY
    assert parse_day("2026-10-22", TODAY) == datetime.date(2026, 10, 22)
    assert parse_day("22.10.2026", TODAY) == datetime.date(2026, 10, 22)
    assert parse_day("1.11.", TODAY) == datetime.date(2026, 11, 1)
    with pytest.raises(ValueError):
        parse_day("Mittwoch", TODAY)


def test_search_result_is_limited():
    hits = [NS(id=f"r{i}", name=f"Curry {i}", url=f"https://x/r{i}") for i in range(20)]
    text = format_search_result(NS(recipes=hits, total=20), limit=3)
    assert text.splitlines()[0] == "Recipes (page 0, showing 3 of 20):"
    assert "- Curry 0 (ID r0) https://x/r0" in text
    assert "Curry 3" not in text
    assert "page=1" in text
    last_page = format_search_result(NS(recipes=hits[:7], total=7), limit=10, page=3)
    assert "page=4" not in last_page
    assert format_search_result(NS(recipes=[], total=0), 5) == "No recipes found."


def test_custom_recipe_list():
    recipes = [NS(id="01ABC", name="Curry", tools=["TM6"], total_time=2100)]
    assert format_custom_recipes(recipes) == "Your own recipes (1):\n- Curry (ID 01ABC, TM6, 35 min)"
    assert format_custom_recipes([]) == "You have no own recipes yet."


def test_week_shows_planned_days_in_order():
    days = [
        # The week plan sends times as text.
        NS(id="2026-10-24", recipes=[NS(id="01ABC", name="Curry", is_custom=True, total_time="4500.0")]),
        NS(id="2026-10-21", recipes=[]),
        NS(id="2026-10-22", recipes=[NS(id="r762586", name="Udon", is_custom=False, total_time=0)]),
    ]
    assert format_week(days, TODAY).splitlines() == [
        "Planned recipes in the week from 2026-10-20:",
        "Thu 2026-10-22:",
        "  - Udon (ID r762586, Cookidoo)",
        "Sat 2026-10-24:",
        "  - Curry (ID 01ABC, own recipe, 1 h 15 min)",
    ]
    assert format_week([], TODAY) == "No recipes planned in the week from 2026-10-20."


def test_catalog_recipe_steps_without_html():
    recipe = NS(
        id="r1", name="Curry", url="https://x/r1", serving_size=4, active_time=600,
        total_time=2400, difficulty="easy", utensils=["Varoma"],
        ingredients=[
            NS(name="Reis", description="250 g", preparation=None),
            NS(name="Zwiebeln", description="100 g", preparation="halbiert"),
        ],
        step_groups=[NS(title="1", recipe_steps=[
            NS(formatted_text="Reis einwiegen und <nobr>20 Min./Varoma/Stufe 4</nobr> garen."),
            NS(formatted_text="Zugeben und <nobr>7 Min./100\xb0C//Stufe 1</nobr> garen."),
        ])],
        notes=["Tipp &amp; Trick"],
    )
    text = format_catalog_recipe(recipe)
    assert "  1. Reis einwiegen und 20 Min./Varoma/Stufe 4 garen." in text
    assert "  2. Zugeben und 7 Min./100°C/Linkslauf/Stufe 1 garen." in text
    assert "  - 250 g Reis" in text
    assert "  - 100 g Zwiebeln, halbiert" in text
    assert "  - Tipp & Trick" in text
    assert "Total time: 40 min" in text


def test_own_recipe_steps_use_upload_notation():
    assert step_text("Turbo /0.5 Sek.") == "Turbo/0.5 Sek."
    assert step_text("12 Min./100°C//Stufe  köcheln") == (
        "12 Min./100°C/Linkslauf/Sanftrührstufe köcheln"
    )
    recipe = NS(
        id="01ABC", name="Brot", url="https://x/01ABC", tools=["TM7"], serving_size=1,
        active_time=0, total_time=300, ingredients=["200 g Mehl"],
        instructions=[NS(text="Teig kneten /2 Min."), "Backen."], hints=[],
    )
    text = format_custom_recipe(recipe)
    assert "  1. Teig kneten/2 Min." in text
    assert "  2. Backen." in text
    assert "Device: TM7" in text
