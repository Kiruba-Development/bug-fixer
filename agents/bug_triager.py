"""
Bug Triager Agent
-----------------
Takes the raw analysis results and classifies each issue into structured
BugReport objects with severity scores.

Tools available:
  - classify_bug     : labels a bug (security | logic | performance | style)
  - score_severity   : returns critical | high | medium | low
  - search_cve       : optional CVE lookup for security-related issues

This is where your RAG background is useful — you can optionally embed
known bug patterns into a Pinecone/FAISS index and do similarity search
to improve classification confidence.
"""

import json
# from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama

from langchain.agents import create_agent

from state import CodeReviewState
import getpass
import os
from dotenv import load_dotenv
from tools.retry_utils import invoke_with_retry

load_dotenv()
if "GROQ_API_KEY" not in os.environ:
    os.environ["GROQ_API_KEY"] = getpass.getpass("Enter your Groq API key: ")

 

from state import CodeReviewState, BugReport
from tools.triager_tools import (
    classify_bug,
    score_severity,
    search_cve,
)

SYSTEM_PROMPT = """You are a security-focused code reviewer and bug triage specialist.

You receive static analysis results and must classify every identified issue.

For each issue found in the analysis results:
1. Call classify_bug to determine the bug type
2. Call score_severity to assign a severity level
3. If the bug type is "security", call search_cve to check for known CVEs

Return a JSON array of bug reports:
[
  {
    "line": int,
    "description": "clear description of the bug",
    "bug_type": "security | logic | performance | style",
    "severity": "critical | high | medium | low",
    "confidence": float  // 0.0 to 1.0
  },
  ...
]

Severity guidelines:
  - critical : exploitable security vulnerability or data corruption risk
  - high     : logic error that will cause incorrect behavior in production
  - medium   : performance issue or code smell that could cause problems
  - low      : style issue, minor inefficiency, or best practice violation

Only include issues with confidence > 0.5. Skip pure style warnings if severity is low."""


def bug_triager_node(state: CodeReviewState) -> dict:
    """
    Classifies all issues from analysis_results into structured BugReport objects.
    Builds severity_summary for the supervisor's routing decision.
    """
    # llm = AzureChatOpenAI(
    #     azure_deployment="gpt-4o",
    #     api_version="2024-08-01-preview",
    #     temperature=0,
    # )
#     llm = ChatGroq(
#     model="llama-3.1-8b-instant",
#     temperature=0,
#     max_tokens=None,
#     timeout=None,
#     max_retries=2,
#     # other params...
# )
    llm = ChatOllama(model="mistral", temperature=0)


    tools = [classify_bug, score_severity, search_cve]
    agent = create_agent(llm, tools, checkpointer=None)

    analysis_str = json.dumps(state["analysis_results"], indent=2)

    user_message = f"""Triage all issues from this analysis report.

Original code:
```{state.get('language', 'python')}
{state['code_input']}
```

Analysis results:
{analysis_str}

Classify every issue and return the JSON array of BugReport objects."""

    result = invoke_with_retry(
        agent.invoke,
        {
            "messages": [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=user_message),
            ]
        },config={"recursion_limit": 10}
    )

    raw_output = result["messages"][-1].content

    try:
        if "```json" in raw_output:
            raw_output = raw_output.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_output:
            raw_output = raw_output.split("```")[1].split("```")[0].strip()

        bugs: list[BugReport] = json.loads(raw_output)
    except json.JSONDecodeError:
        bugs = []

    # ADD THIS — if bugs is empty, put a placeholder so supervisor moves forward
    if not bugs:
        bugs = [{
            "line": 0,
            "description": "No bugs detected or parse failed",
            "bug_type": "style",
            "severity": "low",
            "confidence": 0.5,
        }]

    # Build severity summary for supervisor routing decision
    severity_summary = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for bug in bugs:
        sev = bug.get("severity", "low")
        if sev in severity_summary:
            severity_summary[sev] += 1

    return {
        "bugs": bugs,
        "severity_summary": severity_summary,
        "current_agent": "bug_triager",
        "messages": result["messages"],
    }






# def triager(state):

#     print("running triager")

#     ## Dummy output
#     return {"bugs": ["style_issues"],
#             "severity_scores": ["low"]
#             }