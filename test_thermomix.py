"""Tests for thermomix.py. Run with: pytest test_thermomix.py"""

from thermomix import (
    REVERSE_GLYPH,
    build_instruction,
    build_instructions,
    describe_instructions,
)

STEP_3 = (
    "Currypulver, Garam Masala, Kreuzkümmel, Salz, Ingwerpulver, Zwiebelpulver, "
    "Paprikapulver, Cayennepfeffer, Zucker, Passata, Gemüsebrühe und Sojaschnetzel "
    "in den Mixtopf geben und 15 Min./100°C/Linkslauf/Stufe 1 kochen. "
    "Dabei Messbecher einsetzen."
)


def test_matches_what_the_cookidoo_editor_produces():
    """Ground truth: payload saved by the Cookidoo editor for this very step."""
    instruction = build_instruction(STEP_3)
    assert instruction["type"] == "STEP"
    assert f"15 Min./100°C/{REVERSE_GLYPH}/Stufe 1 kochen." in instruction["text"]
    assert instruction["annotations"] == [
        {
            "type": "TTS",
            "data": {
                "speed": "1",
                "direction": "CCW",
                "time": 900,
                "temperature": {"value": "100", "unit": "C"},
            },
            "position": {"offset": 178, "length": 23},
        }
    ]
    position = instruction["annotations"][0]["position"]
    span = instruction["text"][position["offset"] : position["offset"] + position["length"]]
    assert span == f"15 Min./100°C/{REVERSE_GLYPH}/Stufe 1"


def test_clockwise_with_temperature():
    instruction = build_instruction("Kokosöl dazugeben und 3 Min./120°C/Stufe 1 andünsten.")
    assert instruction["text"] == "Kokosöl dazugeben und 3 Min./120°C/Stufe 1 andünsten."
    (annotation,) = instruction["annotations"]
    assert annotation["data"] == {
        "speed": "1",
        "time": 180,
        "temperature": {"value": "120", "unit": "C"},
    }
    expected_offset = instruction["text"].index("3 Min.")
    assert annotation["position"] == {"offset": expected_offset, "length": 20}


def test_seconds_only_without_temperature():
    instruction = build_instruction("Alles 4 Sek./Stufe 5 zerkleinern.")
    (annotation,) = instruction["annotations"]
    assert annotation["data"] == {"speed": "5", "time": 4}
    expected_offset = instruction["text"].index("4 Sek.")
    assert annotation["position"] == {"offset": expected_offset, "length": 14}


def test_minutes_and_seconds_and_half_speed():
    instruction = build_instruction("Rühren: 1 Min. 30 Sek./Stufe 0,5")
    (annotation,) = instruction["annotations"]
    assert annotation["data"] == {"speed": "0.5", "time": 90}
    assert instruction["text"] == "Rühren: 1 Min. 30 Sek./Stufe 0,5"


def test_reverse_without_heating():
    instruction = build_instruction("Unterheben 5 Min./Linkslauf/Stufe 1")
    (annotation,) = instruction["annotations"]
    assert annotation["data"] == {"speed": "1", "time": 300, "direction": "CCW"}
    assert instruction["text"] == f"Unterheben 5 Min./{REVERSE_GLYPH}/Stufe 1"


def test_editor_form_with_glyph_is_accepted_unchanged():
    text = f"Kochen 15 Min./100°C/{REVERSE_GLYPH}/Stufe 1."
    instruction = build_instruction(text)
    assert instruction["text"] == text
    assert instruction["annotations"][0]["data"]["direction"] == "CCW"


def test_multiple_settings_in_one_step():
    instruction = build_instruction(
        "Erst 5 Min./Linkslauf/Stufe 1 rühren, dann 10 Sek./Stufe 8 mixen."
    )
    first, second = instruction["annotations"]
    for annotation in (first, second):
        pos = annotation["position"]
        assert instruction["text"][pos["offset"] : pos["offset"] + pos["length"]].endswith(
            ("Stufe 1", "Stufe 8")
        )
    assert first["data"]["time"] == 300 and second["data"]["time"] == 10


def test_plain_step_has_no_annotations():
    assert build_instruction("Mit Reis anrichten.") == {
        "type": "STEP",
        "text": "Mit Reis anrichten.",
    }


