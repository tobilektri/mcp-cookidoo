"""
Cookidoo step annotations: Thermomix settings and ingredient links.

Cookidoo only starts guided cooking (automatic time/temperature/speed) for a step
when the step carries a ``TTS`` annotation, and only shows an ingredient as a link
when the step carries an ``INGREDIENT`` annotation. Plain text is just text. This
module builds exactly the structure the Cookidoo editor itself sends, verified
against the editor output of a real recipe (see test_thermomix.py):

    {
        "type": "STEP",
        "text": "... 12 Min./100°C/\\ue003/Stufe \\ue002 köcheln lassen.",
        "annotations": [
            {"type": "INGREDIENT", "data": {"description": "1 Zwiebel"},
             "position": {"offset": 20, "length": 9}},
            {"type": "TTS",
             "data": {"speed": "soft", "direction": "CCW", "time": 720,
                      "temperature": {"value": "100", "unit": "C"}},
             "position": {"offset": 219, "length": 23}}
        ]
    }

Thermomix settings, written in German as printed in Cookidoo recipes:

    4 Sek./Stufe 5
    3 Min./120°C/Stufe 1
    1 Min. 30 Sek./90°C/Stufe 2
    15 Min./100°C/Linkslauf/Stufe 1      (counter-clockwise, "reverse")
    12 Min./100°C/Linkslauf/Sanftrührstufe
    10 Sek./Stufe 0,5

Not supported (left as plain text, no annotation): Varoma, Teigmodus, Turbo, Anbraten,
Warmhalten, Fahrenheit.

Ingredient links: a step links an ingredient when the step text contains the
ingredient line from the ingredient list verbatim (e.g. the list has "1 Zwiebel" and
the step says "1 Zwiebel und 1 Knoblauchzehe in den Mixtopf geben").
"""

from __future__ import annotations

import re
from collections.abc import Iterable

# Private-use glyphs of the Cookidoo icon font, written between the slashes of a setting.
REVERSE_GLYPH = ""  # counter-clockwise
SOFT_GLYPH = ""  # soft stir ("Sanftrührstufe")

# The Cookidoo editor replaces ";" in all texts by this full-width semicolon.
_SEMICOLON = "；"

_TIME = (
    r"(?:(?P<min>\d{1,3})\s*Min\.?(?:\s*(?P<sec>\d{1,2})\s*Sek\.?)?"
    r"|(?P<sec_only>\d{1,4})\s*Sek\.?)"
)
_TEMP = r"(?P<temp>\d{2,3})\s*°\s*C"
_REVERSE = rf"(?P<rev>Linkslauf|{REVERSE_GLYPH}|↺)"
_SPEED = (
    r"(?:Stufe\s*(?P<speed>\d{1,2}(?:[.,]5)?)"
    rf"|(?P<soft>Stufe\s*{SOFT_GLYPH}|Stufe\s+Sanftrühren|Sanftrührstufe))"
)

_TTS_RE = re.compile(
    rf"{_TIME}\s*/\s*(?:{_TEMP}\s*/\s*)?(?:{_REVERSE}?\s*/\s*)?{_SPEED}"
)

# Hints for settings that look like Thermomix instructions but were not recognised.
_UNPARSED_HINT_RE = re.compile(
    r"Stufe\s*\d|Linkslauf|Sanftr|Varoma|Teigmodus", re.IGNORECASE
)

_VALID_SPEEDS = {"0.5"} | {str(n) for n in range(1, 11)}
_MIN_TEMP, _MAX_TEMP = 37, 160


def normalize_text(text: str) -> str:
    """Apply the same text normalisation as the Cookidoo editor (";" -> full-width)."""
    return text.replace(";", _SEMICOLON)


def _u16len(text: str) -> int:
    """Length in UTF-16 code units (what JavaScript/the Cookidoo editor counts)."""
    return len(text.encode("utf-16-le")) // 2


def _format_time(seconds: int) -> str:
    minutes, secs = divmod(seconds, 60)
    parts = []
    if minutes:
        parts.append(f"{minutes} Min.")
    if secs:
        parts.append(f"{secs} Sek.")
    return " ".join(parts)


def _annotation_from_match(match: re.Match) -> tuple[str, dict] | None:
    """Return (canonical text, annotation data) for a regex match, or None if invalid."""
    if match.group("sec_only") is not None:
        seconds = int(match.group("sec_only"))
    else:
        seconds = int(match.group("min")) * 60 + int(match.group("sec") or 0)
    if seconds <= 0:
        return None

    soft = match.group("soft") is not None
    speed = "soft" if soft else match.group("speed").replace(",", ".")
    if not soft and speed not in _VALID_SPEEDS:
        return None

    temperature = match.group("temp")
    if temperature is not None and not _MIN_TEMP <= int(temperature) <= _MAX_TEMP:
        return None

    reverse = bool(match.group("rev"))

    data: dict = {"speed": speed, "time": seconds}
    if reverse:
        data["direction"] = "CCW"
    if temperature is not None:
        data["temperature"] = {"value": str(int(temperature)), "unit": "C"}

    segments = [_format_time(seconds)]
    if temperature is not None:
        segments.append(f"{int(temperature)}°C")
    if reverse:
        segments.append(REVERSE_GLYPH)
    segments.append(f"Stufe {SOFT_GLYPH}" if soft else "Stufe " + speed.replace(".", ","))
    return "/".join(segments), data


