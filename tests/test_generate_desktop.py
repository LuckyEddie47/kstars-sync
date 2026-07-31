import importlib.util
import sys
from pathlib import Path

# Resolve path to generate_desktop.py in the repository root (parent of tests/)
repo_root = Path(__file__).resolve().parent.parent
script_path = repo_root / "generate_desktop.py"

if not script_path.exists():
    # Fallback if tests/ is executed from a non-standard layout
    script_path = Path(__file__).resolve().parent / ".." / "generate_desktop.py"

spec = importlib.util.spec_from_file_location("generate_desktop", script_path.resolve())
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load spec for {script_path}")

generate_desktop = importlib.util.module_from_spec(spec)
sys.modules["generate_desktop"] = generate_desktop
spec.loader.exec_module(generate_desktop)

generate_desktop_file = generate_desktop.generate_desktop_file


def test_generate_desktop_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    generated_path = generate_desktop_file()

    assert generated_path.exists()
    assert generated_path == tmp_path / "kstars-sync.desktop"

    content = generated_path.read_text()

    assert "[Desktop Entry]" in content
    assert "Type=Application" in content
    assert "Name=KStars Sync" in content
    assert f"Exec={sys.executable}" in content
    assert "Terminal=true" in content

    # Verify file is executable
    assert (generated_path.stat().st_mode & 0o111) != 0