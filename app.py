"""MomentFinder: describe a moment, jump to it in the video."""
import subprocess
import sys
from pathlib import Path

import streamlit as st

from limits import take_daily_slot
from moment_search import search, to_seconds

ROOT = Path(__file__).parent
VIDEOS = ROOT / "videos"
EXAMPLES = [
    "golden retriever running",
    "something being pushed off a table",
    "a giraffe eating leaves",
    "ducks crossing a bridge",
]
SESSION_LIMIT = 5  # searches per visit
DAILY_LIMIT = 100  # searches per day, whole site
BADGE = {"seen": "👀", "heard": "👂", "both": "✨"}
COLORS = ["#7C3AED", "#EC4899", "#F59E0B", "#10B981", "#3B82F6", "#EF4444"]

CSS = """
<style>
.stApp {
    background:
        radial-gradient(900px 500px at 5% -10%, #EADDFF 0%, transparent 60%),
        radial-gradient(800px 500px at 100% 0%, #FFE3F1 0%, transparent 55%),
        #FBF8FF;
}
header[data-testid="stHeader"] { background: transparent; }
.hero { margin: 0 0 1.2rem 0; }
.hero h1 {
    font-size: 3.2rem; font-weight: 800; letter-spacing: -0.03em; margin: 0; padding: 0;
}
.hero h1 .grad {
    background: linear-gradient(90deg, #7C3AED, #EC4899 60%, #F59E0B);
    -webkit-background-clip: text; background-clip: text; color: transparent;
}
.hero p { margin: 0.3rem 0 0 0; font-size: 1.05rem; color: #5B4B7A; }

/* search box */
div[data-testid="stTextInput"] label p { font-weight: 700; color: #3B2A66; }
div[data-testid="stTextInput"] input {
    border-radius: 999px; padding: 0.85rem 1.2rem; font-size: 1.05rem;
    border: 2px solid #D9C8FF; background: #FFFFFF; box-shadow: 0 6px 18px rgba(124,58,237,.10);
}
div[data-testid="stTextInput"] input:focus { border-color: #7C3AED; box-shadow: 0 6px 22px rgba(124,58,237,.25); }

div[data-testid="InputInstructions"] { display: none; }

/* main button */
div[data-testid="stForm"] button {
    border: 0; border-radius: 999px; padding: 0.7rem 1rem; font-weight: 700; font-size: 1.05rem;
    background: linear-gradient(90deg, #7C3AED, #EC4899); color: #fff;
    box-shadow: 0 8px 20px rgba(236,72,153,.30); transition: transform .15s, box-shadow .15s;
}
div[data-testid="stForm"] button:hover { transform: translateY(-2px) scale(1.01); box-shadow: 0 12px 26px rgba(236,72,153,.40); color: #fff; }

/* example chips */
.st-key-chips button {
    border-radius: 999px; border: 1.5px dashed #C4A9FF; background: #FFFFFF; color: #5B2DD6;
    padding: 0.25rem 0.9rem; font-size: 0.9rem; transition: all .15s;
}
.st-key-chips button:hover { background: #7C3AED; color: #fff; border-style: solid; transform: rotate(-1.5deg) scale(1.04); }

/* video */
div[data-testid="stVideo"] video {
    border-radius: 20px; box-shadow: 0 18px 40px rgba(60,20,120,.22);
}

/* timeline */
.tl { margin: 1rem 0.2rem 0 0.2rem; }
.tl-track { position: relative; height: 14px; border-radius: 999px; background: #E6DAFB; }
.tl-seg { position: absolute; top: 0; height: 14px; border-radius: 999px; opacity: .75; transition: all .2s; }
.tl-seg.on { opacity: 1; top: -4px; height: 22px; box-shadow: 0 4px 12px rgba(0,0,0,.25); }
.tl-ends { display: flex; justify-content: space-between; font-size: .8rem; color: #7A6A99; margin-top: .45rem; }

/* result cards */
.st-key-results div[data-testid="stButton"] { width: 100%; }
.st-key-results button {
    width: 100%; justify-content: flex-start; text-align: left; border-radius: 16px; padding: 0.8rem 1rem;
    background: #FFFFFF; border: 1px solid #EADFFF; border-left: 8px solid var(--c, #7C3AED);
    box-shadow: 0 6px 16px rgba(60,20,120,.08); transition: transform .15s, box-shadow .15s;
    animation: pop .35s ease both;
}
.st-key-results button:hover { transform: translateX(6px); box-shadow: 0 10px 22px rgba(60,20,120,.16); }
.st-key-results button p { font-weight: 700; font-size: 1.05rem; }
.st-key-results [data-testid="stCaptionContainer"] { margin: .25rem .3rem 1rem 1rem; color: #4B3B6B; }
@keyframes pop { from { opacity: 0; transform: translateY(10px) scale(.97); } to { opacity: 1; transform: none; } }

section[data-testid="stSidebar"] { background: #F1EAFE; }
</style>
"""


def clock(seconds):
    s = int(round(seconds))
    return f"{s // 60}:{s % 60:02d}"


