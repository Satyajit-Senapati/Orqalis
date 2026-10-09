"""Conservative test-integrity signals; these do not prove semantic equivalence."""

import ast
from collections import Counter

_SKIP_NAMES = {"skip", "skipif", "xfail", "skiptest", "expectedfailure"}
_ASSERTION_HELPERS = {"raises", "warns", "fail"}


def _disabled(tree: ast.AST) -> Counter[str]:
    result: Counter[str] = Counter()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = (
                node.func.attr
                if isinstance(node.func, ast.Attribute)
                else (node.func.id if isinstance(node.func, ast.Name) else "")
            )
            if name.casefold() in _SKIP_NAMES:
                result[ast.dump(node)] += 1
        # A module-wide pytestmark may use a bare marker or a collection of markers.
        # Include assignment structure so moving a function marker to module scope
        # does not appear equivalent merely because the marker count is unchanged.
        if (
            isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr))
            and node.value is not None
            and any(
                (
                    child.attr
                    if isinstance(child, ast.Attribute)
                    else child.id
                    if isinstance(child, ast.Name)
                    else ""
                ).casefold()
                in _SKIP_NAMES
                for child in ast.walk(node.value)
            )
        ):
            result["assigned:" + ast.dump(node)] += 1
        # Bare @pytest.mark.skip / @unittest.expectedFailure decorators.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for decorator in node.decorator_list:
                name = (
                    decorator.attr
                    if isinstance(decorator, ast.Attribute)
                    else (decorator.id if isinstance(decorator, ast.Name) else "")
                )
                if name.casefold() in _SKIP_NAMES:
                    result[ast.dump(decorator)] += 1
    return result


def test_weakening(before: str, after: str) -> bool:
    new = _signals(after)
    if new is None:
        # A newly uninspectable test requires review even when no syntax validator runs.
        return True
    old = _signals(before)
    if old is None:
        # Restoring an unparseable baseline is a legitimate repair.
        return False
    old_disabled, old_tests = old
    new_disabled, new_tests = new
    return bool(new_disabled - old_disabled) or any(
        new_tests.get(name, 0) < count for name, count in old_tests.items()
    )


def _signals(source: str) -> tuple[Counter[str], dict[str, int]] | None:
    try:
        tree = ast.parse(source)
        return _disabled(tree), _test_assertions(tree)
    except (SyntaxError, RecursionError):
        # ast.parse and ast.dump can exceed interpreter limits on complex syntax.
        return None


def _test_assertions(tree: ast.AST, prefix: str = "") -> dict[str, int]:
    result: dict[str, int] = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            result.update(_test_assertions(node, prefix + node.name + "."))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test"
        ):
            result[prefix + node.name] = sum(
                isinstance(child, ast.Assert)
                or (
                    isinstance(child, ast.Call)
                    and (
                        (
                            isinstance(child.func, ast.Attribute)
                            and (
                                child.func.attr.startswith("assert")
                                or child.func.attr in _ASSERTION_HELPERS
                            )
                        )
                        or (
                            isinstance(child.func, ast.Name) and child.func.id in _ASSERTION_HELPERS
                        )
                    )
                )
                for child in ast.walk(node)
            )
    return result
