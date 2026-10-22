# -*- coding: utf-8 -*-
"""Full dashboard sync from stream_full.json.

Updates ONLY: courses, tasks, week, announcements, updated.
Preserves:   semester, events, studyPlan.
Run validate_data.py afterwards as the publish gate.
"""
from __future__ import annotations
import json, re, datetime
from pathlib import Path

HERE = Path(__file__).parent
DATA_PATH = HERE / 'data.js'
STREAM_PATH = HERE / 'stream_full.json'
EXTRACT_PATH = HERE / 'extract_run.json'

MONTHS_AR = {'Jan': 'يناير', 'Feb': 'فبراير', 'Mar': 'مارس', 'Apr': 'أبريل', 'May': 'مايو',
             'Jun': 'يونيو', 'Jul': 'يوليو', 'Aug': 'أغسطس', 'Sep': 'سبتمبر', 'Oct': 'أكتوبر',
             'Nov': 'نوفمبر', 'Dec': 'ديسمبر'}

now = datetime.datetime.now()


def load_data() -> dict:
    text = DATA_PATH.read_text(encoding='utf-8-sig')
    m = re.search(r"window\.DATA\s*=\s*(\{.*\})\s*;?\s*$", text, re.S)
    return json.loads(m.group(1))


def parse_dt(raw: str):
    raw = raw.strip()
    m = re.match(r'([A-Za-z]{3})\s+(\d{1,2}),\s*(\d{4})\s+(\d{1,2}):(\d{2})\s*(AM|PM)', raw)
    if m:
        mon, d, y, hh, mm, ap = m.groups()
        hh = int(hh) % 12 + (12 if ap.upper() == 'PM' else 0)
        return datetime.datetime(int(y), list(MONTHS_AR).index(mon) + 1, int(d), hh, int(mm))
    m = re.match(r'(\d+)\s+hours?\s+(\d{1,2}):(\d{2})\s*(AM|PM)', raw)
    if m:
        ago, hh, mm, ap = m.groups()
        base = now - datetime.timedelta(hours=int(ago))
        hh = int(hh) % 12 + (12 if ap.upper() == 'PM' else 0)
        return base.replace(hour=hh, minute=int(mm), second=0, microsecond=0)
    return None


def date_ar(dt: datetime.datetime) -> str:
    hh = dt.hour % 12 or 12
    ap = 'م' if dt.hour >= 12 else 'ص'
    return f"{dt.day} {MONTHS_AR[dt.strftime('%b')]} {dt.year} — {hh}:{dt.minute:02d} {ap}"


def clean_course(s: str) -> str:
    return re.sub(r'\s*CSC_شعبة\(\d+\)نظري.*$', '', s).strip()


def parse_item(raw: str):
    lines = [ln.strip() for ln in raw.split('\n') if ln.strip()]
    if len(lines) < 3:
        return None
    raw_date, course_line, third = lines[0], lines[1], lines[2]
    dt = parse_dt(raw_date)
    course = clean_course(course_line)
    if third.startswith('Added:'):
        return {'kind': 'added', 'title': third[len('Added:'):].strip(), 'course': course, 'dt': dt, 'raw_date': raw_date}
    if third.startswith('New course available'):
        return {'kind': 'newcourse', 'title': third, 'course': course, 'dt': dt, 'raw_date': raw_date}
    if third.startswith('Due:'):
        due = lines[3] if len(lines) > 3 else ''
        return {'kind': 'due', 'title': third[len('Due:'):].strip(), 'course': course, 'dt': dt, 'due': due, 'raw_date': raw_date}
    if third.startswith('Past due:'):
        due = lines[3] if len(lines) > 3 else ''
        return {'kind': 'pastdue', 'title': third[len('Past due:'):].strip(), 'course': course, 'dt': dt, 'due': due, 'raw_date': raw_date}
    # instructor announcement: title not a system marker
    if 'CSC_شعبة' in course_line and 3 < len(third) < 200:
        return {'kind': 'ann', 'title': third, 'course': course, 'dt': dt, 'raw_date': raw_date}
    return None


