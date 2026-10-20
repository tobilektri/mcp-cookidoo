"""
Helpers for finding recipes and planning the week.

Cookidoo has two kinds of recipes: catalogue recipes ("r59322") and the user's own
created recipes (ULIDs such as "01M5A79NY53CEKEW6NKVYBFSTW"). Several Cookidoo calls
differ between them (details, calendar, shopping list), so the tools sort IDs with
``is_custom_recipe_id`` first. The format functions turn cookidoo-api results into the
plain text the MCP tools return; they only read attributes, so they work with any
object of the same shape.
"""

from __future__ import annotations

import datetime
import html
import re
from collections.abc import Iterable

# Crockford base32 ULID (own recipes) and catalogue IDs ("r" + digits).
_CUSTOM_ID = re.compile(r"[0-9A-HJKMNP-TV-Z]{26}")
_CATALOG_ID = re.compile(r"r\d+")
_TAGS = re.compile(r"<[^>]+>")


def is_custom_recipe_id(recipe_id: str) -> bool:
    """True for an own (created) recipe, False for a catalogue recipe."""
    recipe_id = recipe_id.strip()
    if _CUSTOM_ID.fullmatch(recipe_id.upper()):
        return True
    if _CATALOG_ID.fullmatch(recipe_id):
        return False
    raise ValueError(
        f"'{recipe_id}' is not a Cookidoo recipe ID (catalogue IDs look like 'r59322', "
        "own recipes like '01M5A79NY53CEKEW6NKVYBFSTW')"
    )


def split_recipe_ids(text: str) -> tuple[list[str], list[str]]:
    """Split "r123, 01M5..." into (catalogue IDs, own recipe IDs)."""
    catalog: list[str] = []
    custom: list[str] = []
    for recipe_id in re.split(r"[\s,;]+", text.strip()):
        if not recipe_id:
            continue
        if is_custom_recipe_id(recipe_id):
            custom.append(recipe_id.upper())
        else:
            catalog.append(recipe_id)
    if not catalog and not custom:
        raise ValueError("No recipe ID given.")
    return catalog, custom


def parse_day(text: str, today: datetime.date | None = None) -> datetime.date:
    """Parse "2026-10-22", "22.10.2026" or "22.10."; empty means today."""
    today = today or datetime.date.today()
    text = text.strip()
    if not text:
        return today
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        pass
    match = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})?", text)
    if match:
        day, month, year = match.groups()
        return datetime.date(int(year) if year else today.year, int(month), int(day))
    raise ValueError(f"'{text}' is not a date; use YYYY-MM-DD, e.g. {today.isoformat()}")


