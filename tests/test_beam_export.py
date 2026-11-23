import csv
import tempfile
import unittest
from pathlib import Path

from beam_calculations import BeamModel, PointLoad, analyze_beam
from beam_export import CSV_COLUMNS, write_analysis_csv


class BeamCsvExportTests(unittest.TestCase):
    def test_csv_has_unit_headers_and_both_shear_sides_at_point_load(self):
        model = BeamModel(
            support="simple",
            span=20,
            point_loads=(PointLoad(10, 5),),
        )
        analysis = analyze_beam(model)
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "results.csv")
            write_analysis_csv(model, analysis, path)

            with open(path, newline="", encoding="utf-8-sig") as file:
                rows = list(csv.reader(file))

        self.assertEqual(tuple(rows[0]), CSV_COLUMNS)
        at_load = [row for row in rows[1:] if float(row[0]) == 5]
        self.assertEqual([float(row[1]) for row in at_load], [7.5, -2.5])
        self.assertTrue(all(float(row[2]) == 37.5 for row in at_load))
        self.assertAlmostEqual(float(at_load[0][3]), float(at_load[1][3]))


if __name__ == "__main__":
    unittest.main()
