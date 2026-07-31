#!/usr/bin/env python3
"""
generate_desktop.py

Generates a .desktop launcher file pointing to the installed kstars-sync binary.
"""

import shutil
from pathlib import Path


def generate_desktop_file() -> Path:
    # Find kstars-sync in PATH or default to ~/.local/bin/kstars-sync
    exe_path = shutil.which("kstars-sync") or str(Path.home() / ".local/bin/kstars-sync")

    desktop_content = f"""[Desktop Entry]
Type=Application
Name=KStars Sync
Comment=Synchronise KStars Git repository before and after running KStars
Exec={exe_path}
Icon=kstars
Terminal=true
Categories=Education;Science;Astronomy;
"""

    output_path = Path.cwd() / "kstars-sync.desktop"
    output_path.write_text(desktop_content)
    output_path.chmod(0o755)

    return output_path


if __name__ == "__main__":
    target = generate_desktop_file()
    print(f"Generated desktop entry at: {target}")
    print("Move it to ~/.local/share/applications/ to install.")
