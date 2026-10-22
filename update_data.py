# -*- coding: utf-8 -*-
"""Update data.js from extract_run.json: refresh courses/tasks/week/announcements/updated only.
Preserves semester, events, studyPlan from the current file.
Run AFTER extract_all.py (which writes extract_run.json)."""
import json, re, datetime
from pathlib import Path

try:
    import official_calendar
except Exception:
    official_calendar = None

DATA_PATH = Path(__file__).with_name('data.js')
EXTRACT_PATH = Path(__file__).with_name('extract_run.json')

text = DATA_PATH.read_text(encoding='utf-8-sig')
m = re.search(r"window\.DATA\s*=\s*(\{.*\})\s*;?\s*$", text, re.S)
old = json.loads(m.group(1))

raw = EXTRACT_PATH.read_bytes()
try:
    extract = json.loads(raw.decode('utf-8-sig'))
except UnicodeDecodeError:
    extract = json.loads(raw.decode('utf-16'))

now = datetime.datetime.now()
import datetime as _dt
MONTHS_AR = {'Jan': 'يناير', 'Feb': 'فبراير', 'Mar': 'مارس', 'Apr': 'أبريل', 'May': 'مايو',
             'Jun': 'يونيو', 'Jul': 'يوليو', 'Aug': 'أغسطس', 'Sep': 'سبتمبر', 'Oct': 'أكتوبر',
             'Nov': 'نوفمبر', 'Dec': 'ديسمبر'}
MONTHS_AR_FULL = {'January': 'يناير', 'February': 'فبراير', 'March': 'مارس', 'April': 'أبريل', 'May': 'مايو',
                  'June': 'يونيو', 'July': 'يوليو', 'August': 'أغسطس', 'September': 'سبتمبر', 'October': 'أكتوبر',
                  'November': 'نوفمبر', 'December': 'ديسمبر'}
ar_ap = 'م' if now.hour >= 12 else 'ص'
hh12 = now.hour % 12
if hh12 == 0:
    hh12 = 12
updated_str = f"{now.day} {MONTHS_AR_FULL[now.strftime('%B')]} {now.year} - {hh12}:{now.minute:02d} {ar_ap}"
new = {}
new['updated'] = updated_str

# ---- courses: keep existing list (matches extracted course_ids count) ----
courses = old.get('courses', [])
if 'course_ids' in extract:
    new['courses'] = courses  # ids matched previous sync; keep names/instructors

# ---- announcements from activity stream (most recent first) ----
announcements = []
stream = extract.get('stream_items', [])
# each stream item is one string with embedded newlines: date \n course \n Added: X
# or: date \n course \n <announcement title> (instructor announcements)
COURSE_RE = re.compile(r'\s*CSC_شعبة\(\d+\)نظري.*$')
def clean_course(s):
    return COURSE_RE.sub('', s).strip()
for item in stream:
    lines = [ln.strip() for ln in item.split('\n') if ln.strip()]
    if not lines:
        continue
    date_line = lines[0]
    # instructor announcement: date \n course(CSC_شعبة...) \n <title not starting with Added:/New course>
    if (len(lines) >= 3 and 'CSC_شعبة' in lines[1]
            and not lines[2].startswith('Added:')
            and not lines[2].startswith('New course available')
            and 3 < len(lines[2]) < 200):
        announcements.append({'title': lines[2], 'course': clean_course(lines[1]), 'date': date_line})
        continue
    for j, ln in enumerate(lines):
        if ln.startswith('Added:'):
            title = ln[len('Added:'):].strip()
            course_line = lines[j - 1] if j - 1 >= 0 else ''
            course = clean_course(course_line)
            if title:
                announcements.append({'title': title, 'course': course, 'date': date_line})
seen = set()
unique = []
for a in announcements:
    # skip Blackboard's "Past due:" / "Due Date:" Important notices: not real announcements
    if re.match(r'^Past due\s*:', a['title']) or re.match(r'^Due Date\s*:', a['title']):
        continue
    key = (a['title'], a['course'])
    if key not in seen:
        seen.add(key)
        unique.append(a)
announcements = unique[:5]

# convert English/relative stream dates to Arabic display format
# e.g. "Aug 25, 2026 4:46 PM" -> "25 أغسطس 2026 — 4:46 م"
#      "23 hours 9:07 AM"     -> "29 أغسطس 2026 — 9:07 ص" (computed from now)
def to_ar_date(s):
    s = s.strip()
    # relative: "N hours H:MM AM/PM" (Blackboard relative timestamps)
    m = re.match(r'(\d+)\s+hours?\s+(\d{1,2}):(\d{2})\s*(AM|PM)', s, re.I)
    if m:
        hours_ago, hh, mm, ap = m.groups()
        dt = now - _dt.timedelta(hours=int(hours_ago))
        hh = int(hh) % 12
        if hh == 0:
            hh = 12
        ar_ap = 'م' if ap == 'PM' else 'ص'
        return f"{dt.day} {MONTHS_AR_FULL[dt.strftime('%B')]} {dt.year} — {hh}:{mm} {ar_ap}"
    m = re.match(r'([A-Za-z]{3})\s+(\d{1,2}),\s+(\d{4})\s+(\d{1,2}):(\d{2})\s*(AM|PM)', s)
    if m:
        mon, day, year, hh, mm, ap = m.groups()
        hh = int(hh) % 12
        if hh == 0:
            hh = 12
        ar_ap = 'م' if ap == 'PM' else 'ص'
        return f"{int(day)} {MONTHS_AR.get(mon, mon)} {year} — {hh}:{mm} {ar_ap}"
    # "Today Saturday, August 29, 2026" -> "29 أغسطس 2026"
    m2 = re.match(r'Today.*?(\d{1,2}),\s+(\d{4})', s)
    if m2:
        day, year = m2.groups()
        return f"{int(day)} {MONTHS_AR_FULL[now.strftime('%B')]} {year}"
    return s
for a in announcements:
    a['date'] = to_ar_date(a['date'])

# ---- tasks: assignments (none expected; keep previous) ----
tasks = old.get('tasks', [])

# ---- week: schedule API returned no events -> keep previous ----
week = old.get('week', [])

# ---- preserved blocks ----
# semester + events always come from the official UT academic calendar file
if official_calendar is not None:
    new['semester'] = official_calendar.semester_block()
    new['events'] = official_calendar.events_block()
else:
    new['semester'] = old['semester']
    new['events'] = old['events']
new['courses'] = courses
new['tasks'] = tasks
new['week'] = week
new['announcements'] = announcements
new['studyPlan'] = old['studyPlan']

out = 'window.DATA = ' + json.dumps(new, ensure_ascii=False, indent=2) + ';\n'
DATA_PATH.write_text(out, encoding='utf-8')
print('data.js updated:', len(courses), 'courses,', len(tasks), 'tasks,', len(announcements), 'announcements')
for a in announcements:
    print(' -', a['date'], '|', a['course'], '|', a['title'])
