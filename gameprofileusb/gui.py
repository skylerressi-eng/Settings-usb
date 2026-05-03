"""customtkinter GUI for GameProfileUSB."""

from __future__ import annotations

import os
import platform
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Dict, List, Optional

import customtkinter as ctk

from . import games as games_mod
from . import profiles as profiles_mod
from . import sensitivity as sens_mod

# Color palette - dark gaming theme
BG = "#0b0c10"
PANEL = "#15171c"
PANEL_2 = "#1d2026"
PANEL_3 = "#22252c"
PANEL_HI = "#2a2e38"
ACCENT = "#7c3aed"
ACCENT_HOVER = "#6d28d9"
ACCENT_SOFT = "#3b1f70"
SUCCESS = "#10b981"
SUCCESS_HOVER = "#0e9b73"
SUCCESS_SOFT = "#0f3a2f"
WARN = "#f59e0b"
DANGER = "#ef4444"
TEXT = "#e8eaf0"
MUTED = "#8b8f9a"
DIM = "#5b6068"

GAME_GLYPH: Dict[str, str] = {
    "valorant": "V",
    "cs2": "CS",
    "fortnite": "FN",
    "apex": "AP",
    "minecraft": "MC",
    "overwatch": "OW",
}

STATUS_IDLE = ("ready", MUTED, PANEL_HI)
STATUS_BUSY = ("working...", "#fde68a", "#3b2f0a")
STATUS_DONE = ("done", "#bbf7d0", SUCCESS_SOFT)
STATUS_FAIL = ("error", "#fecaca", "#3b1414")


