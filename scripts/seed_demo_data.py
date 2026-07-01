#!/usr/bin/env python3
"""Seed reviewer-safe demo study data for one owner subject."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from interview_prep_mcp.config import load_settings  # noqa: E402
from interview_prep_mcp.db import connect  # noqa: E402
from interview_prep_mcp.service import InterviewPrepService  # noqa: E402


DEMO_STUDY = "AI Engineering Interview"
DEMO_TOPICS = {
    "Transformers": [
        (
            "Multi-head Attention",
            "Explain query/key/value projections, parallel attention heads, concatenation, and output projection.",
        ),
        (
            "Positional Encoding",
            "Explain why transformers need position information and compare sinusoidal and learned encodings.",
        ),
    ],
    "Evaluation": [
        (
            "Precision and Recall",
            "Explain precision, recall, F1, and when each metric matters.",
        ),
        (
            "Overfitting",
            "Explain symptoms, validation behavior, and common regularization strategies.",
        ),
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed demo data for OpenAI app review.")
    parser.add_argument(
        "--subject",
        default="reviewer-demo",
        help="Owner subject to seed. This must match the reviewer account token subject.",
    )
    parser.add_argument(
        "--with-attempts",
        action="store_true",
        help="Also log sample attempts so history views are populated.",
    )
    args = parser.parse_args()

    settings = load_settings()
    db = connect(settings.db_path, settings.database_url)
    service = InterviewPrepService(db, owner_subject=args.subject)
    result = seed_demo_data(service, with_attempts=args.with_attempts)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def seed_demo_data(service: InterviewPrepService, with_attempts: bool = False) -> dict:
    study = _get_or_create_study(service, DEMO_STUDY)
    created = {"studies": 0, "topics": 0, "subtopics": 0, "attempts": 0}
    if study.get("_created"):
        created["studies"] += 1

    subtopic_ids = []
    for topic_name, subtopics in DEMO_TOPICS.items():
        topic = _get_or_create_topic(service, study["id"], topic_name)
        if topic.get("_created"):
            created["topics"] += 1
        for subtopic_name, description in subtopics:
            subtopic = _get_or_create_subtopic(service, topic["id"], subtopic_name, description)
            if subtopic.get("_created"):
                created["subtopics"] += 1
            subtopic_ids.append(subtopic["id"])

    if with_attempts:
        created["attempts"] = _seed_sample_attempts(service, subtopic_ids)

    export = service.export_my_data()

    return {
        "owner_subject": service.owner_subject,
        "study_name": DEMO_STUDY,
        "study_id": study["id"],
        "created": created,
        "totals": {
            "studies": len(export["studies"]),
            "topics": len(export["topics"]),
            "subtopics": len(export["subtopics"]),
            "attempts": len(export["attempts"]),
        },
        "due_count": len(service.get_due_subtopics(study_id=study["id"])),
        "with_attempts": with_attempts,
    }


def _get_or_create_study(service: InterviewPrepService, name: str) -> dict:
    for study in service.list_studies():
        if study["name"] == name:
            return study
    created = service.create_study(name)
    created["_created"] = True
    return created


def _get_or_create_topic(service: InterviewPrepService, study_id: int, name: str) -> dict:
    for topic in service.list_topics(study_id):
        if topic["name"] == name:
            return topic
    created = service.create_topic(study_id, name)
    created["_created"] = True
    return created


def _get_or_create_subtopic(service: InterviewPrepService, topic_id: int, name: str, description: str) -> dict:
    for subtopic in service.list_subtopics(topic_id):
        if subtopic["name"] == name:
            return subtopic
    created = service.create_subtopic(topic_id, name, description)
    created["_created"] = True
    return created


def _seed_sample_attempts(service: InterviewPrepService, subtopic_ids: list[int]) -> int:
    samples = [
        (
            subtopic_ids[0],
            4,
            "Demo answer was mostly correct but missed one implementation detail.",
            "Explain how multi-head attention combines multiple attention heads.",
        ),
        (
            subtopic_ids[-1],
            3,
            "Demo answer identified overfitting but needed clearer validation-set reasoning.",
            "How would you diagnose overfitting during model training?",
        ),
    ]
    created = 0
    for subtopic_id, score, notes, question in samples:
        if service.get_subtopic_history(subtopic_id)["trend"]["attempt_count"] > 0:
            continue
        service.log_attempt(subtopic_id, score, notes, question)
        created += 1
    return created


if __name__ == "__main__":
    sys.exit(main())
