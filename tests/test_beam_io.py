import json
import tempfile
import unittest
from pathlib import Path

from beam_calculations import BeamModel, PointLoad, UniformLoad
from beam_io import BeamFileError, load_beam, save_beam


class BeamFileTests(unittest.TestCase):
    def test_round_trip_preserves_all_model_inputs_and_loads(self):
        model = BeamModel(
            support="cantilever",
            span=15,
            point_loads=(PointLoad(4.5, 15), PointLoad(2, 6)),
            uniform_loads=(UniformLoad(0.75, 2, 12),),
            material="lumber",
            section_name="2x12",
            deflection_limit=240,
        )
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "design.json")
            save_beam(model, path)

            self.assertEqual(load_beam(path), model)

    def test_open_rejects_unsupported_versions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "design.json"
            path.write_text(json.dumps({"format_version": 2}), encoding="utf-8")

            with self.assertRaisesRegex(BeamFileError, "Unsupported beam file version"):
                load_beam(str(path))

    def test_open_rejects_loads_outside_the_beam(self):
        data = {
            "format_version": 1,
            "support": "simple",
            "span": 10,
            "material": "steel",
            "section_name": "W12x26",
            "deflection_limit": 360,
            "point_loads": [{"magnitude": 1, "position": 11}],
            "uniform_loads": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "design.json"
            path.write_text(json.dumps(data), encoding="utf-8")

            with self.assertRaisesRegex(BeamFileError, "within the beam span"):
                load_beam(str(path))

    def test_open_rejects_malformed_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "design.json"
            path.write_text("{", encoding="utf-8")

            with self.assertRaisesRegex(BeamFileError, "Could not read beam file"):
                load_beam(str(path))


if __name__ == "__main__":
    unittest.main()
