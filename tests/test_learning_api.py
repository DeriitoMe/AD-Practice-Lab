"""Offline HTTP contracts for lessons, simulated plans and practice events.

Each test has a fresh SQLite database and an ephemeral loopback server. No
browser, external model, advertising platform or developer database is used.
"""

import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import app
import lab


class LearningAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "learning.sqlite3"
        self.server = app.make_server(0, self.db)
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.base = "http://127.0.0.1:" + str(self.server.server_port)

    def stop_server(self):
        if self.thread.is_alive():
            self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.assertFalse(self.thread.is_alive(), "temporary HTTP server stopped")

    def request(self, path, payload=None):
        if payload is None:
            request = Request(self.base + path)
        else:
            request = Request(
                self.base + path,
                data=json.dumps(payload, allow_nan=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            body = response.read().decode("utf-8")
            return response.code, response.headers.get("Content-Type", ""), body

    def post(self, path, payload):
        status, _, body = self.request(path, payload)
        return status, json.loads(body)

    def events(self):
        with lab.connect(self.db) as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM product_events ORDER BY rowid"
            )]

    def ad_counts(self):
        with lab.connect(self.db) as connection:
            return (
                connection.execute("SELECT COUNT(*) FROM datasets").fetchone()[0],
                connection.execute("SELECT COUNT(*) FROM ad_daily").fetchone()[0],
            )

    def test_curriculum_serves_six_distinct_lessons_and_usable_quizzes(self):
        status, content_type, body = self.request("/curriculum.json")
        self.assertEqual(status, 200)
        self.assertIn("json", content_type)
        lessons = json.loads(body)
        self.assertEqual(len(lessons), 6)
        self.assertEqual(
            {lesson["id"] for lesson in lessons},
            {"roles", "funnel", "setup", "metrics", "returns", "diagnosis"},
        )
        for lesson in lessons:
            with self.subTest(lesson=lesson["id"]):
                self.assertTrue(lesson["title"])
                self.assertTrue(lesson["explanation"])
                quiz = lesson["quiz"]
                self.assertGreaterEqual(len(quiz["options"]), 2)
                self.assertIs(type(quiz["answer"]), int)
                self.assertTrue(0 <= quiz["answer"] < len(quiz["options"]))
                self.assertTrue(quiz["feedback"])
                self.assertTrue(lesson["source"]["url"].startswith("https://"))
        self.assertEqual(self.events(), [])

    def test_simulation_returns_teaching_result_and_paired_success_events(self):
        initial_ads = self.ad_counts()
        status, result = self.post("/api/simulate", {
            "session_id": "api-practice-success",
            "config": {
                "budget": 1000, "audience": "broad", "creative": "benefit",
                "landing": "clear", "bid": "balanced",
            },
        })
        self.assertEqual(status, 200)
        self.assertEqual(result["config"]["budget"], 1000)
        self.assertIn("虚拟", result["label"])
        self.assertTrue(result["model_assumptions"])
        self.assertEqual(len(result["funnel"]), 4)
        self.assertGreater(result["totals"]["impressions"], 0)
        self.assertLessEqual(result["totals"]["spend"], 1000)
        self.assertEqual(self.ad_counts(), initial_ads)
        started, finished = self.events()
        self.assertEqual(started["event_name"], "simulation_started")
        self.assertEqual(finished["event_name"], "simulation_finished")
        self.assertEqual(started["run_id"], finished["run_id"])
        self.assertEqual(started["session_id"], "api-practice-success")
        self.assertEqual(finished["outcome"], "success")
        self.assertGreaterEqual(finished["duration_ms"], 0)
        self.assertEqual(finished["source_kind"], "local_practice")
        self.assertEqual(json.loads(finished["properties_json"]), {
            "operation": "simulation"
        })

    def test_bad_simulation_configs_return_400_and_paired_failure_events(self):
        initial_ads = self.ad_counts()
        bad_configs = [[], {"budget": 0}, {"audience": "unknown"},
                       {"unexpected_field": 1}]
        for config in bad_configs:
            with self.subTest(config=config):
                before = len(self.events())
                status, result = self.post("/api/simulate", {
                    "config": config, "session_id": "api-practice-failure"
                })
                self.assertEqual(status, 400)
                self.assertTrue(result["error"])
                added = self.events()[before:]
                self.assertEqual(len(added), 2)
                self.assertEqual(added[0]["event_name"], "simulation_started")
                self.assertEqual(added[1]["event_name"], "simulation_finished")
                self.assertEqual(added[0]["run_id"], added[1]["run_id"])
                self.assertEqual(added[1]["outcome"], "failed")
                self.assertGreaterEqual(added[1]["duration_ms"], 0)
        self.assertEqual(self.ad_counts(), initial_ads)

    def test_non_object_simulation_request_does_not_create_fake_operation(self):
        status, result = self.post("/api/simulate", ["not an object"])
        self.assertEqual(status, 400)
        self.assertTrue(result["error"])
        self.assertEqual(self.events(), [])

    def test_lesson_boolean_reports_are_local_practice_and_idempotent(self):
        for correct in (True, False):
            payload = {
                "event_name": "lesson_answered", "session_id": "lesson-session",
                "event_id": "lesson-" + str(correct),
                "properties": {"lesson_id": "roles", "correct": correct},
            }
            for _ in range(2):
                status, result = self.post("/api/event", payload)
                self.assertEqual(status, 200)
                self.assertEqual(result["event_id"], payload["event_id"])
        rows = self.events()
        self.assertEqual(len(rows), 2)
        for row, correct in zip(rows, (True, False)):
            self.assertEqual(row["event_name"], "lesson_answered")
            self.assertEqual(row["source_kind"], "local_practice")
            self.assertIsNone(row["outcome"])
            self.assertEqual(json.loads(row["properties_json"]), {
                "lesson_id": "roles", "correct": correct,
                "meaning": "self_reported_practice_answer",
            })

    def test_invalid_lesson_reports_are_rejected_without_recording(self):
        bad_properties = [None, [], {}, {"lesson_id": "unknown", "correct": True},
                          {"lesson_id": "roles", "correct": "true"},
                          {"lesson_id": "roles", "correct": 1}]
        for properties in bad_properties:
            with self.subTest(properties=properties):
                status, result = self.post("/api/event", {
                    "event_name": "lesson_answered", "properties": properties
                })
                self.assertEqual(status, 400)
                self.assertTrue(result["error"])
        self.assertEqual(self.events(), [])

    def test_lesson_report_discards_untrusted_additional_properties(self):
        status, _ = self.post("/api/event", {
            "event_name": "lesson_answered",
            "properties": {
                "lesson_id": "funnel", "correct": False,
                "meaning": "verified_mastery", "private_text": "do not persist",
            },
        })
        self.assertEqual(status, 200)
        properties = json.loads(self.events()[0]["properties_json"])
        self.assertEqual(properties, {
            "lesson_id": "funnel", "correct": False,
            "meaning": "self_reported_practice_answer",
        })

    def test_client_cannot_forge_simulation_completion(self):
        status, result = self.post("/api/event", {
            "event_name": "simulation_finished", "outcome": "success"
        })
        self.assertEqual(status, 400)
        self.assertTrue(result["error"])
        self.assertEqual(self.events(), [])

    def test_learning_page_and_linked_static_routes_are_served(self):
        status, content_type, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("<title>AD Practice Lab", body)
        self.assertIn("广告投放练习室", body)
        for path, expected_type in (("/style.css", "text/css"),
                                    ("/app.js", "javascript"),
                                    ("/favicon.svg", "image/svg+xml"),
                                    ("/docs/portfolio-evidence.md", "text/plain")):
            with self.subTest(path=path):
                status, content_type, body = self.request(path)
                self.assertEqual(status, 200)
                self.assertIn(expected_type, content_type)
                self.assertTrue(body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
