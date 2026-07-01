import unittest

from interview_prep_mcp.db import connect
from interview_prep_mcp.service import InterviewPrepService

from scripts.seed_demo_data import DEMO_STUDY, seed_demo_data


class SeedDemoDataTests(unittest.TestCase):
    def test_seed_demo_data_is_idempotent_and_subject_scoped(self):
        conn = connect(":memory:")
        reviewer = InterviewPrepService(conn, owner_subject="reviewer-demo")
        other = InterviewPrepService(conn, owner_subject="other-user")
        other.create_study("Private Study")

        first = seed_demo_data(reviewer, with_attempts=True)
        second = seed_demo_data(reviewer, with_attempts=True)

        self.assertEqual(first["created"]["studies"], 1)
        self.assertEqual(first["created"]["topics"], 2)
        self.assertEqual(first["created"]["subtopics"], 4)
        self.assertEqual(first["created"]["attempts"], 2)
        self.assertEqual(second["created"], {"studies": 0, "topics": 0, "subtopics": 0, "attempts": 0})
        self.assertEqual(first["study_name"], DEMO_STUDY)
        self.assertEqual(first["totals"]["studies"], 1)
        self.assertEqual(first["totals"]["topics"], 2)
        self.assertEqual(first["totals"]["subtopics"], 4)
        self.assertEqual(first["totals"]["attempts"], 2)
        self.assertTrue(first["with_attempts"])
        self.assertEqual(len(reviewer.list_studies()), 1)
        self.assertEqual([study["name"] for study in other.list_studies()], ["Private Study"])

    def test_seed_demo_data_repairs_partially_seeded_attempts(self):
        conn = connect(":memory:")
        reviewer = InterviewPrepService(conn, owner_subject="reviewer-demo")
        first = seed_demo_data(reviewer, with_attempts=False)
        due = reviewer.get_due_subtopics(study_id=first["study_id"])
        reviewer.log_attempt(
            due[0]["subtopic_id"],
            4,
            "Manual partial seed.",
            "Explain the first demo topic.",
        )

        repaired = seed_demo_data(reviewer, with_attempts=True)
        final = seed_demo_data(reviewer, with_attempts=True)

        self.assertEqual(repaired["created"]["attempts"], 1)
        self.assertEqual(repaired["totals"]["attempts"], 2)
        self.assertEqual(final["created"]["attempts"], 0)
        self.assertEqual(final["totals"]["attempts"], 2)
