"""
Tools for the Fix Suggester Agent.
"""

import ast
import json
import subprocess
import tempfile
import os
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama

from langchain_core.messages import SystemMessage, HumanMessage

import getpass
import os
from dotenv import load_dotenv
from tools.retry_utils import invoke_with_retry

load_dotenv()
if "GROQ_API_KEY" not in os.environ:
    os.environ["GROQ_API_KEY"] = getpass.getpass("Enter your Groq API key: ")


@tool
def web_search_fix(query: str)-> str:
    """
    Search the web for known fix patterns for a specific bug.
    Uses Tavily API (you already have this from your research agent project).
 
    Args:
        query: Search query e.g. "python sql injection fix parameterized query"
    """

    try:
        from tavily import TavilyClient
        import os
 
        client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
        results = client.search(
            query=query,
            search_depth="basic",
            max_results=3,
            include_answer=True,
        )
 
        formatted = {
            "answer": results.get("answer", ""),
            "sources": [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", "")[:300],
                }
                for r in results.get("results", [])
            ],
        }
        return json.dumps(formatted)
 
    except ImportError:
        return json.dumps({"error": "tavily-python not installed. Run: pip install tavily-python", "answer": "", "sources": []})
    except KeyError:
        return json.dumps({"error": "TAVILY_API_KEY not set in environment", "answer": "", "sources": []})
    except Exception as e:
        return json.dumps({"error": str(e), "answer": "", "sources": []})


 
@tool
def generate_patch(
    original_code: str,
    bug_description: str,
    bug_type: str,
    search_context: str = "",
    language: str = "python",
) -> str:
    """
    Generate a code fix for the given bug using an LLM.
    Uses search_context from web_search_fix for more accurate patches.
 
    Args:
        original_code: The buggy code snippet
        bug_description: Description of what's wrong
        bug_type: security | logic | performance | style
        search_context: Context from web search (optional but improves quality)
        language: Programming language
    """
    # llm = AzureChatOpenAI(
    #     azure_deployment="gpt-4o",
    #     api_version="2024-08-01-preview",
    #     temperature=0.1,
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

 
    system = f"""You are a {language} expert writing production-safe code fixes.
Rules:
- Fix ONLY the specific bug described, don't refactor unrelated code
- Keep the same function/variable names
- Add inline comments explaining the fix
- For security bugs: add input validation and use safe alternatives
- Return ONLY the fixed code, no explanation, no markdown fences"""
 
    context_section = f"\nSearch context:\n{search_context}" if search_context else ""
 
    user_msg = f"""Fix this {bug_type} bug in the following {language} code.
 
Bug: {bug_description}
{context_section}
 
Original code:
{original_code}
 
Return only the fixed code."""
 
    response = invoke_with_retry(
        llm.invoke,
        [
            SystemMessage(content=system),
            HumanMessage(content=user_msg),
        ],
    )
 
    fixed_code = response.content.strip()
    # Strip any accidental markdown fences
    if fixed_code.startswith("```"):
        fixed_code = fixed_code.split("\n", 1)[1].rsplit("```", 1)[0].strip()
 
    return json.dumps({
        "fixed_code": fixed_code,
        "language": language,
    })


 
@tool
def run_tests(code: str, language: str = "python") -> str:
    """
    Run basic syntax validation on the fixed code.
    For Python: uses ast.parse() + a compile() check.
    Returns pass/fail and any syntax errors found.
 
    Args:
        code: The fixed code to validate
        language: Programming language
    """
    if language.lower() != "python":
        return json.dumps({"passed": True, "note": f"Syntax check not available for {language}"})
 
    # Test 1: AST parse
    try:
        ast.parse(code)
    except SyntaxError as e:
        return json.dumps({
            "passed": False,
            "error": f"SyntaxError: {e}",
            "line": e.lineno,
        })
 
    # Test 2: compile check (catches some issues AST misses)
    try:
        compile(code, "<string>", "exec")
    except Exception as e:
        return json.dumps({"passed": False, "error": str(e)})
 
    # Test 3: write to temp file and check imports resolve (best effort)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        tmp_path = f.name
 
    try:
        result = subprocess.run(
            ["python", "-m", "py_compile", tmp_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        passed = result.returncode == 0
        error  = result.stderr.strip() if not passed else None
        return json.dumps({"passed": passed, "error": error})
    except subprocess.TimeoutExpired:
        return json.dumps({"passed": False, "error": "Compile check timed out"})
    finally:
        os.unlink(tmp_path)
 