"""Taiwan MOE templates, kept separate from the PRC construction dataset."""
import gzip
import json
import math
from pathlib import Path

TEMPLATES = Path(__file__).parent / 'assets' / 'taiwan-strokes.json.gz'
SOURCE = 'https://github.com/g0v/zh-stroke-data'


def convert_character(strokes):
    """Convert MOE's nominal 2000-unit canvas, preserving full glyph geometry.

    Outline control points and pen tracks may extend outside the nominal box.
    Include them in one uniform character transform instead of rejecting or
    clamping them. Characters already within the box keep their old transform.
    """
    if not isinstance(strokes, list) or not 1 <= len(strokes) <= 80:
        raise ValueError('Invalid Taiwan character.')
    coordinates = []
    commands = {'M': (), 'L': (), 'Q': ('begin', 'end'), 'C': ('begin', 'mid', 'end')}
    for stroke_index, stroke in enumerate(strokes, 1):
        if len(stroke['track']) < 2:
            raise ValueError('Taiwan stroke is missing a direction track.')
        if not stroke['outline']:
            raise ValueError('Taiwan stroke is missing an outline.')
        points = list(stroke['track'])
        for command in stroke['outline']:
            kind = command['type']
            if kind not in commands:
                raise ValueError('Unsupported Taiwan outline command: ' + str(kind))
            points.extend([command[key] for key in commands[kind]] if commands[kind] else [command])
        for value in points:
            xy = [value['x'], value['y']]
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in xy):
                raise ValueError(f'Invalid Taiwan stroke coordinate in stroke {stroke_index}: {xy!r}; expected finite numbers.')
            coordinates.append(xy)
    left = min(0, min(p[0] for p in coordinates))
    top = min(0, min(p[1] for p in coordinates))
    right = max(2000, max(p[0] for p in coordinates))
    bottom = max(2000, max(p[1] for p in coordinates))
    size = max(right - left, bottom - top)
    if not math.isfinite(size):
        raise ValueError('Taiwan character bounds are too large.')
    # Centre the expanded box without stretching either axis. Keeping the
    # nominal box in the bounds preserves spacing for narrow characters.
    offset_x = -left + (size - (right - left)) / 2
    offset_y = -top + (size - (bottom - top)) / 2
    paths, medians = [], []
    def point(value):
        return [round((value['x'] + offset_x) / size * 1024, 3),
                round((value['y'] + offset_y) / size * 1024, 3)]
    def pair(value):
        return ' '.join(str(v) for v in point(value))
    for stroke in strokes:
        track = [point(p) for p in stroke['track']]
        path = []
        for command in stroke['outline']:
            kind = command['type']
            if kind in ('M', 'L'):
                path.append(kind + pair(command))
            elif kind == 'Q':
                path.append('Q' + pair(command['begin']) + ' ' + pair(command['end']))
            elif kind == 'C':
                path.append('C' + pair(command['begin']) + ' ' + pair(command['mid']) + ' ' + pair(command['end']))
            else:
                raise ValueError('Unsupported Taiwan outline command: ' + kind)
        paths.append(' '.join(path) + ' Z')
        medians.append(track)
    return {'strokes': paths, 'medians': medians}


def load_taiwan():
    if not TEMPLATES.exists():
        return {}
    with gzip.open(TEMPLATES, 'rt', encoding='utf-8') as source:
        data = json.load(source)
    if data.get('standard') != 'Taiwan MOE' or data.get('version') != 1:
        raise ValueError('Unrecognised Taiwan stroke dataset. Run scripts/prepare_taiwan.py.')
    return data['characters']
