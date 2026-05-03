"""End-to-end tests for save/apply with stubbed game roots.

We monkey-patch ``GameSpec.path_resolver`` so the tests don't depend on any
real game install. This proves the multi-root (CS2) write path actually works.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gameprofileusb import games as games_mod
from gameprofileusb import profiles as profiles_mod


class GamesIOTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

        # Pretend Valorant + CS2 (with two Steam users) are installed.
        valorant_root = self.root / "valorant" / "Config"
        cs2_user_a = self.root / "steam" / "userA" / "730" / "local" / "cfg"
        cs2_user_b = self.root / "steam" / "userB" / "730" / "local" / "cfg"
        for d in (valorant_root, cs2_user_a, cs2_user_b):
            d.mkdir(parents=True)

        (valorant_root / "GameUserSettings.ini").write_text("[Sens]\nx=1.0\n")
        (cs2_user_a / "video.txt").write_text("user-A original\n")
        (cs2_user_b / "video.txt").write_text("user-B original\n")

        self._orig_valorant = games_mod.GAMES["valorant"].path_resolver
        self._orig_cs2 = games_mod.GAMES["cs2"].path_resolver
        games_mod.GAMES["valorant"].path_resolver = lambda: [valorant_root]
        games_mod.GAMES["cs2"].path_resolver = lambda: [cs2_user_a, cs2_user_b]

        self.cs2_user_a = cs2_user_a
        self.cs2_user_b = cs2_user_b
        self.valorant_root = valorant_root

    def tearDown(self) -> None:
        games_mod.GAMES["valorant"].path_resolver = self._orig_valorant
        games_mod.GAMES["cs2"].path_resolver = self._orig_cs2

    def test_save_then_apply_writes_to_all_steam_users(self):
        profile_path = self.root / "out" / "main.json"

        profiles_mod.save_profile(
            profile_path, selected_games=["valorant", "cs2"]
        )

        data = json.loads(profile_path.read_text())
        self.assertEqual(data["version"], profiles_mod.PROFILE_VERSION)
        self.assertIn("valorant", data["games"])
        self.assertIn("cs2", data["games"])
        cs2_files = data["games"]["cs2"]["files"]
        self.assertIn("video.txt", cs2_files)
        # Save reads from the first detected root (user A).
        self.assertEqual(cs2_files["video.txt"], "user-A original\n")

        # Mutate the on-disk configs so we can prove apply overwrites them.
        (self.cs2_user_a / "video.txt").write_text("user-A LOCAL\n")
        (self.cs2_user_b / "video.txt").write_text("user-B LOCAL\n")

        results = profiles_mod.apply_profile(
            profile_path, selected_games=["cs2"], make_backup=True
        )
        self.assertEqual(results["cs2"], 2)  # one file per user
        self.assertEqual(
            (self.cs2_user_a / "video.txt").read_text(), "user-A original\n"
        )
        self.assertEqual(
            (self.cs2_user_b / "video.txt").read_text(), "user-A original\n"
        )

    def test_backup_snapshot_created_before_apply(self):
        profile_path = self.root / "out" / "main.json"
        profiles_mod.save_profile(profile_path, selected_games=["cs2"])

        (self.cs2_user_a / "video.txt").write_text("about to be overwritten\n")
        profiles_mod.apply_profile(profile_path, make_backup=True)

        backups = list(profile_path.parent.glob("restore-*.json"))
        self.assertEqual(len(backups), 1)
        backup = json.loads(backups[0].read_text())
        snapshots = backup["games"]["cs2"]["snapshots"]
        # Snapshot captures the pre-apply state at every existing root.
        contents = list(snapshots.values())
        self.assertIn({"video.txt": "about to be overwritten\n"}, contents)

    def test_skip_oversized_files(self):
        big = self.valorant_root / "huge.ini"
        big.write_bytes(b"x" * (games_mod.MAX_FILE_BYTES + 1))
        files = games_mod.read_game_configs("valorant")
        self.assertNotIn("huge.ini", files)
        self.assertIn("GameUserSettings.ini", files)

    def test_selected_games_filters_save(self):
        profile_path = self.root / "out" / "subset.json"
        profiles_mod.save_profile(profile_path, selected_games=["valorant"])
        data = json.loads(profile_path.read_text())
        self.assertIn("valorant", data["games"])
        self.assertNotIn("cs2", data["games"])

    def test_profile_summary(self):
        profile_path = self.root / "out" / "summary.json"
        profiles_mod.save_profile(profile_path, selected_games=["valorant", "cs2"])
        meta = profiles_mod.profile_summary(profile_path)
        self.assertEqual(meta["game_counts"]["valorant"], 1)
        self.assertEqual(meta["game_counts"]["cs2"], 1)


class ProfilePathTests(unittest.TestCase):
    def test_safe_name_strips_bad_chars(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = profiles_mod.profile_path(Path(tmp), "my cool / profile?!")
            self.assertTrue(p.name.endswith(".json"))
            for ch in "/\\?!":
                self.assertNotIn(ch, p.name)

    def test_list_profiles_sorted(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for n in ("b.json", "a.json", "c.json"):
                (folder / n).write_text("{}")
            (folder / "ignore.txt").write_text("nope")
            names = [p.name for p in profiles_mod.list_profiles(folder)]
            self.assertEqual(names, ["a.json", "b.json", "c.json"])


if __name__ == "__main__":
    unittest.main()
