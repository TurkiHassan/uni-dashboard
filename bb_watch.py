# -*- coding: utf-8 -*-
"""Blackboard watcher + dashboard syncer for Turki (University of Tabuk).

Usage:
    python bb_watch.py                    # scan + diff + report only
    python bb_watch.py --update-dashboard  # scan + diff + rewrite data.js + git push

Output JSON (also written to bb_watch_report.json):
    status     : OK | LOGIN_REQUIRED | ERROR
    report     : Arabic summary ('' when nothing new)
    new_tasks  : newly-appeared graded items
    new_anns   : newly-appeared announcements
    all_tasks  : current full list
    dashboard  : {'updated': bool, 'message': str}
"""
import json, io, os, sys, re, time, socket, datetime, subprocess

BASE = 'https://lms.ut.edu.sa'
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, 'bb_watch_state.json')
REPORT = os.path.join(HERE, 'bb_watch_report.json')
DATAJS = os.path.join(HERE, 'data.js')

# --- Chrome CDP bootstrap (added 2026-10-07: fix ECONNREFUSED ::1:9222) ---
CDP_HOST = '127.0.0.1'
CDP_PORT = 9222
CDP_URL = 'http://%s:%d' % (CDP_HOST, CDP_PORT)
PROFILE_DIR = os.path.join(os.path.dirname(HERE), 'blackboard_profile')
CHROME_CANDIDATES = [
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    os.path.join(os.environ.get('LOCALAPPDATA', ''), r'Google\Chrome\Application\chrome.exe'),
]


def port_open(timeout=1.0):
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((CDP_HOST, CDP_PORT))
        return True
    except Exception:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


def ensure_chrome_debug(wait_s=45):
    """Make sure a Chrome with --remote-debugging-port is up and reachable.
    Launches the dedicated Blackboard profile when port 9222 is closed.
    Returns 'already-running' | 'launched'."""
    if port_open():
        return 'already-running'
    exe = next((p for p in CHROME_CANDIDATES if os.path.exists(p)), None)
    if not exe:
        raise RuntimeError('لم أجد chrome.exe لتشغيل بروفايل بلاك بورد')
    flags = 0x00000008 if os.name == 'nt' else 0  # DETACHED_PROCESS on Windows
    subprocess.Popen(
        [exe, '--remote-debugging-port=%d' % CDP_PORT, '--remote-debugging-address=' + CDP_HOST,
         '--user-data-dir=' + PROFILE_DIR, '--no-first-run', '--no-default-browser-check',
         '--disable-features=Translate', BASE + '/webapps/login/'],
        creationflags=flags, close_fds=True)
    for _ in range(max(1, wait_s)):
        if port_open():
            time.sleep(2)
            return 'launched'
        time.sleep(1)
    raise RuntimeError('تشغيل Chrome لم يفتح منفذ التنقيح %d' % CDP_PORT)

COURSES = [
    ('_203638_1', 'أساسيات الذكاء الاصطناعي 601', '481_CSC601_28227_1_231_18', 'DR. عماد الحربي'),
    ('_203644_1', 'البرمجة المتقدمة وإطارات برمجة 605', '481_CSC605_28262_1_228_18', 'DR. احمد مباركي'),
    ('_203640_1', 'الرياضيات الحاسوبية 602', '481_CSC602_28261_1_227_18', 'DR. محمد عالم'),
    ('_203650_1', 'طرق بحث 608', '481_CSC608_28263_1_229_18', 'DR. محمد الوكيل'),
]

MONTHS_AR = {1: 'يناير', 2: 'فبراير', 3: 'مارس', 4: 'أبريل', 5: 'مايو', 6: 'يونيو',
             7: 'يوليو', 8: 'أغسطس', 9: 'سبتمبر', 10: 'أكتوبر', 11: 'نوفمبر', 12: 'ديسمبر'}


def load_json(path, default):
    try:
        with io.open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, obj):
    with io.open(path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=2))


def is_login_url(u):
    u = (u or '').rstrip('/')
    return ('new_loc' in u) or ('/webapps/login' in u) or (u == BASE) or u == BASE + '/?'