@st.cache_data
def video_seconds(path):
    """Length of the video via ffprobe; 0 if it is not available."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=15,
        ).stdout.strip()
        return float(out)
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


def timeline(moments, total, active):
    segs = ""
    for i, m in enumerate(moments):
        a, b = to_seconds(m.start), to_seconds(m.end)
        left = 100 * a / total
        width = max(100 * (b - a) / total, 1.6)
        segs += (
            f'<div class="tl-seg{" on" if i == active else ""}" '
            f'style="left:{left:.2f}%;width:{width:.2f}%;background:{COLORS[i % len(COLORS)]}"></div>'
        )
    return (
        f'<div class="tl"><div class="tl-track">{segs}</div>'
        f'<div class="tl-ends"><span>0:00</span><span>{clock(total)}</span></div></div>'
    )


@st.cache_resource
def remembered():
    """Answers to searches already run, shared by every visitor, so repeats cost nothing."""
    return {}


def set_query(q):
    st.session_state.query = q


def play(i, seconds):
    st.session_state.active = i
    st.session_state.start = int(seconds)
    st.session_state.autoplay = True  # only when the visitor clicks a result


st.set_page_config(page_title="MomentFinder", page_icon="🎯", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)
st.markdown(
    '<div class="hero"><h1>🎯 <span class="grad">MomentFinder</span></h1>'
    "<p>Describe what you remember. Jump straight to that moment in the video.</p></div>",
    unsafe_allow_html=True,
)

choices = sorted(p.name for p in VIDEOS.glob("*.mp4"))
if not choices:
    st.info("Put an .mp4 file in the videos/ folder.")
default = choices.index("animals-all.mp4") if "animals-all.mp4" in choices else 0

with st.sidebar:
    st.header("🎬 Video")
    picked = st.selectbox("Choose a video", choices, index=default if choices else None)
    st.caption("The first search on a new video uploads it to Gemini, which takes a short while.")

if not picked:
    st.stop()
video_path = VIDEOS / picked

st.session_state.setdefault("query", "")
st.session_state.setdefault("start", 0)
st.session_state.setdefault("active", 0)
st.session_state.setdefault("results", None)
st.session_state.setdefault("used", 0)

left, right = st.columns([3, 2], gap="large")

with right:
    with st.form("search", border=False):
        st.text_input(
            "What are you looking for?",
            key="query",
            placeholder="e.g. a golden retriever running with a ball",
        )
        go = st.form_submit_button("🔍 Find moment", type="primary", use_container_width=True)
    left_box = st.empty()
    st.caption("Try:")
    with st.container(key="chips"):
        for i, ex in enumerate(EXAMPLES):
            st.button(ex, key=f"ex{i}", on_click=set_query, args=(ex,))

    if go and st.session_state.query.strip():
        q = st.session_state.query.strip()
        memory = remembered()
        found = memory.get((picked, q.lower()))
        if st.session_state.used >= SESSION_LIMIT:
            st.warning(f"You've used your {SESSION_LIMIT} searches for this visit.")
        elif found is None and not take_daily_slot(DAILY_LIMIT):
            st.warning("Today's search limit for this demo has been reached. Please come back tomorrow.")
        else:
            with st.spinner("Watching the video..."):
                try:
                    moments, tokens = found or search(video_path, q)
                    memory[(picked, q.lower())] = (moments, tokens)
                    st.session_state.used += 1
                    st.session_state.results = (q, moments, tokens)
                    st.session_state.active = 0
                    if moments:
                        st.session_state.start = int(to_seconds(moments[0].start))
                        st.toast(f"{len(moments)} moment{'s' if len(moments) != 1 else ''} found", icon="🎉")
                except Exception as e:
                    st.session_state.results = None
                    print(f"Search failed: {e!r}", file=sys.stderr)  # kept in the server log only
                    st.error(
                        "Something went wrong with that search. Please try again in a minute. "
                        "If it keeps happening, the demo may be down for maintenance."
                    )

    left_box.caption(f"{max(SESSION_LIMIT - st.session_state.used, 0)} of {SESSION_LIMIT} searches left")

    res = st.session_state.results
    if res:
        q, moments, tokens = res
        if not moments:
            st.warning(f"No moment found for \"{q}\".")
        else:
            st.subheader(f"{len(moments)} moment{'s' if len(moments) != 1 else ''} found")
        active = st.session_state.active
        accents = "".join(
            f".st-key-card{i} button {{ --c: {COLORS[i % len(COLORS)]}; animation-delay: {i * 0.08}s; }}"
            for i in range(len(moments))
        )
        st.markdown(
            f"<style>{accents}"
            f".st-key-card{active} button {{ background: #F6F0FF; box-shadow: 0 0 0 2px {COLORS[active % len(COLORS)]}; }}"
            "</style>",
            unsafe_allow_html=True,
        )
        with st.container(key="results"):
            for i, m in enumerate(moments):
                badge = BADGE.get(m.source.lower(), "✨")
                label = f"{badge} {clock(to_seconds(m.start))} – {clock(to_seconds(m.end))}  ·  {m.source}"
                with st.container(key=f"card{i}"):
                    st.button(label, key=f"m{i}", on_click=play, args=(i, to_seconds(m.start)), width="stretch")
                    st.caption(m.description)
        st.caption(f"Gemini read {tokens:,} input tokens for this search.")

with left:
    st.video(str(video_path), start_time=st.session_state.start, autoplay=st.session_state.pop("autoplay", False))
    res = st.session_state.results
    total = video_seconds(str(video_path))
    if res and res[1]:
        total = total or max(to_seconds(m.end) for m in res[1]) * 1.1
        st.markdown(timeline(res[1], total, st.session_state.active), unsafe_allow_html=True)
