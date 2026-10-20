# Cookidoo MCP Server

Let an AI assistant (Claude Desktop, Claude Code or any other MCP client) write Thermomix recipes and
save them straight into your [Cookidoo](https://cookidoo.de) account. These are real Cookidoo recipes
with guided cooking: the Thermomix settings are filled in, and ingredients mentioned in a step are
linked. You don't have to fix anything by hand in the Cookidoo editor.

> **Disclaimer:** This is an unofficial project. The developers are not affiliated with, endorsed by,
> or connected to Cookidoo, Vorwerk, Thermomix, or any of their subsidiaries or trademarks.

## What it can do

| Feature | What you get |
|---|---|
| **Connect to Cookidoo** | Signs in to your account with the credentials from your `.env` file. |
| **Look at existing recipes** | Fetches ingredients, steps and times of a Cookidoo catalogue recipe (for inspiration). |
| **Check a recipe before uploading** | Validates name, ingredients, steps, servings and times and shows which Thermomix settings and ingredient links were detected. |
| **Upload your own recipe** | Creates a new recipe in "My recipes" (*Meine Rezepte*) on Cookidoo. |
| **Thermomix settings (guided cooking)** | Settings such as `3 Min./120°C/Stufe 1` in a step become real Thermomix settings. Tap the step and the Thermomix is set up. Works with time, temperature, Varoma, speed, reverse (*Linkslauf*) and soft stir (*Sanftrührstufe*). |
| **Thermomix modes** | Dough, turbo, blend, warm up and rice cooker, and on the TM7 also steaming and browning (`Teig kneten/2 Min.`, `Turbo/1 Sek.` …). The server reads the available modes live from Cookidoo, so it follows when Cookidoo adds or removes one. |
| **TM6 or TM7** | Each recipe is made for one device; the server only uses what that device can do. |
| **Ingredient links** | When a step contains an ingredient line exactly as it appears in the ingredient list, it is shown as a link, as in recipes made with the Cookidoo editor. |
| **Fix an uploaded recipe** | Replaces the steps of a recipe you already uploaded, for example to add Thermomix settings later. Ingredients, times and hints stay unchanged. |

## Setup

You need **Python 3.12 or newer** and a **Cookidoo account** (with an active subscription so you can
create your own recipes).

### 1. Download the project

```bash
git clone https://github.com/tobilektri/mcp-cookidoo.git
cd mcp-cookidoo
```

### 2. Create a virtual environment and install the dependencies

macOS / Linux:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Windows (PowerShell):

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Enter your Cookidoo credentials

Copy the example file and fill in your login:

```bash
cp .env.example .env
```

```ini
COOKIDOO_EMAIL=your-email@example.com
COOKIDOO_PASSWORD=your-password-here

# Optional, defaults to the German Cookidoo
COOKIDOO_COUNTRY=de
COOKIDOO_LANGUAGE=de-DE
```

The `.env` file stays on your computer and is excluded from git.

### 4. Add the server to your MCP client

**Claude Desktop:** open *Settings → Developer → Edit Config* and add the server to
`claude_desktop_config.json`. Use absolute paths to your project folder:

```json
{
  "mcpServers": {
    "cookidoo": {
      "command": "/path/to/mcp-cookidoo/venv/bin/fastmcp",
      "args": ["run", "/path/to/mcp-cookidoo/server.py"]
    }
  }
}
```

On Windows the command is `C:\\path\\to\\mcp-cookidoo\\venv\\Scripts\\fastmcp.exe`.

If you have [uv](https://docs.astral.sh/uv/) installed, you can skip step 2 and the `.env` file.
uv installs the dependencies itself, and the credentials go into the config:

```json
{
  "mcpServers": {
    "cookidoo": {
      "command": "uv",
      "args": [
        "run", "--with", "fastmcp", "--with", "cookidoo-api", "--with", "python-dotenv",
        "--with", "pydantic", "fastmcp", "run", "/path/to/mcp-cookidoo/server.py", "--no-banner"
      ],
      "env": {
        "COOKIDOO_EMAIL": "your-email@example.com",
        "COOKIDOO_PASSWORD": "your-password-here"
      }
    }
  }
}
```

**Claude Code:**

```bash
claude mcp add cookidoo -- /path/to/mcp-cookidoo/venv/bin/fastmcp run /path/to/mcp-cookidoo/server.py
```

Restart the client. The Cookidoo tools now show up in the tool list.

To start the server on its own, for example to see whether it runs at all, use:

```bash
fastmcp run server.py
```

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

### All tools

| Tool | Purpose |
|---|---|
| `connect_to_cookidoo` | Sign in. Call this first. |
| `get_thermomix_modes(device="TM6")` | List the modes Cookidoo offers right now for the TM6 or TM7, with spelling and allowed values. |
| `get_recipe_details(recipe_id)` | Show a catalogue recipe, e.g. `r59322`. Does not work for your own recipes. |
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

Run the tests for the settings, modes and link detection:

```bash
pip install pytest
pytest test_thermomix.py test_modes.py
```

The files in `fixtures/` are the settings dialog of the Cookidoo editor (TM6 and TM7) and steps
the editor itself produced; the tests check that the server builds exactly the same.

Format and lint:

```bash
black .
ruff check .
```

## Acknowledgments

This project is built on top of [cookidoo-api](https://github.com/miaucl/cookidoo-api), which
provides the Python interface to the Cookidoo platform. Special thanks for making this integration
possible!

## License

MIT
