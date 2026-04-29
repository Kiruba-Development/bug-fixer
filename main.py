"""
Streamlit UI
------------
Run with: streamlit run ui/app.py
"""

import uuid
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from graph import run_review

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Code Reviewer",
    page_icon="🔍",
    layout="wide",
)

st.title("🔍 Multi-Agent Code Review System")
st.caption("Powered by LangGraph · Groq llama-3.1-8b-instant · LangChain")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    language = st.selectbox("Language", ["python", "javascript", "java"], index=0)
    filename = st.text_input("Filename", value="app.py")

    st.divider()
    st.subheader("Agent pipeline")
    st.markdown("""
    1. **Supervisor** — routes tasks
    2. **Code Analyzer** — AST, lint, complexity
    3. **Bug Triager** — classify + severity
    4. **Fix Suggester** — patches + search
    5. **Report Generator** — Markdown output
    """)

    st.divider()
    st.caption("Critical bugs trigger a second fix pass automatically.")

# ── Main area ─────────────────────────────────────────────────────────────────
col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("Code Input")
    code = st.text_area(
        label="Paste your code here",
        height=400,
        placeholder="# Paste Python code here...",
        label_visibility="collapsed",
    )

    run_btn = st.button("Run Review", type="primary", use_container_width=True)

with col2:
    st.subheader("Review Report")
    report_placeholder = st.empty()

# ── Run the graph ─────────────────────────────────────────────────────────────
if run_btn:
    if not code.strip():
        st.warning("Please paste some code first.")
    else:
        thread_id = str(uuid.uuid4())  # unique ID per review

        with st.spinner("Running multi-agent review... (this takes ~20-40s)"):
            # Live status updates
            status = st.status("Agents working...", expanded=True)

            with status:
                st.write("🔵 Supervisor routing...")

                try:
                    result = run_review(
                        code=code,
                        language=language,
                        filename=filename,
                        thread_id=thread_id,
                    )

                    bugs     = result.get("bugs", [])
                    fixes    = result.get("fixes", [])
                    summary  = result.get("severity_summary", {})
                    report   = result.get("final_report", "No report generated.")
                    passes   = result.get("pass_count", 1)

                    st.write("✅ Code Analyzer complete")
                    st.write("✅ Bug Triager complete")
                    st.write(f"✅ Fix Suggester complete ({passes} pass{'es' if passes > 1 else ''})")
                    st.write("✅ Report generated")
                    status.update(label="Review complete!", state="complete")

                except Exception as e:
                    status.update(label=f"Error: {e}", state="error")
                    st.error(f"Review failed: {e}")
                    st.stop()

        # ── Metrics row ───────────────────────────────────────────────────────
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Total bugs",  len(bugs))
        m2.metric("🔴 Critical", summary.get("critical", 0))
        m3.metric("🟠 High",     summary.get("high", 0))
        m4.metric("🟡 Medium",   summary.get("medium", 0))
        m5.metric("Fixes",       len(fixes))

        # ── Report tabs ───────────────────────────────────────────────────────
        tab1, tab2, tab3 = st.tabs(["📄 Full Report", "🐛 Bugs", "🔧 Fixes"])

        with tab1:
            st.markdown(report)
            st.download_button(
                "Download Report (.md)",
                data=report,
                file_name=f"review_{filename}.md",
                mime="text/markdown",
            )

        with tab2:
            if bugs:
                for bug in bugs:
                    sev_color = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
                    icon = sev_color.get(bug.get("severity", "low"), "⚪")
                    with st.expander(f"{icon} Line {bug.get('line', '?')} — {bug.get('description', '')[:80]}"):
                        st.json(bug)
            else:
                st.success("No bugs found!")

        with tab3:
            if fixes:
                for i, fix in enumerate(fixes, 1):
                    with st.expander(f"Fix {i}: {fix.get('bug_description', '')[:80]}"):
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.caption("Original")
                            st.code(fix.get("original_code", ""), language=language)
                        with col_b:
                            st.caption("Fixed")
                            st.code(fix.get("fixed_code", ""), language=language)
                        st.info(fix.get("explanation", ""))
            else:
                st.info("No fixes generated.")











# from graph import graph

# if __name__ == "__main__":
#     input_code = """
# a = 10
# b = 20
# print(a)
# """

#     result = graph.invoke({
#         "code_input": input_code,
#         "analysis_results": [],
#         "bugs": [],
#         "severity_scores": [],
#         "fixes": [],
#         "next_step": ""
#     })

#     print("\nFINAL OUTPUT:\n", result)