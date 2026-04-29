"""
Fix Suggester Agent
-------------------
Generates concrete code fixes for each triaged bug.
On a second pass (triggered by supervisor for critical bugs),
it does a deeper search and produces more robust patches.

Tools available:
  - web_search_fix   : Tavily search for known fix patterns / Stack Overflow
  - generate_patch   : LLM call with full context to write the fixed code
  - run_tests        : runs the fixed code through basic syntax/import checks
"""

import json
# from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain.agents import create_agent
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama

from tools.retry_utils import invoke_with_retry

from state import CodeReviewState
import getpass
import os
from dotenv import load_dotenv

load_dotenv()
if "GROQ_API_KEY" not in os.environ:
    os.environ["GROQ_API_KEY"] = getpass.getpass("Enter your Groq API key: ")


from state import CodeReviewState, FixSuggestion
from tools.suggester_tools import (
    web_search_fix,
    generate_patch,
    run_tests,
)
SYSTEM_PROMPT_NORMAL = """You are an expert software engineer who writes code fixes.

CRITICAL: Your response must be ONLY a valid JSON array. No explanation before or after.
No markdown. No preamble. Start your response with [ and end with ].

Return this exact format:
[
  {
    "bug_description": "what the bug is",
    "original_code": "the problematic code snippet",
    "fixed_code": "the corrected code snippet",
    "explanation": "why this fix works",
    "references": []
  }
]

Prioritize critical bugs first, then high, then medium. Skip low severity."""

SYSTEM_PROMPT_SECOND_PASS = """You are doing a DEEP REVIEW pass on critical security vulnerabilities.

The first pass found critical bugs. Your job now:
1. Re-examine each critical bug more carefully
2. Use web_search_fix with more specific queries (include CVE numbers if known)
3. Provide a more robust, production-safe fix
4. Add defensive programming around the fixed code (input validation, error handling)
5. Include test cases that would catch this bug

Return the same JSON format but with richer explanations and more defensive fixes."""


def fix_suggester_node(state: CodeReviewState) -> dict:

    llm = ChatOllama(model="mistral", temperature=0)

    bugs     = state.get("bugs", [])
    language = state.get("language", "python")
    code     = state.get("code_input", "")
    fixes    = []

    for bug in bugs:
        if bug.get("severity") == "low" and state.get("pass_count", 0) == 0:
            continue

        prompt = f"""Fix this bug in the code below.

Bug: {bug.get('description') or bug.get('bug_description', '')}
Type: {bug.get('bug_type')}
Line: {bug.get('line')}

Full code:
```{language}
{code}
```

Reply in this exact format and nothing else:

ORIGINAL:
<the buggy line or snippet>

FIXED:
<the corrected code>

WHY:
<one sentence explanation>"""

        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            raw = response.content.strip()

            print(f"[FIX SUGGESTER] bug='{bug.get('bug_description')}' raw=\n{raw}\n")

            original_code = ""
            fixed_code    = ""
            explanation   = ""

            if "ORIGINAL:" in raw and "FIXED:" in raw:
                parts         = raw.split("FIXED:")
                original_code = parts[0].replace("ORIGINAL:", "").strip()

                if "WHY:" in parts[1]:
                    fixed_parts  = parts[1].split("WHY:")
                    fixed_code   = fixed_parts[0].strip()
                    explanation  = fixed_parts[1].strip()
                else:
                    fixed_code  = parts[1].strip()
                    explanation = "See fixed code above."

                # Strip markdown fences
                for marker in [f"```{language}", "```python", "```"]:
                    original_code = original_code.replace(marker, "").strip()
                    fixed_code    = fixed_code.replace(marker, "").strip()

            else:
                # Mistral returned JSON structure — remap it
                try:
                    parsed = json.loads(raw) if raw.startswith("[") else None
                    if parsed and isinstance(parsed, list):
                        for item in parsed:
                            fix_block = item.get("fix", {})
                            fixes.append({
                                "bug_description": item.get("bug_description", ""),
                                "original_code":   item.get("original_code", ""),
                                "fixed_code":      fix_block.get("code") or item.get("fixed_code", ""),
                                "explanation":     fix_block.get("explanation") or item.get("explanation", ""),
                                "references":      [],
                            })
                        continue   # skip the append below — already added
                except Exception:
                    pass

                fixed_code  = raw
                original_code = bug.get("bug_description", "")
                explanation = "See fixed code above."

            fixes.append({
                "bug_description": bug.get("bug_description") or bug.get("description", ""),
                "original_code":   original_code,
                "fixed_code":      fixed_code,
                "explanation":     explanation,
                "references":      [],
            })

        except Exception as e:
            print(f"[FIX SUGGESTER] Error: {e}")
            fixes.append({
                "bug_description": bug.get("bug_description", ""),
                "original_code":   "",
                "fixed_code":      f"Error: {e}",
                "explanation":     "",
                "references":      [],
            })

    if not fixes:
        fixes = [{
            "bug_description": "No fixes generated",
            "original_code":   "",
            "fixed_code":      "Could not generate fixes",
            "explanation":     "",
            "references":      [],
        }]

    return {
        "fixes":         fixes,
        "pass_count":    state.get("pass_count", 0) + 1,
        "current_agent": "fix_suggester",
        "messages":      [],
    }