def parse_due(raw: str):
    """'10/8/26, 11:59 PM (UTC+3)' -> (dateISO, display)."""
    m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{2,4}),?\s*(\d{1,2}):(\d{2})\s*(AM|PM)', raw)
    if not m:
        return None, None
    mo, d, y, hh, mm, ap = m.groups()
    y = int(y) + (2000 if len(y) == 2 else 0)
    hh24 = int(hh) % 12 + (12 if ap.upper() == 'PM' else 0)
    tz = '+03:00'
    mtz = re.search(r'UTC([+-])(\d{1,2})', raw)
    if mtz:
        tz = f"{mtz.group(1)}{int(mtz.group(2)):02d}:00"
    iso = f"{y:04d}-{int(mo):02d}-{int(d):02d}T{hh24:02d}:{int(mm):02d}:00{tz}"
    disp = f"{int(d)} {MONTHS_AR[datetime.date(y, int(mo), 1).strftime('%b')]} {y} — {hh24 % 12 or 12}:{int(mm):02d} {'م' if hh24 >= 12 else 'ص'}"
    return iso, disp


def main() -> int:
    old = load_data()
    groups = json.loads(STREAM_PATH.read_text(encoding='utf-8'))['groups']

    parsed = []
    for g in groups:
        for raw in g['items']:
            it = parse_item(raw)
            if it:
                parsed.append(it)

    # ---- announcements: Added + instructor (skip new course / due markers) ----
    anns = [it for it in parsed if it['kind'] in ('added', 'ann')]
    anns.sort(key=lambda x: (x['dt'] or datetime.datetime.min), reverse=True)
    seen = set()
    announcements = []
    for it in anns:
        key = (it['title'], it['course'])
        if key in seen:
            continue
        seen.add(key)
        announcements.append({'title': it['title'], 'course': it['course'],
                              'date': date_ar(it['dt']) if it['dt'] else it['raw_date']})
        if len(announcements) >= 6:
            break

    # ---- tasks: assignments (due / past due) ----
    tasks = []
    for it in parsed:
        if it['kind'] not in ('due', 'pastdue'):
            continue
        iso, disp = parse_due(it.get('due', ''))
        tasks.append({'title': it['title'], 'course': it['course'], 'due': disp or it.get('due', ''),
                      'dateISO': iso, 'done': False, 'late': it['kind'] == 'pastdue'})
    # dedupe by (title, course)
    seen_t = set()
    tasks = [t for t in tasks if not ((t['title'], t['course']) in seen_t or seen_t.add((t['title'], t['course'])))]

    hh = now.hour % 12 or 12
    updated = f"{now.day} {MONTHS_AR[now.strftime('%b')]} {now.year} - {hh}:{now.minute:02d} {'م' if now.hour >= 12 else 'ص'}"

    new = {
        'updated': updated,
        'courses': old.get('courses', []),      # unchanged this run (4 courses match)
        'semester': old['semester'],
        'events': old['events'],
        'tasks': tasks,
        'week': old.get('week', []),
        'announcements': announcements,
        'studyPlan': old['studyPlan'],
    }
    # semester + events always come from the official UT academic calendar file
    try:
        import official_calendar
        new['semester'] = official_calendar.semester_block()
        new['events'] = official_calendar.events_block()
    except Exception as e:
        print('WARN official_calendar:', e)
    out = 'window.DATA = ' + json.dumps(new, ensure_ascii=False, indent=2) + ';\n'
    DATA_PATH.write_text(out, encoding='utf-8')

    old_titles = {(a['title'], a['course']) for a in old.get('announcements', [])}
    print('updated:', updated)
    print('announcements:', len(announcements), '| tasks:', len(tasks), '| courses:', len(new['courses']))
    for a in announcements:
        flag = 'NEW' if (a['title'], a['course']) not in old_titles else '   '
        print(f'  [{flag}] {a["date"]} | {a["course"]} | {a["title"]}')
    for t in tasks:
        print(f'  [task] {t["title"]} | {t["course"]} | {t["due"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
