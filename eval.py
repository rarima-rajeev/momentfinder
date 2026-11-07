"""Run the planted-moment queries against the video and score them.

A returned moment is correct if it starts within TOLERANCE seconds of a true window.
Usage: .venv/bin/python eval.py
"""
import json
from pathlib import Path

from moment_search import search, to_seconds

ROOT = Path(__file__).parent
TOLERANCE = 3.0


def near(t, window):
    return window[0] - TOLERANCE <= t <= window[1] + TOLERANCE


key = json.loads((ROOT / "eval_key.json").read_text())
video = ROOT / "videos" / key["video"]
rows, tokens_total = [], 0

for item in key["queries"]:
    moments, tokens = search(video, item["q"])
    tokens_total += tokens
    starts = [to_seconds(m.start) for m in moments]
    windows = item["windows"]
    found = sum(any(near(t, w) for t in starts) for w in windows)
    stray = sum(not any(near(t, w) for w in windows) for t in starts)
    if windows:
        ok = found == len(windows)
        verdict = "HIT" if ok else ("PARTIAL" if found else "MISS")
    else:
        verdict = "CLEAN" if not starts else "FALSE ALARM"
    rows.append((item["q"], verdict, found, len(windows), stray, [m.start for m in moments]))
    print(f"{verdict:12} {item['q'][:48]:48} found {found}/{len(windows)} stray {stray}  {[m.start for m in moments]}", flush=True)

scored = [r for r in rows if r[3] > 0]
hits = sum(r[1] == "HIT" for r in scored)
print(f"\n{hits}/{len(scored)} queries found every true moment within ±{TOLERANCE:.0f}s")
print(f"stray results (wrong moments): {sum(r[4] for r in rows)}")
print(f"negative query: {[r[1] for r in rows if r[3] == 0]}")
print(f"input tokens used: {tokens_total:,}")
