# Cookidoo MCP Server – Thermomix recipes, meal planning & guided cooking with Claude

**Your Thermomix kitchen, run by your AI assistant.** Turn any recipe idea or web recipe into a
real Cookidoo recipe with guided cooking, find the right dish in the Cookidoo catalogue, plan your
week and fill your shopping list, all by just asking Claude (or any other MCP client).

> "Turn this curry from my favourite food blog into a Thermomix recipe for my TM6."
>
> "Find three vegetarian dinners under 30 minutes, plan them for Monday to Wednesday and put the
> ingredients on my shopping list."
>
> "Add the missing Thermomix settings to my bread recipe and knead the dough in dough mode."

**Why you'll like it:**

- **Recipes that cook themselves.** Uploaded recipes are not just text: every step comes with real
  Thermomix settings. Tap the step and your Thermomix is set to the right time, temperature and
  speed. Varoma, reverse and soft stir are included.
- **Every mode Cookidoo knows.** Dough, turbo, blend, warm up and rice cooker, and on the TM7
  steaming and browning too. The server reads the available modes live from Cookidoo, so it keeps
  up when Cookidoo adds new ones.
- **Ingredients linked like in the official editor.** Ingredients in a step become links, exactly
  as if you had made the recipe in the Cookidoo editor by hand. No manual editing in Cookidoo is
  needed.
- **From idea to dinner plan.** Search the whole Cookidoo catalogue and your own recipes, plan them
  in *Meine Woche* and send the ingredients to your Cookidoo shopping list.
- **Checked before it is uploaded.** Every recipe is checked against the same rules the Cookidoo editor applies
  before it is uploaded. Invalid temperatures, speeds or modes are explained instead of breaking
  the upload.
- **Made for the TM6 and the TM7.** Each recipe is built for your device and only uses what it can
  do.

<!-- mcp-name: io.github.tobilektri/mcp-cookidoo -->

> **Disclaimer:** This is an unofficial project. The developers are not affiliated with, endorsed by,
> or connected to Cookidoo, Vorwerk, Thermomix, or any of their subsidiaries or trademarks.

## Auf Deutsch: Thermomix-Rezepte mit KI erstellen und die Woche planen

Mit diesem MCP-Server erstellt dein KI-Assistent (z. B. Claude) **eigene Thermomix-Rezepte direkt in
Cookidoo**, aus einer Idee, einem Rezept aus dem Netz oder einem Familienrezept. Die Rezepte
landen in „Meine Rezepte“ und funktionieren mit **Guided Cooking**:
- **Einstellungen:** Zeit, Temperatur, Stufe, Linkslauf und Varoma sind gesetzt.
- **Modi:** Teig kneten, Turbo, Pürieren, Erwärmen und Reis kochen, beim TM7 auch Dampfgaren und
  Anbraten.
- **Zutaten:** Sie sind in den Schritten verlinkt wie im Cookidoo-Editor.

Nacharbeiten im Editor ist nicht nötig.

Außerdem kann der Assistent:
- **Suchen:** Rezepte im Cookidoo-Katalog und unter deinen eigenen Kreationen finden.
- **Planen:** Rezepte in den **Cookidoo-Wochenplan** („Meine Woche“) eintragen.
- **Einkaufen:** die Zutaten auf die **Cookidoo-Einkaufsliste** setzen.

Er funktioniert mit **Thermomix TM6 und TM7**. Die Einrichtung ist unten beschrieben (englisch).
Die Rezepte selbst kannst du auf Deutsch schreiben lassen.

## What it can do

**Create your own recipes**

| Feature | What you get |
|---|---|
| **Upload your own recipe** | Creates a new recipe in "My recipes" (*Meine Rezepte*) on Cookidoo, for the TM6 or TM7. |
| **Thermomix settings (guided cooking)** | Settings such as `3 Min./120°C/Stufe 1` in a step become real Thermomix settings. Tap the step and the Thermomix is set up. Works with time, temperature, Varoma, speed, reverse (*Linkslauf*) and soft stir (*Sanftrührstufe*). |
| **Thermomix modes** | Dough, turbo, blend, warm up and rice cooker, and on the TM7 also steaming and browning (`Teig kneten/2 Min.`, `Turbo/1 Sek.` …), read live from Cookidoo. |
| **Ingredient links** | When a step contains an ingredient line exactly as it appears in the ingredient list, it is shown as a link, as in recipes made with the Cookidoo editor. |
| **Check before uploading** | Validates the recipe and shows which settings, modes and ingredient links were detected, with a clear reason for anything that does not fit. |
| **Fix an uploaded recipe** | Replaces the steps of a recipe you already uploaded, for example to add Thermomix settings later. Ingredients, times and hints stay unchanged. |

