"""Headless smoke test: actually launch the GUI under Xvfb and verify it
boots, builds widgets, can do a real save against a stubbed game install,
loads the resulting profile, and shuts down without errors.
"""

from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

from gameprofileusb import games as games_mod
from gameprofileusb import profiles as profiles_mod


def main() -> int:
    # Stub a fake game install so detect_games returns something.
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    val = root / "valorant" / "Config"
    val.mkdir(parents=True)
    (val / "GameUserSettings.ini").write_text("[Sens]\nx=1.0\n")
    (val / "Input.ini").write_text("binds...\n")
    fn = root / "fortnite" / "Config"
    fn.mkdir(parents=True)
    (fn / "GameUserSettings.ini").write_text("fortnite\n")

    games_mod.GAMES["valorant"].path_resolver = lambda: [val]
    games_mod.GAMES["fortnite"].path_resolver = lambda: [fn]
    games_mod.GAMES["cs2"].path_resolver = lambda: []
    games_mod.GAMES["apex"].path_resolver = lambda: []
    games_mod.GAMES["minecraft"].path_resolver = lambda: []
    games_mod.GAMES["overwatch"].path_resolver = lambda: []

    # Point the app at our temp folder for profiles.
    profiles_mod.default_profile_dir = lambda: root / "USB"

    from gameprofileusb.gui import GameProfileUSBApp

    print("[1/6] constructing app...")
    app = GameProfileUSBApp()
    print("[2/6] forcing initial paint...")
    app.update_idletasks()
    app.update()

    # Verify detection populated the sidebar.
    assert "valorant" in app.game_rows, "valorant row missing"
    assert "fortnite" in app.game_rows, "fortnite row missing"
    print(f"[3/6] sidebar populated with {len(app.game_rows)} games")

    # Run the converter.
    app.dpi_entry.insert(0, "800")
    app.sens_entry.insert(0, "0.4")
    app.game_select.set("valorant")
    app._convert_mouse_to_controller()
    result = app.controller_entry.get()
    assert result == "1.0", f"expected 1.0, got {result!r}"
    print(f"[4/6] sensitivity converter returned {result}")

    # Run a real save synchronously (skip the async wrapper) so the
    # screenshot captures populated log + progress.
    app.profile_dir_var.set(str(root / "USB"))
    app.profile_name_var.set("vmtest")
    app._save_settings()
    app.update_idletasks()
    app.update()
    profile_file = root / "USB" / "vmtest.json"
    assert profile_file.exists(), f"profile not written: {profile_file}"
    import json
    data = json.loads(profile_file.read_text())
    assert "valorant" in data["games"]
    assert "fortnite" in data["games"]
    print(f"[5/6] save_profile wrote {profile_file.name} with "
          f"{len(data['games'])} game(s)")

    # Refresh profiles so the dropdown + meta box show the saved profile.
    app._refresh_profiles()
    app.update_idletasks()
    app.update()

    screenshot = Path("/home/user/Settings-usb/screenshot.png")
    import subprocess
    subprocess.run(
        ["import", "-window", "root", str(screenshot)],
        check=True, env={"DISPLAY": ":99"},
    )
    print(f"[6/6] screenshot written to {screenshot}")

    app.destroy()
    tmp.cleanup()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
