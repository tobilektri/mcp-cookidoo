"""
Cookidoo Service

Module to encapsulate all cookidoo-api logic for interacting with the Cookidoo platform.
"""

import os
from typing import Optional
from dotenv import find_dotenv, load_dotenv
from aiohttp import ClientSession
from cookidoo_api import Cookidoo, CookidooConfig
from cookidoo_api.helpers import (
    get_localization_options,
)
import asyncio
import sys
import time

from .modes import BUILTIN_CATALOG, ModeCatalog, device_from_tools, parse_editor_html
from .thermomix import build_instructions, normalize_text

# How long a mode catalog read from Cookidoo is reused before it is read again.
_CATALOG_TTL = 3600


def load_cookidoo_credentials() -> tuple[str, str]:
    """
    Load Cookidoo credentials from .env file.
    
    Returns:
        tuple[str, str]: Email and password
        
    Raises:
        ValueError: If credentials are not found in environment variables
    """
    # A .env next to the source code (git checkout) or in the working directory
    # (installed package); credentials set by the MCP client's config take precedence.
    load_dotenv()
    load_dotenv(find_dotenv(usecwd=True))
    
    email = os.getenv("COOKIDOO_EMAIL")
    password = os.getenv("COOKIDOO_PASSWORD")
    
    if not email or not password:
        raise ValueError(
            "Missing Cookidoo credentials. Please set COOKIDOO_EMAIL and "
            "COOKIDOO_PASSWORD in your .env file"
        )
    
    return email, password


