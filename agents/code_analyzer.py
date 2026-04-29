"""
Code Analyzer Agent
-------------------
First agent in the pipeline. Runs static analysis tools on the submitted code.
 
Tools available:
  - run_pylint       : lint score + per-line issues
  - parse_ast        : extract functions, classes, imports, nesting depth
  - check_complexity : cyclomatic complexity via radon
 
The agent is a ReAct-style tool-calling LLM that decides which tools to call
and synthesizes results into analysis_results on the shared state.
"""


import json
import os
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama

from langchain_core.messages import SystemMessage, HumanMessage

from langchain.agents import create_agent

from state import CodeReviewState
from tools.analyzer_tools import (
    run_pylint,
    parse_ast_tool,
    check_complexity
)
from tools.retry_utils import invoke_with_retry

import getpass
import os
from dotenv import load_dotenv

load_dotenv()
if "GROQ_API_KEY" not in os.environ:
    os.environ["GROQ_API_KEY"] = getpass.getpass("Enter your Groq API key: ")

 
SYSTEM_PROMPT = """You are a senior software engineer specializing in static code analysis.
 
Your job:
1. Run the available tools on the provided code.
2. Always call ALL three tools: run_pylint, parse_ast, check_complexity.
3. Synthesize the results into a structured JSON summary.
 
Return a JSON object with this structure:
{
  "lint_score": float,          // pylint score out of 10
  "lint_issues": [...],         // list of {line, message, symbol}
  "functions": [...],           // list of function names
  "classes": [...],             // list of class names
  "imports": [...],             // list of imported modules
  "max_nesting_depth": int,     // deepest nesting level found
  "complexity_scores": {...},   // {function_name: cyclomatic_complexity_int}
  "high_complexity_funcs": [...] // functions with complexity > 10
}
 
Be thorough. Every issue the linter finds is useful input for the bug triager."""


def code_analyzer_node(state: CodeReviewState)-> dict:
    """
    Runs static analysis on the submitted code.
    Updates state with analysis_results.
    """
    
#     llm = ChatGroq(
#     model="llama-3.1-8b-instant",
#     temperature=0,
#     max_tokens=None,
#     timeout=None,
#     max_retries=2,
#     # other params...
# )
    llm = ChatOllama(model="mistral", temperature=0)

    tools = [run_pylint, parse_ast_tool, check_complexity]

    ## Create react agent that can call our tools
    agent = create_agent(llm, tools, checkpointer=None)

    user_message = f"""Analyze this {state.get('language', 'python')} code from file '{state.get('filename', 'unknown')}':
 
        ```{state.get('language', 'python')}
        {state['code_input']}
        ```
        
        Run all three analysis tools and return the structured JSON summary."""
    
    result = invoke_with_retry(
        agent.invoke,
        {
            "messages": [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=user_message),
            ]
        },config={"recursion_limit": 10}
    )
 
    # Extract the last message content (agent's final answer)
    raw_output = result["messages"][-1].content
 
    # Parse the JSON from the agent's response
    try:
        # Handle case where LLM wraps JSON in markdown code blocks
        if "```json" in raw_output:
            raw_output = raw_output.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_output:
            raw_output = raw_output.split("```")[1].split("```")[0].strip()
 
        analysis_results = json.loads(raw_output)
    except json.JSONDecodeError:
        # Fallback: store raw output so pipeline doesn't break
        analysis_results = {"raw_output": raw_output, "parse_error": True}
    

    print(f"[ANALYZER] analysis_results = {analysis_results}")
    return {

        "analysis_results": analysis_results,
        "current_agent": "code_analyzer",
        "messages": result["messages"],
    }
 
 


























































































# from tools.ast_parser import parse_ast
# from tools.complexity import check_complexity
# from tools.pylint_tool import run_pylint

# def analyzer(state):
#     print("running analyzer")

#     # Dummy output for now

#     code = state["code_input"]
#     pylint_output = run_pylint(code)
#     ast_output = parse_ast(code)
#     complexity_output = check_complexity(code)


#     return {"analysis_result": [
#         {
#             "type": "pylint",
#             "data": pylint_output
            
#             },
#             {
#                 "type":"ast",
#                 "data": ast_output
#             },
#             {
#                 "type": "complexity",
#                 "data": complexity_output
#             }
        
#         ]}