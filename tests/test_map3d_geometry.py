"""D2: the 3D network map's pure geometry math (ui/map3d_geometry.py) - no Qt needed. This is the trickiest part
of the whole feature (aligning a cylinder between two arbitrary points via quaternion, not Euler angles, to avoid
gimbal-lock/composition-order bugs), so it gets the most direct scrutiny: every quaternion link_geometry() produces
is checked by actually rotating (0, 1, 0) with it and confirming the result matches the intended direction."""
import math
import unittest

from ui.map3d_geometry import link_geometry, node_depth, node_position, rotate_vector


def close(a, b, tol=1e-6):
    return all(abs(x - y) < tol for x, y in zip(a, b))


class NodeDepthTests(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(node_depth("cloud-edge"), node_depth("cloud-edge"))

    def test_different_ids_spread_out(self):
        depths = {node_depth(f"server-{i}") for i in range(20)}
        self.assertGreater(len(depths), 15)        # not every id collides onto the same depth

    def test_within_range(self):
        for i in range(50):
            d = node_depth(f"srv-{i}")
            self.assertTrue(-1.0 <= d <= 1.0, d)


class NodePositionTests(unittest.TestCase):
    def test_center_of_2d_layout_maps_near_origin_xy(self):
        x, y, z = node_position(0.5, 0.5, "mid")
        self.assertAlmostEqual(x, 0.0)
        self.assertAlmostEqual(y, 0.0)

    def test_2d_x_increases_with_3d_x(self):
        x1, _, _ = node_position(0.1, 0.5, "a")
        x2, _, _ = node_position(0.9, 0.5, "a")
        self.assertLess(x1, x2)

    def test_2d_y_is_flipped_for_a_screen_like_up_is_up_feel(self):
        # 2D layout has y=0 at the top (screen convention); 3D should put that higher up (+y), not lower
        _, y_top, _ = node_position(0.5, 0.0, "a")
        _, y_bottom, _ = node_position(0.5, 1.0, "a")
        self.assertGreater(y_top, y_bottom)


class LinkGeometryTests(unittest.TestCase):
    def test_midpoint_and_length(self):
        g = link_geometry((0, 0, 0), (0, 4, 0))
        self.assertEqual(g["mid"], (0, 2, 0))
        self.assertAlmostEqual(g["length"], 4.0)

    def test_straight_up_is_the_identity_quaternion(self):
        g = link_geometry((0, 0, 0), (0, 5, 0))
        self.assertTrue(close(g["quat"], (1, 0, 0, 0)))
        self.assertTrue(close(rotate_vector(g["quat"], (0, 1, 0)), (0, 1, 0)))

    def test_straight_down_flips_the_cylinder(self):
        g = link_geometry((0, 0, 0), (0, -5, 0))
        rotated = rotate_vector(g["quat"], (0, 1, 0))
        self.assertTrue(close(rotated, (0, -1, 0)))

    def test_horizontal_along_x(self):
        g = link_geometry((0, 0, 0), (5, 0, 0))
        rotated = rotate_vector(g["quat"], (0, 1, 0))
        self.assertTrue(close(rotated, (1, 0, 0)))

    def test_horizontal_along_z(self):
        g = link_geometry((0, 0, 0), (0, 0, 5))
        rotated = rotate_vector(g["quat"], (0, 1, 0))
        self.assertTrue(close(rotated, (0, 0, 1)))

    def test_arbitrary_diagonal_direction(self):
        a, b = (1.0, 2.0, 3.0), (-4.0, 7.0, -1.0)
        g = link_geometry(a, b)
        expected = (-5.0, 5.0, -4.0)
        norm = math.sqrt(sum(c * c for c in expected))
        expected = tuple(c / norm for c in expected)
        rotated = rotate_vector(g["quat"], (0, 1, 0))
        self.assertTrue(close(rotated, expected, tol=1e-5))

    def test_the_quaternion_is_always_unit_length(self):
        for a, b in (((0, 0, 0), (1, 1, 1)), ((2, -3, 5), (-2, 1, 0)), ((0, 0, 0), (0, 0, -3))):
            w, x, y, z = link_geometry(a, b)["quat"]
            self.assertAlmostEqual(w * w + x * x + y * y + z * z, 1.0, places=5)

    def test_zero_length_link_does_not_crash(self):
        g = link_geometry((1, 1, 1), (1, 1, 1))
        self.assertEqual(g["length"], 0.0)


if __name__ == "__main__":
    unittest.main()
