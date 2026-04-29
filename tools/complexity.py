from radon.complexity import cc_visit

def check_complexity(code):
    results = cc_visit(code)

    return [
        {
            "name": r.name,
            "complexity": r.complexity
        }
        for r in results
    ]