def _is_standalone(text: str, start: int, end: int) -> bool:
    """True if text[start:end] is not part of a longer word or number."""
    inner = text[start:end]
    if start > 0 and inner[0].isalnum() and text[start - 1].isalnum():
        return False
    if end < len(text) and inner[-1].isalnum() and text[end].isalnum():
        return False
    return True


def _ingredient_spans(
    text: str, ingredients: list[str], occupied: list[tuple[int, int]]
) -> list[tuple[int, int, str, dict]]:
    """Find verbatim ingredient lines in a step text. Longer ingredients win overlaps."""
    spans: list[tuple[int, int, str, dict]] = []
    taken = list(occupied)
    for ingredient in sorted(set(ingredients), key=len, reverse=True):
        position = 0
        while (start := text.find(ingredient, position)) != -1:
            end = start + len(ingredient)
            position = start + 1
            if not _is_standalone(text, start, end):
                continue
            if any(start < taken_end and end > taken_start for taken_start, taken_end in taken):
                continue
            taken.append((start, end))
            spans.append((start, end, "INGREDIENT", {"description": ingredient}))
            position = end
    return spans


def build_instruction(text: str, ingredients: Iterable[str] = ()) -> dict:
    """
    Turn one step text into a Cookidoo instruction object.

    Every recognised Thermomix setting is rewritten to Cookidoo's canonical text and
    gets a TTS annotation; every ingredient line that appears verbatim in the step
    gets an INGREDIENT annotation. Annotations are ordered by position. Steps without
    any of these are returned as plain ``{"type": "STEP", "text": ...}``.
    """
    text = normalize_text(text)
    ingredient_lines = [normalize_text(i).strip() for i in ingredients if i and i.strip()]

    pieces: list[str] = []
    spans: list[tuple[int, int, str, dict]] = []
    last_end = 0

    for match in _TTS_RE.finditer(text):
        built = _annotation_from_match(match)
        if built is None:
            continue
        canonical, data = built
        pieces.append(text[last_end : match.start()])
        start = len("".join(pieces))
        pieces.append(canonical)
        spans.append((start, start + len(canonical), "TTS", data))
        last_end = match.end()
    pieces.append(text[last_end:])
    final_text = "".join(pieces)

    spans += _ingredient_spans(
        final_text, ingredient_lines, [(start, end) for start, end, _, _ in spans]
    )
    spans.sort(key=lambda span: span[0])

    instruction: dict = {"type": "STEP", "text": final_text}
    if spans:
        instruction["annotations"] = [
            {
                "type": kind,
                "data": data,
                "position": {
                    "offset": _u16len(final_text[:start]),
                    "length": _u16len(final_text[start:end]),
                },
            }
            for start, end, kind, data in spans
        ]
    return instruction


def build_instructions(steps: list[str], ingredients: Iterable[str] = ()) -> list[dict]:
    """Build instruction objects for all steps."""
    ingredient_lines = list(ingredients)
    return [build_instruction(step, ingredient_lines) for step in steps]


def _describe_setting(data: dict) -> str:
    temp = data.get("temperature")
    speed = "Sanftrührstufe" if data["speed"] == "soft" else f"Stufe {data['speed']}"
    parts = [_format_time(data["time"])]
    if temp:
        parts.append(f"{temp['value']}°C")
    if data.get("direction") == "CCW":
        parts.append("Linkslauf")
    parts.append(speed)
    return "/".join(parts)


def describe_instructions(
    instructions: list[dict], ingredients: Iterable[str] = ()
) -> list[str]:
    """
    Human-readable report: Thermomix settings and ingredient links per step, warnings
    for settings that were not recognised, and ingredients that no step links.
    """
    lines: list[str] = []
    linked: set[str] = set()
    for number, instruction in enumerate(instructions, 1):
        remainder = instruction["text"]
        step_links: list[str] = []
        annotations = instruction.get("annotations", [])
        for annotation in sorted(
            annotations, key=lambda a: a["position"]["offset"], reverse=True
        ):
            position = annotation["position"]
            start = position["offset"]
            remainder = remainder[:start] + remainder[start + position["length"] :]
            if annotation["type"] == "TTS":
                lines.append(f"Step {number}: {_describe_setting(annotation['data'])}")
            else:
                description = annotation["data"]["description"]
                linked.add(description)
                step_links.append(description)
        if step_links:
            lines.append(f"Step {number}: links {len(step_links)} ingredient(s)")
        if _UNPARSED_HINT_RE.search(remainder):
            lines.append(
                f"Step {number}: WARNING - mentions speed/direction/Varoma, but no setting "
                f"was recognised (use e.g. '3 Min./120°C/Stufe 1'): {instruction['text'][:80]}"
            )

    ingredient_lines = [normalize_text(i).strip() for i in ingredients if i and i.strip()]
    if ingredient_lines:
        unlinked = [i for i in ingredient_lines if i not in linked]
        lines.append(
            f"Ingredient links: {len(ingredient_lines) - len(unlinked)} of "
            f"{len(ingredient_lines)} ingredients linked in steps."
            + (f" Not linked: {'; '.join(unlinked)}" if unlinked else "")
        )
    return lines
