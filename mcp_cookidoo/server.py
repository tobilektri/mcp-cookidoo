"""
Cookidoo MCP Server

Main server file containing MCP tool definitions for interacting with Cookidoo.
"""

from fastmcp import FastMCP
from .cookidoo_service import CookidooService, load_cookidoo_credentials
from .schemas import CustomRecipe
from .modes import BUILTIN_CATALOG, DEVICES, MODE_RULES, ModeCatalog
from .thermomix import format_time, build_instructions, check_steps, describe_instructions
from .recipes import (
    format_catalog_recipe,
    format_custom_recipe,
    format_custom_recipes,
    format_search_result,
    format_week,
    is_custom_recipe_id,
    parse_day,
    split_recipe_ids,
)
import json
import re

# Initialize FastMCP server
mcp = FastMCP("cookidoo-mcp-server")

# Module-level state to store the authenticated session
_cookidoo_service: CookidooService | None = None
_cookidoo_api = None

# Leading list markers such as "1.", "2)", "-" or "•" (but not "15 Min./..." at step start)
_LIST_MARKER = re.compile(r"^\s*(?:\d+[.)]|[-•*])\s+")


def _parse_steps(steps: str) -> list[str]:
    """Split a multi-line steps string into clean step texts."""
    return [
        _LIST_MARKER.sub("", step).strip()
        for step in steps.split("\n")
        if step.strip()
    ]


def _format_settings_report(
    steps: list[str],
    ingredients: list[str],
    catalog: ModeCatalog = BUILTIN_CATALOG,
    device: str = "TM6",
    note: str = "",
) -> str:
    """Describe settings, modes and ingredient links per step (and what looks wrong)."""
    instructions = build_instructions(steps, ingredients, catalog, device)
    warnings = check_steps(steps, catalog, device)
    warned = {line.split(":", 1)[0] for line in warnings}
    report = [
        line for line in describe_instructions(instructions, ingredients, catalog)
        # The general "not recognised" hint adds nothing to a step with a specific warning.
        if not (line.split(":", 1)[0] in warned and "WARNING" in line)
    ]
    step_lines = [line for line in report + warnings if line.startswith("Step ")]
    step_lines.sort(key=lambda line: int(line.split()[1].rstrip(":")))  # stable per step
    lines = step_lines + [line for line in report if not line.startswith("Step ")]
    has_settings = any(
        annotation["type"] in ("TTS", "MODE")
        for instruction in instructions
        for annotation in instruction.get("annotations", [])
    )
    if not has_settings:
        lines.insert(
            0,
            "No Thermomix settings recognised. Write them like '3 Min./120°C/Stufe 1' or "
            "'Teig kneten/2 Min.' to enable guided cooking (see get_thermomix_modes).",
        )
    source = "read from Cookidoo" if catalog.source == "cookidoo" else "built-in list"
    header = f"Annotations for the {device} (guided cooking and ingredient links, modes {source}):"
    if note:
        header = f"{note}\n{header}"
    return header + "\n" + "\n".join(f"  {line}" for line in lines)


async def _ensure_catalog() -> tuple[ModeCatalog, str]:
    """The modes Cookidoo offers right now; the built-in list if not connected."""
    if not _cookidoo_service or not _cookidoo_api:
        return BUILTIN_CATALOG, (
            "Modes: not connected, used the built-in list. Connect with "
            "'connect_to_cookidoo' to check against what Cookidoo offers."
        )
    return await _cookidoo_service.get_mode_catalog()


def _check_device(device: str) -> str:
    device = device.strip().upper()
    if device not in DEVICES:
        raise ValueError(f"device must be one of {', '.join(DEVICES)}")
    return device


# Spelling of each mode in a step, with "{title}" for the name Cookidoo shows.
_MODE_EXAMPLES = {
    "dough": "{title}/2 Min.",
    "turbo": "{title}/1 Sek.",
    "blend": "{title}/1 Min./Stufe 8",
    "warm_up": "{title}/65°C/Stufe 1",
    "rice_cooker": "[{title}]",
    "steaming": "{title}/20 Min./Stufe 1/im Varoma",
    "browning": "{title}/10 Min./160°C/Leicht",
}


