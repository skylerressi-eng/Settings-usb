"""Game detection and config file collection.

Each game is described by a list of candidate paths (with glob support) under
common Windows user folders. ``detect_games`` returns the games whose config
locations exist on this machine; ``read_game_configs`` loads the file contents
so they can be serialized into a profile.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from glob import glob
from pathlib import Path
from typing import Callable, Dict, List, Optional


def _home() -> Path:
    return Path(os.path.expanduser("~"))


def _appdata_local() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or _home() / "AppData" / "Local")


def _appdata_roaming() -> Path:
    return Path(os.environ.get("APPDATA") or _home() / "AppData" / "Roaming")


def _documents() -> Path:
    docs = _home() / "Documents"
    onedrive = _home() / "OneDrive" / "Documents"
    return onedrive if onedrive.exists() and not docs.exists() else docs


def _steam_userdata_candidates() -> List[Path]:
    roots = [
        Path("C:/Program Files (x86)/Steam/userdata"),
        Path("C:/Program Files/Steam/userdata"),
        _home() / ".steam" / "steam" / "userdata",
        _home() / ".local" / "share" / "Steam" / "userdata",
    ]
    return [r for r in roots if r.exists()]


@dataclass
class GameSpec:
    key: str
    display_name: str
    path_resolver: Callable[[], List[Path]]
    file_globs: List[str] = field(default_factory=lambda: ["**/*"])
    max_files: int = 50


def _valorant_paths() -> List[Path]:
    return [_appdata_local() / "VALORANT" / "Saved" / "Config"]


def _cs2_paths() -> List[Path]:
    out: List[Path] = []
    for root in _steam_userdata_candidates():
        for user_dir in root.glob("*"):
            cfg = user_dir / "730" / "local" / "cfg"
            if cfg.exists():
                out.append(cfg)
    return out


def _fortnite_paths() -> List[Path]:
    return [_appdata_local() / "FortniteGame" / "Saved" / "Config"]


def _apex_paths() -> List[Path]:
    return [_documents() / "Respawn" / "Apex" / "profile"]


def _minecraft_paths() -> List[Path]:
    return [_appdata_roaming() / ".minecraft"]


def _overwatch_paths() -> List[Path]:
    return [_documents() / "Overwatch" / "Settings"]


GAMES: Dict[str, GameSpec] = {
    "valorant": GameSpec(
        "valorant", "Valorant", _valorant_paths,
        file_globs=["**/*.ini", "**/*.json"],
    ),
    "cs2": GameSpec(
        "cs2", "Counter-Strike 2", _cs2_paths,
        file_globs=["**/*.cfg", "**/*.txt", "**/*.vcfg"],
    ),
    "fortnite": GameSpec(
        "fortnite", "Fortnite", _fortnite_paths,
        file_globs=["**/*.ini"],
    ),
    "apex": GameSpec(
        "apex", "Apex Legends", _apex_paths,
        file_globs=["**/*.cfg", "**/*.txt"],
    ),
    "minecraft": GameSpec(
        "minecraft", "Minecraft", _minecraft_paths,
        file_globs=["options.txt", "optionsof.txt", "optionsshaders.txt"],
    ),
    "overwatch": GameSpec(
        "overwatch", "Overwatch 2", _overwatch_paths,
        file_globs=["**/*.ini", "**/*.txt"],
    ),
}


@dataclass
class DetectedGame:
    key: str
    display_name: str
    config_paths: List[Path]


def detect_games() -> List[DetectedGame]:
    found: List[DetectedGame] = []
    for spec in GAMES.values():
        existing = [p for p in spec.path_resolver() if p.exists()]
        if existing:
            found.append(DetectedGame(spec.key, spec.display_name, existing))
    return found


def _collect_files(root: Path, patterns: List[str], cap: int) -> List[Path]:
    seen: List[Path] = []
    for pattern in patterns:
        for match in glob(str(root / pattern), recursive=True):
            p = Path(match)
            if p.is_file() and p not in seen:
                seen.append(p)
                if len(seen) >= cap:
                    return seen
    return seen


def read_game_configs(
    game_key: str,
    log: Optional[Callable[[str], None]] = None,
) -> Dict[str, str]:
    """Return a {relative_path: text_content} map for the given game."""
    spec = GAMES.get(game_key)
    if spec is None:
        raise KeyError(game_key)

    contents: Dict[str, str] = {}
    for root in spec.path_resolver():
        if not root.exists():
            continue
        files = _collect_files(root, spec.file_globs, spec.max_files)
        for f in files:
            try:
                rel = f.relative_to(root).as_posix()
                contents[f"{root.name}/{rel}"] = f.read_text(
                    encoding="utf-8", errors="replace"
                )
            except OSError as exc:
                if log:
                    log(f"  ! could not read {f}: {exc}")
    return contents


def write_game_configs(
    game_key: str,
    files: Dict[str, str],
    log: Optional[Callable[[str], None]] = None,
) -> int:
    """Write previously-saved configs back to the first existing target root."""
    spec = GAMES.get(game_key)
    if spec is None:
        raise KeyError(game_key)

    targets = [p for p in spec.path_resolver() if p.exists()]
    if not targets:
        if log:
            log(f"  ! no install location for {spec.display_name}, skipping")
        return 0
    target_root = targets[0].parent

    written = 0
    for rel, text in files.items():
        dest = target_root / rel
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")
            written += 1
        except OSError as exc:
            if log:
                log(f"  ! failed to write {dest}: {exc}")
    return written
