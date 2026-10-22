# -*- coding: utf-8 -*-
"""Shared loader for the official UT academic calendar (Fall 1448).

Used by bb_watch.py / update_data.py / sync_data.py so the dashboard's
`semester` + `events` blocks always come from the official calendar file
instead of being hand-typed / frozen copies of old data.
"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CAL_PATH = os.path.join(HERE, 'official_calendar_fall_1448.json')


def load_calendar():
    with io.open(CAL_PATH, encoding='utf-8') as f:
        return json.load(f)


def semester_block():
    c = load_calendar()
    s = c['semester']
    br = c.get('breakWeek') or {}
    return {
        'start': s['start'],
        'end': s['end'],
        'endLabel': s.get('endLabel', ''),
        'weeks': s.get('weeks'),
        'breakStart': br.get('start'),
        'breakEnd': br.get('end'),
    }


def events_block():
    return list(load_calendar().get('events', []))


def apply_calendar(d):
    """Overwrite semester/events in a data dict with official values."""
    try:
        d['semester'] = semester_block()
        d['events'] = events_block()
    except Exception as e:  # keep whatever was there if the file is broken
        d.setdefault('semester', {})
        d.setdefault('events', [])
        print('WARN official_calendar:', e)
    return d