# def fix_suggester_node(state: CodeReviewState) -> dict:
#     """
#     Generates fix suggestions for all triaged bugs.
#     On second pass (pass_count >= 1), uses deeper search for critical bugs.
#     """
#     # llm = AzureChatOpenAI(
#     #     azure_deployment="gpt-4o",
#     #     api_version="2024-08-01-preview",
#     #     temperature=0.1,   # slight creativity for fix generation
#     # )
# #     llm = ChatGroq(
# #     model="llama-3.1-8b-instant",
# #     temperature=0,
# #     max_tokens=None,
# #     timeout=None,
# #     max_retries=2,
# #     # other params...
# # )
#     llm = ChatOllama(model="mistral", temperature=0)


#     tools = [web_search_fix, generate_patch, run_tests]

#     is_second_pass = state.get("pass_count", 0) >= 1
#     system_prompt = SYSTEM_PROMPT_SECOND_PASS if is_second_pass else SYSTEM_PROMPT_NORMAL

#     agent = create_agent(llm, tools, checkpointer=None)

#     pass_label = "SECOND PASS (critical bugs only)" if is_second_pass else "first pass"
#     bugs_str = json.dumps(state.get("bugs", []), indent=2)

#     user_message = f"""Generate fixes for these bugs ({pass_label}).

# Original code:
# ```{state.get('language', 'python')}
# {state['code_input']}
# ```

# Bugs to fix:
# {bugs_str}

# Return the JSON array of FixSuggestion objects."""

#     result = invoke_with_retry(
#         agent.invoke,
#         {
#             "messages": [
#                 SystemMessage(content=system_prompt),
#                 HumanMessage(content=user_message),
#             ]
#         },config={"recursion_limit": 10}
#     )

#     raw_output = result["messages"][-1].content

#     # ADD THIS — print so you can see exactly what mistral returned
#     print(f"[FIX SUGGESTER] raw output:\n{raw_output[:500]}")

#     try:
#         # Strip markdown fences
#         cleaned = raw_output.strip()
#         if "```json" in cleaned:
#             cleaned = cleaned.split("```json")[1].split("```")[0].strip()
#         elif "```" in cleaned:
#             cleaned = cleaned.split("```")[1].split("```")[0].strip()

#         # Handle case where model wraps array in an object like {"fixes": [...]}
#         parsed = json.loads(cleaned)
#         if isinstance(parsed, dict):
#             # Mistral sometimes returns {"fixes": [...]} instead of [...]
#             fixes = parsed.get("fixes") or parsed.get("suggestions") or parsed.get("results") or [parsed]
#         elif isinstance(parsed, list):
#             fixes = parsed
#         else:
#             fixes = []
    
#     except json.JSONDecodeError:
#         print(f"[FIX SUGGESTER] JSON parse failed, trying to extract manually")

#     # ADD THIS
#     # Safety net — if still empty after all that
#     if not fixes:
#         print(f"[FIX SUGGESTER] Could not parse fixes. Full output was:\n{raw_output}")
#         fixes = [{
#             "bug_description": "Parse failed — see terminal for raw output",
#             "original_code": "",
#             "fixed_code": "Could not generate fix",
#             "explanation": raw_output[:300],  # show raw output in UI so you can debug
#             "references": [],
#         }]

#     return {
#         "fixes": fixes,
#         "pass_count": state.get("pass_count", 0) + 1,
#         "current_agent": "fix_suggester",
#         "messages": result["messages"],
#     }

























# def fixer(state):

#     print("running fixer")

#     ## Dummy output

#     return {"fixes": ["remove the unused variables"]}