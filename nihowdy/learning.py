"""Pure learning rules. No UI, network, storage, or model dependencies."""
import math
import unicodedata
from datetime import date, timedelta

LEVELS = {
    "flashcards": ["Easy", "Medium", "Hard"],
    "drawing": ["Components", "Guided", "Easy", "Medium", "Hard"],
    "phrases": ["Easy", "Medium", "Hard"],
}


def normalize_answer(text):
    return unicodedata.normalize("NFC", text.strip()).casefold()


def correct_answer(text, accepted):
    return normalize_answer(text) in {normalize_answer(a) for a in accepted}


def transition(progress, correct, lowest, highest, today, guided=False):
    """Return updated progress, preserving independent per-mode state."""
    p = dict(progress)
    p["attempts"] += 1
    if correct:
        p.update(failures=0, boost=0)
        if guided and p["level"] == 1:
            p["guided_completions"] = min(5, p.get("guided_completions", 0) + 1)
            p.update(level=2 if p["guided_completions"] == 5 else 1, status="active")
        elif p["level"] == highest:
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
                if guided and p["level"] == 1:
                    p["guided_completions"] = 0
    return p


def weight(progress, lowest=0, mode=None):
    if mode == 'flashcards' and progress['attempts'] == 0 and progress['level'] == lowest:
        return 0.5
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


def weighted_sample(entries, count, rng):
    """Sample without replacement with odds proportional to positive weights."""
    pool=[(value,w) for value,w in entries if w>0]
    result=[]
    for _ in range(min(count,len(pool))):
        choice=weighted_choice(pool,rng)
        result.append(choice)
        pool=[(value,w) for value,w in pool if value!=choice]
    return result


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


def shape_score(drawn, reference, normalize=False, include_feedback=False):
    """Order/direction-independent geometry match in a 1024-unit drawing box.

    Symmetric coverage penalizes omissions AND extra ink. Per-reference-stroke
    coverage prevents a nearly complete glyph from passing with one stroke absent.
    This is an embedded template matcher, not a learned OCR model.
    """
    if normalize:
        ink_points = [p for s in drawn for p in s]
        target_points = [p for s in reference for p in s]
        if ink_points and target_points:
            def bounds(points):
                xs, ys = zip(*points)
                return min(xs), min(ys), max(xs), max(ys)
            x1,y1,x2,y2 = bounds(ink_points)
            u1,v1,u2,v2 = bounds(target_points)
            size = max(x2-x1,y2-y1)
            if size > 20:
                scale = max(u2-u1,v2-v1)/size
                cx,cy,tx,ty=(x1+x2)/2,(y1+y2)/2,(u1+u2)/2,(v1+v2)/2
                drawn = [[[(x-cx)*scale+tx,(y-cy)*scale+ty] for x,y in s] for s in drawn]
    ink = resample(drawn)
    target = resample(reference)
    radius2 = 58 ** 2

    def coverage(a, b):
        return sum(any((x-u)**2 + (y-v)**2 <= radius2 for u, v in b)
                   for x, y in a) / len(a) if a else 0

    recall = coverage(target, ink)
    precision = coverage(ink, target)
    stroke_coverage = [coverage(resample([s]), ink) for s in reference]
    sufficient = len(ink) >= 3 and bool(target)
    result = {"correct": sufficient and recall >= .84 and precision >= .80 and min(stroke_coverage, default=0) >= .65,
              "coverage": round(recall, 3) if sufficient else 0,
              "precision": round(precision, 3) if sufficient else 0}
    if include_feedback and not result['correct']:
        # Use exactly the aligned ink and tolerance used for grading. Group
        # nearby unmatched samples so the overlay can mark just the extra ink.
        incorrect_ink = []
        for stroke in drawn:
            points = resample([stroke])
            run = []
            for point in points:
                near = any(math.dist(point, expected) <= 58 for expected in target)
                if not near:
                    run.append(point)
                elif run:
                    incorrect_ink.append(run)
                    run = []
            if run:
                incorrect_ink.append(run)
        result['feedback'] = {
            'ink': drawn, 'incorrect_ink': incorrect_ink,
            'missing_strokes': [i for i, score in enumerate(stroke_coverage) if score < .84],
        }
    return result


def guided_stroke_correct(stroke, target):
    """Match a trace in position and direction, including bends and hooks.

    Discrete Frechet distance preserves traversal order, unlike the later
    shape-only levels. Equal spacing makes mouse event frequency immaterial.
    """
    if len(stroke) < 2 or len(target) < 2:
        return False
    if math.dist(stroke[0], target[0]) > 85 or math.dist(stroke[-1], target[-1]) > 85:
        return False
    # A short dot can fit entirely inside the distance tolerance backwards.
    if sum((stroke[-1][i] - stroke[0][i]) * (target[-1][i] - target[0][i]) for i in (0, 1)) <= 0:
        return False
    ink, guide = resample([stroke], 16), resample([target], 16)
    def length(points):
        return sum(math.dist(a, b) for a, b in zip(points, points[1:]))
    target_length = length(target)
    if not .65 * target_length <= length(stroke) <= 1.6 * target_length:
        return False
    previous = [float('inf')] * len(guide)
    for i, point in enumerate(ink):
        current = []
        for j, expected in enumerate(guide):
            distance = math.dist(point, expected)
            best = 0 if i == j == 0 else min(previous[j],
                previous[j-1] if j else float('inf'), current[j-1] if j else float('inf'))
            current.append(max(distance, best))
        previous = current
    return previous[-1] <= 75
