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
        self.assertNotIn("owner_subject", self.service.list_studies()[0])
        self.assertNotIn("owner_subject", study)
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

    def test_deleted_topic_hides_nested_subtopics_from_direct_id_access(self):
        study = self.service.create_study("Calc 3")
        topic = self.service.create_topic(study["id"], "Vector Calculus")
        subtopic = self.service.create_subtopic(topic["id"], "Divergence theorem")
        self.service.log_attempt(subtopic["id"], 5, "Correct.")

        self.service.delete_topic(topic["id"])

        self.assertEqual(self.service.get_due_subtopics(study_id=study["id"]), [])
        with self.assertRaises(ValueError):
            self.service.list_subtopics(topic["id"])
        with self.assertRaises(ValueError):
            self.service.create_subtopic(topic["id"], "Injected")
        with self.assertRaises(ValueError):
            self.service.update_subtopic(subtopic["id"], name="Renamed")
        with self.assertRaises(ValueError):
            self.service.log_attempt(subtopic["id"], 4, "Should not log.")
        with self.assertRaises(ValueError):
            self.service.get_subtopic_history(subtopic["id"])

    def test_deleted_study_hides_nested_topics_and_subtopics_from_direct_id_access(self):
        study = self.service.create_study("AI Engineering Interview")
        topic = self.service.create_topic(study["id"], "Transformers")
        subtopic = self.service.create_subtopic(topic["id"], "Attention")
        self.service.log_attempt(subtopic["id"], 5, "Correct.")

        self.service.delete_study(study["id"])

        self.assertEqual(self.service.list_studies(), [])
        self.assertEqual(self.service.get_due_subtopics(), [])
        with self.assertRaises(ValueError):
            self.service.list_topics(study["id"])
        with self.assertRaises(ValueError):
            self.service.create_topic(study["id"], "Injected")
        with self.assertRaises(ValueError):
            self.service.list_subtopics(topic["id"])
        with self.assertRaises(ValueError):
            self.service.create_subtopic(topic["id"], "Injected")
        with self.assertRaises(ValueError):
            self.service.get_subtopic_history(subtopic["id"])

    def test_invalid_score_is_rejected(self):
        subtopic_id = self._make_subtopic()
        with self.assertRaises(ValueError):
            self.service.log_attempt(subtopic_id, 6, "Impossible score.")

    def test_subjects_are_isolated_in_shared_database(self):
        bem = InterviewPrepService(self.conn, owner_subject="bem")
        public_user = InterviewPrepService(self.conn, owner_subject="user-2")

        bem_study = bem.create_study("AI Engineering Interview")
        bem_topic = bem.create_topic(bem_study["id"], "Transformers")
        bem_subtopic = bem.create_subtopic(bem_topic["id"], "Attention")

        public_study = public_user.create_study("Calc 3")
        public_topic = public_user.create_topic(public_study["id"], "Vector Calculus")
        public_subtopic = public_user.create_subtopic(public_topic["id"], "Curl")

        self.assertEqual([row["name"] for row in bem.list_studies()], ["AI Engineering Interview"])
        self.assertEqual([row["name"] for row in public_user.list_studies()], ["Calc 3"])
        self.assertEqual([row["subtopic_name"] for row in bem.get_due_subtopics()], ["Attention"])
        self.assertEqual([row["subtopic_name"] for row in public_user.get_due_subtopics()], ["Curl"])

        with self.assertRaises(ValueError):
            bem.list_topics(public_study["id"])
        with self.assertRaises(ValueError):
            public_user.log_attempt(bem_subtopic["id"], 5, "Should not cross accounts.")
        with self.assertRaises(ValueError):
            bem.get_subtopic_history(public_subtopic["id"])

    def test_subjects_cannot_mutate_other_subject_hierarchy(self):
        bem = InterviewPrepService(self.conn, owner_subject="bem")
        public_user = InterviewPrepService(self.conn, owner_subject="user-2")

        bem_study = bem.create_study("AI Engineering Interview")
        bem_topic = bem.create_topic(bem_study["id"], "Transformers")
        bem_subtopic = bem.create_subtopic(bem_topic["id"], "Attention")

        with self.assertRaises(ValueError):
            public_user.create_topic(bem_study["id"], "Injected Topic")
        with self.assertRaises(ValueError):
            public_user.create_subtopic(bem_topic["id"], "Injected Subtopic")
        with self.assertRaises(ValueError):
            public_user.update_subtopic(bem_subtopic["id"], name="Renamed")
        with self.assertRaises(ValueError):
            public_user.delete_subtopic(bem_subtopic["id"])
        with self.assertRaises(ValueError):
            public_user.delete_topic(bem_topic["id"])
        with self.assertRaises(ValueError):
            public_user.delete_study(bem_study["id"])
        with self.assertRaises(ValueError):
            public_user.get_due_subtopics(study_id=bem_study["id"])

        self.assertEqual([row["name"] for row in bem.list_studies()], ["AI Engineering Interview"])
        self.assertEqual([row["name"] for row in bem.list_topics(bem_study["id"])], ["Transformers"])
        self.assertEqual([row["name"] for row in bem.list_subtopics(bem_topic["id"])], ["Attention"])
        self.assertEqual(public_user.list_studies(), [])

    def test_export_my_data_includes_only_current_subject(self):
        bem_subtopic_id = self._make_subtopic()
        self.service.log_attempt(bem_subtopic_id, 4, "Good recall.", "Explain the topic.")

        other = InterviewPrepService(self.conn, owner_subject="user-2")
        other_study = other.create_study("Other Study")
        other_topic = other.create_topic(other_study["id"], "Other Topic")
        other.create_subtopic(other_topic["id"], "Other Subtopic")

        exported = self.service.export_my_data()

        self.assertEqual(exported["owner_subject"], "bem")
        self.assertEqual([row["name"] for row in exported["studies"]], ["Study"])
        self.assertEqual([row["name"] for row in exported["topics"]], ["Topic"])
        self.assertEqual([row["name"] for row in exported["subtopics"]], ["Subtopic"])
        self.assertEqual([row["score"] for row in exported["attempts"]], [4])
        self.assertEqual(len(exported["subtopic_state"]), 1)
        self.assertNotIn("Other Study", str(exported))

    def test_delete_my_data_requires_confirmation_and_preserves_other_subjects(self):
        bem_subtopic_id = self._make_subtopic()
        self.service.log_attempt(bem_subtopic_id, 5, "Correct.")

        other = InterviewPrepService(self.conn, owner_subject="user-2")
        other_study = other.create_study("Other Study")
        other_topic = other.create_topic(other_study["id"], "Other Topic")
        other_subtopic = other.create_subtopic(other_topic["id"], "Other Subtopic")
        other.log_attempt(other_subtopic["id"], 3, "Partial.")

        with self.assertRaises(ValueError):
            self.service.delete_my_data("delete")

        result = self.service.delete_my_data("DELETE MY STUDY DATA")

        self.assertTrue(result["deleted"])
        self.assertNotIn("owner_subject", result)
        self.assertEqual(result["deleted_counts"]["studies"], 1)
        self.assertEqual(result["deleted_counts"]["attempts"], 1)
        self.assertEqual(self.service.list_studies(), [])
        self.assertEqual([row["name"] for row in other.list_studies()], ["Other Study"])
        self.assertEqual(other.get_subtopic_history(other_subtopic["id"])["trend"]["attempt_count"], 1)

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