def test_invalid_values_stay_plain_text():
    # speed 11 does not exist, 300 °C is out of range
    for text in ("3 Min./100°C/Stufe 11", "3 Min./300°C/Stufe 1", "0 Sek./Stufe 1"):
        assert "annotations" not in build_instruction(text)


def test_offsets_count_utf16_units():
    # The emoji is 2 UTF-16 code units (1 code point) - JavaScript counts 2.
    instruction = build_instruction("Los 🍛 4 Sek./Stufe 5")
    assert instruction["annotations"][0]["position"]["offset"] == 7


def test_describe_reports_settings_and_warnings():
    lines = describe_instructions(
        [build_instruction(STEP_3), build_instruction("Dann auf Varoma Stufe 2 garen.")]
    )
    assert lines[0] == "Step 1: 15 Min./100°C/Linkslauf/Stufe 1"
    assert "WARNING" in lines[1]


# --- Ground truth: JSON that the Cookidoo editor itself produced (getInstructions())
# for the recipe "Cremiges Kichererbsen-Curry mit Räuchertofu".

REAL_INGREDIENTS = [
    "1 Dose Kichererbsen (240g Abtropfgewicht, abgespült)",
    "250g Räuchertofu (1 Standard-Block, in 1 cm große Würfel geschnitten)",
    "1 Zwiebel",
    "1 Knoblauchzehe",
    "1 TL Olivenöl",
    "150g stückige Tomaten (aus der Dose)",
    "100g Kokosmilch Light",
    "100g frischer Babyspinat",
    "Gewürze: 2 TL Currypulver, 1/2 TL Kreuzkümmel, Salz, Pfeffer",
    "Für das Protein-Topping: 4 gehäufte EL Skyr (ca. 100g)",
]


def _ing(description, offset, length):
    return {
        "type": "INGREDIENT",
        "data": {"description": description},
        "position": {"offset": offset, "length": length},
    }


def _tts(data, offset, length):
    return {"type": "TTS", "data": data, "position": {"offset": offset, "length": length}}


REAL_INSTRUCTIONS = [
    {"type": "STEP", "text": "Nährwerte pro Portion (bei 2 Portionen): ~460 kcal | ~37 g Protein"},
    {
        "type": "STEP",
        "text": "Basis zerkleinern:  1 Zwiebel und 1 Knoblauchzehe in den Mixtopf geben und "
        "5 Sek./Stufe 5 zerkleinern. Mit dem Spatel nach unten schieben.",
        "annotations": [
            _ing("1 Zwiebel", 20, 9),
            _ing("1 Knoblauchzehe", 34, 15),
            _tts({"speed": "5", "time": 5}, 75, 14),
        ],
    },
    {
        "type": "STEP",
        "text": "Anschwitzen:  1 TL Olivenöl und das Gewürze: 2 TL Currypulver, 1/2 TL "
        "Kreuzkümmel, Salz, Pfeffer dazugeben. 3 Min./120°C/Stufe 1 dünsten, damit das "
        "Curry sein volles Aroma entfaltet.",
        "annotations": [
            _ing("1 TL Olivenöl", 14, 13),
            _ing("Gewürze: 2 TL Currypulver, 1/2 TL Kreuzkümmel, Salz, Pfeffer", 36, 60),
            _tts(
                {"speed": "1", "time": 180, "temperature": {"value": "120", "unit": "C"}},
                108,
                20,
            ),
        ],
    },
    {
        "type": "STEP",
        "text": "Kochen:  1 Dose Kichererbsen (240g Abtropfgewicht, abgespült), 250g Räuchertofu "
        "(1 Standard-Block, in 1 cm große Würfel geschnitten), 150g stückige Tomaten (aus der "
        "Dose) und 100g Kokosmilch Light in den Mixtopf geben. "
        "12 Min./100°C//Stufe  köcheln lassen.",
        "annotations": [
            _ing("1 Dose Kichererbsen (240g Abtropfgewicht, abgespült)", 9, 52),
            _ing("250g Räuchertofu (1 Standard-Block, in 1 cm große Würfel geschnitten)", 63, 69),
            _ing("150g stückige Tomaten (aus der Dose)", 134, 36),
            _ing("100g Kokosmilch Light", 175, 21),
            _tts(
                {
                    "speed": "soft",
                    "direction": "CCW",
                    "time": 720,
                    "temperature": {"value": "100", "unit": "C"},
                },
                219,
                23,
            ),
        ],
    },
    {
        "type": "STEP",
        "text": "Spinat dazugeben:  100g frischer Babyspinat in den Mixtopf geben, mit dem Spatel "
        "leicht unterheben und weitere 2 Min./100°C//Stufe  zusammenfallen lassen.",
        "annotations": [
            _ing("100g frischer Babyspinat", 19, 24),
            _tts(
                {
                    "speed": "soft",
                    "direction": "CCW",
                    "time": 120,
                    "temperature": {"value": "100", "unit": "C"},
                },
                111,
                22,
            ),
        ],
    },
    {
        "type": "STEP",
        "text": "Das Curry auf zwei tiefe Teller verteilen. Erst jetzt jeweils 2 EL kalten Skyr "
        "direkt auf das heiße Curry geben und leicht unterrühren. Das macht es extrem cremig "
        "und bringt den extra Proteinschub!",
    },
]


