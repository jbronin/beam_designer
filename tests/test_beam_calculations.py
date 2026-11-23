import math
import unittest

from beam_calculations import (
    BeamModel,
    PointLoad,
    UniformLoad,
    analyze_beam,
    calculate_reactions,
    find_lightest_passing_section,
    shear_at,
)


class BeamValidationTests(unittest.TestCase):
    def test_simply_supported_full_span_uniform_load(self):
        model = BeamModel(
            support="simple",
            span=20,
            uniform_loads=(UniformLoad(1, 0, 20),),
        )
        result = analyze_beam(model)

        self.assertAlmostEqual(result.reactions.left, 10)
        self.assertAlmostEqual(result.reactions.right, 10)
        self.assertAlmostEqual(result.max_shear.value, 10)
        self.assertAlmostEqual(result.max_moment.value, 50)
        self.assertAlmostEqual(result.max_moment.x, 10)
        self.assertAlmostEqual(result.bending_stress, 17.96, places=2)
        self.assertAlmostEqual(abs(result.max_deflection.value), 0.609, delta=0.003)
        self.assertAlmostEqual(result.deflection_limit, 0.667, delta=0.003)
        self.assertTrue(result.bending_pass)
        self.assertTrue(result.deflection_pass)

    def test_simply_supported_point_load(self):
        model = BeamModel(
            support="simple",
            span=20,
            point_loads=(PointLoad(10, 5),),
        )
        result = analyze_beam(model)

        self.assertAlmostEqual(result.reactions.left, 7.5)
        self.assertAlmostEqual(result.reactions.right, 2.5)
        self.assertAlmostEqual(result.max_moment.value, 37.5)
        self.assertAlmostEqual(result.max_moment.x, 5)
        self.assertAlmostEqual(result.bending_stress, 13.47, places=2)
        self.assertAlmostEqual(abs(result.max_deflection.value), 0.340, delta=0.003)
        self.assertAlmostEqual(result.max_deflection.x, 8.82, delta=0.05)

    def test_cantilever_tip_load(self):
        model = BeamModel(
            support="cantilever",
            span=10,
            point_loads=(PointLoad(5, 10),),
        )
        result = analyze_beam(model)

        self.assertAlmostEqual(result.reactions.left, 5)
        self.assertAlmostEqual(result.reactions.fixed_moment, 50)
        self.assertAlmostEqual(abs(result.max_deflection.value), 0.487, delta=0.003)
        self.assertAlmostEqual(result.max_deflection.x, 10)
        self.assertAlmostEqual(result.deflection_limit, 0.333, delta=0.003)
        self.assertFalse(result.deflection_pass)

    def test_lumber_beam(self):
        model = BeamModel(
            support="simple",
            span=12,
            uniform_loads=(UniformLoad(0.05, 0, 12),),
            material="lumber",
            section_name="2x10",
        )
        result = analyze_beam(model)

        self.assertAlmostEqual(result.max_moment.value, 0.9)
        self.assertAlmostEqual(result.bending_stress, 0.505, delta=0.003)
        self.assertAlmostEqual(abs(result.max_deflection.value), 0.147, delta=0.003)
        self.assertTrue(result.bending_pass)
        self.assertTrue(result.deflection_pass)

    def test_half_span_uniform_load_on_w18x35(self):
        model = BeamModel(
            support="simple",
            span=30,
            uniform_loads=(UniformLoad(2, 0, 15),),
            section_name="W18x35",
        )
        result = analyze_beam(model)

        self.assertAlmostEqual(result.reactions.left, 22.5)
        self.assertAlmostEqual(result.reactions.right, 7.5)
        self.assertAlmostEqual(result.max_moment.value, 126.6, delta=0.1)
        self.assertAlmostEqual(result.max_moment.x, 11.25)

    def test_shear_at_point_load_checks_both_sides(self):
        model = BeamModel(
            support="simple",
            span=20,
            point_loads=(PointLoad(10, 5),),
        )

        self.assertAlmostEqual(shear_at(model, 5, "left"), 7.5)
        self.assertAlmostEqual(shear_at(model, 5, "right"), -2.5)

    def test_reversed_uniform_load_bounds_are_normalized(self):
        model = BeamModel(
            support="simple",
            span=20,
            uniform_loads=(UniformLoad(1, 18, 10),),
        )
        reactions = calculate_reactions(model)

        self.assertAlmostEqual(reactions.left, 2.4)
        self.assertAlmostEqual(reactions.right, 5.6)

    def test_zero_load_has_zero_response_and_recommendation(self):
        model = BeamModel(support="simple", span=20)
        result = analyze_beam(model)

        self.assertEqual(result.max_shear.value, 0)
        self.assertEqual(result.max_moment.value, 0)
        self.assertEqual(result.max_deflection.value, 0)
        self.assertEqual(find_lightest_passing_section(model).name, "W8x10")

    def test_invalid_span_and_non_finite_load_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Span"):
            analyze_beam(BeamModel(support="simple", span=math.nan))
        with self.assertRaisesRegex(ValueError, "magnitude"):
            analyze_beam(
                BeamModel(
                    support="simple",
                    span=20,
                    point_loads=(PointLoad(math.inf, 10),),
                )
            )

    def test_load_magnitudes_and_positions_are_bounded(self):
        with self.assertRaisesRegex(ValueError, "magnitude"):
            analyze_beam(
                BeamModel(
                    support="simple",
                    span=20,
                    point_loads=(PointLoad(10001, 10),),
                )
            )
        with self.assertRaisesRegex(ValueError, "position"):
            analyze_beam(
                BeamModel(
                    support="simple",
                    span=20,
                    point_loads=(PointLoad(1, 51),),
                )
            )

    def test_loads_outside_the_span_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "within the beam span"):
            analyze_beam(
                BeamModel(
                    support="simple",
                    span=20,
                    point_loads=(PointLoad(1, 21),),
                )
            )
        with self.assertRaisesRegex(ValueError, "within the beam span"):
            analyze_beam(
                BeamModel(
                    support="simple",
                    span=20,
                    uniform_loads=(UniformLoad(1, 0, 21),),
                )
            )

    def test_section_must_match_material(self):
        model = BeamModel(
            support="simple",
            span=12,
            material="lumber",
            section_name="2x10",
        )
        with self.assertRaisesRegex(ValueError, "does not match"):
            analyze_beam(model, section=analyze_beam(BeamModel("simple", 20)).section)


if __name__ == "__main__":
    unittest.main()
