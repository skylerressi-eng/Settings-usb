"""Profile load/save to a JSON file on a USB drive (or any chosen folder)."""

from __future__ import annotations

import json
import platform
import string
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

from . import games as games_mod

PROFILE_FILENAME = "gameprofileusb_profile.json"
PROFILE_VERSION = 1


def list_removable_drives() -> List[Path]:
    """Best-effort enumeration of likely USB mount points."""
    system = platform.system()
    candidates: List[Path] = []

    if system == "Windows":
        import ctypes

        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        DRIVE_REMOVABLE = 2
        for i, letter in enumerate(string.ascii_uppercase):
            if not (bitmask >> i) & 1:
                continue
            root = f"{letter}:\\"
            if ctypes.windll.kernel32.GetDriveTypeW(root) == DRIVE_REMOVABLE:
                candidates.append(Path(root))
    elif system == "Darwin":
        vol = Path("/Volumes")
        if vol.exists():
            candidates.extend(p for p in vol.iterdir() if p.is_dir())
    else:
        for base in (Path("/media") / Path.home().name, Path("/run/media") / Path.home().name, Path("/mnt")):
            if base.exists():
                candidates.extend(p for p in base.iterdir() if p.is_dir())

    return candidates


def default_profile_path() -> Path:
    drives = list_removable_drives()
    if drives:
        return drives[0] / PROFILE_FILENAME
    return Path.home() / PROFILE_FILENAME


def save_profile(
    path: Path,
    log: Optional[Callable[[str], None]] = None,
) -> Path:
    """Read all detected games' configs and save them to a JSON profile."""
    detected = games_mod.detect_games()
    profile: Dict[str, dict] = {
        "version": PROFILE_VERSION,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "host": platform.node(),
        "games": {},
    }
    for game in detected:
        if log:
            log(f"  reading {game.display_name}...")
        files = games_mod.read_game_configs(game.key, log=log)
        profile["games"][game.key] = {
            "display_name": game.display_name,
            "files": files,
        }
        if log:
            log(f"    captured {len(files)} file(s)")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    return path


def load_profile(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def apply_profile(
    path: Path,
    log: Optional[Callable[[str], None]] = None,
) -> Dict[str, int]:
    """Apply a previously-saved profile to this PC. Returns per-game write counts."""
    profile = load_profile(path)
    results: Dict[str, int] = {}
    for game_key, payload in profile.get("games", {}).items():
        files = payload.get("files", {})
        display = payload.get("display_name", game_key)
        if log:
            log(f"  applying {display} ({len(files)} file(s))...")
        try:
            written = games_mod.write_game_configs(game_key, files, log=log)
        except KeyError:
            if log:
                log(f"  ! unknown game key '{game_key}' in profile, skipping")
            written = 0
        results[game_key] = written
        if log:
            log(f"    wrote {written} file(s)")
    return results
