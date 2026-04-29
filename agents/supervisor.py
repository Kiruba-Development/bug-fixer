"""
Supervisor Agent
----------------
The central router. Decides which agent to call next based on current state.
Uses conditional edges in LangGraph — no LLM needed for routing itself,
just pure state inspection logic (fast + deterministic).

For more advanced routing you can swap decide_next_agent() to an LLM call
that reads state and returns the next node name.
"""

# from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from state import CodeReviewState


# ── Routing constants ──────────────────────────────────────────────────────────
ANALYZER  = "code_analyzer"
TRIAGER   = "bug_triager"
SUGGESTER = "fix_suggester"
REPORTER  = "report_generator"
END       = "__end__"


# def decide_next_agent(state: CodeReviewState) -> str:
#     """
#     Pure routing logic — called by LangGraph's conditional_edges.
#     Returns the name of the next node to execute.

#     Flow:
#       1. No analysis yet          → run code_analyzer
#       2. Analysis done, no bugs   → run bug_triager
#       3. Bugs triaged, no fixes   → run fix_suggester
#       4. Critical bugs + < 2 pass → re-run fix_suggester (second pass)
#       5. Everything done          → generate report → END
#     """
#     # Step 1: always analyze first
#     if not state.get("analysis_results"):
#         return ANALYZER

#     # Step 2: analyze done but bugs not yet classified
#     if not state.get("bugs"):
#         return TRIAGER

#     # Step 3: bugs classified but no fixes yet
#     if not state.get("fixes"):
#         return SUGGESTER

#     # Step 4: critical bugs found and we haven't done a second pass yet
#     summary = state.get("severity_summary", {})
#     if summary.get("critical", 0) > 0 and state.get("pass_count", 0) < 2:
#         return SUGGESTER   # re-route for a deeper fix pass

#     # Step 5: all done — generate the final report
#     return REPORTER

def decide_next_agent(state: CodeReviewState) -> str:

    analysis = state.get("analysis_results", {})
    bugs = state.get("bugs", [])
    fixes = state.get("fixes", [])
    pass_count = state.get("pass_count", 0)
    summary = state.get("severity_summary", {})

    # Add this — print state at every routing decision so you can see what's happening
    print(f"\n[SUPERVISOR] analysis={bool(analysis)} bugs={len(bugs)} fixes={len(fixes)} pass_count={pass_count}")

    # Step 1: No analysis yet
    if not analysis:
        print("[SUPERVISOR] → ANALYZER")
        return ANALYZER

    # Step 2: Analysis done but has parse_error — don't loop, move on
    if analysis.get("parse_error"):
        print("[SUPERVISOR] → TRIAGER (analysis had parse error, moving on)")
        return TRIAGER

    # Step 3: No bugs classified yet
    if not bugs:
        print("[SUPERVISOR] → TRIAGER")
        return TRIAGER

    # Step 4: No fixes yet
    if not fixes:
        print("[SUPERVISOR] → SUGGESTER")
        return SUGGESTER

    # Step 5: Critical bugs on first pass only
    if summary.get("critical", 0) > 0 and pass_count < 2:
        print("[SUPERVISOR] → SUGGESTER (second pass for critical bugs)")
        return SUGGESTER

    # Step 6: Everything done
    print("[SUPERVISOR] → REPORTER")
    return REPORTER


def supervisor_node(state: CodeReviewState) -> dict:
    """
    The supervisor node itself just updates control-flow metadata.
    Actual routing happens in decide_next_agent (used as edge condition).
    """
    next_agent = decide_next_agent(state)

    return {
        "current_agent": next_agent,
        "pass_count": state.get("pass_count", 0),   # pass_count incremented by fix_suggester
    }











# def supervisor(state):
#     ## Decide  the next step based on state

#     if not state.get("analysis_result"):
#         return {"next_step": "analyzer"}
    
#     elif not state.get("bugs"):
#         return {"next_step": "triager"}
    
#     elif not state.get("fixes"):
#         return {"next_step": "fixer"}
    
#     else:
#         return {"next_step": "end"}