def _describe_rule(name: str, catalog: ModeCatalog, device: str) -> str:
    rule = MODE_RULES[name]
    parts = []
    if name == "turbo":
        parts.append(f"time {' / '.join(catalog.turbo_times)} Sek.")
        if device == "TM7":
            parts.append(f"optional pulses {catalog.pulse_counts[0]}x-{catalog.pulse_counts[-1]}x")
    elif rule.min_time is not None:
        parts.append(f"time {format_time(rule.min_time)} to {format_time(rule.max_time)}")
    if rule.temperatures:
        temps = [t for t in rule.temperatures if t in catalog.temperatures]
        parts.append(f"temperature {', '.join(temps)}°C")
    if rule.speeds:
        speeds = [s.replace("soft", "Sanftrührstufe") for s in rule.speeds if s in catalog.speeds]
        parts.append(f"speed {', '.join(speeds)}")
    if "reverse" in rule.allowed:
        parts.append("optional Linkslauf")
    if "accessory" in rule.allowed:
        parts.append(f"optional {' / '.join(catalog.accessories.values())}")
    if "power" in rule.allowed:
        parts.append(f"optional {' / '.join(catalog.browning_powers.values())}")
    defaults = {
        "time": lambda v: format_time(v),
        "speed": lambda v: "Sanftrührstufe" if v == "soft" else f"Stufe {v}",
        "accessory": lambda v: catalog.accessories.get(v, v),
        "power": lambda v: catalog.browning_powers.get(v, v),
    }
    for key, value in rule.defaults.items():
        parts.append(f"without {key}: {defaults.get(key, str)(value)}")
    return "; ".join(parts) or "no values"


@mcp.tool()
async def connect_to_cookidoo() -> str:
    """
    Authenticate with Cookidoo and store the session.
    
    This tool must be called before using other Cookidoo tools. It will:
    1. Load your Cookidoo credentials from the .env file
    2. Authenticate with the Cookidoo platform
    3. Store the authenticated session for use by other tools
        
    Returns:
        str: Success message confirming connection
        
    Raises:
        ValueError: If credentials are missing from .env file
        Exception: If authentication fails
    """
    global _cookidoo_service, _cookidoo_api
    
    try:
        # Load credentials from .env file
        email, password = load_cookidoo_credentials()
        
        # Create Cookidoo service instance
        _cookidoo_service = CookidooService(email, password)
        
        # Authenticate and get API client
        _cookidoo_api = await _cookidoo_service.login()
        
        return f"Successfully connected to Cookidoo as {email}"
        
    except ValueError as e:
        # Missing credentials
        return f"Configuration Error: {str(e)}\n\nPlease ensure your .env file contains COOKIDOO_EMAIL and COOKIDOO_PASSWORD"
        
    except Exception as e:
        # Authentication or other errors
        return f"Connection Failed: {str(e)}\n\nPlease check your credentials and try again."


@mcp.tool()
async def get_thermomix_modes(device: str = "TM6") -> str:
    """
    List the Thermomix modes Cookidoo offers right now and how to write them in a step.

    Call this before writing a recipe that uses modes (dough, turbo, blend, warm up,
    rice cooker, and for the TM7 steaming and browning). The list is read live from
    the Cookidoo recipe editor, so new or removed modes show up here. Normal settings
    (time/temperature/speed, e.g. "3 Min./120°C/Stufe 1") always work in addition.

    Args:
        device: "TM6" (default) or "TM7"

    Returns:
        str: Available modes with spelling and allowed values
    """
    try:
        device = _check_device(device)
        catalog, note = await _ensure_catalog()

        lines = [f"Thermomix modes for the {device}:"]
        for name, title in catalog.available_modes(device).items():
            example = _MODE_EXAMPLES.get(name, "{title}").format(title=title)
            lines.append(f"  {title}: write '{example}' ({_describe_rule(name, catalog, device)})")

        varoma = catalog.labels["varoma"]
        temps = [t for t in catalog.tts_temperatures(device) if t.isdigit()]
        lines.append("")
        lines.append(
            "Normal settings (always available): time/temperature/speed, e.g. "
            "'3 Min./120°C/Stufe 1', '15 Min./100°C/Linkslauf/Stufe 1', "
            "'12 Min./100°C/Linkslauf/Sanftrührstufe'."
        )
        lines.append(f"  Temperatures: {', '.join(temps)}°C; heating only up to speed 6.")
        if "varoma" in catalog.tts_temperatures(device):
            lines.append(f"  {varoma}: '20 Min./{varoma}/Stufe 1'.")
        else:
            lines.append(f"  {varoma} as a temperature is not available for the {device}.")

        other = [
            title for name, title in catalog.modes.items()
            if name in MODE_RULES and not catalog.is_available(name, device)
        ]
        if other:
            lines.append(f"Not available for the {device}: {', '.join(other)}.")
        unsupported = catalog.unsupported_modes()
        if unsupported:
            lines.append(
                "Offered by Cookidoo but not supported by this server yet (leave as text): "
                + ", ".join(unsupported.values())
            )
        source = "read from Cookidoo" if catalog.source == "cookidoo" else "built-in list"
        lines.append(f"Source: {source}.")
        if note:
            lines.append(note)
        return "\n".join(lines)

    except Exception as e:
        return f"Failed to list Thermomix modes: {str(e)}"


