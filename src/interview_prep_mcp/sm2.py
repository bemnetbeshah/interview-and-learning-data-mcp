"""SM-2 spaced repetition calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class ReviewState:
    mastery_level: int = 0
    ease_factor: float = 2.5
    interval_days: int = 0
    consecutive_correct: int = 0


@dataclass(frozen=True)
class ReviewUpdate:
    mastery_level: int
    ease_factor: float
    interval_days: int
    next_review_date: date
    consecutive_correct: int

    @property
    def next_review_summary(self) -> str:
        if self.interval_days == 1:
            return "next review: in 1 day"
        return f"next review: in {self.interval_days} days"


def update_review_state(state: ReviewState, score: int, today: date) -> ReviewUpdate:
    if score < 1 or score > 5:
        raise ValueError("score must be between 1 and 5")

    ease_factor = _updated_ease_factor(state.ease_factor, score)

    if score <= 2:
        consecutive_correct = 0
        interval_days = 1
    else:
        consecutive_correct = state.consecutive_correct + 1
        if consecutive_correct == 1:
            interval_days = 1
        elif consecutive_correct == 2:
            interval_days = 6
        else:
            interval_days = max(1, round(state.interval_days * ease_factor))

    mastery_level = _mastery_level(consecutive_correct, score)
    return ReviewUpdate(
        mastery_level=mastery_level,
        ease_factor=ease_factor,
        interval_days=interval_days,
        next_review_date=today + timedelta(days=interval_days),
        consecutive_correct=consecutive_correct,
    )


def _updated_ease_factor(current: float, score: int) -> float:
    adjusted = current + (0.1 - (5 - score) * (0.08 + (5 - score) * 0.02))
    return max(1.3, round(adjusted, 4))


def _mastery_level(consecutive_correct: int, score: int) -> int:
    if score <= 2:
        return max(0, score * 8)

    streak_component = min(70, consecutive_correct * 18)
    score_component = {3: 10, 4: 20, 5: 30}[score]
    return min(100, streak_component + score_component)
