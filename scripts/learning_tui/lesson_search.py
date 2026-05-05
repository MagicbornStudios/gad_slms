from __future__ import annotations

from . import icons
from .lessons import LESSONS
from .models import Lesson


def normalize_search_text(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").replace("_", " ").split())


def levenshtein_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if left == "":
        return len(right)
    if right == "":
        return len(left)
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            insert_cost = current[right_index - 1] + 1
            delete_cost = previous[right_index] + 1
            replace_cost = previous[right_index - 1] + (left_char != right_char)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current
    return previous[-1]


def score_lesson_match(query: str, index: int, lesson: Lesson) -> int:
    lesson_number = str(index + 1)
    fields = [
        lesson_number,
        lesson.id,
        lesson.title,
        lesson.goal,
    ]
    normalized_fields = [normalize_search_text(field) for field in fields]
    haystack = " ".join(normalized_fields)
    words = set(haystack.split())
    query_words = set(query.split())

    score = 0
    if query == lesson_number or query == lesson.id:
        score += 160
    if lesson.id.startswith(query):
        score += 120
    if query in haystack:
        score += 80
    score += 18 * len(query_words & words)

    best_distance = min(
        levenshtein_distance(query, candidate)
        for candidate in [lesson.id, lesson_number, *words]
        if candidate
    )
    typo_allowance = 1 if len(query) < 6 else 2
    if best_distance <= typo_allowance:
        score += 70 - (best_distance * 20)

    if score == 0 and len(query) >= 3:
        closest_word = min((levenshtein_distance(query, word) for word in words), default=99)
        if closest_word <= max(2, len(query) // 3):
            score = 25 - closest_word
    return score


def matching_lessons(query: str) -> list[tuple[int, Lesson]]:
    if query == "":
        return list(enumerate(LESSONS))
    normalized = normalize_search_text(query)
    matches: list[tuple[int, int, Lesson]] = []
    for index, lesson in enumerate(LESSONS):
        score = score_lesson_match(normalized, index, lesson)
        if score > 0:
            matches.append((score, index, lesson))
    matches.sort(key=lambda match: (-match[0], match[1]))
    return [(index, lesson) for _score, index, lesson in matches]


def format_lesson_suggestion(lesson_index: int, lesson: Lesson, query: str) -> str:
    prefix = "recommended" if query else "lesson"
    return f"{lesson_index + 1}. {icons.CHAT} /lesson {lesson.id}  -  {lesson.title}  [{prefix}]"
