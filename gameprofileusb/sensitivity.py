"""Mouse eDPI <-> controller sensitivity conversion.

Uses the project formula:
    controller_sens = (DPI * in_game_sens) / 1600 * 5

Controller scale is clamped to 0-10.
"""

from __future__ import annotations

SUPPORTED_GAMES = ("valorant", "cs2", "apex", "fortnite")
_DIVISOR = 1600.0
_MULTIPLIER = 5.0


def _normalize(game: str) -> str:
    g = game.strip().lower()
    if g not in SUPPORTED_GAMES:
        raise ValueError(
            f"Unsupported game '{game}'. Supported: {', '.join(SUPPORTED_GAMES)}"
        )
    return g


def mouse_to_controller(dpi: float, in_game_sens: float, game: str) -> float:
    """Convert mouse DPI + in-game sens to a controller value in [0, 10]."""
    _normalize(game)
    if dpi <= 0 or in_game_sens <= 0:
        raise ValueError("DPI and in-game sensitivity must be positive.")
    raw = (dpi * in_game_sens) / _DIVISOR * _MULTIPLIER
    return round(max(0.0, min(10.0, raw)), 3)


def controller_to_mouse(controller_sens: float, dpi: float, game: str) -> float:
    """Invert the formula to get the in-game mouse sens for a given DPI."""
    _normalize(game)
    if not 0 <= controller_sens <= 10:
        raise ValueError("Controller sensitivity must be in [0, 10].")
    if dpi <= 0:
        raise ValueError("DPI must be positive.")
    return round((controller_sens * _DIVISOR) / (_MULTIPLIER * dpi), 4)


def edpi(dpi: float, in_game_sens: float) -> float:
    return round(dpi * in_game_sens, 3)
