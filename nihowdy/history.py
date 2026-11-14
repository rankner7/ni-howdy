"""Daily vocabulary mastery reconstructed from persisted scoring results."""
from collections import Counter
from datetime import date, datetime, timedelta


def mastery_history(attempts, progress, forms, today, zone, started_on):
    # Each skill and dictionary sense has independent progress. The chart counts
    # a written form once while any of those skills/senses remains mastered.
    events = []
    recorded = set()
    for attempt in attempts:
        result = attempt['progress']
        if not result or attempt['item_id'] not in forms:
            continue
        key = (attempt['item_id'], attempt['mode'])
        recorded.add(key)
        day = datetime.fromisoformat(attempt['created_at']).astimezone(zone).date().isoformat()
        events.append((day, attempt['id'], key, result['status'] in ('mastered', 'review')))
    # Legacy/imported progress can predate the available scored prompts.
    for p in progress:
        key = (p['item_id'], p['mode'])
        if (key not in recorded and p['item_id'] in forms and
                p['mode'] in ('flashcards', 'drawing') and
                p['status'] in ('mastered', 'review') and p['mastered_on']):
            events.append((p['mastered_on'], -1, key, True))
    first_day = min([today, started_on] + [event[0] for event in events])
    baseline = (date.fromisoformat(first_day) - timedelta(days=1)).isoformat()
    daily = {baseline: 0}
    skills, counts, total = {}, Counter(), 0
    for day, _, key, mastered in sorted(events):
        if day > today:
            continue
        previous = skills.get(key, False)
        skills[key] = mastered
        form = forms[key[0]]
        before = counts[form] > 0
        counts[form] += int(mastered) - int(previous)
        total += int(counts[form] > 0) - int(before)
        daily[day] = total
    # Current progress is authoritative after imports, deletion, or repairs.
    daily[today] = len({forms[p['item_id']] for p in progress
                        if p['item_id'] in forms and p['mode'] in ('flashcards', 'drawing')
                        and p['status'] in ('mastered', 'review')})
    return [{'date': day, 'mastered': count} for day, count in sorted(daily.items())]
