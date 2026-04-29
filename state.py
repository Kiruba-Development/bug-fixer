"""
Shared state schema for the multi-agent code review system.
All agents read from and write to this state via LangGraph's StateGraph.
"""



from typing import TypedDict, List, Dict

class AgentState(TypedDict):
    code_input: str
    analysis_result: List[Dict]
    bugs: List[str]
    severity_scores: List[str]
    fixes: List[str]
    next_step: str


from typing import Annotated, Any
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages

class BugReport(TypedDict):
    line: int
    description: str
    bug_type: str   ## security | logic | Performance | Style 
    severity: str   ## critical | medium | high | low
    confidence: float

class FixSuggestion(TypedDict):
    bug_description: str
    original_code: str
    fixed_code: str
    explanation: str
    references: list[str]

class CodeReviewState(TypedDict):
    code_input: str                 # Code submitted by user
    language: str                   # python | java
    filename: str                   
    analysis_results: dict[str, Any] # from codeAnalyzer Agen-p9u\t
    bugs: list[BugReport]           # from BugTriager agent
    fixes: list[FixSuggestion]      # from FixSuggesterAgent
    current_agent: str              # which agent is active
    needs_second_pass: bool         # supervisor sets true if  critical bug found 
    pass_count: int                 # track how many routing passess happend
    error: str | None               # Any runtime error message
    final_report: str               # compiled markdown report
    severity_summary: dict[str, int] # critical 1, high 2

    # --- Conversation history (LangGraph message passing) ---
    messages: Annotated[list, add_messages]