@mcp.tool()
async def search_recipes(
    query: str,
    ingredients: str = "",
    exclude_ingredients: str = "",
    max_total_time: int = 0,
    difficulty: str = "",
    portions: int = 0,
    device: str = "",
    limit: int = 10,
    page: int = 0,
) -> str:
    """
    Search the Cookidoo recipe catalogue.

    Returns names, IDs and links. Use get_recipe_details with an ID for ingredients and
    steps, and plan_recipe to put a recipe into the week plan. Your own recipes are not
    part of the catalogue; use list_my_recipes for them. You must be connected first
    using connect_to_cookidoo.

    Args:
        query: Search words, e.g. "Kichererbsen Curry"
        ingredients: Optional ingredients the recipe should contain, comma-separated
        exclude_ingredients: Optional ingredients to leave out, comma-separated
        max_total_time: Optional maximum total time in minutes (0 = any)
        difficulty: Optional "easy", "medium" or "advanced"
        portions: Optional number of portions (0 = any)
        device: Optional Thermomix the recipe must be made for: "TM5", "TM6" or "TM7"
        limit: How many results to show (default 10, at most 20 per page)
        page: Result page, starting at 0

    Returns:
        str: Matching recipes with name, ID and link
    """
    try:
        if not _cookidoo_api:
            return "Not connected. Please run 'connect_to_cookidoo' first."

        def listed(text: str) -> list[str] | None:
            values = [v.strip() for v in text.split(",") if v.strip()]
            return values or None

        result = await _cookidoo_api.search_recipes(
            query.strip() or None,
            ingredients=listed(ingredients),
            exclude_ingredients=listed(exclude_ingredients),
            total_time=max_total_time * 60 if max_total_time > 0 else None,
            difficulty=difficulty.strip() or None,
            portions=portions if portions > 0 else None,
            tmv=device.strip().upper() or None,
            page=page if page > 0 else None,
        )
        return format_search_result(result, max(1, limit), max(0, page))

    except Exception as e:
        return f"Search failed: {str(e)}"


@mcp.tool()
async def list_my_recipes() -> str:
    """
    List your own (created) Cookidoo recipes with name, ID, device and total time.

    You must be connected first using connect_to_cookidoo.

    Returns:
        str: Your own recipes
    """
    try:
        if not _cookidoo_api:
            return "Not connected. Please run 'connect_to_cookidoo' first."
        return format_custom_recipes(await _cookidoo_api.list_custom_recipes())

    except Exception as e:
        return f"Listing your recipes failed: {str(e)}"


@mcp.tool()
async def get_recipe_details(recipe_id: str) -> str:
    """
    Get ingredients, steps and times of a recipe by its ID.

    Works for Cookidoo catalogue recipes (e.g. "r59322", from search_recipes) and for
    your own recipes (e.g. "01M5A79NY53CEKEW6NKVYBFSTW", from list_my_recipes). Steps of
    own recipes are shown in the notation update_custom_recipe_steps accepts. You must
    be connected first using connect_to_cookidoo.

    Args:
        recipe_id: The Cookidoo recipe ID

    Returns:
        str: Recipe details including ingredients, steps and times
    """
    try:
        if not _cookidoo_api:
            return "Not connected. Please run 'connect_to_cookidoo' first."

        recipe_id = recipe_id.strip()
        if is_custom_recipe_id(recipe_id):
            return format_custom_recipe(await _cookidoo_api.get_custom_recipe(recipe_id.upper()))
        return format_catalog_recipe(await _cookidoo_api.get_recipe_details(recipe_id))

    except Exception as e:
        return f"Failed to get recipe details: {str(e)}"


