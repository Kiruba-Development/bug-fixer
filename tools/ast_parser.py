import ast

def parse_ast(code):
    tree = ast.parse(code)

    functions = [
        node.name for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    ]

    return {
        "num_functions": len(functions),
        "functions": functions
    }