class CookidooService:
    """Service class for managing Cookidoo API interactions."""
    
    def __init__(self, email: str, password: str):
        """
        Initialize the Cookidoo service with credentials.
        
        Args:
            email: Cookidoo account email
            password: Cookidoo account password
        """
        self.email = email
        self.password = password
        self._api_client: Optional[Cookidoo] = None
        self._session: Optional[ClientSession] = None
        self._catalog: Optional[ModeCatalog] = None
        self._catalog_time = 0.0
    
    async def login(self) -> Cookidoo:
        """
        Authenticate with Cookidoo and return the API client.
        
        Returns:
            Cookidoo: Authenticated Cookidoo API client
            
        Raises:
            Exception: If authentication fails
        """
        try:
            # Create aiohttp ClientSession with a timeout
            self._session = ClientSession()
            

            # Create CookidooConfig with credentials
            config = CookidooConfig(
                email=self.email,
                password=self.password,
                localization=(
                    await get_localization_options(
                        country=os.getenv("COOKIDOO_COUNTRY", "de"),
                        language=os.getenv("COOKIDOO_LANGUAGE", "de-DE"),
                    )
                )[0],
            )
            
            # Create Cookidoo API client with session and config
            self._api_client = Cookidoo(session=self._session, cfg=config)
            
            # Perform login (no parameters needed - uses config)
            await self._api_client.login()
            
            return self._api_client
            
        except Exception as e:
            # Clean up session if login fails
            if self._session:
                await self._session.close()
            raise Exception(f"Failed to authenticate with Cookidoo: {str(e)}") from e
    
    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session:
            await self._session.close()
    
    async def create_custom_recipe(
        self,
        name: str,
        ingredients: list[str],
        steps: list[str],
        servings: int = 4,
        prep_time: int = 30,
        total_time: int = 60,
        hints: Optional[list[str]] = None,
        device: str = "TM6",
    ) -> tuple[str, ModeCatalog, str]:
        """
        Create a completely new custom recipe from scratch using the undocumented API.
        
        Args:
            name: Recipe name
            ingredients: List of ingredient descriptions
            steps: List of cooking step descriptions
            servings: Number of servings (default: 4)
            prep_time: Preparation time in minutes (default: 30)
            total_time: Total cooking time in minutes (default: 60)
            hints: Optional list of hints/tips for the recipe
            device: Thermomix the recipe is for ("TM6" or "TM7")

        Returns:
            tuple: (created recipe ID, mode catalog the steps were built with, note -
            empty unless the built-in catalog had to be used)
            
        Raises:
            Exception: If recipe creation fails
        """
        try:
            base_url, locale, headers, api_session = self._request_context()

            # Step 1: Create the recipe with just the name
            create_url = f"{base_url}/created-recipes/{locale}"
            create_data = {"recipeName": name}
            
            async with api_session.post(
                create_url, json=create_data, headers=headers
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(
                        f"Failed to create recipe. Status: {response.status}, Error: {error_text}"
                    )
                
                result = await response.json()
                recipe_id = result.get("recipeId")
                
                if not recipe_id:
                    raise Exception("No recipe ID returned from creation")
            
            # The modes are read from the editor page of the new recipe, so the steps are
            # always built with what Cookidoo offers right now.
            catalog, note = await self.get_mode_catalog(recipe_id, refresh=True)

            # Step 2: Update recipe with ingredients
            update_url = f"{base_url}/created-recipes/{locale}/{recipe_id}"
            
            # PATCH requires a complete recipe structure with ALL required fields
            update_data = {
                "name": name,
                "image": None,  # Can be null or match pattern: ^((prod|nonprod)/img/customer-recipe/)?[A-Za-z0-9-_]{1,}.(bmp|jpe|jpeg|jpg|png)$
                "isImageOwnedByUser": False,
                "tools": [device],
                "yield": {"value": servings, "unitText": "portion"},
                "prepTime": prep_time * 60,  # Convert minutes to seconds
                "cookTime": 0,
                "totalTime": total_time * 60,  # Convert minutes to seconds
                "ingredients": [
                    {"type": "INGREDIENT", "text": normalize_text(ing)} for ing in ingredients
                ],
                # Thermomix settings ("3 Min./120°C/Stufe 1") and modes ("Teig kneten/
                # 2 Min.") in the step texts become TTS/MODE annotations (guided cooking);
                # ingredient lines that appear verbatim in a step become INGREDIENT
                # annotations (links).
                "instructions": build_instructions(steps, ingredients, catalog, device),
                "hints": "\n".join(hints) if hints and isinstance(hints, list) else (hints if hints else ""),
                "workStatus": "PRIVATE",
                "recipeMetadata": {
                    "requiresAnnotationsCheck": False
                }
            }
            
            await asyncio.sleep(5)

            async with api_session.patch(update_url, json=update_data, headers=headers) as response:
                response_text = await response.text()
                
                if response.status not in [200, 204]:
                    raise Exception(f"Failed to update recipe: {response_text}")
            
            return recipe_id, catalog, note
            
        except Exception as e:
            raise Exception(f"Failed to create custom recipe: {str(e)}") from e
    
    async def update_recipe_steps(
        self,
        recipe_id: str,
        steps: list[str],
        ingredients: Optional[list[str]] = None,
    ) -> tuple[list[str], str, ModeCatalog, str]:
        """
        Replace the instructions of an existing custom recipe.

        Only the instructions are sent (the Cookidoo editor does the same), so all other
        recipe fields stay untouched. Thermomix settings and modes inside the step texts
        are converted to TTS/MODE annotations and ingredient lines that appear verbatim
        in a step to INGREDIENT annotations (links). The device (TM6/TM7) is taken from
        the recipe and the modes from its editor page.

        Args:
            recipe_id: ID of a custom recipe, as returned by create_custom_recipe
            steps: New step texts
            ingredients: Ingredient lines to link. If None, the recipe's current
                ingredients are loaded from Cookidoo.

        Returns:
            tuple: (ingredient lines used for linking, device, mode catalog, notes -
            empty unless something had to fall back)

        Raises:
            Exception: If the update fails
        """
        try:
            base_url, locale, headers, api_session = self._request_context()
            loaded, device, recipe_note = await self._fetch_recipe_info(recipe_id)
            notes = []
            if ingredients is None:
                ingredients = loaded
                if recipe_note:
                    notes.append(f"Ingredient links skipped: {recipe_note}")
            if recipe_note:
                notes.append(f"Device unknown, built for the TM6: {recipe_note}")
            catalog, catalog_note = await self.get_mode_catalog(recipe_id, refresh=True)
            if catalog_note:
                notes.append(catalog_note)

            instructions = build_instructions(steps, ingredients, catalog, device)
            update_url = f"{base_url}/created-recipes/{locale}/{recipe_id}"

            async with api_session.patch(
                update_url, json={"instructions": instructions}, headers=headers
            ) as response:
                if response.status not in [200, 204]:
                    response_text = await response.text()
                    raise Exception(
                        f"Status: {response.status}, Error: {response_text}"
                    )

            return ingredients, device, catalog, "\n".join(notes)

        except Exception as e:
            raise Exception(f"Failed to update recipe steps: {str(e)}") from e

    async def _fetch_recipe_info(self, recipe_id: str) -> tuple[list[str], str, str]:
        """
        Load the ingredient lines and the device of a custom recipe.

        Returns:
            tuple: (ingredient lines, device, note). On failure the list is empty, the
            device is "TM6" and the note says why.
        """
        try:
            base_url, locale, headers, api_session = self._request_context()
            url = f"{base_url}/created-recipes/{locale}/{recipe_id}"
            async with api_session.get(url, headers=headers) as response:
                if response.status != 200:
                    return [], "TM6", f"could not load the recipe (status {response.status})."
                data = await response.json()

            content = data.get("recipeContent", {})
            lines = content.get("recipeIngredient") or [
                item.get("text", "") for item in content.get("ingredients", [])
            ]
            device = device_from_tools(content.get("tool") or content.get("tools"))
            return [line for line in lines if line], device, ""

        except Exception as e:
            return [], "TM6", f"could not load the recipe ({e})."

    def recipe_url(self, recipe_id: str) -> str:
        """Web address of a custom recipe on Cookidoo."""
        base_url, locale, _, _ = self._request_context()
        return f"{base_url}/created-recipes/{locale}/{recipe_id}"

    async def list_recipe_ids(self) -> list[str]:
        """IDs of the user's own (created) recipes, newest first."""
        base_url, locale, headers, api_session = self._request_context()
        async with api_session.get(
            f"{base_url}/created-recipes/{locale}", headers=headers
        ) as response:
            if response.status != 200:
                raise Exception(f"could not list recipes (status {response.status})")
            data = await response.json()
        return [item["recipeId"] for item in data.get("items", []) if item.get("recipeId")]

    async def get_mode_catalog(
        self, recipe_id: Optional[str] = None, refresh: bool = False
    ) -> tuple[ModeCatalog, str]:
        """
        Read the Thermomix modes Cookidoo offers from the recipe editor page.

        The editor page of any own recipe lists all modes, speeds, temperatures etc.
        (see modes.py). Without a recipe ID the newest own recipe is used. The result
        is reused for an hour unless ``refresh`` is set.

        Returns:
            tuple: (catalog, note). If the page cannot be read, the built-in catalog is
            returned and the note says why.
        """
        if (
            not refresh
            and self._catalog is not None
            and time.monotonic() - self._catalog_time < _CATALOG_TTL
        ):
            return self._catalog, ""
        try:
            base_url, locale, headers, api_session = self._request_context()
            if recipe_id is None:
                ids = await self.list_recipe_ids()
                if not ids:
                    return BUILTIN_CATALOG, (
                        "Modes: no own recipe yet to read them from Cookidoo, used the "
                        "built-in list (20.10.2026). Uploading reads them from Cookidoo."
                    )
                recipe_id = ids[0]
            url = (
                f"{base_url}/created-recipes/{locale}/{recipe_id}"
                "/edit/ingredients-and-preparation-steps"
            )
            async with api_session.get(
                url, headers={**headers, "Accept": "text/html"}
            ) as response:
                if response.status != 200:
                    raise Exception(f"status {response.status}")
                html = await response.text()
            self._catalog = parse_editor_html(html)
            self._catalog_time = time.monotonic()
            return self._catalog, ""
        except Exception as e:
            return BUILTIN_CATALOG, (
                f"Modes: could not read them from Cookidoo ({e}), used the built-in "
                "list (20.10.2026)."
            )

    def _request_context(self):
        """
        Build everything needed to call the undocumented created-recipes API.

        Returns:
            tuple: (base_url, locale, headers, aiohttp session)

        Raises:
            Exception: If not authenticated
        """
        if not self._api_client or not self._session:
            raise Exception("Not authenticated. Please call login() first.")

        # Get the access token from the authenticated client
        auth_data = self._api_client.auth_data
        if not auth_data:
            raise Exception("No authentication data available")

        localization = self._api_client.localization
        # Extract base domain from the URL (e.g., "https://cookidoo.fr/foundation/fr-FR" -> "https://cookidoo.fr")
        url_parts = localization.url.split("/")
        base_url = f"{url_parts[0]}//{url_parts[2]}"  # protocol + domain
        locale = localization.language

        # Headers for the undocumented API
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_data.access_token}",
        }

        # Use the API client's session to ensure cookies are shared
        return base_url, locale, headers, self._api_client._session

    @property
    def api_client(self) -> Optional[Cookidoo]:
        """Get the current API client instance."""
        return self._api_client