**Find, plan and shop**

| Feature | What you get |
|---|---|
| **Find recipes** | Searches the Cookidoo catalogue (with filters such as ingredients to leave out, maximum time or device) and lists your own recipes. |
| **Look at a recipe** | Shows ingredients, steps and times of a catalogue recipe or one of your own. |
| **Plan your week** | Shows your Cookidoo week plan (*Meine Woche*), puts catalogue or own recipes on a day and removes them again. |
| **Shopping list** | Adds the ingredients of recipes to your Cookidoo shopping list. |

## Setup

You need a **Cookidoo account** (with an active subscription so you can create your own recipes)
and [uv](https://docs.astral.sh/uv/getting-started/installation/), which installs Python and the
server for you. No download of this project is needed.

### Claude Desktop

Open *Settings → Developer → Edit Config* and add the server to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cookidoo": {
      "command": "uvx",
      "args": ["mcp-cookidoo"],
      "env": {
        "COOKIDOO_EMAIL": "your-email@example.com",
        "COOKIDOO_PASSWORD": "your-password-here"
      }
    }
  }
}
```

Restart Claude Desktop. The Cookidoo tools now show up in the tool list.

### Claude Code

```bash
claude mcp add cookidoo -e COOKIDOO_EMAIL=your-email@example.com -e COOKIDOO_PASSWORD=your-password-here -- uvx mcp-cookidoo
```

### Other countries

The server uses the German Cookidoo by default. For another country add, for example,
`"COOKIDOO_COUNTRY": "fr"` and `"COOKIDOO_LANGUAGE": "fr-FR"` to `env`. The Thermomix settings in
steps are always written in German notation (see below).

### Running from a source checkout

For development, or if you prefer not to use uvx:

```bash
git clone https://github.com/tobilektri/mcp-cookidoo.git
cd mcp-cookidoo
python -m venv venv
source venv/bin/activate        # Windows: .\venv\Scripts\Activate.ps1
pip install -e ".[dev]"
cp .env.example .env            # then enter your Cookidoo login in .env
```

In the MCP client use the command `/path/to/mcp-cookidoo/venv/bin/mcp-cookidoo` (Windows:
`C:\\path\\to\\mcp-cookidoo\\venv\\Scripts\\mcp-cookidoo.exe`) instead of `uvx`. The `.env` file
stays on your computer and is excluded from git. `fastmcp run server.py` in the project folder
starts the server as well.

## Using it

Copy the example prompt below into your assistant and replace the dish in the first line. It
contains everything the assistant needs to know to get the Thermomix settings and ingredient links
right. You can write it in any language; the last rule decides the language of the recipe.

```text
Create a Thermomix recipe for [DISH, e.g. "vegetable curry for 4 people"] and save it to my
Cookidoo account with the Cookidoo tools.

Rules for the recipe:
- Ingredients: one per line, short and without preparation notes ("1 Zwiebel", not
  "1 Zwiebel, halbiert"). Notes like "halbiert" go into the step.
- Every ingredient must appear in a step exactly as written in the ingredient list, word for
  word, so that it is linked. Write "1 Zwiebel in den Mixtopf geben", not "die Zwiebel".
- Write each Thermomix setting in Cookidoo notation as time/temperature/speed, in German, e.g.
  "5 Sek./Stufe 5", "3 Min./120°C/Stufe 1", "15 Min./100°C/Linkslauf/Stufe 1" or
  "12 Min./100°C/Linkslauf/Sanftrührstufe".
- Use Thermomix modes (dough, turbo, blend, ...) where they fit, written exactly as
  get_thermomix_modes shows them, e.g. "Teig kneten/2 Min." or "Turbo/1 Sek.".
- Use only one Thermomix setting or mode per step; split longer processes into several steps.
- The recipe is for my [TM6 / TM7].
- Write the recipe in German.

Process:
1. Connect with connect_to_cookidoo.
2. Call get_thermomix_modes for my device and use only the modes and values it lists.
3. Check the recipe with generate_recipe_structure (with my device). If the output lists
   warnings, unlinked ingredients or unrecognised settings, fix the steps and check again until
   everything is linked.