def parse_mdy(s):
    """'10/8/26' -> date(2026,10,8)"""
    m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{2,4})', s or '')
    if not m:
        return None
    mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100:
        y += 2000
    try:
        return datetime.date(y, mo, d)
    except ValueError:
        return None


def clean_title(t):
    t = re.sub(r'\s*Unlimited attempts possible\s*', ' ', t or '')
    t = re.sub(r'\s*\(\s*Late\s*\)\s*', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()


def fmt_due(d, hh=23, mm=59):
    """24h hour in -> Arabic 12h display string."""
    if not d:
        return ''
    ap = 'م' if hh >= 12 else 'ص'
    return '%d %s %d — %d:%02d %s' % (d.day, MONTHS_AR[d.month], d.year, (hh % 12) or 12, mm, ap)


def fmt_ann_date(posted):
    """'9/2/26, 12:39 PM' -> '2 سبتمبر 2026 — 12:39 م'"""
    d = parse_mdy(posted)
    tm = re.search(r'(\d{1,2}:\d{2})\s*(AM|PM)', posted or '', re.I)
    if not d:
        return (posted or '').strip()
    if tm:
        hhmm, ap = tm.group(1), tm.group(2).upper()
        return '%d %s %d — %s %s' % (d.day, MONTHS_AR[d.month], d.year, hhmm, 'م' if ap == 'PM' else 'ص')
    return '%d %s %d' % (d.day, MONTHS_AR[d.month], d.year)


def scan():
    """Return dict with status/tasks/anns."""
    res = {'status': 'OK', 'tasks': [], 'anns': []}
    res['chrome'] = ensure_chrome_debug()
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP_URL)
        ctx = b.contexts[0]
        page = None
        for pg in list(ctx.pages):
            try:
                if 'lms.ut.edu.sa' in pg.url and not is_login_url(pg.url):
                    page = pg
                    break
            except Exception:
                pass
        if page is None:
            page = ctx.new_page()

        page.goto(BASE + '/ultra/course', timeout=90000)
        page.wait_for_timeout(9000)
        try:
            body_head = page.inner_text('body')[:400]
        except Exception:
            body_head = ''
        if is_login_url(page.url) or ('اسم المستخدم' in body_head and 'كلمة المرور' in body_head):
            # The profile has saved credentials: one click on #entry-login usually suffices.
            try:
                page.click('#entry-login', timeout=5000)
                page.wait_for_timeout(8000)
                body_head = page.inner_text('body')[:400]
            except Exception:
                pass
            if is_login_url(page.url) or ('اسم المستخدم' in body_head and 'كلمة المرور' in body_head):
                res['status'] = 'LOGIN_REQUIRED'
                return res

        for cid, cname, code, instr in COURSES:
            # ---- exact due times from the outline ----
            times = {}
            try:
                page.goto(BASE + '/ultra/courses/%s/outline' % cid, timeout=90000)
                page.wait_for_timeout(8000)
                txt = page.inner_text('body')
                for m in re.finditer(r'Due date:\s*(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d{1,2}):(\d{2})\s*(AM|PM)', txt, re.I):
                    d = parse_mdy(m.group(1))
                    if d:
                        h = int(m.group(2)) % 12
                        if m.group(4).upper() == 'PM':
                            h += 12
                        times[d] = (h, int(m.group(3)))
            except Exception:
                pass

            # ---- graded items ----
            try:
                page.goto(BASE + '/ultra/courses/%s/grades' % cid, timeout=90000)
                page.wait_for_timeout(8000)
                rows = page.evaluate("""() => {
                  const out = [];
                  document.querySelectorAll('table tr').forEach(tr => {
                    const c = Array.from(tr.querySelectorAll('th,td'))
                      .map(x => (x.innerText||'').replace(/\\s+/g,' ').trim());
                    if (c.length >= 3 && c.some(Boolean)) out.push(c);
                  });
                  return out;
                }""")
                for r in rows:
                    if not r or r[0] in ('Item Name', ''):
                        continue
                    raw_title = (r[0] or '').strip()
                    due = (r[1] if len(r) > 1 else '').strip()
                    status = (r[2] if len(r) > 2 else '').strip()
                    grade = (r[3] if len(r) > 3 else '').strip()
                    d = parse_mdy(due)
                    if not d:
                        continue  # skip undated items (e.g. Attendance / Ongoing)
                    late = ('late' in raw_title.lower()) or ('late' in status.lower())
                    done = status.lower() in ('graded', 'submitted', 'completed')
                    t = times.get(d, (23, 59))
                    res['tasks'].append({
                        'course': cname, 'code': code, 'title': clean_title(raw_title),
                        'raw_title': raw_title, 'due_date': d.isoformat(),
                        'due': fmt_due(d, t[0], t[1]),
                        'dateISO': '%sT%02d:%02d:00+03:00' % (d.isoformat(), t[0], t[1]),
                        'status': status, 'grade': grade, 'done': done, 'late': late,
                    })
            except Exception as e:
                res['tasks'].append({'course': cname, 'title': '__ERR__', 'err': str(e)})

            # ---- announcements ----
            try:
                page.goto(BASE + '/ultra/courses/%s/announcements' % cid, timeout=90000)
                page.wait_for_timeout(7000)
                items = page.evaluate("""() => {
                  const out = [];
                  document.querySelectorAll('table tr').forEach(tr => {
                    const c = Array.from(tr.querySelectorAll('th,td')).map(x => (x.innerText||'').trim());
                    if (c.length < 2) return;
                    if (c[0].split('\\n')[0].trim() === 'Announcement') return;
                    if (!/^\\d{1,2}\\/\\d{1,2}\\/\\d{2}/.test(c[1])) return;
                    out.push({t: c[0], p: c[1]});
                  });
                  return out.slice(0, 30);
                }""")
                for it in items:
                    lines = [x.strip() for x in (it['t'] or '').split('\n') if x.strip()]
                    title = re.sub(r'\s+', ' ', lines[0]).strip() if lines else ''
                    if not title:
                        continue
                    res['anns'].append({
                        'course': cname, 'title': title, 'posted': it['p'],
                        'date': fmt_ann_date(it['p']),
                        'raw': '%s (%s)' % (title, it['p']),
                    })
            except Exception:
                pass
    return res


