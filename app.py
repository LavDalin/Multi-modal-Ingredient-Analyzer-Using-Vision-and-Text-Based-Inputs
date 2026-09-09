import streamlit as st
import os
import sys
import time
import google.api_core.exceptions
from phi.agent import Agent
from phi.model.google import Gemini
from phi.tools.tavily import TavilyTools
from tempfile import NamedTemporaryFile
from PIL import Image
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from constants import SYSTEM_PROMPT, INSTRUCTIONS

def log(msg):
    """Print with a timestamp, flushed immediately, so it shows up live in
    Streamlit Cloud's log viewer instead of being buffered."""
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)

AGENT_TIMEOUT_SECONDS = 75

def run_with_timeout(fn, *args, timeout=AGENT_TIMEOUT_SECONDS, **kwargs):
    """Run fn in a background thread and enforce a hard wall-clock timeout.

    Some tool calls the agent can make (e.g. the Tavily web search, or the
    Gemini API itself) have no built-in timeout, so a slow/unreachable
    network call can hang agent.run() forever with no error and no log
    output. This bounds that wait so the UI always resolves.
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn, *args, **kwargs)
        try:
            return future.result(timeout=timeout)
        except FutureTimeoutError:
            raise TimeoutError(
                f"No response after {timeout}s — the AI service or web search is taking too "
                "long to respond. Please try again in a moment."
            )

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Ingredient Lens",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Baloo+2:wght@600;700;800&family=Nunito:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap');

/* ── Root / Background ── */
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background-color: #ffffff !important;
    background-image: none !important;
}
[data-testid="stHeader"], [data-testid="stToolbar"] {
    background: transparent !important;
}
section[data-testid="stMain"] > div {
    padding-top: 2rem;
}

/* ── Global type ── */
html, body, div, span, p, label, input, textarea, button {
    font-family: 'Nunito', 'Segoe UI', sans-serif !important;
    color: #3a3530;
}

/* ── Hide default Streamlit chrome ── */
#MainMenu, footer, [data-testid="stDecoration"] { display: none !important; }

/* ── Layout cap ── */
.block-container {
    max-width: 820px !important;
    padding: 0 24px 80px !important;
}

/* ── Header ── */
.app-header {
    border-bottom: 1px solid #ece4d6;
    padding-bottom: 24px;
    margin-bottom: 40px;
}
.app-badge {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    background: #eaf7ef;
    border: 1px solid #bfe6cc;
    border-radius: 20px;
    padding: 5px 13px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #1a8f5c;
    margin-bottom: 14px;
}
.badge-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: #22b36b;
    box-shadow: 0 0 8px rgba(34,179,107,0.6);
    display: inline-block;
    animation: badgePulse 2s ease-in-out infinite;
}
@keyframes badgePulse {
    0%,100% { box-shadow: 0 0 8px rgba(34,179,107,0.6); opacity: 1; }
    50%      { box-shadow: 0 0 3px rgba(34,179,107,0.4); opacity: 0.55; }
}
.app-title {
    font-family: 'Baloo 2', 'Arial Rounded MT Bold', sans-serif !important;
    font-weight: 800;
    font-size: clamp(32px, 5vw, 48px);
    letter-spacing: -0.01em;
    line-height: 1.1;
    background: linear-gradient(135deg, #1f6b46 0%, #2fb872 55%, #f6a94a 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0 0 8px;
}
.app-sub {
    color: #7a7267;
    font-size: 14.5px;
    letter-spacing: 0.01em;
    line-height: 1.7;
    margin: 0;
}

/* ── Section labels ── */
.section-label {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #a89f8e;
    margin-bottom: 14px;
}
.section-label::after {
    content: '';
    flex: 1;
    height: 1px;
    background: #ece4d6;
}

/* ── Content sections (no boxes — blend into the white page) ── */
.glass-card {
    background: transparent;
    padding: 0;
    margin-bottom: 24px;
}
.result-card {
    background: transparent;
    padding: 0;
    margin-bottom: 32px;
    position: relative;
    animation: fadeUp 0.4s ease;
    border-top: 2px solid #ffe4da;
    padding-top: 24px;
}
@keyframes fadeUp {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
}
.result-label {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #ff5a36;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    background: transparent !important;
}
[data-testid="stFileUploader"] > div {
    background: #fffdf8 !important;
    border: 2px dashed #e0d5bf !important;
    border-radius: 14px !important;
    transition: border-color 0.2s ease, background 0.2s ease !important;
}
[data-testid="stFileUploader"] > div:hover {
    border-color: #ff5a36 !important;
    background: #fff5f2 !important;
}
[data-testid="stFileUploader"] label {
    color: #b3aa9c !important;
    font-size: 13px !important;
}
[data-testid="stFileUploaderDropzone"] p,
[data-testid="stFileUploaderDropzone"] span,
[data-testid="stFileUploaderDropzone"] small {
    color: #b3aa9c !important;
}

/* ── Camera input ── */
[data-testid="stCameraInput"] video,
[data-testid="stCameraInput"] canvas {
    border-radius: 14px !important;
    border: 1px solid #ece4d6 !important;
}

/* ── Buttons ── */
[data-testid="stButton"] > button {
    font-family: 'Nunito', sans-serif !important;
    font-size: 13px !important;
    font-weight: 700 !important;
    letter-spacing: 0.03em !important;
    border-radius: 10px !important;
    transition: all 0.2s ease !important;
    border: none !important;
}
/* Primary buttons (analyze) */
[data-testid="stButton"]:has(button[kind="primary"]) button,
[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #ff7a52, #ff5a36) !important;
    color: #ffffff !important;
    padding: 11px 22px !important;
}
[data-testid="stButton"] > button[kind="primary"]:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 8px 22px rgba(255,90,54,0.32) !important;
}
/* Secondary buttons */
[data-testid="stButton"] > button[kind="secondary"],
[data-testid="stButton"] > button:not([kind]) {
    background: #ffffff !important;
    color: #ff5a36 !important;
    border: 1px solid #ffd9cc !important;
}
[data-testid="stButton"] > button:hover {
    border-color: #ff5a36 !important;
}

/* ── Text input ── */
[data-testid="stTextInput"] input,
[data-testid="stTextInput"] textarea {
    background: #ffffff !important;
    border: 1px solid #ece4d6 !important;
    border-radius: 10px !important;
    color: #3a3530 !important;
    caret-color: #000000 !important;
    font-family: 'Nunito', sans-serif !important;
    font-size: 14.5px !important;
    padding: 14px 16px !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: #ff5a36 !important;
    box-shadow: 0 0 0 3px rgba(255,90,54,0.14) !important;
}
[data-testid="stTextInput"] label {
    color: #a89f8e !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
}

/* ── Spinner ── */
[data-testid="stSpinner"] {
    color: #ff5a36 !important;
}

/* ── Alert / info boxes ── */
[data-testid="stAlert"] {
    background: #fdeeee !important;
    border: 1px solid #f4c6c6 !important;
    border-radius: 10px !important;
    color: #b23a3a !important;
}
[data-testid="stInfo"] {
    background: #eaf3fd !important;
    border: 1px solid #bfdcf7 !important;
    border-radius: 10px !important;
    color: #26588a !important;
}

/* ── Markdown output ── */
.stMarkdown p, .stMarkdown li, .stMarkdown span {
    color: #4a453d !important;
    font-size: 18px !important;
    line-height: 1.85 !important;
}
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 {
    font-family: 'Baloo 2', sans-serif !important;
    color: #ff5a36 !important;
    letter-spacing: -0.005em !important;
    font-weight: 700 !important;
}
.stMarkdown h1 {
    font-size: 34px !important;
    margin: 34px 0 16px !important;
}
.stMarkdown h2 {
    font-size: 27px !important;
    margin: 32px 0 14px !important;
}
.stMarkdown h3 {
    font-size: 21px !important;
    margin: 24px 0 10px !important;
}
.stMarkdown h4 {
    font-size: 17px !important;
    text-transform: uppercase;
    letter-spacing: 0.04em !important;
    margin: 18px 0 8px !important;
}
.stMarkdown h1:first-child, .stMarkdown h2:first-child, .stMarkdown h3:first-child {
    margin-top: 0 !important;
}
.stMarkdown strong { color: #1f1b16 !important; font-weight: 800 !important; }
.stMarkdown code {
    background: #f3f0e8 !important;
    border: 1px solid #e5ddc9 !important;
    border-radius: 5px !important;
    color: #b3701f !important;
    font-size: 13px !important;
    padding: 2px 6px !important;
}

/* ── Success / status ── */
.status-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 0;
    background: transparent;
    font-size: 12.5px;
    color: #7a7267;
    letter-spacing: 0.01em;
    margin-bottom: 14px;
}
.status-ok { color: #ff5a36; }

/* ── Q&A history ── */
.qa-block {
    background: transparent;
    padding: 0;
    padding-top: 18px;
    margin-bottom: 18px;
    border-top: 1px solid #f3ece6;
    animation: fadeUp 0.3s ease;
}
.qa-question {
    font-size: 13px;
    font-weight: 700;
    color: #2e73c9;
    margin-bottom: 10px;
    line-height: 1.6;
    letter-spacing: 0.01em;
}
.qa-divider {
    display: none;
}
.qa-answer {
    font-size: 14.5px;
    color: #4a453d;
    line-height: 1.85;
}
</style>
""", unsafe_allow_html=True)

