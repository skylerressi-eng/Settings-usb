"""Profile load/save to a JSON file on a regular USB drive (or any folder).

A "profile" is a single JSON file. Multiple named profiles can live side by
side in the same folder; the GUI lists every ``*.json`` profile it finds.
Before any apply, the current on-disk configs are snapshotted to a sibling
``restore-<timestamp>.json`` so the user can roll back.
"""

from __future__ import annotations

import json
import platform
import re
import string
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

ProgressCb = Callable[[str, str, int, int], None]
"""Called as ``progress(stage, game_key, index, total)``.

``stage`` is one of ``"start"``, ``"game"``, or ``"done"``. ``game_key`` is the
key currently being processed (empty for ``start``/``done``). ``index`` is the
1-based position; ``total`` is the total number of games for the run.
"""

from . import games as games_mod

PROFILE_GLOB = "*.json"
PROFILE_VERSION = 2
DEFAULT_PROFILE_NAME = "my-profile"


def list_removable_drives() -> List[Path]:
    """Best-effort enumeration of likely USB mount points."""
    system = platform.system()
    candidates: List[Path] = []

    if system == "Windows":
        try:
            import ctypes

            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            DRIVE_REMOVABLE = 2
            for i, letter in enumerate(string.ascii_uppercase):
                if not (bitmask >> i) & 1:
                    continue
                root = f"{letter}:\\"
                if ctypes.windll.kernel32.GetDriveTypeW(root) == DRIVE_REMOVABLE:
                    candidates.append(Path(root))
        except (OSError, AttributeError):
            pass
    elif system == "Darwin":
        vol = Path("/Volumes")
        if vol.exists():
            candidates.extend(p for p in vol.iterdir() if p.is_dir())
    else:
        user = Path.home().name
        for base in (
            Path("/media") / user,
            Path("/run/media") / user,
            Path("/media"),
            Path("/mnt"),
        ):
            if base.exists():
                candidates.extend(p for p in base.iterdir() if p.is_dir())

    # de-dupe while preserving order
    seen: List[Path] = []
    for c in candidates:
        if c not in seen:
            seen.append(c)
    return seen


def default_profile_dir() -> Path:
    drives = list_removable_drives()
    if drives:
        return drives[0] / "GameProfileUSB"
    return Path.home() / "GameProfileUSB"


def list_profiles(folder: Path) -> List[Path]:
    folder = Path(folder)
    if not folder.exists():
        return []
    return sorted(p for p in folder.glob(PROFILE_GLOB) if p.is_file())


def _safe_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip()) or DEFAULT_PROFILE_NAME
    return cleaned[:64]


def profile_path(folder: Path, name: str) -> Path:
    name = _safe_name(name)
    if not name.endswith(".json"):
        name += ".json"
    return Path(folder) / name


def save_profile(
    path: Path,
    selected_games: Optional[Iterable[str]] = None,
    log: Optional[Callable[[str], None]] = None,
    progress: Optional[ProgressCb] = None,
) -> Path:
    """Read selected (or all detected) games' configs and save a JSON profile."""
    detected = games_mod.detect_games()
    if selected_games is not None:
        wanted = set(selected_games)
        detected = [g for g in detected if g.key in wanted]

    total = len(detected)
    if progress:
        progress("start", "", 0, total)

    profile: Dict[str, Any] = {
        "version": PROFILE_VERSION,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "host": platform.node(),
        "games": {},
    }
    games_block: Dict[str, dict] = profile["games"]

    for index, game in enumerate(detected, start=1):
        if progress:
            progress("game", game.key, index, total)
        if log:
            log(f"-> Taking {game.display_name} settings...")
        files = games_mod.read_game_configs(game.key, log=log)
        games_block[game.key] = {
            "display_name": game.display_name,
            "files": files,
        }
        if log:
            log(f"   captured {len(files)} file(s) from {game.display_name}")

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    if progress:
        progress("done", "", total, total)
    return path


def load_profile(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def profile_summary(path: Path) -> Dict[str, object]:
    """Lightweight summary used by the GUI without loading every byte twice."""
    data = load_profile(path)
    games = data.get("games", {})
    return {
        "saved_at": data.get("saved_at", "unknown"),
        "host": data.get("host", "unknown"),
        "version": data.get("version", "?"),
        "game_counts": {
            key: len(payload.get("files", {}))
            for key, payload in games.items()
        },
    }


def _backup_path(profile: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path(profile).parent / f"restore-{stamp}.json"


def _build_backup(profile_data: dict) -> dict:
    backup: Dict[str, object] = {
        "version": PROFILE_VERSION,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "host": platform.node(),
        "kind": "auto-restore-snapshot",
        "games": {},
    }
    games_block: Dict[str, dict] = backup["games"]  # type: ignore[assignment]
    for key, payload in profile_data.get("games", {}).items():
        rels = list(payload.get("files", {}).keys())
        try:
            snap = games_mod.snapshot_current_configs(key, rels)
        except KeyError:
            continue
        # Flatten: store one snapshot per existing root.
        games_block[key] = {
            "display_name": payload.get("display_name", key),
            "snapshots": snap,
        }
    return backup


def apply_profile(
    path: Path,
    selected_games: Optional[Iterable[str]] = None,
    log: Optional[Callable[[str], None]] = None,
    make_backup: bool = True,
    progress: Optional[ProgressCb] = None,
) -> Dict[str, int]:
    """Apply a saved profile. Returns per-game counts of files written."""
    profile = load_profile(path)
    games_in_profile = profile.get("games", {})
    if selected_games is not None:
        wanted = set(selected_games)
        games_in_profile = {k: v for k, v in games_in_profile.items() if k in wanted}

    total = len(games_in_profile)
    if progress:
        progress("start", "", 0, total)

    if make_backup and games_in_profile:
        backup = _build_backup({"games": games_in_profile})
        backup_path = _backup_path(path)
        try:
            backup_path.write_text(json.dumps(backup, indent=2), encoding="utf-8")
            if log:
                log(f"   backup written -> {backup_path.name}")
        except OSError as exc:
            if log:
                log(f"   ! could not write backup: {exc}")

    results: Dict[str, int] = {}
    for index, (game_key, payload) in enumerate(games_in_profile.items(), start=1):
        files = payload.get("files", {})
        display = payload.get("display_name", game_key)
        if progress:
            progress("game", game_key, index, total)
        if log:
            log(f"-> Applying {display} settings ({len(files)} file(s))...")
        try:
            written = games_mod.write_game_configs(game_key, files, log=log)
        except KeyError:
            if log:
                log(f"   ! unknown game key '{game_key}' in profile, skipping")
            written = 0
        results[game_key] = written
        if log:
            log(f"   applied {written} file(s) to {display}")
    if progress:
        progress("done", "", total, total)
    return results
