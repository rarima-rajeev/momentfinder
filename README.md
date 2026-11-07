# MomentFinder

Describe a moment you remember and jump straight to it in the video.

Type something like "a golden retriever running" or "something being pushed off a table". The
app asks Gemini to watch the video and returns the time ranges that match, as clickable cards and
a timeline. It searches by meaning, not by keyword or transcript.

## Demo video

`videos/animals-all.mp4` is about 78 seconds, joined from eight short clips generated with Gemini
(a dog, cat, hummingbird, cows, giraffe, puppy, ducklings, and a cat on a cow). All footage is
AI-generated. Visitors cannot upload their own videos.

## How it works

One fixed pipeline, not an agent: upload the video to Gemini once, send it with the search text,
get back a list of `MM:SS` ranges as structured JSON, and seek the player to the one you pick.
`moment_search.py` holds the search; `app.py` is the page.

## Limits

- 5 searches per visit and 100 searches per day for the whole site. Repeat searches are answered
  from memory and cost nothing.
- Your search text and the demo video are sent to Google's Gemini API.
- Timestamps come from a language model and can be off. Treat them as a starting point.

## Eval

`eval_key.json` lists 14 queries with the true time range of each, taken from the order the clips
were joined. `eval.py` runs them and counts a hit when a result starts within 3 seconds of a true
range.

First run: 13 of 13 queries found every true moment, and the query with no answer ("an elephant")
returned nothing. This is an easy test. The eight clips look very different from each other, and
the answer key only knows which clip each moment is in, not the exact second. Audio-only search
and slide or diagram search have not been tested yet.

## Run it yourself

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # then add your Gemini API key
.venv/bin/streamlit run app.py
```

`ffmpeg` is optional; without it the timeline falls back to an estimated video length.

To score the search: `.venv/bin/python eval.py`.
