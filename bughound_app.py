import difflib
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from bughound_agent import BugHoundAgent
from codereview.ui_review import (
    FileValidationError,
    apply_preview,
    build_cleanup_preview,
    build_review_preview,
    validate_python_file,
)
from llm_client import MockClient, OpenAIClient

APP_DIR = Path(__file__).resolve().parent
ENV_FILE = APP_DIR / ".env"

# ----------------------------
# App setup
# ----------------------------
st.set_page_config(page_title="BugHound", page_icon="🐶", layout="wide")


def apply_glass_theme() -> None:
    """Apply a restrained dark glass skin to Streamlit's default components."""
    st.markdown(
        """
        <style>
        :root {
            --app-bg: #090d13;
            --panel: rgba(18, 24, 33, 0.72);
            --panel-solid: #121821;
            --panel-soft: rgba(255, 255, 255, 0.045);
            --border: rgba(226, 232, 240, 0.12);
            --border-strong: rgba(226, 232, 240, 0.22);
            --text: #e5edf7;
            --muted: #93a4b8;
            --primary: #67e8f9;
            --primary-strong: #22d3ee;
            --primary-soft: rgba(103, 232, 249, 0.12);
            --shadow: 0 18px 48px rgba(0, 0, 0, 0.32);
        }

        .stApp {
            color: var(--text);
            background:
                linear-gradient(180deg, rgba(103, 232, 249, 0.055), transparent 22rem),
                linear-gradient(180deg, var(--app-bg), #0c1118 48%, #090d13);
            background-attachment: fixed;
        }

        [data-testid="stHeader"] {
            background: rgba(9, 13, 19, 0.92);
            border-bottom: 1px solid var(--border);
            backdrop-filter: blur(18px);
            -webkit-backdrop-filter: blur(18px);
        }

        [data-testid="stToolbar"] {
            background: transparent;
        }

        [data-testid="stHeader"] button,
        [data-testid="stToolbar"] button {
            color: var(--text);
        }

        .block-container {
            max-width: 1240px;
            padding-top: 2.25rem;
            padding-bottom: 3rem;
        }

        h1, h2, h3, h4, h5, h6, p, label {
            letter-spacing: 0;
        }

        h1 {
            color: var(--text);
            font-weight: 800;
            margin-bottom: 0.15rem;
        }

        [data-testid="stCaptionContainer"] {
            color: var(--muted);
        }

        [data-testid="stSidebar"] {
            background: rgba(9, 13, 19, 0.84);
            border-right: 1px solid var(--border);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
        }

        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            gap: 0.9rem;
        }

        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
            color: var(--text);
        }

        [data-testid="stSidebar"] hr,
        [data-testid="stMarkdownContainer"] hr {
            border-color: var(--border);
        }

        [data-testid="stTabs"] [role="tablist"] {
            gap: 0.25rem;
            padding: 0.35rem;
            margin-bottom: 1.15rem;
            width: fit-content;
            border: 1px solid var(--border);
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.04);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
        }

        [data-testid="stTabs"] [role="tab"] {
            min-height: 2.4rem;
            padding: 0.35rem 1rem;
            color: var(--muted);
            border-radius: 8px;
        }

        [data-testid="stTabs"] [role="tab"][aria-selected="true"] {
            color: #041014;
            background: var(--primary);
            font-weight: 700;
        }

        [data-testid="stStatusWidget"],
        [data-testid="stExpander"],
        [data-testid="stMetric"],
        [data-testid="stAlert"] {
            border: 1px solid var(--border);
            border-radius: 8px;
            background: var(--panel);
            box-shadow: var(--shadow);
            backdrop-filter: blur(18px);
            -webkit-backdrop-filter: blur(18px);
        }

        [data-testid="stMetric"] {
            padding: 0.85rem 1rem;
        }

        [data-testid="stMetricValue"] {
            color: var(--primary);
        }

        [data-testid="stTextArea"] textarea,
        [data-testid="stTextInput"] input,
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        [data-testid="stNumberInput"] input {
            color: var(--text);
            border: 1px solid var(--border);
            border-radius: 8px;
            background: rgba(8, 12, 18, 0.82);
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);
        }

        [data-testid="stTextArea"] textarea:focus,
        [data-testid="stTextInput"] input:focus {
            border-color: rgba(103, 232, 249, 0.7);
            box-shadow: 0 0 0 1px rgba(103, 232, 249, 0.24);
        }

        [data-testid="stButton"] button {
            min-height: 2.6rem;
            color: var(--text);
            border: 1px solid var(--border-strong);
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.06);
            box-shadow: 0 10px 24px rgba(0, 0, 0, 0.20);
            transition: border-color 140ms ease, background 140ms ease, transform 140ms ease;
        }

        [data-testid="stButton"] button:hover {
            border-color: rgba(103, 232, 249, 0.58);
            background: var(--primary-soft);
            transform: translateY(-1px);
        }

        [data-testid="stButton"] button[kind="primary"],
        [data-testid="stButton"] button[kind="primaryFormSubmit"] {
            color: #031116;
            border-color: var(--primary-strong);
            background: var(--primary);
            font-weight: 800;
        }

        [data-testid="stButton"] button:disabled {
            color: rgba(238, 242, 246, 0.35);
            border-color: rgba(255, 255, 255, 0.08);
            background: rgba(255, 255, 255, 0.045);
            box-shadow: none;
            transform: none;
        }

        [data-testid="stCodeBlock"],
        pre {
            border: 1px solid var(--border);
            border-radius: 8px;
            background: rgba(5, 8, 13, 0.92) !important;
        }

        code {
            color: #dce9f9;
        }

        [data-testid="stJson"] {
            border: 1px solid var(--border);
            border-radius: 8px;
            background: rgba(5, 8, 13, 0.92);
        }

        div[data-baseweb="popover"],
        ul[role="listbox"] {
            border: 1px solid var(--border);
            background: var(--panel-solid);
            backdrop-filter: blur(18px);
            -webkit-backdrop-filter: blur(18px);
        }

        [data-testid="stAlert"] {
            color: var(--text);
        }

        [data-testid="stAlert"] div {
            color: inherit;
        }

        [data-testid="stDecoration"] {
            background: var(--primary);
        }

        @media (max-width: 760px) {
            .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
            }

            [data-testid="stTabs"] [role="tab"] {
                padding-left: 0.7rem;
                padding-right: 0.7rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


apply_glass_theme()
st.title("🐶 BugHound")
st.caption(
    "Analyze snippets with the starter agent, or preview codereview comments and focused rewrites for local Python files."
)

# Load environment variables from the project .env, independent of launch cwd.
load_dotenv(dotenv_path=ENV_FILE)

# ----------------------------
# Helpers
# ----------------------------
SAMPLE_SNIPPETS = {
    "print_spam.py": """def greet(name):
    print("Hello", name)
    print("Welcome!")
    return True
""",
    "flaky_try_except.py": """def load_data(path):
    try:
        data = open(path).read()
    except:
        return None
    return data
""",
    "mixed_issues.py": """# TODO: replace with real implementation
def compute(x, y):
    print("computing...")
    try:
        return x / y
    except:
        return 0
""",
    "cleanish.py": """import logging

def add(a, b):
    logging.info("Adding numbers")
    return a + b
""",
}


def render_diff(original: str, revised: str) -> str:
    """Return a unified diff string."""
    diff_lines = difflib.unified_diff(
        original.splitlines(),
        revised.splitlines(),
        fromfile="original",
        tofile="fixed",
        lineterm="",
    )
    return "\n".join(diff_lines)


def require_code_input(code: str) -> bool:
    if not code.strip():
        st.warning("Paste some code or load a sample snippet to begin.")
        return False
    return True


def get_snippet_client(mode: str, model_name: str, temperature: float):
    """Build the selected BugHound snippet client."""
    if mode == "Heuristic only (no API)":
        return MockClient(), "Using MockClient. No network calls."

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None, f"Missing OPENAI_API_KEY. Expected .env at {ENV_FILE}."
    return OpenAIClient(model_name=model_name, temperature=temperature), "OpenAI client ready."


# ----------------------------
# Sidebar controls
# ----------------------------
st.sidebar.header("Settings")

mode = st.sidebar.selectbox(
    "Snippet model mode",
    [
        "Heuristic only (no API)",
        "OpenAI (requires API key)",
    ],
    help="Heuristic mode runs fully offline. OpenAI mode calls the OpenAI API for analysis and fix proposal.",
)

if mode == "OpenAI (requires API key)":
    st.sidebar.warning("API mode uses your OpenAI key. Use Heuristic mode for quick offline demos.")

model_name = st.sidebar.selectbox(
    "OpenAI model",
    ["gpt-5.4-mini", "gpt-5.4"],
    disabled=(mode != "OpenAI (requires API key)"),
)

temperature = st.sidebar.slider(
    "Temperature",
    min_value=0.0,
    max_value=1.0,
    value=0.2,
    step=0.1,
    disabled=(mode != "OpenAI (requires API key)"),
    help="Lower values tend to be more consistent. Higher values tend to be more creative.",
)

st.sidebar.divider()

sample_choice = st.sidebar.selectbox(
    "Load a sample snippet",
    ["(none)"] + list(SAMPLE_SNIPPETS.keys()),
)

show_debug = st.sidebar.checkbox("Show debug details", value=False)

client, client_status = get_snippet_client(mode, model_name, temperature)
st.sidebar.info(client_status)

snippet_tab, file_tab = st.tabs(["Snippet Review", "File Review Chat"])


with snippet_tab:
    # ----------------------------
    # Main input
    # ----------------------------
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("Input code")
        if sample_choice != "(none)":
            default_code = SAMPLE_SNIPPETS[sample_choice]
        else:
            default_code = st.session_state.get("code_input", "")

        code_input = st.text_area(
            "Paste a Python snippet",
            value=default_code,
            height=320,
            placeholder="Paste code here...",
            label_visibility="collapsed",
        )
        st.session_state["code_input"] = code_input

        run_button = st.button("Run BugHound", type="primary", use_container_width=True)

    with col_right:
        st.subheader("Outputs")
        st.write("Run the workflow to see issues, a proposed fix, and a risk report.")

    # ----------------------------
    # Run workflow
    # ----------------------------
    if run_button:
        if not require_code_input(code_input):
            st.stop()

        if mode == "OpenAI (requires API key)" and client is None:
            st.error("OpenAI mode is selected, but no API key is available.")
            st.stop()

        agent = BugHoundAgent(client=client)

        with st.spinner("BugHound is running the snippet workflow..."):
            result = agent.run(code_input)

        issues = result.get("issues", [])
        fixed_code = result.get("fixed_code", "")
        risk = result.get("risk", {})
        logs = result.get("logs", [])

        res_left, res_right = st.columns([1, 1])

        with res_left:
            st.subheader("Detected issues")
            if not issues:
                st.success("No issues detected by the current analyzer.")
            else:
                for i, issue in enumerate(issues, start=1):
                    issue_type = issue.get("type", "Issue")
                    severity = issue.get("severity", "Unknown")
                    msg = issue.get("msg", "").strip()

                    badge = f"{issue_type} | {severity}"
                    st.markdown(f"**{i}. {badge}**")
                    if msg:
                        st.write(msg)

        with res_right:
            st.subheader("Risk report")
            if not risk:
                st.info("No risk report was produced.")
            else:
                score = risk.get("score", None)
                level = risk.get("level", "unknown")
                should_autofix = risk.get("should_autofix", None)
                reasons = risk.get("reasons", [])

                top_cols = st.columns(3)
                with top_cols[0]:
                    st.metric("Risk level", str(level).upper())
                with top_cols[1]:
                    st.metric("Score", "-" if score is None else int(score))
                with top_cols[2]:
                    st.metric("Auto-fix?", "-" if should_autofix is None else ("YES" if should_autofix else "NO"))

                if reasons:
                    st.write("**Reasons:**")
                    for reason in reasons:
                        st.write(f"- {reason}")

        st.divider()

        if any("API Error" in log.get("message", "") for log in logs):
            st.warning("API request failed; BugHound used heuristic rules instead.")

        st.subheader("Proposed fix")
        if not fixed_code.strip():
            st.warning("No fix was produced. This can happen if the agent refused or had parsing errors.")
        else:
            fix_cols = st.columns([1, 1])

            with fix_cols[0]:
                st.text_area("Fixed code", value=fixed_code, height=320)

            with fix_cols[1]:
                diff_text = render_diff(code_input, fixed_code)
                st.text_area("Diff (unified)", value=diff_text, height=320)

        st.divider()

        st.subheader("Agent trace")
        if not logs:
            st.info("No trace logs were produced.")
        else:
            for entry in logs:
                step = entry.get("step", "LOG")
                message = entry.get("message", "")
                st.write(f"**{step}:** {message}")

        if show_debug:
            st.divider()
            st.subheader("Debug payload")
            st.json(result)


with file_tab:
    st.subheader("Local file review")
    path_input = st.text_input(
        "Python file path",
        value=st.session_state.get("file_review_path", "trial/buggy_service.py"),
        placeholder="/path/to/file.py",
    )
    st.session_state["file_review_path"] = path_input

    instruction = st.text_area(
        "Review instruction",
        value=st.session_state.get("file_review_instruction", "review this file"),
        height=100,
    )
    st.session_state["file_review_instruction"] = instruction

    target = None
    file_text = ""
    try:
        target = validate_python_file(path_input)
        file_text = target.read_text(encoding="utf-8")
    except FileValidationError as exc:
        st.warning(str(exc))
    except UnicodeDecodeError:
        st.error("The selected file could not be read as UTF-8 text.")

    preview_cols = st.columns([1, 1])
    with preview_cols[0]:
        st.button(
            "Preview review",
            type="primary",
            use_container_width=True,
            disabled=(target is None),
            key="preview_review_button",
        )
    with preview_cols[1]:
        st.button(
            "Preview cleanup",
            use_container_width=True,
            disabled=(target is None),
            key="preview_cleanup_button",
        )

    if st.session_state.get("preview_review_button") and target is not None:
        try:
            live_logs: list[str] = []
            with st.status("Running codereview agent loop...", expanded=True) as status:
                trace_placeholder = st.empty()

                def show_live_log(message: str) -> None:
                    live_logs.append(message)
                    trace_placeholder.markdown(
                        "\n".join(f"- **codereview:** {entry}" for entry in live_logs)
                    )

                st.session_state["file_review_preview"] = build_review_preview(
                    target,
                    instruction,
                    log_sink=show_live_log,
                )
                status.update(label="codereview preview ready", state="complete")
        except (FileValidationError, RuntimeError, ValueError) as exc:
            st.error(str(exc))

    if st.session_state.get("preview_cleanup_button") and target is not None:
        st.session_state["file_review_preview"] = build_cleanup_preview(target)

    st.divider()
    st.subheader("File preview")
    if file_text:
        st.code(file_text, language="python", line_numbers=True)
    else:
        st.info("Select a local Python file to preview its contents.")

    preview = st.session_state.get("file_review_preview")
    if preview is not None:
        st.divider()
        st.subheader("Pending diff")
        st.write(preview.summary)
        if preview.diff:
            st.code(preview.diff, language="diff")
        else:
            st.info("No changes were produced for this preview.")

        if preview.logs:
            st.subheader("codereview agent trace")
            for entry in preview.logs:
                st.write(f"**codereview:** {entry}")

        apply_cols = st.columns([1, 1])
        with apply_cols[0]:
            if st.button(
                "Apply pending changes",
                type="primary",
                disabled=not preview.has_changes,
                use_container_width=True,
            ):
                apply_preview(preview)
                st.session_state.pop("file_review_preview", None)
                st.success(f"Applied changes to {preview.target}")
                st.rerun()
        with apply_cols[1]:
            if st.button("Discard preview", use_container_width=True):
                st.session_state.pop("file_review_preview", None)
                st.rerun()
