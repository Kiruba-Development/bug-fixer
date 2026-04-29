"""
Graph Assembly
--------------
This is the heart of the project. Assembles all nodes into a LangGraph
StateGraph with conditional routing and shared memory via checkpointer.

Usage:
    from code_review_agent.graph import build_graph

    graph = build_graph()
    result = graph.invoke({
        "code_input": your_code,
        "language": "python",
        "filename": "app.py",
    })
    print(result["final_report"])
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.memory import InMemorySaver
import sqlite3
import streamlit as st

from state import CodeReviewState
from agents.supervisor import (
    supervisor_node,
    decide_next_agent,
    ANALYZER,
    TRIAGER,
    SUGGESTER,
    REPORTER,
)
from agents.code_analyzer   import code_analyzer_node
from agents.bug_triager     import bug_triager_node
from agents.fix_suggester   import fix_suggester_node
from agents.report_generator import report_generator_node


def build_graph(db_path: str = "checkpoints.db"):
    """
    Build and compile the multi-agent code review graph.

    Args:
        db_path: Path to SQLite file for conversation checkpointing.
                 Use ":memory:" for in-memory (no persistence).

    Returns:
        Compiled LangGraph runnable.
    """
    # ── State graph ───────────────────────────────────────────────────────────
    builder = StateGraph(CodeReviewState)

    # ── Add nodes ─────────────────────────────────────────────────────────────
    builder.add_node("supervisor",        supervisor_node)
    builder.add_node(ANALYZER,            code_analyzer_node)
    builder.add_node(TRIAGER,             bug_triager_node)
    builder.add_node(SUGGESTER,           fix_suggester_node)
    builder.add_node(REPORTER,            report_generator_node)

    # ── Entry point ───────────────────────────────────────────────────────────
    builder.set_entry_point("supervisor")

    # ── Conditional routing from supervisor ───────────────────────────────────
    # decide_next_agent() returns a node name — LangGraph maps it to the next node
    builder.add_conditional_edges(
        "supervisor",
        decide_next_agent,
        {
            ANALYZER:  ANALYZER,
            TRIAGER:   TRIAGER,
            SUGGESTER: SUGGESTER,
            REPORTER:  REPORTER,
        }
    )

    # ── All agents route back to supervisor after completing ──────────────────
    builder.add_edge(ANALYZER,  "supervisor")
    builder.add_edge(TRIAGER,   "supervisor")
    builder.add_edge(SUGGESTER, "supervisor")

    # ── Report generator is the terminal node ─────────────────────────────────
    builder.add_edge(REPORTER, END)

    # ── Memory / checkpointing ────────────────────────────────────────────────
    # Try to use SqliteSaver, fall back to InMemorySaver if threading issues occur
    try:
        if db_path == ":memory:":
            checkpointer = InMemorySaver()
        else:
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            checkpointer = SqliteSaver(conn)
    except Exception as e:
        print(f"Warning: Could not create SqliteSaver ({e}), using InMemorySaver instead")
        checkpointer = InMemorySaver()

    graph = builder.compile(checkpointer=checkpointer)
    return graph


def run_review(
    code: str,
    language: str = "python",
    filename: str = "code.py",
    thread_id: str = "review-001",
    db_path: str = "checkpoints.db",
) -> dict:
    """
    Convenience function to run a full code review.

    Args:
        code: Source code to review
        language: Programming language
        filename: Name of the file (for the report)
        thread_id: Unique ID for this review session (enables resumability)
        db_path: Path to the checkpoint database

    Returns:
        Final state dict including 'final_report', 'bugs', 'fixes', etc.
    """
    graph = build_graph(db_path=db_path)

    initial_state = {
        "code_input":      code,
        "language":        language,
        "filename":        filename,
        "analysis_results": {},
        "bugs":            [],
        "fixes":           [],
        "severity_summary": {},
        "current_agent":   "",
        "needs_second_pass": False,
        "pass_count":      0,
        "error":           None,
        "final_report":    "",
        "messages":        [],
    }

    config = {"configurable": {"thread_id": thread_id},"recursion_limit": 50,}

    result = graph.invoke(initial_state, config=config,)
    return result


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    SAMPLE_CODE = '''
import os
import pickle

def get_user_data(user_id):
    # Vulnerable: SQL injection
    query = "SELECT * FROM users WHERE id = " + user_id
    return db.execute(query)

def process_file(filename):
    # Vulnerable: arbitrary deserialization
    with open(filename, "rb") as f:
        data = pickle.loads(f.read())
    return data

def calculate(items):
    result = ""
    for item in items:
        result += str(item)  # performance: string concatenation in loop
    return result

def nested_logic(data):
    if data:
        for item in data:
            if item > 0:
                for sub in item:
                    if sub:
                        try:
                            pass
                        except:  # bare except
                            pass
'''

    print("Running code review...")
    result = run_review(SAMPLE_CODE, language="python", filename="vulnerable_app.py")
    print(result["final_report"])

















# from langgraph.graph import StateGraph, END, START
# from state import AgentState

# from agents.supervisor import supervisor
# from agents.code_analyzer import analyzer
# from agents.bug_triager import triager
# from agents.fix_suggester import fixer

# builder = StateGraph(AgentState)

# builder.add_node("supervisor", supervisor)
# builder.add_node("analyzer", analyzer)
# builder.add_node("triager", triager)
# builder.add_node("fixer", fixer)

# ## Entry Point
# builder.set_entry_point("supervisor")



# ##Conditional routing

# def route(state):
#     return state["next_step"]

# builder.add_conditional_edges(
#     "supervisor", route,
#     {
#         "analyzer": "analyzer",
#         "triager": "triager",
#         "fixer": "fixer",
#         "end": END
#     }
# )

# # Flow edges back to supervisor
# builder.add_edge("analyzer", "supervisor")
# builder.add_edge("triager", "supervisor")
# builder.add_edge("fixer", "supervisor")

# graph = builder.compile()