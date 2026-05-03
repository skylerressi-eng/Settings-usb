"""customtkinter GUI for GameProfileUSB."""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from typing import Dict, List, Optional

import customtkinter as ctk

from . import games as games_mod
from . import profiles as profiles_mod
from . import sensitivity as sens_mod

ACCENT = "#7c3aed"
ACCENT_HOVER = "#6d28d9"
DANGER = "#ef4444"
SUCCESS = "#10b981"
SUCCESS_HOVER = "#0e9b73"
PANEL = "#15171c"
PANEL_2 = "#1d2026"
PANEL_3 = "#22252c"
MUTED = "#8b8f9a"


class GameProfileUSBApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title("GameProfileUSB")
        self.geometry("1180x740")
        self.minsize(1020, 640)
        self.configure(fg_color="#0b0c0f")

        self.profile_dir_var = ctk.StringVar(
            value=str(profiles_mod.default_profile_dir())
        )
        self.profile_name_var = ctk.StringVar(value=profiles_mod.DEFAULT_PROFILE_NAME)
        self.selected_profile_var = ctk.StringVar(value="")
        self.backup_var = ctk.BooleanVar(value=True)

        self.game_check_vars: Dict[str, ctk.BooleanVar] = {}

        self._build_layout()
        self._refresh_games()
        self._refresh_profiles()
        self.log("Ready. Pick a USB folder, choose games, then Save or Apply.")

    # ---------- layout ----------
    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=0, minsize=320)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_main()

    def _build_sidebar(self) -> None:
        side = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        side.grid(row=0, column=0, sticky="nsew")
        side.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            side, text="GameProfile\nUSB",
            font=ctk.CTkFont(size=22, weight="bold"), justify="left",
        ).grid(row=0, column=0, padx=20, pady=(20, 4), sticky="w")

        ctk.CTkLabel(
            side, text="Detected games  (toggle to include)",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=MUTED,
        ).grid(row=1, column=0, padx=20, pady=(16, 4), sticky="w")

        self.games_frame = ctk.CTkScrollableFrame(side, fg_color=PANEL_2)
        self.games_frame.grid(row=2, column=0, padx=12, pady=4, sticky="nsew")

        button_row = ctk.CTkFrame(side, fg_color="transparent")
        button_row.grid(row=3, column=0, padx=12, pady=(8, 16), sticky="ew")
        button_row.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(
            button_row, text="Re-scan", command=self._refresh_games,
            fg_color=PANEL_2, hover_color=PANEL_3,
        ).grid(row=0, column=0, padx=(0, 4), sticky="ew")
        ctk.CTkButton(
            button_row, text="Select all", command=self._toggle_all_games,
            fg_color=PANEL_2, hover_color=PANEL_3,
        ).grid(row=0, column=1, padx=(4, 0), sticky="ew")

    def _build_main(self) -> None:
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(3, weight=1)

        self._build_profile_panel(main).grid(row=0, column=0, sticky="ew")
        self._build_action_panel(main).grid(row=1, column=0, sticky="ew", pady=(16, 0))
        self._build_converter(main).grid(row=2, column=0, sticky="ew", pady=(16, 0))
        self._build_log(main).grid(row=3, column=0, sticky="nsew", pady=(16, 0))

    def _build_profile_panel(self, parent) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=14)
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            frame, text="USB / profile folder",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, columnspan=4, padx=16, pady=(12, 4), sticky="w")

        ctk.CTkLabel(frame, text="Folder", width=70, anchor="w").grid(
            row=1, column=0, padx=(16, 6), pady=4, sticky="w"
        )
        self.drive_select = ctk.CTkOptionMenu(
            frame, values=self._drive_options(),
            command=self._on_drive_pick,
            fg_color=PANEL_2, button_color=ACCENT, button_hover_color=ACCENT_HOVER,
            width=160,
        )
        self.drive_select.grid(row=1, column=1, sticky="w", pady=4)

        ctk.CTkEntry(frame, textvariable=self.profile_dir_var).grid(
            row=1, column=2, sticky="ew", padx=8, pady=4
        )
        ctk.CTkButton(
            frame, text="Browse", width=90, command=self._pick_folder,
            fg_color=PANEL_2, hover_color=PANEL_3,
        ).grid(row=1, column=3, padx=(0, 16), pady=4)

        ctk.CTkLabel(frame, text="Profile", width=70, anchor="w").grid(
            row=2, column=0, padx=(16, 6), pady=4, sticky="w"
        )
        self.profile_select = ctk.CTkOptionMenu(
            frame, values=["(no profiles yet)"],
            command=self._on_profile_pick,
            fg_color=PANEL_2, button_color=ACCENT, button_hover_color=ACCENT_HOVER,
        )
        self.profile_select.grid(row=2, column=1, columnspan=2, sticky="ew", pady=4)
        ctk.CTkButton(
            frame, text="Refresh", width=90, command=self._refresh_profiles,
            fg_color=PANEL_2, hover_color=PANEL_3,
        ).grid(row=2, column=3, padx=(0, 16), pady=4)

        ctk.CTkLabel(frame, text="Save as", width=70, anchor="w").grid(
            row=3, column=0, padx=(16, 6), pady=(4, 12), sticky="w"
        )
        ctk.CTkEntry(frame, textvariable=self.profile_name_var).grid(
            row=3, column=1, columnspan=2, sticky="ew", pady=(4, 12)
        )
        ctk.CTkLabel(frame, text=".json", text_color=MUTED).grid(
            row=3, column=3, sticky="w", padx=(0, 16), pady=(4, 12)
        )

        self.profile_meta_label = ctk.CTkLabel(
            frame, text="No profile selected.",
            text_color=MUTED, anchor="w", justify="left",
        )
        self.profile_meta_label.grid(
            row=4, column=0, columnspan=4, sticky="ew", padx=16, pady=(0, 12)
        )

        return frame

    def _build_action_panel(self, parent) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=14)
        frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            frame, text="Save My Settings", height=46,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self._run_async(self._save_settings),
        ).grid(row=0, column=0, padx=(16, 8), pady=14, sticky="ew")

        ctk.CTkButton(
            frame, text="Apply My Settings", height=46,
            fg_color=SUCCESS, hover_color=SUCCESS_HOVER,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self._run_async(self._apply_settings),
        ).grid(row=0, column=1, padx=(8, 16), pady=14, sticky="ew")

        ctk.CTkCheckBox(
            frame, text="Backup current configs before applying",
            variable=self.backup_var,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
        ).grid(row=1, column=0, columnspan=2, padx=16, pady=(0, 14), sticky="w")

        return frame

    def _build_converter(self, parent) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=14)
        frame.grid_columnconfigure((1, 3, 5), weight=1)

        ctk.CTkLabel(
            frame, text="Sensitivity converter",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, columnspan=6, sticky="w", padx=16, pady=(12, 4))

        ctk.CTkLabel(frame, text="Game").grid(row=1, column=0, padx=(16, 6), pady=8, sticky="e")
        self.game_select = ctk.CTkOptionMenu(
            frame, values=list(sens_mod.SUPPORTED_GAMES),
            fg_color=PANEL_2, button_color=ACCENT, button_hover_color=ACCENT_HOVER,
        )
        self.game_select.grid(row=1, column=1, pady=8, sticky="ew")

        ctk.CTkLabel(frame, text="DPI").grid(row=1, column=2, padx=(16, 6), pady=8, sticky="e")
        self.dpi_entry = ctk.CTkEntry(frame, placeholder_text="800")
        self.dpi_entry.grid(row=1, column=3, pady=8, sticky="ew")

        ctk.CTkLabel(frame, text="In-game sens").grid(row=1, column=4, padx=(16, 6), pady=8, sticky="e")
        self.sens_entry = ctk.CTkEntry(frame, placeholder_text="0.4")
        self.sens_entry.grid(row=1, column=5, padx=(0, 16), pady=8, sticky="ew")

        ctk.CTkLabel(frame, text="Controller (0-10)").grid(
            row=2, column=0, padx=(16, 6), pady=(8, 14), sticky="e"
        )
        self.controller_entry = ctk.CTkEntry(frame, placeholder_text="result")
        self.controller_entry.grid(row=2, column=1, pady=(8, 14), sticky="ew")

        ctk.CTkButton(
            frame, text="Mouse -> Controller",
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._convert_mouse_to_controller,
        ).grid(row=2, column=2, columnspan=2, padx=8, pady=(8, 14), sticky="ew")

        ctk.CTkButton(
            frame, text="Controller -> Mouse",
            fg_color=PANEL_2, hover_color=PANEL_3,
            command=self._convert_controller_to_mouse,
        ).grid(row=2, column=4, columnspan=2, padx=(8, 16), pady=(8, 14), sticky="ew")

        return frame

    def _build_log(self, parent) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=14)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            frame, text="Status log",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))

        self.log_box = ctk.CTkTextbox(
            frame, fg_color=PANEL_2, text_color="#d8dbe2",
            font=ctk.CTkFont(family="Consolas", size=12),
        )
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.log_box.configure(state="disabled")
        return frame

    # ---------- helpers ----------
    def _drive_options(self) -> List[str]:
        opts = [str(p) for p in profiles_mod.list_removable_drives()]
        opts.append("Other...")
        return opts or ["Other..."]

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

    def _refresh_games(self) -> None:
        for child in self.games_frame.winfo_children():
            child.destroy()
        self.game_check_vars.clear()

        detected = games_mod.detect_games()
        if not detected:
            ctk.CTkLabel(
                self.games_frame, text="No supported games detected on this PC.",
                text_color=MUTED, wraplength=240, justify="left",
            ).pack(padx=8, pady=12, anchor="w")
            self.log("No supported games detected.")
            return

        for game in detected:
            var = ctk.BooleanVar(value=True)
            self.game_check_vars[game.key] = var
            row = ctk.CTkFrame(self.games_frame, fg_color=PANEL_3, corner_radius=10)
            row.pack(fill="x", padx=4, pady=4)
            ctk.CTkCheckBox(
                row, text=game.display_name, variable=var,
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color=ACCENT, hover_color=ACCENT_HOVER,
            ).pack(fill="x", padx=10, pady=(8, 0), anchor="w")
            for path in game.config_paths[:3]:
                ctk.CTkLabel(
                    row, text=str(path), anchor="w",
                    text_color=MUTED, wraplength=240, justify="left",
                    font=ctk.CTkFont(size=10),
                ).pack(fill="x", padx=10, pady=0)
            ctk.CTkLabel(row, text="", height=4).pack()
        self.log(f"Detected {len(detected)} game(s).")

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
                text=f"No profiles found in {folder}.",
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
        games_str = ", ".join(f"{k} ({n})" for k, n in counts.items()) or "no games"
        text = (
            f"Saved {meta['saved_at']}  on  {meta['host']}  "
            f"(v{meta['version']})\nGames: {games_str}"
        )
        self.profile_meta_label.configure(text=text, text_color=MUTED)

    def _pick_folder(self) -> None:
        chosen = filedialog.askdirectory(
            title="Pick USB folder for profiles",
            initialdir=self.profile_dir_var.get() or str(Path.home()),
        )
        if chosen:
            self.profile_dir_var.set(chosen)
            self._refresh_profiles()

    def _run_async(self, func) -> None:
        threading.Thread(target=func, daemon=True).start()

    # ---------- save / apply ----------
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
        self.log(f"Saving profile to {path} ...")
        try:
            profiles_mod.save_profile(path, selected_games=selected, log=self.log)
            self.log(f"Profile saved -> {path}")
            self.after(0, self._refresh_profiles)
        except Exception as exc:  # noqa: BLE001
            self.log(f"ERROR while saving: {exc}")

    def _apply_settings(self) -> None:
        folder = Path(self.profile_dir_var.get())
        name = self.selected_profile_var.get() or self.profile_name_var.get()
        if not name or name == "(no profiles yet)":
            self.log("ERROR: no profile selected to apply.")
            return
        path = folder / name if name.endswith(".json") else profiles_mod.profile_path(folder, name)
        if not path.exists():
            self.log(f"ERROR: profile not found at {path}")
            return
        selected = self._selected_game_keys() or None
        self.log(f"Applying profile from {path} ...")
        try:
            results = profiles_mod.apply_profile(
                path, selected_games=selected, log=self.log,
                make_backup=self.backup_var.get(),
            )
            total = sum(results.values())
            self.log(f"Applied {total} file(s) across {len(results)} game(s).")
        except Exception as exc:  # noqa: BLE001
            self.log(f"ERROR while applying: {exc}")

    # ---------- converter ----------
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
