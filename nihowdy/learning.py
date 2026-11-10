"""Pure learning rules. No UI, network, storage, or model dependencies."""
import math
import unicodedata
from datetime import date, timedelta

LEVELS = {
    "flashcards": ["Easy", "Medium", "Hard"],
    "drawing": ["Components", "Easy", "Medium", "Hard"],
    "phrases": ["Easy", "Medium", "Hard"],
}


def normalize_answer(text):
    return unicodedata.normalize("NFC", text.strip()).casefold()


def correct_answer(text, accepted):
    return normalize_answer(text) in {normalize_answer(a) for a in accepted}


def transition(progress, correct, lowest, highest, today):
    """Return updated progress, preserving independent per-mode state."""
    p = dict(progress)
    p["attempts"] += 1
    if correct:
        p.update(failures=0, boost=0)
        if p["level"] == highest:
            p.update(status="mastered", mastered_on=today, checked_on=today)
        else:
            p.update(level=p["level"] + 1, status="active")
    else:
        p["failures"] += 1
        if p["failures"] == 3:
            p["failures"] = 0
            if p["level"] == lowest:
                p["boost"] = min(2, p["boost"] + 1)
            else:
                p.update(level=p["level"] - 1, status="active", mastered_on=None,
                         checked_on=None)
    return p


def weight(progress, lowest=0):
    return (0.5 ** (progress["level"] - lowest)
            * (2 if progress["attempts"] == 0 else 1)
            * min(4, 2 ** progress["boost"]))


def weighted_choice(entries, rng):
    """entries: (value, positive weight) pairs."""
    if not entries:
        return None
    total = sum(w for _, w in entries)
    point = rng.random() * total
    for value, w in entries:
        point -= w
        if point < 0:
            return value
    return entries[-1][0]


def review_trials(checked_on, today, probability, rng):
    """One persisted trial per unexamined calendar day; stop on selection."""
    day = date.fromisoformat(checked_on) + timedelta(days=1)
    end = date.fromisoformat(today)
    trials = []
    while day <= end:
        draw = rng.random()
        selected = draw < probability
        trials.append((day.isoformat(), draw, selected))
        if selected:
            break
        day += timedelta(days=1)
    return trials


def phrase_coverage(tokens, mastered):
    return sum(token in mastered for token in tokens) / len(tokens) if tokens else 0


def resample(strokes, spacing=12):
    points = []
    for stroke in strokes:
        for a, b in zip(stroke, stroke[1:]):
            distance = math.dist(a, b)
            steps = max(1, math.ceil(distance / spacing))
            points.extend((a[0] + (b[0]-a[0])*i/steps, a[1] + (b[1]-a[1])*i/steps)
                          for i in range(steps))
        if stroke:
            points.append(stroke[-1])
    return points


def shape_score(drawn, reference):
    """Order/direction-independent geometry match in a 1024-unit drawing box.

    Symmetric coverage penalizes omissions AND extra ink. Per-reference-stroke
    coverage prevents a nearly complete glyph from passing with one stroke absent.
    This is an embedded template matcher, not a learned OCR model.
    """
    ink = resample(drawn)
    target = resample(reference)
    if len(ink) < 3 or not target:
        return {"correct": False, "coverage": 0, "precision": 0}
    radius2 = 58 ** 2

    def coverage(a, b):
        return sum(any((x-u)**2 + (y-v)**2 <= radius2 for u, v in b)
                   for x, y in a) / len(a) if a else 0

    recall = coverage(target, ink)
    precision = coverage(ink, target)
    weakest = min(coverage(resample([s]), ink) for s in reference)
    return {"correct": recall >= .84 and precision >= .80 and weakest >= .65,
            "coverage": round(recall, 3), "precision": round(precision, 3)}