4. Show me the recipe and wait for my OK.
5. Upload it with upload_custom_recipe and give me the recipe ID and link.
```

The assistant then works through these tools:

1. `connect_to_cookidoo` signs in.
2. `get_thermomix_modes` lists the modes Cookidoo offers for the device and how to write them.
3. `generate_recipe_structure` checks the recipe and reports detected settings, modes and links.
4. `upload_custom_recipe` saves it to your account and returns the recipe ID and link.

### Planning the week

You can also ask the assistant to find recipes and plan them, for example:

```text
Connect to Cookidoo. Find three quick vegetarian dinners (at most 30 minutes, for my TM6)
in the Cookidoo catalogue or among my own recipes, show them to me and, after my OK, plan
them for Monday to Wednesday next week and put their ingredients on my shopping list.
```

The assistant uses `search_recipes` and `list_my_recipes` to find recipes, `get_recipe_details`
to look at them, and `plan_recipe`, `get_week_plan` and `add_to_shopping_list` to plan and shop.

### All tools

| Tool | Purpose |
|---|---|
| `connect_to_cookidoo` | Sign in. Call this first. |
| `get_thermomix_modes(device="TM6")` | List the modes Cookidoo offers right now for the TM6 or TM7, with spelling and allowed values. |
| `search_recipes(query, ingredients, exclude_ingredients, max_total_time, difficulty, portions, device, limit, page)` | Search the Cookidoo catalogue. All filters are optional; Cookidoo returns up to 20 results per page. |
| `list_my_recipes()` | List your own recipes with ID, device and time. |
| `get_recipe_details(recipe_id)` | Show ingredients, steps and times of a catalogue recipe (`r59322`) or one of your own (`01M5…`). Steps of own recipes are shown in the notation `update_custom_recipe_steps` accepts. |
| `get_week_plan(day="")` | Show the recipes planned in the week starting at `day` (YYYY-MM-DD, default today). |
| `plan_recipe(day, recipe_ids)` | Plan one or more recipes (comma-separated, catalogue and own mixed) on a day. |
| `unplan_recipe(day, recipe_id)` | Remove a recipe from a day of the week plan. |
| `add_to_shopping_list(recipe_ids)` | Add the ingredients of recipes to the Cookidoo shopping list. |
| `generate_recipe_structure(name, ingredients, steps, servings, prep_time, total_time, hints, device="TM6")` | Validate a recipe and preview the detected settings, modes and links. |
| `upload_custom_recipe(recipe_json)` | Create the recipe on Cookidoo (pass the JSON from `generate_recipe_structure`). |
| `update_custom_recipe_steps(recipe_id, steps, ingredients="")` | Replace **all** steps of one of your recipes. The device is taken from the recipe. Without `ingredients`, the current ingredient list is loaded from Cookidoo. |

You don't have to call `get_thermomix_modes` for the checks to work: checking, uploading and
updating always read the modes from Cookidoo themselves before building the steps. Without a
connection, `generate_recipe_structure` uses a built-in list and says so.

Ingredients, steps and hints are passed one per line. List markers such as `1.` or `-` at the start
of a step are removed.

## Writing Thermomix settings

Write the settings into the step text the way Cookidoo prints them, as `time/temperature/speed`:

| In the step | Meaning |
|---|---|
| `4 Sek./Stufe 5` | 4 seconds, speed 5 |
| `3 Min./120°C/Stufe 1` | 3 minutes, 120 °C, speed 1 |
| `1 Min. 30 Sek./90°C/Stufe 2` | 1 minute 30 seconds, 90 °C, speed 2 |
| `15 Min./100°C/Linkslauf/Stufe 1` | reverse (counter-clockwise) |
| `12 Min./100°C/Linkslauf/Sanftrührstufe` | reverse with soft stir (`Stufe Sanftrühren` also works) |
| `20 Min./Varoma/Stufe 1` | Varoma temperature (TM6 only) |
| `10 Sek./Stufe 0,5` | speed 0.5 |

Example step:

```text
1 Zwiebel in den Mixtopf geben und 5 Sek./Stufe 5 zerkleinern.
```

Rules (the same ones the Cookidoo editor applies):

- Speeds **0.5 to 10** in half steps and soft stir are valid. The temperature is optional and one
  of the Thermomix steps from **37 to 120 °C** (37, 40, 45 … 95, 98, 100, 105, 110, 115, 120).
- With heating, the speed can be at most **6**.
- Times up to 5 minutes in 10-second steps, up to 20 minutes in half minutes, then whole minutes,
  at most 99 minutes. Other times are used, but the tool output warns about them.
- The notation is the German one (`Min.`, `Sek.`, `Stufe`, `Linkslauf`), whatever language the
  rest of the recipe is in.
- Invalid values (e.g. `Stufe 12` or `42°C`) stay plain text, and the tool output says why.
- **Not supported yet:** Fahrenheit.

## Thermomix modes

Write the mode name as Cookidoo shows it, then its values, separated by `/`:

| In the step | Mode | Device | Allowed values |
|---|---|---|---|
| `Teig kneten/2 Min.` | dough (also `Teigstufe`, `Teigmodus`) | TM6, TM7 | 1 second to 20 minutes |
| `Turbo/1 Sek.` | turbo | TM6, TM7 | 0.5, 1 or 2 seconds |
| `Turbo/1 Sek./3x` | turbo with pulses | TM7 | 1 to 9 pulses |
| `Pürieren/1 Min./Stufe 8` | blend | TM6, TM7 | 10 seconds to 5 minutes, speed 6 to 8 |
| `Erwärmen/65°C/Stufe 1` | warm up | TM6, TM7 | 37 to 90 °C, soft stir (default), speed 1 or 2 |
| `[Reis kochen]` | rice cooker | TM6, TM7 | none (the brackets mark it as a mode) |
| `Dampfgaren/20 Min./Stufe 1/im Varoma` | steaming | TM7 | up to 99 minutes, soft stir to speed 5, optional `Linkslauf`, `im Varoma` (default), `im Gareinsatz` or `in beidem` |
| `Anbraten/10 Min./160°C/Leicht` | browning | TM7 | 140 to 160 °C, up to 30 minutes (default 10), `Leicht` (default) or `Intensiv` |

In the recipe the step then shows the mode the way Cookidoo does (name, mode icon and time, e.g.
"Teig kneten" with the dough icon and "2 Min."), and tapping it starts the mode on the Thermomix.

The list above is the state of October 2026. The server reads the current list from Cookidoo
(`get_thermomix_modes`): a mode Cookidoo stops offering is no longer used, and a new one is listed
as "not supported yet" until the server knows its values.

## Ingredient links

An ingredient is linked when its line from the ingredient list appears **word for word** in a step.

| Ingredient list | Step | Linked? |
|---|---|---|
| `1 Zwiebel` | `1 Zwiebel und 1 Knoblauchzehe in den Mixtopf geben` | yes |
| `1 Zwiebel` | `Die Zwiebel in den Mixtopf geben` | no |

Short ingredient lines (`1 Zwiebel` instead of `1 Zwiebel, halbiert`) keep the steps readable.
The tool output lists which ingredients are linked and which are not.

Like the Cookidoo editor, the server replaces `;` with a full-width semicolon (`；`) in ingredients
and steps.

## Fixing an uploaded recipe

Forgot the settings, or a link is missing? Pass the recipe ID (from the upload output or the URL of
the recipe on Cookidoo) and the complete new list of steps to `update_custom_recipe_steps`. It
replaces all steps and leaves everything else alone.

## Development

The code lives in the `mcp_cookidoo` package. In a source checkout (see above) run the tests for
the settings, modes, links and recipe helpers with:

```bash
pytest
```

The files in `fixtures/` are the settings dialog of the Cookidoo editor (TM6 and TM7) and steps
the editor itself produced; the tests check that the server builds exactly the same.

Format and lint:

```bash
black .
ruff check .
```

### Releasing

1. Set the new version in `pyproject.toml`, `mcp_cookidoo/__init__.py`, `fastmcp.json` and
   twice in `server.json`.
2. Commit, then tag and push: `git tag v1.0.1 && git push origin v1.0.1`.

The GitHub Actions workflow `publish.yml` runs the tests, publishes the package to
[PyPI](https://pypi.org/project/mcp-cookidoo/) and the server to the
[MCP Registry](https://registry.modelcontextprotocol.io).

## Acknowledgments

This project started as a fork of [alexandrepa/mcp-cookidoo](https://github.com/alexandrepa/mcp-cookidoo)
by Alexandre Patelli, who built the first version of the server (login, recipe structure and
upload). Thank you!

It is built on top of [cookidoo-api](https://github.com/miaucl/cookidoo-api), which provides the
Python interface to the Cookidoo platform. Special thanks for making this integration possible!

## License

MIT, see [LICENSE](LICENSE).
