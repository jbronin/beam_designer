import tempfile
import unittest
from pathlib import Path

from beam_calculations import BeamModel, UniformLoad, analyze_beam
from beam_report import save_calculation_sheet


class BeamReportTests(unittest.TestCase):
    def test_calculation_sheet_generates_a_pdf(self):
        model = BeamModel(
            support="simple",
            span=20,
            uniform_loads=(UniformLoad(1, 0, 20),),
        )
        analysis = analyze_beam(model)
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "calculation-sheet.pdf")
            save_calculation_sheet(model, analysis, path)
            content = Path(path).read_bytes()

        self.assertTrue(content.startswith(b"%PDF-"))
        self.assertTrue(content.rstrip().endswith(b"%%EOF"))


if __name__ == "__main__":
    unittest.main()
