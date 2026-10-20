"""
Cookidoo step annotations: Thermomix settings, modes and ingredient links.

Cookidoo only starts guided cooking for a step when the step carries a ``TTS``
annotation (time/temperature/speed) or a ``MODE`` annotation (dough, turbo, ...), and
only shows an ingredient as a link when the step carries an ``INGREDIENT`` annotation.
Plain text is just text. This module builds exactly the structure the Cookidoo editor
itself sends, verified against the editor output of real recipes (see
test_thermomix.py and test_modes.py):

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

Normal Thermomix settings, written in German as printed in Cookidoo recipes:

    4 Sek./Stufe 5
    3 Min./120°C/Stufe 1
    1 Min. 30 Sek./90°C/Stufe 2
    15 Min./100°C/Linkslauf/Stufe 1      (counter-clockwise, "reverse")
    12 Min./100°C/Linkslauf/Sanftrührstufe
    20 Min./Varoma/Stufe 1               (TM6 only)
    10 Sek./Stufe 0,5

Modes: the mode title as Cookidoo shows it, then its values, separated by "/". Which
modes exist and what they are called comes from the mode catalog (modes.py):

    Teig kneten/2 Min.
    Turbo/1 Sek.                         (TM7 also: Turbo/1 Sek./3x)
    Pürieren/1 Min./Stufe 8
    Erwärmen/65°C/Stufe 1
    [Reis kochen]                        (brackets for modes without values)
    Dampfgaren/20 Min./Stufe 1/im Varoma (TM7)
    Anbraten/10 Min./160°C/Leicht        (TM7)

Ingredient links: a step links an ingredient when the step text contains the
ingredient line from the ingredient list verbatim (e.g. the list has "1 Zwiebel" and
the step says "1 Zwiebel und 1 Knoblauchzehe in den Mixtopf geben").
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from .modes import (
    BUILTIN_CATALOG,
    MODE_RULES,
    TTS_MAX_HEATING_SPEED,
    TTS_MAX_TIME,
    VAROMA,
    ModeCatalog,
)

# Private-use glyphs of the Cookidoo icon font, written between the slashes of a setting.
REVERSE_GLYPH = ""  # counter-clockwise
SOFT_GLYPH = ""  # soft stir ("Sanftrührstufe")

# The Cookidoo editor replaces ";" in all texts by this full-width semicolon.
_SEMICOLON = "；"

_TIME = (
    r"(?:(?P<min>\d{1,3})\s*Min\.?(?:\s*(?P<sec>\d{1,2})\s*Sek\.?)?"
    r"|(?P<sec_only>\d{1,4}(?:[.,]5)?)\s*Sek\.?)"
)
_REVERSE = rf"(?P<rev>Linkslauf|{REVERSE_GLYPH}|↺)"
_SPEED = (
    r"(?:Stufe\s*(?P<speed>\d{1,2}(?:[.,]5)?)"
    rf"|(?P<soft>Stufe\s*{SOFT_GLYPH}|Stufe\s+Sanftrühren|Sanftrührstufe))"
)

# Hints for settings that look like Thermomix instructions but were not recognised.
_UNPARSED_HINT_RE = re.compile(
    r"Stufe\s*\d|Linkslauf|Sanftr|Varoma|Teigmodus|Teigstufe|Turbo", re.IGNORECASE
)

# Time grid of the Cookidoo editor: up to 5 min in 10 s steps, up to 20 min in 30 s
# steps, then whole minutes.
_GRID = ((300, 10), (1200, 30), (TTS_MAX_TIME, 60))


def normalize_text(text: str) -> str:
    """Apply the same text normalisation as the Cookidoo editor (";" -> full-width)."""
    return text.replace(";", _SEMICOLON)


def _u16len(text: str) -> int:
    """Length in UTF-16 code units (what JavaScript/the Cookidoo editor counts)."""
    return len(text.encode("utf-16-le")) // 2


def _number(value: float) -> int | float:
    return int(value) if float(value).is_integer() else value


def format_time(seconds: float, catalog: ModeCatalog = BUILTIN_CATALOG) -> str:
    """Like the editor: "2 Min.", "1 Min. 30 Sek.", "0.5 Sek."."""
    minutes, secs = divmod(seconds, 60)
    parts = []
    if minutes:
        parts.append(f"{int(minutes)} {catalog.labels['minutes']}")
    if secs:
        parts.append(f"{_number(secs)} {catalog.labels['seconds']}")
    return " ".join(parts)


def _seconds(match: re.Match) -> float:
    if match.group("sec_only") is not None:
        return float(match.group("sec_only").replace(",", "."))
    return int(match.group("min")) * 60 + int(match.group("sec") or 0)


def _off_grid(seconds: float) -> bool:
    for limit, step in _GRID:
        if seconds <= limit:
            return seconds % step != 0 if seconds > 60 else False
    return True


def _speed_text(speed: str) -> str:
    return f"Stufe {SOFT_GLYPH}" if speed == "soft" else "Stufe " + speed.replace(".", ",")


def _speed_label(speed: str) -> str:
    return "Sanftrührstufe" if speed == "soft" else f"Stufe {speed}"


def _alternation(words: Iterable[str]) -> str:
    return "|".join(re.escape(w) for w in sorted(set(words), key=len, reverse=True) if w)


# --- Normal settings (TTS) ---------------------------------------------------------


def _tts_regex(catalog: ModeCatalog) -> re.Pattern:
    temp = rf"(?:(?P<temp>\d{{2,3}})\s*°\s*C|(?P<varoma>{re.escape(catalog.labels['varoma'])}))"
    return re.compile(
        rf"{_TIME}\s*/\s*(?:{temp}\s*/\s*)?(?:{_REVERSE}?\s*/\s*)?{_SPEED}"
    )


def _tts_from_match(
    match: re.Match, catalog: ModeCatalog, device: str
) -> tuple[str, dict, str | None] | str:
    """(canonical text, data, warning or None) for a valid match, else the reason."""
    seconds = _seconds(match)
    if seconds <= 0 or not float(seconds).is_integer():
        return "the time must be whole seconds"
    if seconds > TTS_MAX_TIME:
        return "the time can be at most 99 Min."
    seconds = int(seconds)

    soft = match.group("soft") is not None
    speed = "soft" if soft else match.group("speed").replace(",", ".")
    if not soft and speed not in catalog.speeds:
        return f"speed {speed} does not exist"

    temperature = None
    if match.group("varoma") is not None:
        if VAROMA not in catalog.tts_temperatures(device):
            return f"Varoma as a temperature is not available for the {device}"
        temperature = VAROMA
    elif match.group("temp") is not None:
        temperature = str(int(match.group("temp")))
        if temperature not in catalog.tts_temperatures(device):
            allowed = ", ".join(t for t in catalog.tts_temperatures(device) if t != VAROMA)
            return f"{temperature}°C is not a Thermomix temperature (allowed: {allowed})"
    if temperature is not None and speed != "soft" and float(speed) > TTS_MAX_HEATING_SPEED:
        return "heating is only possible up to speed 6"

    reverse = bool(match.group("rev"))
    data: dict = {"speed": speed, "time": seconds}
    if reverse:
        data["direction"] = "CCW"
    if temperature is not None:
        data["temperature"] = {"value": temperature, "unit": "C"}

    segments = [format_time(seconds, catalog)]
    if temperature == VAROMA:
        segments.append(catalog.labels["varoma"])
    elif temperature is not None:
        segments.append(f"{temperature}°C")
    if reverse:
        segments.append(REVERSE_GLYPH)
    segments.append(_speed_text(speed))

    warning = None
    if _off_grid(seconds):
        warning = (
            f"{format_time(seconds)} is not on the Cookidoo time grid (up to 5 Min. in "
            "10 Sek. steps, up to 20 Min. in 30 Sek. steps, then whole minutes)"
        )
    return "/".join(segments), data, warning


# --- Modes -------------------------------------------------------------------------


def _mode_titles(catalog: ModeCatalog) -> dict[str, str]:
    """Every accepted spelling (catalog title, alias) -> mode name, for all modes with a rule."""
    titles: dict[str, str] = {}
    for name, rule in MODE_RULES.items():
        if name in catalog.modes:
            titles[catalog.modes[name]] = name
        for alias in rule.aliases:
            titles.setdefault(alias, name)
    return titles


def _token_patterns(catalog: ModeCatalog) -> dict[str, str]:
    accessories = list(catalog.accessories) + list(catalog.accessories.values())
    powers = list(catalog.browning_powers) + list(catalog.browning_powers.values())
    patterns = {
        "time": _TIME,
        "temperature": rf"(?:\d{{2,3}}\s*°\s*C|{re.escape(catalog.labels['varoma'])})",
        "speed": _SPEED,
        "reverse": _REVERSE,
        "pulses": r"\d{1,2}\s*(?:x|×|-?[mM]al)",
    }
    if accessories:
        patterns["accessory"] = rf"(?:{_alternation(accessories)})"
    if powers:
        patterns["power"] = rf"(?:{_alternation(powers)})"
    return patterns


def _mode_regex(catalog: ModeCatalog, titles: dict[str, str]) -> re.Pattern | None:
    if not titles:
        return None
    # Strip named groups from the token patterns: they are re-parsed piece by piece.
    tokens = "|".join(
        re.sub(r"\(\?P<\w+>", "(?:", pattern) for pattern in _token_patterns(catalog).values()
    )
    glyphs = "".join(rule.glyph for rule in MODE_RULES.values())
    return re.compile(
        rf"(?P<open>\[\s*)?(?<![\w-])(?P<title>{_alternation(titles)})(?![\w-])"
        rf"(?P<glyph>\s*[{glyphs}])?"
        rf"(?P<params>(?:\s*/\s*(?:{tokens}))*)"
        rf"(?(open)\s*\])"
    )


def _parse_params(
    params: str, catalog: ModeCatalog, allowed: Iterable[str]
) -> dict[str, re.Match] | str:
    """Classify the "/"-separated values; kinds the mode accepts are tried first."""
    patterns = {kind: re.compile(p) for kind, p in _token_patterns(catalog).items()}
    preferred = set(allowed)
    ordered = sorted(patterns.items(), key=lambda item: item[0] not in preferred)
    found: dict[str, re.Match] = {}
    for piece in (p.strip() for p in params.split("/")):
        if not piece:
            continue
        for kind, pattern in ordered:
            match = pattern.fullmatch(piece)
            if match:
                if kind in found:
                    return f"'{piece}' is given twice"
                found[kind] = match
                break
        else:
            return f"'{piece}' is not understood"
    return found


def _lookup(value: str, choices: dict[str, str]) -> str | None:
    """Map a value or a localised title to the Cookidoo value (case-insensitive)."""
    for key, title in choices.items():
        if value.casefold() in (key.casefold(), title.casefold()):
            return key
    return None


def _mode_from_match(
    match: re.Match, catalog: ModeCatalog, device: str, titles: dict[str, str]
) -> tuple[str, str, dict] | str:
    """(canonical text, mode name, data) for a valid match, else the reason."""
    if not match.group("params") and not match.group("open") and not match.group("glyph"):
        # A bare title ("Reis kochen") is ordinary text unless written as "[Reis kochen]".
        return None
    name = titles[match.group("title")]
    rule = MODE_RULES[name]
    title = catalog.title(name)
    if name not in catalog.modes:
        return f"Cookidoo no longer offers '{title}'"
    if not catalog.is_available(name, device):
        return f"'{title}' is not available for the {device}"

    found = _parse_params(match.group("params"), catalog, rule.allowed)
    if isinstance(found, str):
        return found
    not_allowed = [kind for kind in found if kind not in rule.allowed]
    if not_allowed:
        return f"'{title}' takes no {' or '.join(not_allowed)}"

    values: dict = dict(rule.defaults)

    if "time" in found:
        seconds = _seconds(found["time"])
        if name == "turbo":
            allowed = [float(t) for t in catalog.turbo_times]
            if seconds not in allowed:
                return f"Turbo time must be {' / '.join(catalog.turbo_times)} Sek."
        elif not float(seconds).is_integer() or not (
            rule.min_time <= seconds <= rule.max_time
        ):
            return (
                f"'{title}' time must be between {format_time(rule.min_time)} and "
                f"{format_time(rule.max_time)}"
            )
        values["time"] = _number(seconds)

    if "temperature" in found:
        piece = found["temperature"].group(0)
        digits = re.match(r"\d+", piece)
        temperature = digits.group(0) if digits else VAROMA
        allowed = [t for t in (rule.temperatures or ()) if t in catalog.temperatures]
        if temperature not in allowed:
            return f"'{title}' temperature must be one of {', '.join(allowed)}°C"
        values["temperature"] = {"value": temperature, "unit": "C"}

    if "speed" in found:
        speed_match = found["speed"]
        speed = (
            "soft" if speed_match.group("soft") else speed_match.group("speed").replace(",", ".")
        )
        allowed = [s for s in (rule.speeds or catalog.speeds) if s in catalog.speeds]
        if speed not in allowed:
            return f"'{title}' speed must be one of {', '.join(_speed_label(s) for s in allowed)}"
        values["speed"] = speed

    if "reverse" in found:
        values["direction"] = "CCW"

    if "pulses" in found:
        count = re.match(r"\d+", found["pulses"].group(0)).group(0)
        if device != "TM7":
            return "turbo pulses are only available for the TM7; write e.g. '3-mal' as text"
        if count not in catalog.pulse_counts:
            return f"turbo pulses must be {' / '.join(catalog.pulse_counts)}"
        values["pulseCount"] = int(count)

    if "accessory" in found:
        accessory = _lookup(found["accessory"].group(0), catalog.accessories)
        if accessory is None:
            return f"unknown accessory '{found['accessory'].group(0)}'"
        values["accessory"] = accessory

    if "power" in found:
        power = _lookup(found["power"].group(0), catalog.browning_powers)
        if power is None:
            return f"unknown power '{found['power'].group(0)}'"
        values["power"] = power

    missing = [kind for kind in rule.required if kind not in found and kind not in values]
    if missing:
        return f"'{title}' needs {' and '.join(sorted(missing))}"

    order = ("time", "temperature", "speed", "direction", "pulseCount", "accessory", "power")
    data = {key: values[key] for key in order if key in values}

    text = f"{title} {rule.glyph}"
    if rule.text_value == "time":
        text += "/" + format_time(data["time"], catalog)
    elif rule.text_value == "temperature":
        text += f"/{data['temperature']['value']}°C"
    return text, name, data


# --- Building ----------------------------------------------------------------------


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


def _parse(
    text: str, catalog: ModeCatalog, device: str
) -> tuple[str, list[tuple[int, int, str, dict]], list[str]]:
    """Rewrite settings and modes to editor form: (text, spans, warnings)."""
    titles = _mode_titles(catalog)
    candidates: list[tuple[int, int, str, str, dict]] = []  # start, end, canonical, kind, data
    rejected: list[tuple[int, int]] = []  # modes that were meant but are invalid
    warnings: list[str] = []

    mode_regex = _mode_regex(catalog, titles)
    if mode_regex:
        for match in mode_regex.finditer(text):
            built = _mode_from_match(match, catalog, device, titles)
            if built is None:
                continue
            if isinstance(built, str):
                warnings.append(f"'{match.group(0).strip()}' not used: {built}")
                rejected.append((match.start(), match.end()))
                continue
            canonical, name, data = built
            candidates.append((match.start(), match.end(), canonical, "MODE", {"name": name, **data}))

    blocked = [(start, end) for start, end, *_ in candidates] + rejected
    for match in _tts_regex(catalog).finditer(text):
        if any(match.start() < end and match.end() > start for start, end in blocked):
            continue
        built = _tts_from_match(match, catalog, device)
        if isinstance(built, str):
            warnings.append(f"'{match.group(0)}' not used: {built}")
            continue
        canonical, data, warning = built
        if warning:
            warnings.append(warning)
        candidates.append((match.start(), match.end(), canonical, "TTS", data))

    candidates.sort(key=lambda c: c[0])
    pieces: list[str] = []
    spans: list[tuple[int, int, str, dict]] = []
    last_end = 0
    for start, end, canonical, kind, data in candidates:
        pieces.append(text[last_end:start])
        new_start = len("".join(pieces))
        pieces.append(canonical)
        spans.append((new_start, new_start + len(canonical), kind, data))
        last_end = end
    pieces.append(text[last_end:])
    return "".join(pieces), spans, warnings


def _annotation(kind: str, data: dict, text: str, start: int, end: int) -> dict:
    position = {"offset": _u16len(text[:start]), "length": _u16len(text[start:end])}
    if kind == "MODE":
        data = dict(data)
        name = data.pop("name")
        return {"type": "MODE", "name": name, "data": data, "position": position}
    return {"type": kind, "data": data, "position": position}


def build_instruction(
    text: str,
    ingredients: Iterable[str] = (),
    catalog: ModeCatalog = BUILTIN_CATALOG,
    device: str = "TM6",
) -> dict:
    """
    Turn one step text into a Cookidoo instruction object.

    Every recognised Thermomix setting and mode is rewritten to Cookidoo's canonical
    text and gets a TTS or MODE annotation; every ingredient line that appears verbatim
    in the step gets an INGREDIENT annotation. Annotations are ordered by position.
    Steps without any of these are returned as plain ``{"type": "STEP", "text": ...}``.
    """
    text = normalize_text(text)
    ingredient_lines = [normalize_text(i).strip() for i in ingredients if i and i.strip()]

    final_text, spans, _ = _parse(text, catalog, device)
    spans += _ingredient_spans(
        final_text, ingredient_lines, [(start, end) for start, end, _, _ in spans]
    )
    spans.sort(key=lambda span: span[0])

    instruction: dict = {"type": "STEP", "text": final_text}
    if spans:
        instruction["annotations"] = [
            _annotation(kind, data, final_text, start, end) for start, end, kind, data in spans
        ]
    return instruction


def build_instructions(
    steps: list[str],
    ingredients: Iterable[str] = (),
    catalog: ModeCatalog = BUILTIN_CATALOG,
    device: str = "TM6",
) -> list[dict]:
    """Build instruction objects for all steps."""
    ingredient_lines = list(ingredients)
    return [build_instruction(step, ingredient_lines, catalog, device) for step in steps]


def check_steps(
    steps: list[str], catalog: ModeCatalog = BUILTIN_CATALOG, device: str = "TM6"
) -> list[str]:
    """Warnings for settings and modes that were found but could not be used."""
    lines = []
    for number, step in enumerate(steps, 1):
        for warning in _parse(normalize_text(step), catalog, device)[2]:
            lines.append(f"Step {number}: WARNING - {warning}")
    return lines


# --- Report ------------------------------------------------------------------------


def _describe_setting(data: dict, catalog: ModeCatalog = BUILTIN_CATALOG) -> str:
    temp = data.get("temperature")
    parts = [format_time(data["time"], catalog)]
    if temp:
        parts.append(catalog.labels["varoma"] if temp["value"] == VAROMA else f"{temp['value']}°C")
    if data.get("direction") == "CCW":
        parts.append("Linkslauf")
    parts.append(_speed_label(data["speed"]))
    return "/".join(parts)


def _describe_mode(name: str, data: dict, catalog: ModeCatalog = BUILTIN_CATALOG) -> str:
    parts = [catalog.title(name)]
    if "time" in data:
        parts.append(format_time(data["time"], catalog))
    if "temperature" in data:
        parts.append(f"{data['temperature']['value']}°C")
    if "speed" in data:
        parts.append(_speed_label(data["speed"]))
    if data.get("direction") == "CCW":
        parts.append("Linkslauf")
    if "pulseCount" in data:
        parts.append(f"{data['pulseCount']}x")
    if "accessory" in data:
        parts.append(catalog.accessories.get(data["accessory"], data["accessory"]))
    if "power" in data:
        parts.append(catalog.browning_powers.get(data["power"], data["power"]))
    return "/".join(parts)


def describe_instructions(
    instructions: list[dict],
    ingredients: Iterable[str] = (),
    catalog: ModeCatalog = BUILTIN_CATALOG,
) -> list[str]:
    """
    Human-readable report: Thermomix settings, modes and ingredient links per step,
    warnings for settings that were not recognised, and ingredients that no step links.
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
        for annotation in annotations:
            if annotation["type"] == "TTS":
                lines.append(f"Step {number}: {_describe_setting(annotation['data'], catalog)}")
            elif annotation["type"] == "MODE":
                lines.append(
                    f"Step {number}: "
                    f"{_describe_mode(annotation['name'], annotation['data'], catalog)}"
                )
            else:
                description = annotation["data"]["description"]
                linked.add(description)
                step_links.append(description)
        if step_links:
            lines.append(f"Step {number}: links {len(step_links)} ingredient(s)")
        if _UNPARSED_HINT_RE.search(remainder):
            lines.append(
                f"Step {number}: WARNING - mentions a Thermomix setting or mode, but none was "
                f"recognised (use e.g. '3 Min./120°C/Stufe 1' or 'Teig kneten/2 Min.'): "
                f"{instruction['text'][:80]}"
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