def read_datajs():
    try:
        with io.open(DATAJS, encoding='utf-8') as f:
            raw = f.read()
        m = re.search(r'window\.DATA\s*=\s*(\{.*\})\s*;?\s*$', raw, re.S)
        return json.loads(m.group(1)) if m else {}
    except Exception:
        return {}


def write_datajs(d):
    with io.open(DATAJS, 'w', encoding='utf-8') as f:
        f.write('window.DATA = ' + json.dumps(d, ensure_ascii=False, indent=2) + ';\n')


def git_push(msg):
    def run(args):
        r = subprocess.run(args, cwd=HERE, capture_output=True, text=True)
        return (r.returncode, (r.stdout or '') + (r.stderr or ''))
    run(['git', 'add', 'data.js'])
    rc, o = run(['git', '-c', 'user.name=Clove', '-c', 'user.email=clove@local', 'commit', '-m', msg])
    if rc != 0 and 'nothing to commit' in o:
        return 'لا تغيير في data.js'
    rc2, o2 = run(['git', 'push', 'origin', 'HEAD'])
    return 'تم الدفع' if rc2 == 0 else ('فشل الدفع: ' + o2.strip()[:200])


def update_dashboard(scanres):
    d = read_datajs()
    if not d:
        return {'updated': False, 'message': 'تعذّر قراءة data.js'}

    now = datetime.datetime.now()
    d['updated'] = '%d %s %d — %d:%02d %s' % (now.day, MONTHS_AR[now.month], now.year,
                                              (now.hour % 12) or 12, now.minute, 'م' if now.hour >= 12 else 'ص')
    d['updatedISO'] = now.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    d['sync'] = {'status': 'ok', 'timestamp': d['updatedISO'],
                 'message': 'مزامنة تلقائية من Blackboard Ultra (كل ٧٢ ساعة)'}

    tasks = []
    for t in scanres['tasks']:
        if t.get('title') == '__ERR__':
            continue
        item = {'title': t['title'], 'course': t['course'], 'due': t['due'],
                'dateISO': t['dateISO'], 'done': t['done'], 'late': t['late']}
        note = []
        if t.get('grade') and t['grade'] not in ('Not graded',):
            note.append('الدرجة ' + t['grade'])
        if t.get('late'):
            note.append('مسجَّل متأخر')
        if note:
            item['note'] = ' — '.join(note)
        tasks.append(item)
    if tasks:
        d['tasks'] = tasks

    anns = scanres['anns'][:8]
    if anns:
        d['announcements'] = [{'title': a['title'], 'course': a['course'], 'date': a['date']} for a in anns]

    # semester + events always come from the official UT academic calendar file
    try:
        import official_calendar
        d['semester'] = official_calendar.semester_block()
        d['events'] = official_calendar.events_block()
    except Exception as e:
        print('WARN official_calendar:', e)

    write_datajs(d)
    msg = git_push('auto sync: blackboard scan %s' % now.strftime('%Y-%m-%d %H:%M'))
    return {'updated': True, 'message': msg, 'tasks': len(tasks), 'anns': len(anns)}


