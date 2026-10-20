"""
Thermomix mode catalog: which modes Cookidoo offers and how to build them.

The Cookidoo recipe editor renders its settings dialog on the server. The page
``/created-recipes/{locale}/{id}/edit/ingredients-and-preparation-steps`` contains, as
plain HTML, every mode the editor offers (``<cr-tts-mode>``), the speeds, temperatures,
turbo times, turbo pulse counts, steaming accessories and browning powers, plus the
localised labels. ``parse_editor_html`` reads that into a ``ModeCatalog``, so the MCP
follows Cookidoo when modes are added or removed.

What the HTML does not contain are the limits per mode (time range, allowed speeds)
and the icon glyph written into the step text. Those live in the editor's JavaScript
(pl-customer-recipes 1.174.12) and are kept here in ``MODE_RULES``. A mode Cookidoo
offers without a rule here is reported as unsupported; a rule whose mode Cookidoo no
longer offers is not used.

Saved form of a mode (verified against the editor dialog and the PATCH response):

    {"type": "MODE", "name": "dough", "data": {"time": 120},
     "position": {"offset": 5, "length": 20}}

with the step text "... Teig kneten \\ue001/2 Min. ...".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser

DEVICES = ("TM6", "TM7")


@dataclass(frozen=True)
class ModeRule:
    """Editor limits for one mode. ``None`` means: take the values from the catalog."""

    name: str
    glyph: str
    # Which value is printed after the glyph in the step text: "time", "temperature" or "".
    text_value: str
    # Parameters the step text may give, and those it must give.
    allowed: frozenset[str]
    required: frozenset[str] = frozenset()
    min_time: float | None = None
    max_time: float | None = None
    speeds: tuple[str, ...] | None = None
    temperatures: tuple[str, ...] | None = None
    devices: tuple[str, ...] = DEVICES
    # Additional names accepted in the step text besides the catalog title.
    aliases: tuple[str, ...] = ()
    defaults: dict = field(default_factory=dict)


def _celsius(low: int, high: int) -> tuple[str, ...]:
    steps = [37, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 98, 100, 105, 110, 115, 120,
             140, 145, 150, 155, 160]
    return tuple(str(t) for t in steps if low <= t <= high)


MODE_RULES: dict[str, ModeRule] = {
    rule.name: rule
    for rule in (
        ModeRule(
            "dough", "\ue001", "time", frozenset({"time"}), frozenset({"time"}),
            min_time=1, max_time=1200, aliases=("Teigstufe", "Teigmodus", "Kneten"),
        ),
        ModeRule(
            # Turbo times come from the catalog (a fixed choice, 0.5/1/2 s); pulses: TM7.
            "turbo", "\ue00b", "time", frozenset({"time", "pulses"}), frozenset({"time"}),
        ),
        ModeRule(
            "blend", "\ue01e", "time", frozenset({"time", "speed"}),
            frozenset({"time", "speed"}), min_time=10, max_time=300,
            speeds=("6", "6.5", "7", "7.5", "8"),
        ),
        ModeRule(
            "warm_up", "\ue019", "temperature", frozenset({"temperature", "speed"}),
            frozenset({"temperature"}), speeds=("soft", "1", "2"),
            temperatures=_celsius(37, 90), defaults={"speed": "soft"},
        ),
        ModeRule("rice_cooker", "\ue00d", "", frozenset()),
        ModeRule(
            "steaming", "\ue008", "time",
            frozenset({"time", "speed", "reverse", "accessory"}), frozenset({"time", "speed"}),
            min_time=1, max_time=5940,
            speeds=("soft", "0.5", "1", "1.5", "2", "2.5", "3", "3.5", "4", "4.5", "5"),
            devices=("TM7",), defaults={"accessory": "Varoma"},
        ),
        ModeRule(
            "browning", "\ue026", "", frozenset({"time", "temperature", "power"}),
            frozenset({"temperature"}), min_time=1, max_time=1800,
            temperatures=_celsius(140, 160), devices=("TM7",),
            defaults={"time": 600, "power": "Gentle"},
        ),
    )
}

# Normal settings (TTS): temperatures up to 120 °C, Varoma only in the TM6 editor,
# heating only up to speed 6, at most 99 minutes.
TTS_MAX_TEMPERATURE = 120
TTS_MAX_HEATING_SPEED = 6.0
TTS_MAX_TIME = 5940
VAROMA = "varoma"


@dataclass(frozen=True)
class ModeCatalog:
    """What the Cookidoo editor offers (values are Cookidoo's internal names)."""

    modes: dict[str, str]  # value -> localised title, e.g. "dough" -> "Teig kneten"
    tm7_only: frozenset[str]
    speeds: tuple[str, ...]
    temperatures: tuple[str, ...]  # including "varoma", without "OFF"
    turbo_times: tuple[str, ...]
    pulse_counts: tuple[str, ...]
    accessories: dict[str, str]  # value -> title, e.g. "Varoma" -> "im Varoma"
    browning_powers: dict[str, str]  # value -> title, e.g. "Gentle" -> "Leicht"
    labels: dict[str, str]  # minutes, seconds, speed, varoma
    source: str = "builtin"

    def is_available(self, name: str, device: str) -> bool:
        """True if Cookidoo offers the mode, the MCP has a rule for it and the device has it."""
        rule = MODE_RULES.get(name)
        if rule is None or name not in self.modes or device not in rule.devices:
            return False
        return device == "TM7" or name not in self.tm7_only

    def available_modes(self, device: str) -> dict[str, str]:
        """value -> title of the modes that can be built for this device."""
        return {
            name: title for name, title in self.modes.items() if self.is_available(name, device)
        }

    def unsupported_modes(self) -> dict[str, str]:
        """Modes Cookidoo offers but the MCP has no rule for (newly introduced)."""
        return {name: title for name, title in self.modes.items() if name not in MODE_RULES}

    def tts_temperatures(self, device: str) -> tuple[str, ...]:
        """Temperatures for normal settings; Varoma only for TM6."""
        values = tuple(
            t for t in self.temperatures if t.isdigit() and int(t) <= TTS_MAX_TEMPERATURE
        )
        if device == "TM6" and VAROMA in self.temperatures:
            values += (VAROMA,)
        return values

    def title(self, name: str) -> str:
        return self.modes.get(name, name)


_SECTIONS = {
    "cr-tts-mode", "cr-tts-speed", "cr-tts-temperature", "cr-tts-time",
    "cr-tts-pulse-count", "cr-tts-steaming-accessory", "cr-tts-browning-power",
}


class _EditorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.section: str | None = None
        self.radios: dict[str, list[tuple[str, str, str]]] = {s: [] for s in _SECTIONS}
        self.section_attrs: dict[str, dict[str, str]] = {}
        self.tm7_labels: set[str] = set()
        self.last_text = ""

    def handle_starttag(self, tag, attrs):
        attributes = {k: v or "" for k, v in attrs}
        if tag in _SECTIONS:
            self.section = tag
            self.section_attrs.setdefault(tag, attributes)
        elif tag == "input" and self.section and attributes.get("type") == "radio":
            title = attributes.get("header-title") or self.last_text.strip()
            self.radios[self.section].append(
                (attributes.get("value", ""), title, attributes.get("id", ""))
            )
        elif tag == "label" and "tm7-mode" in attributes:
            self.tm7_labels.add(attributes.get("for", ""))
        if tag == "span":
            self.last_text = ""

    def handle_endtag(self, tag):
        if tag == self.section:
            self.section = None

    def handle_data(self, data):
        if data.strip():
            self.last_text = data


def parse_editor_html(html: str) -> ModeCatalog:
    """
    Read the mode catalog from the HTML of the Cookidoo editor page.

    Raises:
        ValueError: If the page contains no modes (e.g. a login page).
    """
    parser = _EditorParser()
    parser.feed(html)
    modes = parser.radios["cr-tts-mode"]
    if not modes:
        raise ValueError("The Cookidoo editor page contains no Thermomix modes.")

    def values(section: str) -> tuple[str, ...]:
        return tuple(value for value, _, _ in parser.radios[section])

    def titled(section: str) -> dict[str, str]:
        return {value: title for value, title, _ in parser.radios[section]}

    speeds = tuple(v for v in values("cr-tts-speed") if v not in ("CW", "CCW"))
    temperature_attrs = parser.section_attrs.get("cr-tts-temperature", {})
    time_attrs = parser.section_attrs.get("cr-tts-time", {})
    speed_attrs = parser.section_attrs.get("cr-tts-speed", {})
    return ModeCatalog(
        modes={value: title for value, title, _ in modes},
        tm7_only=frozenset(value for value, _, id_ in modes if id_ in parser.tm7_labels),
        speeds=speeds,
        temperatures=tuple(v for v in values("cr-tts-temperature") if v != "OFF"),
        turbo_times=values("cr-tts-time"),
        pulse_counts=values("cr-tts-pulse-count"),
        accessories=titled("cr-tts-steaming-accessory"),
        browning_powers=titled("cr-tts-browning-power"),
        labels={
            "minutes": time_attrs.get("minutes-translation", "Min."),
            "seconds": time_attrs.get("seconds-translation", "Sek."),
            "speed": speed_attrs.get("speed-translation", "Stufe"),
            "varoma": temperature_attrs.get("varoma-translation", "Varoma"),
        },
        source="cookidoo",
    )


# Snapshot of cookidoo.de (de-DE) from 20.10.2026, used when the live catalog cannot be
# loaded (not connected, no own recipe yet, network error).
BUILTIN_CATALOG = ModeCatalog(
    modes={
        "dough": "Teig kneten",
        "browning": "Anbraten",
        "turbo": "Turbo",
        "steaming": "Dampfgaren",
        "blend": "Pürieren",
        "warm_up": "Erwärmen",
        "rice_cooker": "Reis kochen",
    },
    tm7_only=frozenset({"browning", "steaming"}),
    speeds=("soft", "0.5", "1", "1.5", "2", "2.5", "3", "3.5", "4", "4.5", "5", "5.5", "6",
            "6.5", "7", "7.5", "8", "8.5", "9", "9.5", "10"),
    temperatures=_celsius(37, 160) + (VAROMA,),
    turbo_times=("0.5", "1", "2"),
    pulse_counts=("1", "2", "3", "4", "5", "6", "7", "8", "9"),
    accessories={
        "Varoma": "im Varoma",
        "SimmeringBasket": "im Gareinsatz",
        "VaromaAndSimmeringBasket": "in beidem",
    },
    browning_powers={"Gentle": "Leicht", "Intense": "Intensiv"},
    labels={"minutes": "Min.", "seconds": "Sek.", "speed": "Stufe", "varoma": "Varoma"},
    source="builtin",
)


def device_from_tools(tools) -> str:
    """Cookidoo shows the TM7 editor as soon as TM7 is one of the recipe's devices."""
    return "TM7" if tools and "TM7" in tools else "TM6"