def test_editor_text_reproduces_editor_output_exactly():
    """Feeding the editor's own step texts must give the editor's own JSON back."""
    texts = [step["text"] for step in REAL_INSTRUCTIONS]
    assert build_instructions(texts, REAL_INGREDIENTS) == REAL_INSTRUCTIONS


def test_notation_reproduces_editor_output_exactly():
    """Linkslauf / Sanftrührstufe notation gives the same result as the editor glyphs."""
    texts = [
        step["text"].replace("//Stufe ", "/Linkslauf/Sanftrührstufe")
        for step in REAL_INSTRUCTIONS
    ]
    assert "Sanftrührstufe" in texts[4]
    assert build_instructions(texts, REAL_INGREDIENTS) == REAL_INSTRUCTIONS


def test_soft_stir_alternative_spellings():
    for spelling in ("Sanftrührstufe", "Stufe Sanftrühren", "Stufe "):
        instruction = build_instruction(f"Rühren 2 Min./Linkslauf/{spelling} fertig.")
        (annotation,) = instruction["annotations"]
        assert annotation["data"] == {"speed": "soft", "time": 120, "direction": "CCW"}
        assert "Stufe  fertig." in instruction["text"]


def test_ingredient_needs_standalone_match():
    # "1 Zwiebel" must not link inside "11 Zwiebeln" / "1 Zwiebeln"
    assert "annotations" not in build_instruction("Dazu 11 Zwiebel", ["1 Zwiebel"])
    assert "annotations" not in build_instruction("Dazu 1 Zwiebeln", ["1 Zwiebel"])
    assert "annotations" in build_instruction("Dazu 1 Zwiebel.", ["1 Zwiebel"])


def test_longer_ingredient_wins_over_contained_one():
    instruction = build_instruction(
        "Mixen: 1 Zwiebel, geschält dazu.", ["1 Zwiebel", "1 Zwiebel, geschält"]
    )
    (annotation,) = instruction["annotations"]
    assert annotation["data"]["description"] == "1 Zwiebel, geschält"


def test_same_ingredient_linked_every_time_it_occurs():
    text = "Salz dazu, später Salz nachlegen."
    instruction = build_instruction(text, ["Salz"])
    offsets = [a["position"]["offset"] for a in instruction["annotations"]]
    assert offsets == [0, text.rindex("Salz")]


def test_semicolons_are_replaced_like_in_the_editor():
    instruction = build_instruction("Zutat A; Zutat B dazu", ["Zutat A; Zutat B"])
    assert instruction["text"] == "Zutat A； Zutat B dazu"
    (annotation,) = instruction["annotations"]
    assert annotation["data"]["description"] == "Zutat A； Zutat B"


def test_describe_reports_unlinked_ingredients():
    instructions = build_instructions(["1 Zwiebel dazu."], ["1 Zwiebel", "2 Eier"])
    lines = describe_instructions(instructions, ["1 Zwiebel", "2 Eier"])
    assert lines[0] == "Step 1: links 1 ingredient(s)"
    assert lines[-1] == "Ingredient links: 1 of 2 ingredients linked in steps. Not linked: 2 Eier"
