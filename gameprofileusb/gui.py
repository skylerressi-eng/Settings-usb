"""customtkinter GUI for GameProfileUSB."""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from . import games as games_mod
from . import profiles as profiles_mod
from . import sensitivity as sens_mod

ACCENT = "#7c3aed"
ACCENT_HOVER = "#6d28d9"
DANGER = "#ef4444"
SUCCESS = "#10b981"
PANEL = "#15171c"
PANEL_2 = "#1d2026"


class GameProfileUSBApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title("GameProfileUSB")
        self.geometry("1080x680")
        self.minsize(960, 600)
        self.configure(fg_color="#0b0c0f")

        self.profile_path_var = ctk.StringVar(
            value=str(profiles_mod.default_profile_path())
        )

        self._build_layout()
        self._refresh_games()
        self.log("Ready. Detected games listed on the left.")

    # ---------- layout ----------
    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=0, minsize=300)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main()

    def _build_sidebar(self) -> None:
        side = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        side.grid(row=0, column=0, sticky="nsew")
        side.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            side,
            text="GameProfile\nUSB",
            font=ctk.CTkFont(size=22, weight="bold"),
            justify="left",
        ).grid(row=0, column=0, padx=20, pady=(20, 4), sticky="w")

        ctk.CTkLabel(
            side,
            text="Detected games",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#8b8f9a",
        ).grid(row=1, column=0, padx=20, pady=(16, 4), sticky="w")

        self.games_frame = ctk.CTkScrollableFrame(side, fg_color=PANEL_2)
        self.games_frame.grid(row=2, column=0, padx=12, pady=4, sticky="nsew")

        ctk.CTkButton(
            side, text="Re-scan games", command=self._refresh_games,
            fg_color=PANEL_2, hover_color="#262a32",
        ).grid(row=3, column=0, padx=12, pady=(8, 16), sticky="ew")

    def _build_main(self) -> None:
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)

        # Profile actions
        actions = ctk.CTkFrame(main, fg_color=PANEL, corner_radius=14)
        actions.grid(row=0, column=0, sticky="ew")
        actions.grid_columnconfigure(0, weight=1)

        path_row = ctk.CTkFrame(actions, fg_color="transparent")
        path_row.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        path_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(path_row, text="Profile file", width=80, anchor="w").grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkEntry(path_row, textvariable=self.profile_path_var).grid(
            row=0, column=1, sticky="ew", padx=8
        )
        ctk.CTkButton(path_row, text="Browse", width=90, command=self._pick_path,
                      fg_color=PANEL_2, hover_color="#262a32").grid(row=0, column=2)

        button_row = ctk.CTkFrame(actions, fg_color="transparent")
        button_row.grid(row=1, column=0, sticky="ew", padx=16, pady=(4, 16))
        button_row.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            button_row, text="Save My Settings", height=44,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self._run_async(self._save_settings),
        ).grid(row=0, column=0, padx=(0, 8), sticky="ew")

        ctk.CTkButton(
            button_row, text="Apply My Settings", height=44,
            fg_color=SUCCESS, hover_color="#0e9b73",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self._run_async(self._apply_settings),
        ).grid(row=0, column=1, padx=(8, 0), sticky="ew")

        # Sensitivity converter
        self._build_converter(main).grid(row=1, column=0, sticky="ew", pady=(16, 0))

        # Status log
        log_frame = ctk.CTkFrame(main, fg_color=PANEL, corner_radius=14)
        log_frame.grid(row=2, column=0, sticky="nsew", pady=(16, 0))
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            log_frame, text="Status log",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))

        self.log_box = ctk.CTkTextbox(
            log_frame, fg_color=PANEL_2, text_color="#d8dbe2",
            font=ctk.CTkFont(family="Consolas", size=12),
        )
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.log_box.configure(state="disabled")

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
            row=2, column=0, padx=(16, 6), pady=8, sticky="e"
        )
        self.controller_entry = ctk.CTkEntry(frame, placeholder_text="result")
        self.controller_entry.grid(row=2, column=1, pady=8, sticky="ew")

        ctk.CTkButton(
            frame, text="Mouse -> Controller",
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._convert_mouse_to_controller,
        ).grid(row=2, column=2, columnspan=2, padx=8, pady=8, sticky="ew")

        ctk.CTkButton(
            frame, text="Controller -> Mouse",
            fg_color=PANEL_2, hover_color="#262a32",
            command=self._convert_controller_to_mouse,
        ).grid(row=2, column=4, columnspan=2, padx=(8, 16), pady=8, sticky="ew")

        return frame

    # ---------- behaviors ----------
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

        detected = games_mod.detect_games()
        if not detected:
            ctk.CTkLabel(
                self.games_frame, text="No supported games detected.",
                text_color="#8b8f9a", wraplength=240, justify="left",
            ).pack(padx=8, pady=12, anchor="w")
            return

        for game in detected:
            row = ctk.CTkFrame(self.games_frame, fg_color="#22252c", corner_radius=10)
            row.pack(fill="x", padx=4, pady=4)
            ctk.CTkLabel(
                row, text=game.display_name, anchor="w",
                font=ctk.CTkFont(size=13, weight="bold"),
            ).pack(fill="x", padx=10, pady=(8, 0))
            ctk.CTkLabel(
                row, text=str(game.config_paths[0]), anchor="w",
                text_color="#8b8f9a", wraplength=240, justify="left",
                font=ctk.CTkFont(size=10),
            ).pack(fill="x", padx=10, pady=(0, 8))

        self.log(f"Detected {len(detected)} game(s).")

    def _pick_path(self) -> None:
        initial = Path(self.profile_path_var.get())
        chosen = filedialog.asksaveasfilename(
            title="Profile location",
            initialdir=str(initial.parent),
            initialfile=initial.name or profiles_mod.PROFILE_FILENAME,
            defaultextension=".json",
            filetypes=[("JSON profile", "*.json")],
        )
        if chosen:
            self.profile_path_var.set(chosen)

    def _run_async(self, func) -> None:
        threading.Thread(target=func, daemon=True).start()

    def _save_settings(self) -> None:
        path = Path(self.profile_path_var.get())
        self.log(f"Saving profile to {path} ...")
        try:
            profiles_mod.save_profile(path, log=self.log)
            self.log(f"Profile saved -> {path}")
        except Exception as exc:  # noqa: BLE001
            self.log(f"ERROR while saving: {exc}")

    def _apply_settings(self) -> None:
        path = Path(self.profile_path_var.get())
        if not path.exists():
            self.log(f"ERROR: profile not found at {path}")
            return
        self.log(f"Applying profile from {path} ...")
        try:
            results = profiles_mod.apply_profile(path, log=self.log)
            total = sum(results.values())
            self.log(f"Applied {total} file(s) across {len(results)} game(s).")
        except Exception as exc:  # noqa: BLE001
            self.log(f"ERROR while applying: {exc}")

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