def main():
    update = '--update-dashboard' in sys.argv
    out = {'status': 'OK', 'report': '', 'new_tasks': [], 'new_anns': [],
           'all_tasks': [], 'dashboard': {'updated': False, 'message': ''},
           'scanned_at': datetime.datetime.now().isoformat(timespec='seconds')}
    try:
        res = scan()
    except Exception as e:
        out['status'] = 'ERROR'
        out['report'] = 'فشل الفحص: %s' % e
        save_json(REPORT, out)
        print(json.dumps(out, ensure_ascii=False))
        return

    if res['status'] == 'LOGIN_REQUIRED':
        out['status'] = 'LOGIN_REQUIRED'
        out['report'] = 'جلسة بلاك بورد منتهية — يحتاج تركي يسجّل دخول من جديد.'
        save_json(REPORT, out)
        print(json.dumps(out, ensure_ascii=False))
        return

    tasks, anns = res['tasks'], res['anns']
    out['all_tasks'] = tasks

    prev = load_json(STATE, {})
    prev_task_keys = set(prev.get('task_keys', []))
    prev_ann_keys = set(prev.get('ann_keys', []))
    cur_task_keys = set('%s||%s||%s' % (t['course'], t.get('title'), t.get('due')) for t in tasks)
    cur_ann_keys = set('%s||%s' % (a['course'], a['raw'][:120]) for a in anns if a.get('raw'))

    new_task_keys = cur_task_keys - prev_task_keys
    new_ann_keys = cur_ann_keys - prev_ann_keys

    out['new_tasks'] = [t for t in tasks if ('%s||%s||%s' % (t['course'], t.get('title'), t.get('due'))) in new_task_keys]
    out['new_anns'] = [a for a in anns if a.get('raw') and ('%s||%s' % (a['course'], a['raw'][:120])) in new_ann_keys]

    lines = []
    if out['new_tasks']:
        lines.append('📚 بنود جديدة أو محدّثة:')
        for t in out['new_tasks']:
            extra = (' — الدرجة ' + t['grade']) if t.get('grade') and t['grade'] != 'Not graded' else ''
            lines.append('• %s — %s — التسليم %s%s' % (t['title'], t['course'], t['due'], extra))
    if out['new_anns']:
        if lines:
            lines.append('')
        lines.append('📢 إعلانات جديدة:')
        for a in out['new_anns']:
            lines.append('• %s: %s — %s' % (a['course'], a['title'][:100], a['posted']))
    out['report'] = '\n'.join(lines)

    if update:
        try:
            out['dashboard'] = update_dashboard(res)
        except Exception as e:
            out['dashboard'] = {'updated': False, 'message': 'فشل تحديث اللوحة: %s' % e}

    save_json(STATE, {'task_keys': sorted(cur_task_keys), 'ann_keys': sorted(cur_ann_keys),
                      'updated': out['scanned_at'], 'all_tasks': tasks})
    save_json(REPORT, out)
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