@mcp.tool()
async def get_week_plan(day: str = "") -> str:
    """
    Show the recipes planned in your Cookidoo week plan ("Meine Woche").

    You must be connected first using connect_to_cookidoo.

    Args:
        day: First day of the week to show, as YYYY-MM-DD (default: today)

    Returns:
        str: Planned recipes per day with name and ID
    """
    try:
        if not _cookidoo_api:
            return "Not connected. Please run 'connect_to_cookidoo' first."

        start = parse_day(day)
        days = await _cookidoo_api.get_recipes_in_calendar_week(
            start, resolve_custom_recipes=True
        )
        return format_week(days, start)

    except Exception as e:
        return f"Loading the week plan failed: {str(e)}"


@mcp.tool()
async def plan_recipe(day: str, recipe_ids: str) -> str:
    """
    Put one or more recipes into your Cookidoo week plan on a given day.

    Catalogue recipes ("r59322") and your own recipes ("01M5...") can be mixed. You
    must be connected first using connect_to_cookidoo.

    Args:
        day: The day, as YYYY-MM-DD
        recipe_ids: Recipe IDs, comma-separated

    Returns:
        str: The recipes now planned on that day
    """
    try:
        if not _cookidoo_api:
            return "Not connected. Please run 'connect_to_cookidoo' first."
        if not day.strip():
            return "Please give the day, as YYYY-MM-DD."

        planned_day = parse_day(day)
        catalog, custom = split_recipe_ids(recipe_ids)
        if catalog:
            await _cookidoo_api.add_recipes_to_calendar(planned_day, catalog)
        if custom:
            await _cookidoo_api.add_custom_recipes_to_calendar(planned_day, custom)

        days = await _cookidoo_api.get_recipes_in_calendar_week(
            planned_day, resolve_custom_recipes=True
        )
        days = [d for d in days if d.id == planned_day.isoformat()]
        return (
            f"Planned {len(catalog) + len(custom)} recipe(s) on {planned_day.isoformat()}.\n\n"
            + format_week(days, planned_day)
        )

    except Exception as e:
        return f"Planning failed: {str(e)}"


@mcp.tool()
async def unplan_recipe(day: str, recipe_id: str) -> str:
    """
    Remove a recipe from your Cookidoo week plan on a given day.

    You must be connected first using connect_to_cookidoo.

    Args:
        day: The day, as YYYY-MM-DD
        recipe_id: The recipe ID as shown by get_week_plan

    Returns:
        str: Confirmation
    """
    try:
        if not _cookidoo_api:
            return "Not connected. Please run 'connect_to_cookidoo' first."

        planned_day = parse_day(day)
        recipe_id = recipe_id.strip()
        if is_custom_recipe_id(recipe_id):
            await _cookidoo_api.remove_custom_recipe_from_calendar(planned_day, recipe_id.upper())
        else:
            await _cookidoo_api.remove_recipe_from_calendar(planned_day, recipe_id)
        return f"Removed {recipe_id} from {planned_day.isoformat()}."

    except Exception as e:
        return f"Removing failed: {str(e)}"


@mcp.tool()
async def add_to_shopping_list(recipe_ids: str) -> str:
    """
    Add the ingredients of one or more recipes to your Cookidoo shopping list.

    Catalogue recipes ("r59322") and your own recipes ("01M5...") can be mixed. You
    must be connected first using connect_to_cookidoo.

    Args:
        recipe_ids: Recipe IDs, comma-separated

    Returns:
        str: The ingredients that were added
    """
    try:
        if not _cookidoo_api:
            return "Not connected. Please run 'connect_to_cookidoo' first."

        catalog, custom = split_recipe_ids(recipe_ids)
        items = []
        if catalog:
            items += await _cookidoo_api.add_ingredient_items_for_recipes(catalog)
        if custom:
            items += await _cookidoo_api.add_ingredient_items_for_custom_recipes(custom)
        lines = [f"Added {len(items)} ingredient(s) to the shopping list:"]
        lines += [
            "  - " + " ".join(part for part in (item.description, item.name) if part)
            for item in items
        ]
        return "\n".join(lines)

    except Exception as e:
        return f"Adding to the shopping list failed: {str(e)}"


