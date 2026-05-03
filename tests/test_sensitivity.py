import math
import unittest

from gameprofileusb import sensitivity as s


class SensitivityTests(unittest.TestCase):
    def test_known_value(self):
        # 800 DPI x 0.4 sens -> 320 eDPI -> /1600 *5 -> 1.0
        self.assertAlmostEqual(s.mouse_to_controller(800, 0.4, "valorant"), 1.0)

    def test_round_trip(self):
        for dpi in (400, 800, 1600):
            for sens in (0.2, 0.5, 1.3):
                c = s.mouse_to_controller(dpi, sens, "cs2")
                if c >= 10.0:  # clamped, can't invert
                    continue
                back = s.controller_to_mouse(c, dpi, "cs2")
                self.assertTrue(math.isclose(back, sens, rel_tol=1e-3))

    def test_clamp_high_end(self):
        self.assertEqual(s.mouse_to_controller(50000, 5, "apex"), 10.0)

    def test_unsupported_game_rejected(self):
        with self.assertRaises(ValueError):
            s.mouse_to_controller(800, 0.4, "minecraft")
        with self.assertRaises(ValueError):
            s.mouse_to_controller(800, 0.4, "overwatch")

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            s.mouse_to_controller(0, 0.4, "fortnite")
        with self.assertRaises(ValueError):
            s.mouse_to_controller(800, -1, "fortnite")
        with self.assertRaises(ValueError):
            s.controller_to_mouse(11, 800, "valorant")

    def test_edpi(self):
        self.assertEqual(s.edpi(800, 0.4), 320.0)


if __name__ == "__main__":
    unittest.main()