class GameRow(ctk.CTkFrame):
    """A single game card in the sidebar with checkbox, glyph, and status badge."""

    def __init__(self, parent, game: games_mod.DetectedGame, var: ctk.BooleanVar):
        super().__init__(parent, fg_color=PANEL_3, corner_radius=12)
        self.game = game

        glyph = ctk.CTkLabel(
            self, text=GAME_GLYPH.get(game.key, "?"),
            width=44, height=44, corner_radius=10,
            fg_color=ACCENT_SOFT, text_color="#ddd6fe",
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        glyph.grid(row=0, column=0, rowspan=2, padx=(10, 10), pady=10)

        ctk.CTkCheckBox(
            self, text=game.display_name, variable=var,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color=TEXT, checkbox_width=18, checkbox_height=18,
        ).grid(row=0, column=1, sticky="w", pady=(10, 0))

        path_text = str(game.config_paths[0])
        if len(path_text) > 48:
            path_text = "..." + path_text[-45:]
        if len(game.config_paths) > 1:
            path_text += f"  (+{len(game.config_paths) - 1} more)"
        ctk.CTkLabel(
            self, text=path_text, anchor="w",
            text_color=DIM, font=ctk.CTkFont(size=10),
        ).grid(row=1, column=1, sticky="w", pady=(0, 10))

        text, fg, bg = STATUS_IDLE
        self.status_badge = ctk.CTkLabel(
            self, text=text, fg_color=bg, text_color=fg,
            corner_radius=8, font=ctk.CTkFont(size=10, weight="bold"),
            width=72, height=22,
        )
        self.status_badge.grid(row=0, column=2, rowspan=2, padx=(8, 12))

        self.grid_columnconfigure(1, weight=1)

    def set_status(self, kind: str) -> None:
        mapping = {
            "idle": STATUS_IDLE, "busy": STATUS_BUSY,
            "done": STATUS_DONE, "fail": STATUS_FAIL,
        }
        text, fg, bg = mapping.get(kind, STATUS_IDLE)
        self.status_badge.configure(text=text, text_color=fg, fg_color=bg)


class GameProfileUSBApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title("GameProfileUSB")
        self.geometry("1240x820")
        self.minsize(1080, 680)
        self.configure(fg_color=BG)

        self.profile_dir_var = ctk.StringVar(
            value=str(profiles_mod.default_profile_dir())
        )
        self.profile_name_var = ctk.StringVar(value=profiles_mod.DEFAULT_PROFILE_NAME)
        self.selected_profile_var = ctk.StringVar(value="")
        self.backup_var = ctk.BooleanVar(value=True)
        self.current_action_var = ctk.StringVar(value="Idle")
        self.app_status_var = ctk.StringVar(value="Ready")

        self.game_check_vars: Dict[str, ctk.BooleanVar] = {}
        self.game_rows: Dict[str, GameRow] = {}
        self._busy = False

        self._build_layout()
        self._refresh_games()
        self._refresh_profiles()
        self.bind("<FocusIn>", self._on_focus)
        self.bind("<Control-s>", lambda _e: self._run_async(self._save_settings))
        self.bind("<Control-r>", lambda _e: self._refresh_games())
        self.log("Ready. Pick a USB folder, choose your games, then Save or Apply.")
        self.log("Tip: Ctrl+S = save, Ctrl+R = re-scan games.")

    def _on_focus(self, event) -> None:
        # Only refresh on top-level focus, not every internal widget focus.
        if event.widget is self:
            self._refresh_drives()

    # ---------------- layout ----------------
    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=0, minsize=340)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_sidebar()
        self._build_main()

    def _build_header(self) -> None:
        bar = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0, height=64)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(1, weight=1)

        logo = ctk.CTkLabel(
            bar, text="  GP", width=44, height=44, corner_radius=10,
            fg_color=ACCENT, text_color="#ffffff",
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        logo.grid(row=0, column=0, padx=(16, 12), pady=10)

        title = ctk.CTkFrame(bar, fg_color="transparent")
        title.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(
            title, text="GameProfileUSB",
            font=ctk.CTkFont(size=18, weight="bold"), text_color=TEXT,
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            title, text="Portable game settings  |  save once, play anywhere",
            font=ctk.CTkFont(size=11), text_color=MUTED,
        ).grid(row=1, column=0, sticky="w")

        status = ctk.CTkFrame(bar, fg_color="transparent")
        status.grid(row=0, column=2, padx=20)
        self.status_dot = ctk.CTkLabel(
            status, text="", width=12, height=12, corner_radius=6,
            fg_color=SUCCESS,
        )
        self.status_dot.grid(row=0, column=0, padx=(0, 8))
        ctk.CTkLabel(
            status, textvariable=self.app_status_var,
            font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT,
        ).grid(row=0, column=1)

    def _build_sidebar(self) -> None:
        side = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        side.grid(row=1, column=0, sticky="nsew")
        side.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            side, text="DETECTED GAMES",
            font=ctk.CTkFont(size=11, weight="bold"), text_color=MUTED,
        ).grid(row=0, column=0, padx=20, pady=(20, 2), sticky="w")
        self.detected_count_label = ctk.CTkLabel(
            side, text="Toggle the games you want to include",
            text_color=DIM, font=ctk.CTkFont(size=11),
        )
        self.detected_count_label.grid(row=1, column=0, padx=20, pady=(0, 8), sticky="w")

        self.games_frame = ctk.CTkScrollableFrame(side, fg_color=PANEL_2, corner_radius=12)
        self.games_frame.grid(row=2, column=0, padx=12, pady=4, sticky="nsew")

        button_row = ctk.CTkFrame(side, fg_color="transparent")
        button_row.grid(row=3, column=0, padx=12, pady=(8, 16), sticky="ew")
        button_row.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(
            button_row, text="Re-scan", command=self._refresh_games,
            fg_color=PANEL_2, hover_color=PANEL_HI, height=34,
        ).grid(row=0, column=0, padx=(0, 4), sticky="ew")
        ctk.CTkButton(
            button_row, text="Toggle all", command=self._toggle_all_games,
            fg_color=PANEL_2, hover_color=PANEL_HI, height=34,
        ).grid(row=0, column=1, padx=(4, 0), sticky="ew")

    def _build_main(self) -> None:
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=1, column=1, sticky="nsew", padx=18, pady=18)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(3, weight=1)

        self._build_profile_panel(main).grid(row=0, column=0, sticky="ew")
        self._build_action_panel(main).grid(row=1, column=0, sticky="ew", pady=(16, 0))
        self._build_converter(main).grid(row=2, column=0, sticky="ew", pady=(16, 0))
        self._build_log(main).grid(row=3, column=0, sticky="nsew", pady=(16, 0))

    def _section_header(self, parent, title: str, subtitle: str = "") -> None:
        ctk.CTkLabel(
            parent, text=title.upper(),
            font=ctk.CTkFont(size=11, weight="bold"), text_color=ACCENT,
        ).grid(row=0, column=0, columnspan=8, padx=18, pady=(14, 0), sticky="w")
        if subtitle:
            ctk.CTkLabel(
                parent, text=subtitle, text_color=MUTED,
                font=ctk.CTkFont(size=11),
            ).grid(row=1, column=0, columnspan=8, padx=18, pady=(0, 6), sticky="w")

    def _build_profile_panel(self, parent) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=14)
        frame.grid_columnconfigure(2, weight=1)

        self._section_header(
            frame, "USB / Profile folder",
            "Where your gameprofile JSON files live",
        )

        ctk.CTkLabel(frame, text="Drive", width=70, anchor="w", text_color=MUTED).grid(
            row=2, column=0, padx=(18, 6), pady=4, sticky="w"
        )
        self.drive_select = ctk.CTkOptionMenu(
            frame, values=self._drive_options(),
            command=self._on_drive_pick,
            fg_color=PANEL_2, button_color=ACCENT, button_hover_color=ACCENT_HOVER,
            text_color=TEXT, width=180,
        )
        self.drive_select.grid(row=2, column=1, sticky="w", pady=4)
        ctk.CTkEntry(frame, textvariable=self.profile_dir_var, height=32).grid(
            row=2, column=2, sticky="ew", padx=8, pady=4
        )
        folder_btns = ctk.CTkFrame(frame, fg_color="transparent")
        folder_btns.grid(row=2, column=3, padx=(0, 18), pady=4)
        ctk.CTkButton(
            folder_btns, text="Browse", width=80, height=32, command=self._pick_folder,
            fg_color=PANEL_2, hover_color=PANEL_HI,
        ).grid(row=0, column=0, padx=(0, 4))
        ctk.CTkButton(
            folder_btns, text="Open", width=60, height=32, command=self._open_folder,
            fg_color=PANEL_2, hover_color=PANEL_HI,
        ).grid(row=0, column=1)

        ctk.CTkLabel(frame, text="Profile", width=70, anchor="w", text_color=MUTED).grid(
            row=3, column=0, padx=(18, 6), pady=4, sticky="w"
        )
        self.profile_select = ctk.CTkOptionMenu(
            frame, values=["(no profiles yet)"],
            command=self._on_profile_pick,
            fg_color=PANEL_2, button_color=ACCENT, button_hover_color=ACCENT_HOVER,
            text_color=TEXT,
        )
        self.profile_select.grid(row=3, column=1, columnspan=2, sticky="ew", pady=4)
        prof_btns = ctk.CTkFrame(frame, fg_color="transparent")
        prof_btns.grid(row=3, column=3, padx=(0, 18), pady=4)
        ctk.CTkButton(
            prof_btns, text="Refresh", width=80, height=32,
            command=self._refresh_profiles,
            fg_color=PANEL_2, hover_color=PANEL_HI,
        ).grid(row=0, column=0, padx=(0, 4))
        ctk.CTkButton(
            prof_btns, text="Delete", width=60, height=32,
            command=self._delete_profile,
            fg_color="#3a1414", hover_color="#5a1818", text_color="#fecaca",
        ).grid(row=0, column=1)

        ctk.CTkLabel(frame, text="Save as", width=70, anchor="w", text_color=MUTED).grid(
            row=4, column=0, padx=(18, 6), pady=(4, 12), sticky="w"
        )
        ctk.CTkEntry(frame, textvariable=self.profile_name_var, height=32).grid(
            row=4, column=1, columnspan=2, sticky="ew", pady=(4, 12)
        )
        ctk.CTkLabel(frame, text=".json", text_color=DIM).grid(
            row=4, column=3, sticky="w", padx=(0, 18), pady=(4, 12)
        )

        meta_box = ctk.CTkFrame(frame, fg_color=PANEL_2, corner_radius=10)
        meta_box.grid(row=5, column=0, columnspan=4, sticky="ew", padx=18, pady=(0, 14))
        self.profile_meta_label = ctk.CTkLabel(
            meta_box, text="No profile selected.",
            text_color=MUTED, anchor="w", justify="left",
            font=ctk.CTkFont(size=11),
        )
        self.profile_meta_label.pack(fill="x", padx=12, pady=10, anchor="w")

        return frame

    def _build_action_panel(self, parent) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=14)
        frame.grid_columnconfigure((0, 1), weight=1)

        self._section_header(frame, "Actions")

        # Big "current action" hero label
        hero = ctk.CTkFrame(frame, fg_color=PANEL_2, corner_radius=12)
        hero.grid(row=2, column=0, columnspan=2, sticky="ew", padx=18, pady=(4, 12))
        hero.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hero, text="CURRENT ACTION",
            text_color=DIM, font=ctk.CTkFont(size=10, weight="bold"),
        ).grid(row=0, column=0, padx=14, pady=(10, 0), sticky="w")
        self.current_action_label = ctk.CTkLabel(
            hero, textvariable=self.current_action_var,
            text_color=TEXT, font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
        )
        self.current_action_label.grid(row=1, column=0, padx=14, pady=(0, 8), sticky="ew")
        self.progress = ctk.CTkProgressBar(
            hero, height=8, corner_radius=4,
            fg_color=PANEL_HI, progress_color=ACCENT,
        )
        self.progress.grid(row=2, column=0, padx=14, pady=(0, 14), sticky="ew")
        self.progress.set(0)

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.grid(row=3, column=0, columnspan=2, padx=18, pady=(0, 8), sticky="ew")
        btn_row.grid_columnconfigure((0, 1, 2), weight=1)

        self.save_btn = ctk.CTkButton(
            btn_row, text="Save My Settings", height=48,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self._run_async(self._save_settings),
        )
        self.save_btn.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        self.apply_btn = ctk.CTkButton(
            btn_row, text="Apply My Settings", height=48,
            fg_color=SUCCESS, hover_color=SUCCESS_HOVER,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self._run_async(self._apply_settings),
        )
        self.apply_btn.grid(row=0, column=1, padx=6, sticky="ew")

        self.restore_btn = ctk.CTkButton(
            btn_row, text="Restore Backup", height=48,
            fg_color=WARN, hover_color="#c2820a",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self._run_async(self._restore_backup),
        )
        self.restore_btn.grid(row=0, column=2, padx=(6, 0), sticky="ew")

        ctk.CTkCheckBox(
            frame, text="Auto-backup current configs before applying (recommended)",
            variable=self.backup_var,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            checkbox_width=18, checkbox_height=18,
        ).grid(row=4, column=0, columnspan=2, padx=18, pady=(4, 14), sticky="w")

        return frame

    def _build_converter(self, parent) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=14)
        frame.grid_columnconfigure((1, 3, 5), weight=1)

        self._section_header(
            frame, "Sensitivity converter",
            "Mouse eDPI <-> controller (0-10).  Formula: (DPI x sens) / 1600 x 5",
        )

        ctk.CTkLabel(frame, text="Game", text_color=MUTED).grid(
            row=2, column=0, padx=(18, 6), pady=8, sticky="e"
        )
        self.game_select = ctk.CTkOptionMenu(
            frame, values=list(sens_mod.SUPPORTED_GAMES),
            fg_color=PANEL_2, button_color=ACCENT, button_hover_color=ACCENT_HOVER,
            text_color=TEXT,
        )
        self.game_select.grid(row=2, column=1, pady=8, sticky="ew")

        ctk.CTkLabel(frame, text="DPI", text_color=MUTED).grid(
            row=2, column=2, padx=(18, 6), pady=8, sticky="e"
        )
        self.dpi_entry = ctk.CTkEntry(frame, placeholder_text="800", height=32)
        self.dpi_entry.grid(row=2, column=3, pady=8, sticky="ew")

        ctk.CTkLabel(frame, text="In-game sens", text_color=MUTED).grid(
            row=2, column=4, padx=(18, 6), pady=8, sticky="e"
        )
        self.sens_entry = ctk.CTkEntry(frame, placeholder_text="0.4", height=32)
        self.sens_entry.grid(row=2, column=5, padx=(0, 18), pady=8, sticky="ew")

        ctk.CTkLabel(frame, text="Controller (0-10)", text_color=MUTED).grid(
            row=3, column=0, padx=(18, 6), pady=(8, 14), sticky="e"
        )
        self.controller_entry = ctk.CTkEntry(frame, placeholder_text="result", height=32)
        self.controller_entry.grid(row=3, column=1, pady=(8, 14), sticky="ew")

        ctk.CTkButton(
            frame, text="Mouse -> Controller", height=34,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._convert_mouse_to_controller,
        ).grid(row=3, column=2, columnspan=2, padx=8, pady=(8, 14), sticky="ew")

        ctk.CTkButton(
            frame, text="Controller -> Mouse", height=34,
            fg_color=PANEL_2, hover_color=PANEL_HI,
            command=self._convert_controller_to_mouse,
        ).grid(row=3, column=4, columnspan=2, padx=(8, 18), pady=(8, 14), sticky="ew")

        return frame

    def _build_log(self, parent) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=14)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(2, weight=1)

        self._section_header(frame, "Activity log")

        controls = ctk.CTkFrame(frame, fg_color="transparent")
        controls.grid(row=2, column=0, sticky="nsew", padx=12, pady=(4, 12))
        controls.grid_columnconfigure(0, weight=1)
        controls.grid_rowconfigure(0, weight=1)

        self.log_box = ctk.CTkTextbox(
            controls, fg_color=PANEL_2, text_color="#d8dbe2",
            font=ctk.CTkFont(family="Consolas", size=12), corner_radius=10,
        )
        self.log_box.grid(row=0, column=0, sticky="nsew")
        self.log_box.configure(state="disabled")

        clear_btn = ctk.CTkButton(
            controls, text="Clear log", width=90, height=28,
            fg_color=PANEL_2, hover_color=PANEL_HI,
            command=self._clear_log,
        )
        clear_btn.grid(row=1, column=0, sticky="e", pady=(8, 0))

        return frame

    # ---------------- helpers ----------------
    def _drive_options(self) -> List[str]:
        opts = [str(p) for p in profiles_mod.list_removable_drives()]
        opts.append("Other...")
        return opts

    def _selected_game_keys(self) -> List[str]:
        return [k for k, v in self.game_check_vars.items() if v.get()]

    def log(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{stamp}] {message}\n"

        def _append() -> None:
            self.log_box.configure(state="normal")
            self.log_box.insert("end", line)
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        self.after(0, _append)

    def _clear_log(self) -> None:
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _set_app_status(self, text: str, color: str) -> None:
        def _do() -> None:
            self.app_status_var.set(text)
            self.status_dot.configure(fg_color=color)
        self.after(0, _do)

    def _set_action(self, text: str) -> None:
        self.after(0, lambda: self.current_action_var.set(text))

    def _set_progress(self, fraction: float) -> None:
        self.after(0, lambda: self.progress.set(max(0.0, min(1.0, fraction))))

    def _set_buttons_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        def _do() -> None:
            self.save_btn.configure(state=state)
            self.apply_btn.configure(state=state)
            self.restore_btn.configure(state=state)
        self.after(0, _do)

    def _set_row_status(self, key: str, kind: str) -> None:
        row = self.game_rows.get(key)
        if row is None:
            return
        self.after(0, lambda: row.set_status(kind))

    def _reset_all_row_status(self) -> None:
        for row in self.game_rows.values():
            self.after(0, lambda r=row: r.set_status("idle"))

    def _refresh_games(self) -> None:
        for child in self.games_frame.winfo_children():
            child.destroy()
        self.game_check_vars.clear()
        self.game_rows.clear()

        detected = games_mod.detect_games()
        if not detected:
            ctk.CTkLabel(
                self.games_frame,
                text="No supported games detected on this PC.\n\n"
                     "Install Valorant, CS2, Fortnite, Apex,\n"
                     "Minecraft, or Overwatch 2 and re-scan.",
                text_color=MUTED, justify="left",
            ).pack(padx=12, pady=18, anchor="w")
            self.detected_count_label.configure(text="0 games found")
            self.log("No supported games detected.")
            return

        for game in detected:
            var = ctk.BooleanVar(value=True)
            self.game_check_vars[game.key] = var
            row = GameRow(self.games_frame, game, var)
            row.pack(fill="x", padx=4, pady=4)
            self.game_rows[game.key] = row

        self.detected_count_label.configure(
            text=f"{len(detected)} game(s) found - all selected by default"
        )
        self.log(f"Detected {len(detected)} game(s): "
                 + ", ".join(g.display_name for g in detected))

    def _toggle_all_games(self) -> None:
        if not self.game_check_vars:
            return
        new_value = not all(v.get() for v in self.game_check_vars.values())
        for v in self.game_check_vars.values():
            v.set(new_value)

    def _refresh_profiles(self) -> None:
        folder = Path(self.profile_dir_var.get())
        profiles = profiles_mod.list_profiles(folder)
        if profiles:
            names = [p.name for p in profiles]
            self.profile_select.configure(values=names)
            current = self.selected_profile_var.get()
            if current not in names:
                current = names[0]
                self.selected_profile_var.set(current)
            self.profile_select.set(current)
            self._load_profile_meta(folder / current)
        else:
            self.profile_select.configure(values=["(no profiles yet)"])
            self.profile_select.set("(no profiles yet)")
            self.profile_meta_label.configure(
                text=f"No profiles found in:\n{folder}",
                text_color=MUTED,
            )

    def _on_drive_pick(self, value: str) -> None:
        if value == "Other...":
            self._pick_folder()
            return
        self.profile_dir_var.set(str(Path(value) / "GameProfileUSB"))
        self._refresh_profiles()

    def _on_profile_pick(self, value: str) -> None:
        if value == "(no profiles yet)":
            return
        self.selected_profile_var.set(value)
        self.profile_name_var.set(Path(value).stem)
        self._load_profile_meta(Path(self.profile_dir_var.get()) / value)

    def _load_profile_meta(self, path: Path) -> None:
        try:
            meta = profiles_mod.profile_summary(path)
        except (OSError, ValueError) as exc:
            self.profile_meta_label.configure(
                text=f"Could not read profile: {exc}", text_color=DANGER,
            )
            return
        counts = meta["game_counts"]
        games_str = "  -  ".join(f"{k} ({n} files)" for k, n in counts.items()) or "no games"
        text = (
            f"Saved {meta['saved_at']}   |   host: {meta['host']}   |   "
            f"format v{meta['version']}\nIncludes:  {games_str}"
        )
        self.profile_meta_label.configure(text=text, text_color=TEXT)

    def _pick_folder(self) -> None:
        chosen = filedialog.askdirectory(
            title="Pick USB folder for profiles",
            initialdir=self.profile_dir_var.get() or str(Path.home()),
        )
        if chosen:
            self.profile_dir_var.set(chosen)
            self._refresh_profiles()

    def _open_folder(self) -> None:
        folder = Path(self.profile_dir_var.get())
        if not folder.exists():
            try:
                folder.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                self.log(f"ERROR: cannot create {folder}: {exc}")
                return
        try:
            system = platform.system()
            if system == "Windows":
                os.startfile(str(folder))  # type: ignore[attr-defined]
            elif system == "Darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except OSError as exc:
            self.log(f"ERROR: could not open folder: {exc}")

    def _delete_profile(self) -> None:
        folder = Path(self.profile_dir_var.get())
        name = self.selected_profile_var.get()
        if not name or name == "(no profiles yet)":
            self.log("ERROR: no profile selected to delete.")
            return
        path = folder / name
        if not messagebox.askyesno(
            "Delete profile",
            f"Permanently delete '{name}'?\n\n{path}\n\nThis cannot be undone.",
        ):
            return
        try:
            profiles_mod.delete_profile(path)
            self.log(f"Deleted profile: {name}")
            self.selected_profile_var.set("")
            self._refresh_profiles()
        except OSError as exc:
            self.log(f"ERROR: could not delete profile: {exc}")

    def _refresh_drives(self) -> None:
        self.drive_select.configure(values=self._drive_options())

    def _run_async(self, func) -> None:
        if self._busy:
            self.log("ERROR: another operation is already running.")
            return
        threading.Thread(target=func, daemon=True).start()

    # ---------------- save / apply ----------------
    def _begin_op(self, label: str) -> None:
        self._busy = True
        self._set_buttons_enabled(False)
        self._set_app_status("Working", WARN)
        self._set_action(label)
        self._set_progress(0)
        self._reset_all_row_status()

    def _end_op(self, label: str, ok: bool) -> None:
        self._busy = False
        self._set_buttons_enabled(True)
        self._set_app_status("Ready" if ok else "Error", SUCCESS if ok else DANGER)
        self._set_action(label)
        self._set_progress(1.0 if ok else 0.0)

    def _make_progress_cb(self, verb: str):
        def cb(stage: str, key: str, index: int, total: int) -> None:
            if stage == "start":
                self._set_action(f"{verb} {total} game(s)...")
                self._set_progress(0.0)
            elif stage == "game":
                spec = games_mod.GAMES.get(key)
                name = spec.display_name if spec else key
                self._set_action(f"{verb} {name}...   ({index} of {total})")
                self._set_progress((index - 1) / max(total, 1))
                self._set_row_status(key, "busy")
                # Mark previously processed games as done.
                for k in list(self.game_rows.keys()):
                    if k == key:
                        continue
                    row = self.game_rows[k]
                    if row.status_badge.cget("text") == STATUS_BUSY[0]:
                        self._set_row_status(k, "done")
            elif stage == "done":
                self._set_progress(1.0)
                # Last in-flight game gets marked done.
                for k, row in self.game_rows.items():
                    if row.status_badge.cget("text") == STATUS_BUSY[0]:
                        self._set_row_status(k, "done")
        return cb

    def _current_profile_path(self) -> Optional[Path]:
        folder = Path(self.profile_dir_var.get())
        name = self.profile_name_var.get().strip()
        if not name:
            self.log("ERROR: profile name is empty.")
            return None
        return profiles_mod.profile_path(folder, name)

    def _save_settings(self) -> None:
        path = self._current_profile_path()
        if path is None:
            return
        selected = self._selected_game_keys()
        if not selected:
            self.log("ERROR: select at least one game to save.")
            return
        self._begin_op("Scanning for game settings...")
        self.log(f"Saving profile to {path}")
        try:
            profiles_mod.save_profile(
                path, selected_games=selected, log=self.log,
                progress=self._make_progress_cb("Saving"),
            )
            self.log(f"OK  -  Profile saved to {path}")
            self.after(0, self._refresh_profiles)
            self._end_op(f"Saved profile -> {path.name}", ok=True)
        except Exception as exc:  # noqa: BLE001
            self.log(f"ERROR while saving: {exc}")
            self._end_op(f"Save failed: {exc}", ok=False)

    def _apply_settings(self) -> None:
        folder = Path(self.profile_dir_var.get())
        name = self.selected_profile_var.get() or self.profile_name_var.get()
        if not name or name == "(no profiles yet)":
            self.log("ERROR: no profile selected to apply.")
            return
        if name.endswith(".json"):
            path = folder / name
        else:
            path = profiles_mod.profile_path(folder, name)
        if not path.exists():
            self.log(f"ERROR: profile not found at {path}")
            return
        selected = self._selected_game_keys() or None
        self._begin_op("Preparing to apply settings...")
        self.log(f"Applying profile from {path}")
        try:
            results = profiles_mod.apply_profile(
                path, selected_games=selected, log=self.log,
                make_backup=self.backup_var.get(),
                progress=self._make_progress_cb("Applying"),
            )
            total = sum(results.values())
            self.log(f"OK  -  Applied {total} file(s) across {len(results)} game(s).")
            self._end_op(f"Applied {total} file(s) from {path.name}", ok=True)
        except Exception as exc:  # noqa: BLE001
            self.log(f"ERROR while applying: {exc}")
            self._end_op(f"Apply failed: {exc}", ok=False)

    def _restore_backup(self) -> None:
        folder = Path(self.profile_dir_var.get())
        name = self.selected_profile_var.get()
        path: Optional[Path] = None
        if name and name != "(no profiles yet)" and (folder / name).exists():
            candidate = folder / name
            if profiles_mod.is_backup(candidate):
                path = candidate
        if path is None:
            backups = profiles_mod.list_backups(folder)
            if not backups:
                self.log("ERROR: no restore-*.json backups found in this folder.")
                return
            path = backups[0]
            self.log(f"Using newest backup: {path.name}")

        if not messagebox.askyesno(
            "Restore backup",
            f"Restore configs from:\n{path.name}\n\n"
            "This will overwrite current settings (and delete files\n"
            "the most recent apply created). Continue?",
        ):
            return

        self._begin_op("Restoring backup...")
        self.log(f"Restoring backup from {path}")
        try:
            results = profiles_mod.restore_backup(
                path, log=self.log,
                progress=self._make_progress_cb("Restoring"),
            )
            total = sum(results.values())
            self.log(f"OK  -  Restored {total} file(s) across {len(results)} game(s).")
            self._end_op(f"Restored {total} file(s) from {path.name}", ok=True)
        except Exception as exc:  # noqa: BLE001
            self.log(f"ERROR while restoring: {exc}")
            self._end_op(f"Restore failed: {exc}", ok=False)

    # ---------------- converter ----------------
    def _read_dpi_sens(self):
        try:
            dpi = float(self.dpi_entry.get())
            sens = float(self.sens_entry.get() or 0)
        except ValueError:
            self.log("ERROR: DPI and in-game sens must be numbers.")
            return None, None
        return dpi, sens

    def _convert_mouse_to_controller(self) -> None:
        dpi, sens = self._read_dpi_sens()
        if dpi is None:
            return
        try:
            value = sens_mod.mouse_to_controller(dpi, sens, self.game_select.get())
        except ValueError as exc:
            self.log(f"ERROR: {exc}")
            return
        self.controller_entry.delete(0, "end")
        self.controller_entry.insert(0, str(value))
        self.log(
            f"{self.game_select.get()}: {dpi} DPI x {sens} sens -> "
            f"controller {value} (eDPI {sens_mod.edpi(dpi, sens)})"
        )

    def _convert_controller_to_mouse(self) -> None:
        try:
            controller = float(self.controller_entry.get())
            dpi = float(self.dpi_entry.get())
        except ValueError:
            self.log("ERROR: controller value and DPI must be numbers.")
            return
        try:
            sens = sens_mod.controller_to_mouse(controller, dpi, self.game_select.get())
        except ValueError as exc:
            self.log(f"ERROR: {exc}")
            return
        self.sens_entry.delete(0, "end")
        self.sens_entry.insert(0, str(sens))
        self.log(
            f"{self.game_select.get()}: controller {controller} @ {dpi} DPI -> "
            f"in-game sens {sens}"
        )


def run() -> None:
    app = GameProfileUSBApp()
    app.mainloop()