@mcp.tool()
async def generate_recipe_structure(
    name: str,
    ingredients: str,
    steps: str,
    servings: int = 4,
    prep_time: int = 30,
    total_time: int = 60,
    hints: str = "",
    device: str = "TM6",
) -> str:
    """
    Generate and validate a recipe structure ready for upload to Cookidoo.
    
    This tool helps you structure your recipe data properly before uploading.
    It validates all fields and returns a JSON structure that can be used with
    the upload_custom_recipe tool. The modes are checked against what Cookidoo offers
    right now (call get_thermomix_modes to see them and their spelling).
    
    Thermomix settings: write them inside the step text in Cookidoo notation and
    they are turned into real Thermomix settings (guided cooking) on upload:
        "4 Sek./Stufe 5"                 time/speed
        "3 Min./120°C/Stufe 1"           time/temperature/speed
        "15 Min./100°C/Linkslauf/Stufe 1"  counter-clockwise (reverse) stirring
        "12 Min./100°C/Linkslauf/Sanftrührstufe"  soft stir (Sanftrührstufe)
        "20 Min./Varoma/Stufe 1"         Varoma (TM6 only)
        "1 Min. 30 Sek./Stufe 0,5"       minutes and seconds, half speed
    Temperatures 37-120 °C in Cookidoo's steps (37, 40, 45 ... 95, 98, 100, 105 ...),
    heating only up to speed 6.

    Modes: the mode name, then its values, separated by "/":
        "Teig kneten/2 Min."             dough
        "Turbo/1 Sek."                   turbo 0.5/1/2 s (TM7 also "Turbo/1 Sek./3x")
        "Pürieren/1 Min./Stufe 8"        blend, speed 6-8
        "Erwärmen/65°C/Stufe 1"          warm up, 37-90 °C
        "[Reis kochen]"                  rice cooker (brackets: no values)
        "Dampfgaren/20 Min./Stufe 1/im Varoma"  steaming (TM7)
        "Anbraten/10 Min./160°C/Leicht"  browning (TM7)
    Invalid values stay plain text and are listed as warnings in the output.

    Ingredient links: if a step contains an ingredient line verbatim (exactly as it
    appears in the ingredients list, e.g. "1 Zwiebel"), that text becomes a link to the
    ingredient in Cookidoo. So write steps like "1 Zwiebel und 1 Knoblauchzehe in den
    Mixtopf geben" using the ingredient lines word for word.

    Args:
        name: Recipe name (required)
        ingredients: Ingredients list, one per line or comma-separated
        steps: Cooking steps, one per line or numbered
        servings: Number of servings (default: 4, range: 1-20)
        prep_time: Preparation time in minutes (default: 30)
        total_time: Total cooking time in minutes (default: 60)
        hints: Optional cooking tips, one per line or comma-separated
        device: Thermomix the recipe is for, "TM6" (default) or "TM7"
        
    Returns:
        str: Validated recipe structure in JSON format, ready for upload
    """
    try:
        device = _check_device(device)

        # Parse ingredients (split by newlines or commas)
        ingredients_list = [
            ing.strip() 
            for ing in (ingredients.split('\n') if '\n' in ingredients else ingredients.split(','))
            if ing.strip()
        ]
        
        # Parse steps (split by newlines, strip list markers like "1." or "-")
        steps_list = _parse_steps(steps)
        
        # Parse hints if provided
        hints_list = None
        if hints:
            hints_list = [
                hint.strip()
                for hint in (hints.split('\n') if '\n' in hints else hints.split(','))
                if hint.strip()
            ]
        
        # Create and validate the recipe using Pydantic
        recipe = CustomRecipe(
            name=name,
            ingredients=ingredients_list,
            steps=steps_list,
            servings=servings,
            prep_time=prep_time,
            total_time=total_time,
            hints=hints_list,
            device=device,
        )
        
        # Return formatted JSON
        recipe_json = recipe.model_dump_json(indent=2)
        
        catalog, note = await _ensure_catalog()
        settings_report = _format_settings_report(
            recipe.steps, recipe.ingredients, catalog, device, note
        )

        return f"Recipe structure validated successfully!\n\n{recipe_json}\n\n{settings_report}\n\nYou can now use this with 'upload_custom_recipe'."
        
    except Exception as e:
        return f"Validation failed: {str(e)}\n\nPlease check your recipe data and try again."


