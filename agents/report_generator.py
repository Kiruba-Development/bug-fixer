"""
Report Generator
----------------
Terminal node in the graph. Takes all accumulated state and compiles
a clean, structured Markdown report. No LLM needed — pure formatting.
"""

from datetime import datetime
from state import CodeReviewState


def severity_emoji(severity: str) -> str:
    return {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(severity, "⚪")


def report_generator_node(state: CodeReviewState) -> dict:
    """
    Compiles the final Markdown review report from all agent outputs.
    This is the last node before END.
    """
    bugs      = state.get("bugs", [])
    fixes     = state.get("fixes", [])
    analysis  = state.get("analysis_results", {})
    summary   = state.get("severity_summary", {})
    filename  = state.get("filename", "submitted code")
    language  = state.get("language", "python")
    now       = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── Header ────────────────────────────────────────────────────────────────
    lines = [
        f"# Code Review Report",
        f"**File:** `{filename}` | **Language:** {language} | **Generated:** {now}",
        "",
        "---",
        "",
    ]

    # ── Severity summary ──────────────────────────────────────────────────────
    lines += [
        "## Summary",
        "",
        f"| Severity | Count |",
        f"|----------|-------|",
        f"| 🔴 Critical | {summary.get('critical', 0)} |",
        f"| 🟠 High     | {summary.get('high', 0)} |",
        f"| 🟡 Medium   | {summary.get('medium', 0)} |",
        f"| 🟢 Low      | {summary.get('low', 0)} |",
        f"| **Total**  | **{len(bugs)}** |",
        "",
    ]

    # ── Static analysis stats ─────────────────────────────────────────────────
    if analysis and not analysis.get("parse_error"):
        lint_score = analysis.get("lint_score", "N/A")
        high_complexity = analysis.get("high_complexity_funcs", [])

        lines += [
            "## Static Analysis",
            "",
            f"- **Pylint score:** {lint_score}/10",
            f"- **Functions:** {len(analysis.get('functions', []))}",
            f"- **Max nesting depth:** {analysis.get('max_nesting_depth', 'N/A')}",
        ]
        if high_complexity:
            lines.append(f"- **High complexity functions:** {', '.join(f'`{f}`' for f in high_complexity)}")
        lines.append("")

    # ── Bug details ───────────────────────────────────────────────────────────
    if bugs:
        lines += ["## Issues Found", ""]
        for i, bug in enumerate(bugs, 1):
            sev   = bug.get("severity", "low")
            btype = bug.get("bug_type", "unknown")
            line  = bug.get("line", "?")
            desc  = bug.get("description", "")
            conf  = bug.get("confidence", 0)

            lines += [
                f"### {severity_emoji(sev)} Issue {i} — {sev.upper()} ({btype})",
                "",
                f"**Line:** {line}  ",
                f"**Description:** {desc}  ",
                f"**Confidence:** {conf:.0%}",
                "",
            ]
    else:
        lines += ["## Issues Found", "", "No issues found. ✅", ""]

    # ── Fix suggestions ───────────────────────────────────────────────────────
    if fixes:
        lines += ["## Suggested Fixes", ""]
        for i, fix in enumerate(fixes, 1):
            bug_desc = fix.get("bug_description", "")
            original = fix.get("original_code", "")
            fixed    = fix.get("fixed_code", "")
            explanation = fix.get("explanation", "")
            refs     = fix.get("references", [])

            lines += [
                f"### Fix {i}: {bug_desc}",
                "",
                "**Original:**",
                f"```{language}",
                original,
                "```",
                "",
                "**Fixed:**",
                f"```{language}",
                fixed,
                "```",
                "",
                f"**Why:** {explanation}",
                "",
            ]
            if refs:
                lines.append("**References:**")
                for ref in refs:
                    lines.append(f"- {ref}")
                lines.append("")

    # ── Pass info ─────────────────────────────────────────────────────────────
    pass_count = state.get("pass_count", 1)
    if pass_count > 1:
        lines += [
            "---",
            f"> ℹ️ Critical bugs detected — the fix suggester ran **{pass_count} passes** for deeper analysis.",
            "",
        ]

    final_report = "\n".join(lines)

    return {
        "final_report": final_report,
        "current_agent": "report_generator",
    }