# ── API keys ─────────────────────────────────────────────────────────────────
os.environ['TAVILY_API_KEY'] = st.secrets['TAVILY_KEY']
os.environ['GOOGLE_API_KEY'] = st.secrets['GEMINI_KEY']

# ── Agent ─────────────────────────────────────────────────────────────────────
@st.cache_resource
def get_agent():
    log("Creating agent (should only happen once per app instance)...")
    t0 = time.time()
    agent = Agent(
        model=Gemini(id="gemini-3.6-flash"),
        system_prompt=SYSTEM_PROMPT,
        instructions=INSTRUCTIONS,
        tools=[TavilyTools(api_key=os.getenv("TAVILY_API_KEY"), search_depth="basic")],
        markdown=True,
        show_tool_calls=True,
    )
    log(f"Agent created in {time.time() - t0:.2f}s")
    return agent

# ── Helpers ───────────────────────────────────────────────────────────────────
MAX_IMAGE_WIDTH = 300

def resize_image_for_display(image_file):
    if isinstance(image_file, str):
        img = Image.open(image_file)
    else:
        img = Image.open(image_file)
        image_file.seek(0)
    aspect_ratio = img.height / img.width
    new_height = int(MAX_IMAGE_WIDTH * aspect_ratio)
    img = img.resize((MAX_IMAGE_WIDTH, new_height), Image.Resampling.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

ANALYSIS_MAX_DIMENSION = 1600  # px, longest side — plenty to read a label, much lighter than a raw phone photo

def save_uploaded_file(uploaded_file, max_dimension=ANALYSIS_MAX_DIMENSION, quality=85):
    """Save the upload to a temp file, downscaled/compressed for the AI call.

    Phone photos can be 4000px+ on a side and several MB — sending that
    straight to the model adds real upload + processing latency. Ingredient
    text is still perfectly legible at 1600px, so we shrink and re-encode
    as JPEG before analysis (the on-screen preview is handled separately by
    resize_image_for_display and is unaffected).
    """
    img = Image.open(uploaded_file).convert("RGB")
    w, h = img.size
    if max(w, h) > max_dimension:
        scale = max_dimension / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    with NamedTemporaryFile(dir='.', suffix='.jpg', delete=False) as f:
        img.save(f, format="JPEG", quality=quality, optimize=True)
        return f.name

def analyze_image(image_path):
    agent = get_agent()
    size_kb = os.path.getsize(image_path) / 1024
    log(f"analyze_image start — file={image_path} size={size_kb:.0f}KB")
    with st.spinner('Analyzing image... this can take up to a minute'):
        t0 = time.time()
        try:
            response = run_with_timeout(
                agent.run, "Analyze the given image", images=[image_path]
            )
            log(f"analyze_image done in {time.time() - t0:.2f}s")
            st.session_state.ingredients = response.content
            st.markdown(
                '<div class="result-label">◈ &nbsp; Ingredient Report</div>',
                unsafe_allow_html=True,
            )
            st.markdown(response.content)
        except google.api_core.exceptions.ResourceExhausted:
            log(f"analyze_image ResourceExhausted after {time.time() - t0:.2f}s")
            st.error("⚠️ Google's Free Tier quota is temporarily exhausted.")
            st.info("This usually resets every 60 seconds — please wait a moment and try again.")
        except TimeoutError as e:
            log(f"analyze_image TIMED OUT after {time.time() - t0:.2f}s: {e}")
            st.error(f"⏱️ {e}")
        except Exception as e:
            log(f"analyze_image FAILED after {time.time() - t0:.2f}s: {type(e).__name__}: {e}")
            st.error(f"An unexpected error occurred: {e}")

# ── App ───────────────────────────────────────────────────────────────────────
def main():
    # Session state
    if 'ingredients' not in st.session_state:
        st.session_state.ingredients = None
    if 'show_camera' not in st.session_state:
        st.session_state.show_camera = False
    if 'qa_history' not in st.session_state:
        st.session_state.qa_history = []

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="app-header">
        <div class="app-badge"><span class="badge-dot"></span> AI&nbsp;Powered</div>
        <h1 class="app-title">Ingredient Lens</h1>
        <p class="app-sub">Upload a product photo · Get instant ingredient analysis · Ask follow-up questions</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Upload Section ────────────────────────────────────────────────────────
    st.markdown('<div class="section-label">01 — Upload Photo</div>', unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "Drop your image here or click to browse",
        type=["jpg", "jpeg", "png"],
        help="Upload a clear photo of the product's ingredient label",
        label_visibility="collapsed",
    )

    if uploaded_file:
        resized = resize_image_for_display(uploaded_file)
        col_img, col_btn = st.columns([1, 2])
        with col_img:
            st.image(resized, use_container_width=False, width=MAX_IMAGE_WIDTH)
        with col_btn:
            st.markdown(
                f'<div class="status-bar"><span class="status-ok">✓</span> {uploaded_file.name}</div>',
                unsafe_allow_html=True,
            )
            analyze_clicked = st.button("⬡ &nbsp; Analyze Photo", key="analyze_upload", type="primary")
        if analyze_clicked:
            temp_path = save_uploaded_file(uploaded_file)
            st.markdown('<div class="result-card">', unsafe_allow_html=True)
            analyze_image(temp_path)
            st.markdown('</div>', unsafe_allow_html=True)
            os.unlink(temp_path)

    # ── Camera Section ────────────────────────────────────────────────────────
    st.markdown('<div class="section-label">02 — Take Photo</div>', unsafe_allow_html=True)

    if not st.session_state.show_camera:
        if st.button("⬡ &nbsp; Open Camera", key="open_camera"):
            st.session_state.show_camera = True
    else:
        camera_photo = st.camera_input("Point at the ingredient label and capture")
        if camera_photo:
            resized = resize_image_for_display(camera_photo)
            col_img, col_btn = st.columns([1, 2])
            with col_img:
                st.image(resized, use_container_width=False, width=MAX_IMAGE_WIDTH)
            with col_btn:
                st.markdown(
                    '<div class="status-bar"><span class="status-ok">✓</span> Camera capture ready</div>',
                    unsafe_allow_html=True,
                )
                analyze_clicked = st.button("⬡ &nbsp; Analyze Photo", key="analyze_camera", type="primary")
            if analyze_clicked:
                temp_path = save_uploaded_file(camera_photo)
                st.markdown('<div class="result-card">', unsafe_allow_html=True)
                analyze_image(temp_path)
                st.markdown('</div>', unsafe_allow_html=True)
                os.unlink(temp_path)
            st.session_state.show_camera = False

    # ── Q&A Section ───────────────────────────────────────────────────────────
    st.markdown('<div class="section-label">03 — Ask Questions</div>', unsafe_allow_html=True)

    user_question = st.text_input(
        "Question",
        placeholder="e.g. Is this safe for someone with a gluten allergy?",
        label_visibility="collapsed",
    )

    if user_question:
        agent = get_agent()
        if st.session_state.ingredients:
            prompt = f"""You are a product ingredient expert. Here is the extracted ingredient list:

{st.session_state.ingredients}

Now answer this question specifically based on the ingredients above:
{user_question}"""
        else:
            prompt = user_question

        with st.spinner("Processing your question..."):
            try:
                response = run_with_timeout(agent.run, prompt)
                st.session_state.qa_history.append({
                    "q": user_question,
                    "a": response.content,
                })
            except TimeoutError as e:
                st.error(f"⏱️ {e}")
            except Exception as e:
                st.error(f"Error: {e}")

    # Render Q&A history (newest first)
    for item in reversed(st.session_state.qa_history):
        st.markdown(f"""
        <div class="qa-block">
            <div class="qa-question">▸ &nbsp;{item['q']}</div>
            <div class="qa-divider"></div>
            <div class="qa-answer">{item['a']}</div>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()