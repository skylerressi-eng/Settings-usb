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

    def test_progress_callback_fires_per_game(self):
        profile_path = self.root / "out" / "progress.json"
        events: list = []

        def progress(stage, key, idx, total):
            events.append((stage, key, idx, total))

        profiles_mod.save_profile(
            profile_path, selected_games=["valorant", "cs2"], progress=progress
        )
        # Expect: start -> game(valorant,1,2) -> game(cs2,2,2) -> done
        self.assertEqual(events[0], ("start", "", 0, 2))
        self.assertEqual(events[-1], ("done", "", 2, 2))
        game_events = [e for e in events if e[0] == "game"]
        self.assertEqual(len(game_events), 2)
        self.assertEqual(game_events[0][1], "valorant")
        self.assertEqual(game_events[0][2:], (1, 2))
        self.assertEqual(game_events[1][1], "cs2")
        self.assertEqual(game_events[1][2:], (2, 2))

    def test_log_callback_announces_each_file(self):
        profile_path = self.root / "out" / "log.json"
        lines: list = []
        profiles_mod.save_profile(
            profile_path, selected_games=["valorant"], log=lines.append
        )
        joined = "\n".join(lines)
        self.assertIn("Taking Valorant settings", joined)
        self.assertIn("saving GameUserSettings.ini", joined)
        self.assertIn("captured 1 file(s) from Valorant", joined)

    def test_restore_backup_undoes_apply(self):
        # Save a profile from machine A (val + cs2)
        profile_path = self.root / "out" / "main.json"
        profiles_mod.save_profile(profile_path, selected_games=["valorant", "cs2"])

        # Simulate a fresh PC by changing the on-disk content.
        (self.valorant_root / "GameUserSettings.ini").write_text("local-original\n")
        (self.cs2_user_a / "video.txt").write_text("local-A\n")
        (self.cs2_user_b / "video.txt").write_text("local-B\n")

        # Apply (with backup), proving overwrite happened.
        profiles_mod.apply_profile(profile_path, make_backup=True)
        self.assertEqual(
            (self.cs2_user_a / "video.txt").read_text(), "user-A original\n"
        )

        # Restore from the backup file.
        backups = profiles_mod.list_backups(profile_path.parent)
        self.assertEqual(len(backups), 1)
        results = profiles_mod.restore_backup(backups[0])
        self.assertGreater(sum(results.values()), 0)

        # Local content is back.
        self.assertEqual(
            (self.cs2_user_a / "video.txt").read_text(), "local-A\n"
        )
        self.assertEqual(
            (self.cs2_user_b / "video.txt").read_text(), "local-B\n"
        )
        self.assertEqual(
            (self.valorant_root / "GameUserSettings.ini").read_text(),
            "local-original\n",
        )

    def test_restore_deletes_files_apply_created(self):
        # Profile contains a brand-new file that doesn't exist locally yet.
        profile_path = self.root / "out" / "novel.json"
        # Manually craft a profile with a file that's not in the source root.
        (self.valorant_root / "Brand-new.ini").write_text("from-source\n")
        profiles_mod.save_profile(profile_path, selected_games=["valorant"])
        (self.valorant_root / "Brand-new.ini").unlink()  # gone on this PC

        self.assertFalse((self.valorant_root / "Brand-new.ini").exists())
        profiles_mod.apply_profile(profile_path, make_backup=True)
        self.assertTrue((self.valorant_root / "Brand-new.ini").exists())

        backups = profiles_mod.list_backups(profile_path.parent)
        profiles_mod.restore_backup(backups[0])

        # Restore deleted the file apply created.
        self.assertFalse((self.valorant_root / "Brand-new.ini").exists())

    def test_restore_rejects_non_backup_file(self):
        profile_path = self.root / "out" / "regular.json"
        profiles_mod.save_profile(profile_path, selected_games=["valorant"])
        with self.assertRaises(ValueError):
            profiles_mod.restore_backup(profile_path)

    def test_is_backup_and_list_backups(self):
        profile_path = self.root / "out" / "main.json"
        profiles_mod.save_profile(profile_path, selected_games=["valorant"])
        profiles_mod.apply_profile(profile_path, make_backup=True)

        regular = profile_path
        backups = profiles_mod.list_backups(profile_path.parent)
        self.assertFalse(profiles_mod.is_backup(regular))
        self.assertTrue(profiles_mod.is_backup(backups[0]))

    def test_delete_profile(self):
        profile_path = self.root / "out" / "doomed.json"
        profiles_mod.save_profile(profile_path, selected_games=["valorant"])
        self.assertTrue(profile_path.exists())
        profiles_mod.delete_profile(profile_path)
        self.assertFalse(profile_path.exists())
        # Deleting a non-existent file is a no-op.
        profiles_mod.delete_profile(profile_path)

    def test_apply_progress_and_log(self):
        profile_path = self.root / "out" / "applylog.json"
        profiles_mod.save_profile(profile_path, selected_games=["valorant"])

        events: list = []
        lines: list = []
        profiles_mod.apply_profile(
            profile_path, log=lines.append,
            progress=lambda *a: events.append(a),
            make_backup=False,
        )
        joined = "\n".join(lines)
        self.assertIn("Applying Valorant settings", joined)
        self.assertIn("applied GameUserSettings.ini", joined)
        self.assertEqual(events[0][0], "start")
        self.assertEqual(events[-1][0], "done")


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
