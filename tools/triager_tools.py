"""
Tools for the Bug Triager Agent.
"""

import json 
import re
from langchain_ollama import ChatOllama
import requests
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama


import getpass
import os
from dotenv import load_dotenv
from tools.retry_utils import invoke_with_retry

load_dotenv()
if "GROQ_API_KEY" not in os.environ:
    os.environ["GROQ_API_KEY"] = getpass.getpass("Enter your Groq API key: ")




# Known bug patterns for rule-based classification (fast, no LLM needed)
BUG_PATTERNS = {
    "security": [
        r"eval\s*\(", r"exec\s*\(", r"__import__",
        r"subprocess.*shell=True", r"os\.system",
        r"pickle\.loads", r"yaml\.load\s*\(",
        r"sql.*\+.*input", r"f[\"'].*SELECT",
        r"password.*=.*[\"'][^\"']+[\"']",  # hardcoded password
    ],
    "logic": [
        r"except\s*:", r"except\s+Exception\s*:",   # bare except
        r"is\s+[0-9]",                               # is comparison with int literal
        r"==\s*True", r"==\s*False",                 # should use `is`
        r"not\s+.+\s+in\s+",                         # should be `not in`
    ],
    "performance": [
        r"\.append\(.+\)\s+in\s+for",               # append in loop
        r"for.*in.*range.*len\(",                    # range(len(...)) antipattern
        r"\+\s*=\s*[\"']",                          # string concatenation in loop
    ],
}

@tool
def classify_bug(description: str, code_snippet: str="") -> str:
    """
    Classify a bug into one of: security | logic | performance | style.
    Uses pattern matching first, falls back to LLM classification.
 
    Args:
        description: The bug description from the linter or analysis
        code_snippet: Optional code snippet where the bug occurs
    """
      
    combined = (description +" "+code_snippet).lower()

    # Fast rule based classification

    for bug_type, patterns in BUG_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, combined, re.IGNORECASE):
                return json.dumps({
                    "bug_type": bug_type,
                    "method": "pattern_match",
                    "matched_pattern": pattern,
                })
    # Fallback: LLM classification for ambiguous cases
    # llm = AzureChatOpenAI(azure_deployment="gpt-4o", api_version="2024-08-01-preview", temperature=0)
#     llm = ChatGroq(
#     model="llama-3.1-8b-instant",
#     temperature=0,
#     max_tokens=None,
#     timeout=None,
#     max_retries=2,
#     # other params...
# )
    llm = ChatOllama(model="mistral", temperature=0)

 
    prompt = f"""Classify this code issue into exactly one category: security, logic, performance, or style.
 
                Issue: {description}
                Code: {code_snippet}
 
                Reply with ONLY the category name, nothing else."""
 
    response = invoke_with_retry(llm.invoke, [HumanMessage(content=prompt)])
    category = response.content.strip().lower()
 
    valid = {"security", "logic", "performance", "style"}
    if category not in valid:
        category = "style"  # safe default
 
    return json.dumps({"bug_type": category, "method": "llm_classification"})



@tool
def score_severity(bug_type: str, description: str, code_snippet: str = "") -> str:
    """
    Score the severity of a bug: critical | high | medium | low.
 
    Args:
        bug_type: The classified bug type (security | logic | performance | style)
        description: Human-readable bug description
        code_snippet: The problematic code snippet
    """
    # Rule-based severity scoring
    description_lower = description.lower()
 
    # Critical indicators
    critical_keywords = [
        "sql injection", "command injection", "remote code execution",
        "rce", "arbitrary code", "shell=true", "eval(", "exec(",
        "pickle.loads", "yaml.load",
    ]
    if bug_type == "security" and any(kw in description_lower for kw in critical_keywords):
        return json.dumps({"severity": "critical", "reasoning": "Exploitable security vulnerability"})
 
    # High severity indicators
    high_keywords = [
        "hardcoded password", "hardcoded secret", "bare except",
        "data loss", "infinite loop", "null pointer", "index out of range",
    ]
    if any(kw in description_lower for kw in high_keywords):
        return json.dumps({"severity": "high", "reasoning": "Likely to cause incorrect behavior in production"})
 
    # Severity by bug type
    type_default_severity = {
        "security": "high",
        "logic": "medium",
        "performance": "medium",
        "style": "low",
    }
 
    severity = type_default_severity.get(bug_type, "low")
    return json.dumps({"severity": severity, "reasoning": f"Default severity for {bug_type} issues"})


 
@tool
def search_cve(description: str, technology: str = "python") -> str:
    """
    Search for known CVEs related to a security issue using the NVD API.
    Returns matching CVEs or an empty list if none found.
 
    Args:
        description: Description of the security vulnerability
        technology: Technology/library involved
    """
    # Build a simple search query from the description
    keywords = " ".join(description.split()[:5])  # first 5 words
    query = f"{keywords} {technology}"
 
    try:
        url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
        params = {
            "keywordSearch": query,
            "resultsPerPage": 3,
        }
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
 
        cves = []
        for vuln in data.get("vulnerabilities", [])[:3]:
            cve = vuln.get("cve", {})
            cve_id = cve.get("id", "")
            descriptions = cve.get("descriptions", [])
            desc = next((d["value"] for d in descriptions if d["lang"] == "en"), "")
            cves.append({"id": cve_id, "description": desc[:200]})
 
        return json.dumps({"cves": cves, "query": query})
 
    except Exception as e:
        # CVE search is optional — never fail the pipeline over it
        return json.dumps({"cves": [], "error": str(e), "note": "CVE search unavailable"})
 