def _minutes(seconds) -> str:
    try:
        seconds = float(seconds or 0)  # the week plan sends "1200.0"
    except ValueError:
        return ""
    if not seconds:
        return ""
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60} h {minutes % 60} min" if minutes % 60 else f"{minutes // 60} h"


def plain_text(text: str) -> str:
    """Cookidoo step texts contain HTML (<nobr>, <strong>); return readable text."""
    return html.unescape(_TAGS.sub("", text or "")).strip()


def step_text(text: str) -> str:
    """
    Own recipe steps carry icon glyphs ("Turbo \\ue00b/1 Sek.", "\\ue003" for reverse).
    Write them the way the upload tools accept them ("Turbo/1 Sek.", "Linkslauf"), so a
    step can be copied into update_custom_recipe_steps.
    """
    text = text.replace("Stufe \ue002", "Sanftrührstufe").replace("\ue003", "Linkslauf")
    return re.sub(r"\s?[\ue000-\uf8ff]", "", plain_text(text))


# Cookidoo returns at most this many results per page.
SEARCH_PAGE_SIZE = 20


def format_search_result(result, limit: int, page: int = 0) -> str:
    found = list(result.recipes)
    hits = found[:limit]
    if not hits:
        return "No recipes found." if page == 0 else f"No more recipes on page {page}."
    lines = [f"Recipes (page {page}, showing {len(hits)} of {len(found)}):"]
    lines += [f"- {hit.name} (ID {hit.id}) {hit.url}" for hit in hits]
    if len(found) >= SEARCH_PAGE_SIZE:
        lines.append(f"More results: search again with page={page + 1}.")
    lines.append("Use get_recipe_details with an ID to see ingredients and steps.")
    return "\n".join(lines)


def format_custom_recipes(recipes: Iterable) -> str:
    recipes = list(recipes)
    if not recipes:
        return "You have no own recipes yet."
    lines = [f"Your own recipes ({len(recipes)}):"]
    for recipe in recipes:
        details = ", ".join(
            part for part in (", ".join(recipe.tools or []), _minutes(recipe.total_time)) if part
        )
        lines.append(f"- {recipe.name} (ID {recipe.id}{', ' + details if details else ''})")
    return "\n".join(lines)


def format_week(days: Iterable, start: datetime.date) -> str:
    days = [day for day in days if day.recipes]
    if not days:
        return f"No recipes planned in the week from {start.isoformat()}."
    lines = [f"Planned recipes in the week from {start.isoformat()}:"]
    for day in sorted(days, key=lambda d: d.id):
        lines.append(f"{_weekday(day.id)} {day.id}:")
        for recipe in day.recipes:
            kind = "own recipe" if recipe.is_custom else "Cookidoo"
            time = _minutes(recipe.total_time)
            lines.append(
                f"  - {recipe.name} (ID {recipe.id}, {kind}{', ' + time if time else ''})"
            )
    return "\n".join(lines)


_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _weekday(day_id: str) -> str:
    try:
        return _WEEKDAYS[datetime.date.fromisoformat(day_id).weekday()]
    except ValueError:
        return ""


def format_catalog_recipe(recipe) -> str:
    lines = [f"{recipe.name} (ID {recipe.id})", recipe.url, ""]
    facts = [
        f"Servings: {recipe.serving_size}" if recipe.serving_size else "",
        f"Active time: {_minutes(recipe.active_time)}" if recipe.active_time else "",
        f"Total time: {_minutes(recipe.total_time)}" if recipe.total_time else "",
        f"Difficulty: {recipe.difficulty}" if recipe.difficulty else "",
    ]
    lines += [fact for fact in facts if fact]
    if recipe.utensils:
        lines.append(f"Utensils: {', '.join(recipe.utensils)}")
    lines += ["", "Ingredients:"]
    for ingredient in recipe.ingredients:
        line = " ".join(p for p in (plain_text(ingredient.description), ingredient.name) if p)
        if ingredient.preparation:
            line += f", {plain_text(ingredient.preparation)}"
        lines.append(f"  - {line}")
    lines += ["", "Steps:"]
    number = 0
    for group in recipe.step_groups:
        if group.title and len(recipe.step_groups) > 1:
            lines.append(f"  {plain_text(group.title)}")
        for step in group.recipe_steps:
            number += 1
            lines.append(f"  {number}. {step_text(step.formatted_text)}")
    if recipe.notes:
        lines += ["", "Hints:"] + [f"  - {plain_text(note)}" for note in recipe.notes]
    return "\n".join(lines)


def format_custom_recipe(recipe) -> str:
    lines = [f"{recipe.name} (ID {recipe.id}, own recipe)", recipe.url, ""]
    facts = [
        f"Device: {', '.join(recipe.tools)}" if recipe.tools else "",
        f"Servings: {recipe.serving_size}" if recipe.serving_size else "",
        f"Active time: {_minutes(recipe.active_time)}" if recipe.active_time else "",
        f"Total time: {_minutes(recipe.total_time)}" if recipe.total_time else "",
    ]
    lines += [fact for fact in facts if fact]
    lines += ["", "Ingredients:"] + [f"  - {line}" for line in recipe.ingredients]
    lines += ["", "Steps:"]
    for number, instruction in enumerate(recipe.instructions, 1):
        text = instruction if isinstance(instruction, str) else instruction.text
        lines.append(f"  {number}. {step_text(text)}")
    if recipe.hints:
        lines += ["", "Hints:"] + [f"  - {hint}" for hint in recipe.hints]
    return "\n".join(lines)
