"""
Tools for the Code Analyzer Agent.
Each tool is a LangChain @tool decorated function.
"""

import ast
import  json
import subprocess
import tempfile
import os
from langchain_core.tools import tool


@tool
def run_pylint(code:str, language:str = "python")-> str:
    """
    Run pylint on the provided code snippet.
    Returns a JSON string with lint score and list of issues.
 
    Args:
        code: The source code to lint
        language: Programming language (currently supports python)
    """

    if language.lower() != "python":
        return json.dump({"score":None, "issues":[], "note": f"Pylint only support python, got {language}"})
    
        # Write code to a temp file — pylint needs a real file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            ["pylint", tmp_path, "--output-format=json", "--score=yes"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        issues = []
        score = None   

        # Parse JSON output from pylint
        if result.stdout.strip():
            try:
                raw_issues = json.loads(result.stdout)
                issues = [
                    {
                        "line": issue.get("line"),
                        "message": issue.get("message"),
                        "symbol": issue.get("symbol"),
                        "type": issue.get("type"),  # C/W/E/F/R
                    }
                    for issue in raw_issues
                ]
            except json.JSONDecodeError:
                pass

        # Extract score from stderr (pylint prints "Your code has been rated at X/10")
        for line in result.stderr.splitlines():
            if "rated at" in line:
                try:
                    score = float(line.split("rated at")[1].split("/")[0].strip())
                except (IndexError, ValueError):
                    pass
 
        return json.dumps({"score": score, "issues": issues, "issue_count": len(issues)})
 
    except FileNotFoundError:
        return json.dumps({"error": "pylint not installed. Run: pip install pylint", "issues": []})
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "pylint timed out", "issues": []})
    finally:
        os.unlink(tmp_path)


@tool
def parse_ast_tool(code:str)->str:
    """
    Parse Python code using the AST module to extract structure.
    Returns functions, classes, imports, and max nesting depth.
 
    Args:
        code: Python source code to parse
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return json.dumps({"error": f"Syntax error: {e}", "functions": [], "classes": [], "imports": []})
    
    functions = []
    classes = []
    imports = []
    max_depth = [0]


    def get_nesting_depth(node, depth=0):
        max_depth[0] = max(max_depth[0], depth)
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                get_nesting_depth(child, depth + 1)
            else:
                get_nesting_depth(child, depth)
 
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            functions.append({
                "name": node.name,
                "line": node.lineno,
                "args": [arg.arg for arg in node.args.args],
                "has_docstring": (
                    isinstance(node.body[0], ast.Expr) and
                    isinstance(node.body[0].value, ast.Constant)
                    if node.body else False
                ),
            })
        elif isinstance(node, ast.ClassDef):
            classes.append({"name": node.name, "line": node.lineno})
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                imports.extend([alias.name for alias in node.names])
            else:
                module = node.module or ""
                imports.append(module)
 
    get_nesting_depth(tree)
 
    return json.dumps({
        "functions": functions,
        "classes": classes,
        "imports": list(set(imports)),
        "max_nesting_depth": max_depth[0],
        "total_lines": len(code.splitlines()),
    })


@tool
def check_complexity(code:str)-> str:
    """
    Calculate cyclomatic complexity for each function using radon.
    Functions with complexity > 10 are flagged as high complexity.
 
    Args:
        code: Python source code to analyze
    """

    try:
        from radon.complexity import cc_visit
        from radon.metrics import mi_visit


        blocks = cc_visit(code)

        complexity_scores = {}
        high_complexity = []


        for block in blocks:
            complexity_scores[block.name] = block.complexity
            if block.complexity > 10:
                high_complexity.append({
                    "name": block.name,
                    "complexity": block.complexity,
                    "line": block.lineno,
                })
 
        # Maintainability Index (0-100, higher is better)
        mi_score = mi_visit(code, multi=True)
 
        return json.dumps({
            "complexity_scores": complexity_scores,
            "high_complexity_funcs": [h["name"] for h in high_complexity],
            "high_complexity_details": high_complexity,
            "maintainability_index": round(mi_score, 2),
            "avg_complexity": (
                round(sum(complexity_scores.values()) / len(complexity_scores), 2)
                if complexity_scores else 0
            ),
        })
 
    except ImportError:
        # Fallback: basic line counting if radon not installed
        lines = code.splitlines()
        branch_keywords = ("if ", "elif ", "for ", "while ", "except ", "with ", "and ", "or ")
        estimated_complexity = sum(
            1 for line in lines if any(kw in line for kw in branch_keywords)
        )
        return json.dumps({
            "complexity_scores": {"estimated_total": estimated_complexity},
            "high_complexity_funcs": [],
            "note": "radon not installed — using rough estimate. Run: pip install radon",
        })
 
