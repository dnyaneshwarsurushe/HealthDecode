import unittest
from unittest.mock import patch

from app import app, parse_lab_text


class LabParserTests(unittest.TestCase):
    def setUp(self):
        app.testing = True
        self.client = app.test_client()

    def test_sample_report_still_has_seven_markers_and_five_out_of_range(self):
        sample_report = """
        Hemoglobin 11 g/dL (12-15.5)
        TLC 8 x10^9/L (4-11)
        RBC 4.5 million/uL (4-5.5)
        Platelet Count 500 x10^9/L (150-450)
        Fasting Blood Sugar 110 mg/dL (70-99)
        Creatinine 1.4 mg/dL (0.6-1.2)
        Vitamin D 20 ng/mL (30-100)
        """

        results = parse_lab_text(sample_report)

        self.assertEqual(len(results), 7)
        self.assertEqual(sum(result["status"] != "normal" for result in results), 5)

    def test_indian_lab_aliases_match_existing_markers(self):
        cases = [
            ("TLC 8", "WBC (White Blood Cells)"),
            ("Total leukocyte count 8", "WBC (White Blood Cells)"),
            ("Total leucocyte count 8", "WBC (White Blood Cells)"),
            ("Total WBC count 8", "WBC (White Blood Cells)"),
            ("SGOT 20", "AST"),
            ("SGPT 20", "ALT"),
            ("PPBS 110", "Glucose"),
            ("Post prandial blood sugar 110", "Glucose"),
            ("RBS 110", "Glucose"),
            ("Random blood sugar 110", "Glucose"),
            ("Hemoglobin 13", "Hemoglobin"),
            ("Haemoglobin 13", "Hemoglobin"),
            ("Hb 13", "Hemoglobin"),
        ]

        for report_text, expected_name in cases:
            with self.subTest(report_text=report_text):
                results = parse_lab_text(report_text)
                self.assertEqual([result["name"] for result in results], [expected_name])

    def test_table_value_can_be_farther_than_25_characters_and_have_commas(self):
        report_text = "Platelet Count" + (" " * 35) + "1,50,000 /uL (1,50,000-4,50,000)"

        results = parse_lab_text(report_text)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["value"], 150000)
        self.assertEqual(results[0]["low"], 150000)
        self.assertEqual(results[0]["high"], 450000)
        self.assertEqual(results[0]["status"], "normal")
        self.assertEqual(results[0]["range_source"], "range printed in your report")

    def test_table_value_can_follow_test_name_on_next_line(self):
        results = parse_lab_text("SGOT\n                    45 U/L (0-50)")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "AST")
        self.assertEqual(results[0]["value"], 45)
        self.assertEqual(results[0]["status"], "normal")

    def test_analyze_explains_scanned_or_image_based_text(self):
        response = self.client.post("/analyze", json={"text": " \n "})

        self.assertEqual(response.status_code, 400)
        self.assertIn("scanned or photo-based", response.get_json()["error"])
        self.assertIn("text PDF or paste", response.get_json()["error"])

    def test_analyze_accepts_short_text_when_it_contains_a_valid_result(self):
        with patch("app.ollama_summary", return_value=(None, False)):
            response = self.client.post("/analyze", json={"text": "Hb 13"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()["results"]), 1)

    def test_analyze_lists_seen_test_names_when_markers_do_not_match(self):
        with patch("app.ollama_summary") as ollama_summary:
            response = self.client.post(
                "/analyze",
                json={"text": "Calcium       9.2 mg/dL\nSodium        140 mmol/L"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Calcium", response.get_json()["error"])
        self.assertIn("Sodium", response.get_json()["error"])
        ollama_summary.assert_not_called()

    def test_analyze_does_not_crash_on_non_object_or_non_text_json(self):
        for payload in ([], {"text": 123}):
            with self.subTest(payload=payload):
                response = self.client.post("/analyze", json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.get_json())

    def test_analyze_never_returns_empty_success(self):
        with patch("app.ollama_summary", return_value=(None, False)):
            response = self.client.post(
                "/analyze",
                json={"text": "Calcium 9.2 and sodium 140 in this report text."},
            )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("results", response.get_json())


if __name__ == "__main__":
    unittest.main()
