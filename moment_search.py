"""Search a video with Gemini. Shared by the app and the eval."""
import json
import os
import time
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values
from google import genai
from google.genai import types
from pydantic import BaseModel

ROOT = Path(__file__).parent
UPLOAD_CACHE = ROOT / ".upload_cache.json"
MODEL = "gemini-3.8-flash"

PROMPT = """You are searching a video, both what is shown and what is heard, for moments that match a description.

Description: "{query}"

Rules:
- Match by meaning. The description does not have to use the words that appear on screen or in the audio.
- Return every distinct moment that matches. If nothing matches, return an empty list. Do not guess.
- start and end are timestamps from the very start of the video, written as MM:SS (for example 01:07).
- source is "seen" if it is visible only, "heard" if it is audible only, "both" if either.
- description is one short sentence saying what happens at that moment."""


class Moment(BaseModel):
    start: str
    end: str
    source: str
    description: str


def to_seconds(stamp):
    """Turn "MM:SS" (or "H:MM:SS") into seconds; 0 if Gemini sends something unreadable."""
    try:
        total = 0
        for part in stamp.strip().split(":"):
            total = total * 60 + float(part)
        return total
    except ValueError:
        return 0


@lru_cache(maxsize=1)
def client():
    key = os.environ.get("GEMINI_API_KEY") or dotenv_values(ROOT / ".env").get("GEMINI_API_KEY", "")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set. Add it to the .env file or the host's secrets.")
    return genai.Client(api_key=key, http_options=types.HttpOptions(api_version="v1beta"))


def _load_cache():
    try:
        return json.loads(UPLOAD_CACHE.read_text())
    except (OSError, ValueError):
        return {}


def gemini_file(path):
    """Upload the video once; reuse it while Gemini still holds it (about 48 hours)."""
    c = client()
    cache = _load_cache()
    key = f"{path.name}:{path.stat().st_size}"
    if key in cache:
        try:
            f = c.files.get(name=cache[key])
            if f.state.name == "ACTIVE":
                return f
        except Exception:
            pass
    f = c.files.upload(file=str(path))
    while f.state.name == "PROCESSING":
        time.sleep(2)
        f = c.files.get(name=f.name)
    if f.state.name != "ACTIVE":
        raise RuntimeError(f"Gemini could not process the video ({f.state.name}).")
    cache[key] = f.name
    UPLOAD_CACHE.write_text(json.dumps(cache))
    return f


def search(path, query):
    """Return (moments sorted by start time, input tokens used)."""
    f = gemini_file(path)
    response = client().models.generate_content(
        model=MODEL,
        contents=[
            types.Part.from_uri(file_uri=f.uri, mime_type=f.mime_type),
            PROMPT.format(query=query),
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=list[Moment],
            temperature=0,
        ),
    )
    moments = sorted(response.parsed or [], key=lambda m: to_seconds(m.start))
    return moments, response.usage_metadata.prompt_token_count
