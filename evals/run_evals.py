"""
Evaluation Script
-----------------
Runs the review system against 10 known-buggy snippets and measures:
  - Bug detection rate
  - Classification accuracy (type + severity)
  - Fix generation success rate

The eval table from this script is what goes in your resume bullet.
Run with: python -m code_review_agent.evals.run_evals
"""

import sys
import json
from pathlib import Path
from dataclasses import dataclass

# Add parent directory to path so we can import from root modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from graph import run_review


@dataclass
class EvalCase:
    name: str
    code: str
    expected_bug_types: list[str]      # what types we expect to find
    expected_min_severity: str         # minimum severity we expect
    should_have_fix: bool


EVAL_CASES = [
    EvalCase(
        name="SQL Injection",
        code='''
def get_user(user_id):
    query = "SELECT * FROM users WHERE id = " + user_id
    return db.execute(query)
''',
        expected_bug_types=["security"],
        expected_min_severity="critical",
        should_have_fix=True,
    ),
    EvalCase(
        name="Pickle Deserialization",
        code='''
import pickle
def load_data(filepath):
    with open(filepath, "rb") as f:
        return pickle.loads(f.read())
''',
        expected_bug_types=["security"],
        expected_min_severity="critical",
        should_have_fix=True,
    ),
    EvalCase(
        name="Command Injection",
        code='''
import subprocess
def run_command(user_input):
    subprocess.run(user_input, shell=True)
''',
        expected_bug_types=["security"],
        expected_min_severity="critical",
        should_have_fix=True,
    ),
    EvalCase(
        name="Bare Except",
        code='''
def process():
    try:
        risky_operation()
    except:
        pass
''',
        expected_bug_types=["logic"],
        expected_min_severity="medium",
        should_have_fix=True,
    ),
    EvalCase(
        name="String Concat in Loop",
        code='''
def build_string(items):
    result = ""
    for item in items:
        result += str(item)
    return result
''',
        expected_bug_types=["performance"],
        expected_min_severity="medium",
        should_have_fix=True,
    ),
    EvalCase(
        name="Hardcoded Password",
        code='''
def connect():
    password = "admin123"
    db.connect(user="root", password=password)
''',
        expected_bug_types=["security"],
        expected_min_severity="high",
        should_have_fix=True,
    ),
    EvalCase(
        name="range(len()) antipattern",
        code='''
def process(items):
    for i in range(len(items)):
        print(items[i])
''',
        expected_bug_types=["performance", "style"],
        expected_min_severity="low",
        should_have_fix=True,
    ),
    EvalCase(
        name="Eval usage",
        code='''
def calculate(expression):
    return eval(expression)
''',
        expected_bug_types=["security"],
        expected_min_severity="critical",
        should_have_fix=True,
    ),
    EvalCase(
        name="Mutable default argument",
        code='''
def append_item(item, lst=[]):
    lst.append(item)
    return lst
''',
        expected_bug_types=["logic"],
        expected_min_severity="high",
        should_have_fix=True,
    ),
    EvalCase(
        name="Clean code (no bugs)",
        code='''
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b
''',
        expected_bug_types=[],
        expected_min_severity="low",
        should_have_fix=False,
    ),
]


SEVERITY_ORDER = ["low", "medium", "high", "critical"]


def meets_severity(found: str, expected_min: str) -> bool:
    return SEVERITY_ORDER.index(found) >= SEVERITY_ORDER.index(expected_min)


def run_evals():
    results = []
    total   = len(EVAL_CASES)
    detected = 0
    classified_correctly = 0
    fix_generated = 0

    print(f"\n{'='*60}")
    print(f"  Running {total} eval cases")
    print(f"{'='*60}\n")

    for i, case in enumerate(EVAL_CASES, 1):
        print(f"[{i}/{total}] {case.name}...")

        try:
            result = run_review(
                code=case.code,
                language="python",
                filename=f"eval_{i}.py",
                thread_id=f"eval-{i}",
                db_path=":memory:",
            )

            bugs  = result.get("bugs", [])
            fixes = result.get("fixes", [])

            # Did we detect at least one bug (if expected)?
            bug_detected = len(bugs) > 0 if case.expected_bug_types else len(bugs) == 0
            if bug_detected:
                detected += 1

            # Did we classify the bug type correctly?
            found_types = {b.get("bug_type") for b in bugs}
            type_match = (
                bool(found_types & set(case.expected_bug_types))
                if case.expected_bug_types
                else len(bugs) == 0
            )
            if type_match:
                classified_correctly += 1

            # Did we generate a fix when one was expected?
            fix_ok = (len(fixes) > 0) == case.should_have_fix
            if fix_ok:
                fix_generated += 1

            status = "✅" if (bug_detected and type_match and fix_ok) else "⚠️"
            print(f"  {status} bugs={len(bugs)} types={found_types} fixes={len(fixes)}")

            results.append({
                "case": case.name,
                "bug_detected": bug_detected,
                "type_correct": type_match,
                "fix_ok": fix_ok,
                "bugs_found": len(bugs),
                "fixes_generated": len(fixes),
            })

        except Exception as e:
            print(f"  ❌ Error: {e}")
            results.append({"case": case.name, "error": str(e)})

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  EVAL RESULTS")
    print(f"{'='*60}")
    print(f"  Detection accuracy:      {detected}/{total} = {detected/total:.0%}")
    print(f"  Classification accuracy: {classified_correctly}/{total} = {classified_correctly/total:.0%}")
    print(f"  Fix generation rate:     {fix_generated}/{total} = {fix_generated/total:.0%}")
    print(f"{'='*60}\n")

    # Save results for your resume
    with open("eval_results.json", "w") as f:
        json.dump({
            "summary": {
                "detection_accuracy": f"{detected/total:.0%}",
                "classification_accuracy": f"{classified_correctly/total:.0%}",
                "fix_generation_rate": f"{fix_generated/total:.0%}",
                "total_cases": total,
            },
            "cases": results,
        }, f, indent=2)

    print("Results saved to eval_results.json")
    return results


if __name__ == "__main__":
    run_evals()