@mcp.tool()
async def upload_custom_recipe(recipe_json: str) -> str:
    """
    Upload a custom recipe to your Cookidoo account.
    
    This tool creates a brand new recipe from scratch on your Cookidoo account.
    Use 'generate_recipe_structure' first to validate your recipe data, then
    pass the resulting JSON to this tool.

    Thermomix settings and modes written in the step texts (e.g. "3 Min./120°C/Stufe 1",
    "Teig kneten/2 Min.") are uploaded as real Thermomix settings, and ingredient lines
    that appear verbatim in a step are uploaded as ingredient links, so no manual editing
    in Cookidoo is needed. The modes are read from Cookidoo right before the upload.

    Args:
        recipe_json: The validated recipe JSON from generate_recipe_structure
        
    Returns:
        str: Success message with the created recipe ID
    """
    global _cookidoo_service, _cookidoo_api
    
    try:
        # Check if connected
        if not _cookidoo_service or not _cookidoo_api:
            return "Not connected. Please run 'connect_to_cookidoo' first."
        
        # Parse and validate the recipe JSON
        try:
            recipe_data = json.loads(recipe_json)
            recipe = CustomRecipe(**recipe_data)
        except json.JSONDecodeError as e:
            return f"Invalid JSON: {str(e)}"
        except Exception as e:
            return f"Invalid recipe data: {str(e)}"
        
        # Create the recipe using our custom service method
        recipe_id, catalog, note = await _cookidoo_service.create_custom_recipe(
            name=recipe.name,
            ingredients=recipe.ingredients,
            steps=recipe.steps,
            servings=recipe.servings,
            prep_time=recipe.prep_time,
            total_time=recipe.total_time,
            hints=recipe.hints,
            device=recipe.device,
        )

        recipe_url = _cookidoo_service.recipe_url(recipe_id)

        settings_report = _format_settings_report(
            recipe.steps, recipe.ingredients, catalog, recipe.device, note
        )

        return f"Recipe '{recipe.name}' created successfully!\n\nRecipe ID: {recipe_id}\nURL: {recipe_url}\n\n{settings_report}\n\nYour recipe is now saved in your Cookidoo account!"

    except Exception as e:
        return f"Upload failed: {str(e)}"


@mcp.tool()
async def update_custom_recipe_steps(
    recipe_id: str, steps: str, ingredients: str = ""
) -> str:
    """
    Replace the steps of an existing custom recipe, including Thermomix settings and
    ingredient links.

    Use this to fix or add Thermomix settings (time, temperature, speed, reverse, soft
    stir), modes (dough, turbo, ...) and ingredient links on a recipe that was already
    uploaded. Only the steps are changed; ingredients, times and hints stay as they are.
    The device (TM6/TM7) is taken from the recipe, the modes are read from Cookidoo.
    You must be connected first using connect_to_cookidoo.

    Write the settings inside the step text in Cookidoo notation, for example
    "3 Min./120°C/Stufe 1", "12 Min./100°C/Linkslauf/Sanftrührstufe" or
    "Teig kneten/2 Min." (see generate_recipe_structure and get_thermomix_modes for all
    forms). Ingredient lines that appear verbatim in a step become links.

    Args:
        recipe_id: ID of your custom recipe (e.g., "01M5A79NY53CEKEW6NKVYBFSTW")
        steps: ALL steps of the recipe, one per line. This replaces the existing steps.
        ingredients: Optional ingredient lines to link, one per line. If empty, the
            recipe's current ingredients are loaded from Cookidoo.

    Returns:
        str: Success message listing the Thermomix settings and ingredient links set
    """
    global _cookidoo_service, _cookidoo_api

    try:
        if not _cookidoo_service or not _cookidoo_api:
            return "Not connected. Please run 'connect_to_cookidoo' first."

        steps_list = _parse_steps(steps)
        if not steps_list:
            return "No steps given. Pass all steps of the recipe, one per line."

        given_ingredients = [
            line.strip() for line in ingredients.split("\n") if line.strip()
        ] or None

        ingredient_lines, device, catalog, note = await _cookidoo_service.update_recipe_steps(
            recipe_id, steps_list, given_ingredients
        )

        settings_report = _format_settings_report(
            steps_list, ingredient_lines, catalog, device, note
        )
        return f"Steps of recipe {recipe_id} updated ({len(steps_list)} steps).\n\n{settings_report}"

    except Exception as e:
        return f"Update failed: {str(e)}"


def main() -> None:
    """Start the server over stdio (the ``mcp-cookidoo`` command)."""
    mcp.run()


if __name__ == "__main__":
    main()
