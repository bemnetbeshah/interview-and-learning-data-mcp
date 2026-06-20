import sqlite3
import unittest
from datetime import date, timedelta

from interview_prep_mcp.db import connect
from interview_prep_mcp.service import InterviewPrepService
from interview_prep_mcp.sm2 import ReviewState, update_review_state


class InterviewPrepServiceTests(unittest.TestCase):
    def setUp(self):
        self.conn = connect(":memory:")
        self.service = InterviewPrepService(self.conn)

    def test_create_hierarchy_and_due_subtopic(self):
        study = self.service.create_study("AI Engineering Interview")
        topic = self.service.create_topic(study["id"], "Transformers")
        subtopic = self.service.create_subtopic(
            topic["id"],
            "Multi-head Attention",
            "Explain heads, projections, and concatenation.",
        )

        self.assertEqual(self.service.list_studies()[0]["name"], study["name"])
        self.assertEqual(self.service.list_topics(study["id"])[0]["name"], topic["name"])

        listed = self.service.list_subtopics(topic["id"])[0]
        self.assertEqual(listed["name"], subtopic["name"])
        self.assertEqual(listed["mastery_level"], 0)

        due = self.service.get_due_subtopics()
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0]["subtopic_name"], "Multi-head Attention")
        self.assertEqual(due[0]["study_name"], "AI Engineering Interview")

    def test_log_attempt_updates_state_and_history(self):
        subtopic_id = self._make_subtopic()

        first = self.service.log_attempt(
            subtopic_id=subtopic_id,
            score=5,
            model_notes="Correct explanation.",
            question_asked="Explain dot-product attention.",
        )
        self.assertEqual(first["interval_days"], 1)
        self.assertEqual(first["consecutive_correct"], 1)
        self.assertEqual(first["summary"], "next review: in 1 day")

        second = self.service.log_attempt(
            subtopic_id=subtopic_id,
            score=4,
            model_notes="Mostly correct.",
        )
        self.assertEqual(second["interval_days"], 6)
        self.assertEqual(second["consecutive_correct"], 2)

        history = self.service.get_subtopic_history(subtopic_id)
        self.assertEqual(history["trend"]["attempt_count"], 2)
        self.assertEqual(history["trend"]["latest_score"], 4)
        self.assertEqual(history["attempts"][0]["score"], 4)

    def test_low_score_resets_interval_and_streak(self):
        subtopic_id = self._make_subtopic()
        self.service.log_attempt(subtopic_id, 5, "Correct.")
        self.service.log_attempt(subtopic_id, 5, "Correct again.")

        reset = self.service.log_attempt(subtopic_id, 2, "Incorrect but familiar.")
        self.assertEqual(reset["interval_days"], 1)
        self.assertEqual(reset["consecutive_correct"], 0)

    def test_due_queue_filters_soft_deleted_items(self):
        study = self.service.create_study("Calc 3")
        topic = self.service.create_topic(study["id"], "Vector Calculus")
        subtopic = self.service.create_subtopic(topic["id"], "Divergence theorem")

        self.assertEqual(len(self.service.get_due_subtopics(study_id=study["id"])), 1)
        self.service.delete_subtopic(subtopic["id"])
        self.assertEqual(self.service.get_due_subtopics(study_id=study["id"]), [])

    def test_invalid_score_is_rejected(self):
        subtopic_id = self._make_subtopic()
        with self.assertRaises(ValueError):
            self.service.log_attempt(subtopic_id, 6, "Impossible score.")

    def test_sm2_intervals_follow_prd_rules(self):
        today = date.today()
        first = update_review_state(ReviewState(), 3, today)
        second = update_review_state(
            ReviewState(
                mastery_level=first.mastery_level,
                ease_factor=first.ease_factor,
                interval_days=first.interval_days,
                consecutive_correct=first.consecutive_correct,
            ),
            4,
            today,
        )
        third = update_review_state(
            ReviewState(
                mastery_level=second.mastery_level,
                ease_factor=second.ease_factor,
                interval_days=second.interval_days,
                consecutive_correct=second.consecutive_correct,
            ),
            5,
            today,
        )

        self.assertEqual(first.interval_days, 1)
        self.assertEqual(second.interval_days, 6)
        self.assertGreater(third.interval_days, 6)
        self.assertEqual(first.next_review_date, today + timedelta(days=1))

    def _make_subtopic(self):
        study = self.service.create_study("Study")
        topic = self.service.create_topic(study["id"], "Topic")
        subtopic = self.service.create_subtopic(topic["id"], "Subtopic")
        return subtopic["id"]


if __name__ == "__main__":
    unittest.main()
