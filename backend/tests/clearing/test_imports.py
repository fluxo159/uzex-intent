import ast
import pathlib
import subprocess
import sys

FORBIDDEN = ("intake", "explain", "anthropic", "google", "genai", "openai", "httpx", "requests", "elevenlabs")
PKG = pathlib.Path(__file__).resolve().parents[2] / "app" / "clearing"

def test_clearing_has_no_forbidden_imports():
    files = [f for f in PKG.glob("*.py") if f.name != "router.py"]
    assert files
    for f in files:
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""] + [a.name for a in node.names]
            for n in names:
                assert not any(part in FORBIDDEN for part in n.split(".")), f"{f.name}: {n}"

def test_engine_import_does_not_pull_forbidden_modules():
    code = ("import sys; import app.clearing.engine; "
            "bad=[m for m in sys.modules if m.startswith(('app.intake','app.explain','anthropic','google.genai','openai'))]; "
            "print(bad); sys.exit(1 if bad else 0)")
    r = subprocess.run([sys.executable, "-c", code], cwd=PKG.parents[1], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
