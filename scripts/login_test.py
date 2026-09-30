"""Manual live test: python scripts/login_test.py  (prompts for password and OTP).

Run from the repo root inside the test venv. Nothing is stored or printed except
counts, so it is safe to paste the output.
"""

import asyncio
import getpass
import importlib.util
import sys
import types
from pathlib import Path

import aiohttp

base = Path(__file__).resolve().parent.parent / "custom_components" / "minijob_manager"
pkg = types.ModuleType("mm")
pkg.__path__ = [str(base)]
sys.modules["mm"] = pkg


def load(name):
    spec = importlib.util.spec_from_file_location(f"mm.{name}", base / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"mm.{name}"] = mod
    spec.loader.exec_module(mod)
    return mod


const, api = load("const"), load("api")


async def main() -> None:
    user = input("E-Mail: ")
    pw = getpass.getpass("Passwort: ")
    async with aiohttp.ClientSession() as s:
        login = api.MinijobLogin(s)
        await login.start(user, pw)
        print("Passwort ok, Code per E-Mail unterwegs")
        tokens = await login.finish(input("Code: "))
        client = api.MinijobClient(s, tokens)
        partner = await client.get("geschaeftspartner/geschaeftspartnernummer")
        print("Beschäftigte:", partner["mjmDaten"]["anzahlBeschaeftigter"])
        emps = await client.get_all_pages("meldezeiten", {"sort": "nachname"})
        print("Meldezeiten-Einträge:", len(emps))
        print("Beitragszeilen:", len(await client.get("beitraege", {"from": "2025-01-01"})))
        await client._refresh()
        print("Refresh ok, neue Laufzeit (s):", int(client.tokens["refresh_expires_at"] - __import__("time").time()))


asyncio.run(main())
