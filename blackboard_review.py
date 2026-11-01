"""Read-only Blackboard grade review with durable snapshots and explicit public exports."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from blackboard_storage import HERE, PRIVATE, atomic_json, load_json, sync_lock

RIYADH = dt.timezone(dt.timedelta(hours=3))
SNAPSHOT = PRIVATE / 'grades.json'
REPORT = PRIVATE / 'review.json'
UNGRADED = {'', '-', '—', 'not graded', 'not marked', 'ungraded', 'لم يتم التقدير', 'لم ترصد', 'غير مقدر', 'لم يتم الرصد'}
DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫', '01234567890123456789.')

def timestamp():
    return dt.datetime.now(RIYADH).isoformat(timespec='seconds')

def clean(value):
    value = unicodedata.normalize('NFKC', str(value or '')).replace('\u200e', '').replace('\u200f', '')
    value = re.sub(r'Unlimited attempts possible|\(Content isn.t available\)', '', value, flags=re.I)
    return re.sub(r'\s+', ' ', value).strip()

def grade_value(raw):
    text = clean(raw).translate(DIGITS)
    if text.lower() in UNGRADED:
        return {'grade': '', 'score': None, 'maximum': None, 'pct': None}
    number = r'\d+(?:[.,]\d+)?'
    match = re.search(rf'({number})\s*(?:/|من|out of)\s*({number})', text, re.I)
    if match:
        a, b = [float(x.replace(',', '.')) for x in match.groups()]
        return {'grade': f'{a:g} / {b:g}', 'score': a, 'maximum': b,
                'pct': round(a / b * 100, 1) if b > 0 else None}
    percent = re.fullmatch(rf'({number})\s*[%٪]', text)
    if percent:
        value = float(percent.group(1).replace(',', '.'))
        return {'grade': f'{value:g}%', 'score': None, 'maximum': None, 'pct': value}
    return {'grade': text, 'score': None, 'maximum': None, 'pct': None}

def item_key(course_id, title, source_id=''):
    value = str(course_id) + '|' + (str(source_id) if source_id else clean(title).casefold())
    return hashlib.sha256(value.encode()).hexdigest()[:24]

def parse_rows(course, payload):
    """Keep undated grades, zero grades, textual grades, and grade withdrawals."""
    headers = [clean(x).casefold() for x in payload.get('headers', [])]
    aliases = {'title': ['item name', 'اسم العنصر', 'اسم البند', 'العنصر'],
               'due': ['due date', 'تاريخ الاستحقاق', 'تاريخ التسليم'],
               'status': ['status', 'الحالة'], 'grade': ['grade', 'التقدير', 'الدرجة']}
    offsets = {'title': 0, 'due': 1, 'status': 2, 'grade': 3}
    for name, candidates in aliases.items():
        index = next((i for i, h in enumerate(headers) if h in candidates), None)
        if index is not None:
            offsets[name] = index
    items = {}
    for row in payload.get('rows', []):
        cells = row.get('cells', []) if isinstance(row, dict) else row
        source_id = row.get('id', '') if isinstance(row, dict) else ''
        if len(cells) < 4:
            continue
        values = {name: clean(cells[index]) if index < len(cells) else '' for name, index in offsets.items()}
        title = values['title']
        if not title or title.casefold() in aliases['title'] or 'gradebook.table.' in title:
            continue
        key = item_key(course['id'], title, source_id)
        items[key] = {'id': key, 'courseId': course['id'], 'course': course['name'], 'code': course['code'],
                      'item': title, 'due': values['due'], 'status': values['status'],
                      **grade_value(values['grade'])}
    return list(items.values())

def load_snapshot(path=SNAPSHOT):
    saved = load_json(path)
    if saved:
        return saved
    legacy = load_json(HERE / 'bb_grades_state.json', {})
    return {'status': 'not_checked', 'lastAttemptAt': None, 'lastSuccessAt': legacy.get('scanned_at'),
            'items': list(legacy.get('items', {}).values()), 'courses': {}, 'changes': [],
            'message': 'بيانات محفوظة سابقًا؛ شغّل التحديث للتحقق من حداثتها.'}

def merge_results(previous, results, scanned_at):
    items = list(previous.get('items', []))
    courses = dict(previous.get('courses', {}))
    changes = []
    successes = 0
    for result in results:
        course = result['course']
        cid = course['id']
        old_rows = [x for x in items if x.get('courseId') == cid or x.get('code') == course['code']]
        if result['status'] != 'OK':
            courses[cid] = {**courses.get(cid, {}), 'name': course['name'], 'code': course['code'],
                            'status': result['status'], 'lastAttemptAt': scanned_at,
                            'message': result.get('message', 'تعذر فحص المقرر؛ احتُفظ بالبيانات السابقة.')}
            continue
        successes += 1
        old = {clean(x.get('item')).casefold(): x for x in old_rows}
        for item in result['items']:
            prior = old.get(clean(item['item']).casefold())
            if prior and prior.get('grade', '') != item['grade']:
                changes.append({'id': item['id'], 'course': item['course'], 'item': item['item'],
                                'old': prior.get('grade', ''), 'new': item['grade'], 'kind': 'changed'})
            elif item['grade'] and (not prior or not prior.get('grade')):
                changes.append({'id': item['id'], 'course': item['course'], 'item': item['item'],
                                'old': '', 'new': item['grade'], 'kind': 'new'})
            item['checkedAt'] = scanned_at
        items = [x for x in items if not (x.get('courseId') == cid or x.get('code') == course['code'])] + result['items']
        courses[cid] = {'name': course['name'], 'code': course['code'], 'status': 'OK',
                        'lastAttemptAt': scanned_at, 'lastSuccessAt': scanned_at,
                        'count': len(result['items'])}
    all_ok = bool(results) and successes == len(results)
    login = any(x['status'] == 'LOGIN_REQUIRED' for x in results)
    status = 'OK' if all_ok else 'PARTIAL' if successes else 'LOGIN_REQUIRED' if login else 'ERROR'
    message = ('اكتمل التحقق من تقديرات جميع المقررات.' if all_ok else
               'اكتمل بعض المقررات؛ احتُفظ ببيانات المقررات المتعذرة.' if successes else
               'تحتاج جلسة Blackboard إلى تسجيل الدخول؛ احتُفظ بآخر بيانات.' if login else
               'تعذر التحديث؛ احتُفظ بآخر بيانات محفوظة.')
    return {'status': status, 'message': message, 'lastAttemptAt': scanned_at,
            'lastSuccessAt': scanned_at if all_ok else previous.get('lastSuccessAt'),
            'items': items, 'courses': courses, 'changes': changes}

EXTRACT_ROWS = """() => {
  const table = document.querySelector('table, [role="table"], [role="grid"]');
  const headers = table ? [...table.querySelectorAll('thead th, [role="columnheader"]')].map(x=>x.innerText.trim()) : [];
  const rows = table ? [...table.querySelectorAll('tbody tr, [role="row"]')].map(tr=>({
    id:tr.getAttribute('data-item-id') || '',
    cells:[...tr.querySelectorAll('td, [role="gridcell"], [role="cell"]')].map(x=>x.innerText.trim())
  })).filter(x=>x.cells.length>=4) : [];
  const body=document.body.innerText;
  const empty=/no (?:items|grades|results)|Kick back and relax|instructor.{0,20}assigned work yet|لا توجد (?:عناصر|تقديرات|درجات)/i.test(body);
  return {headers, rows, empty, table:!!table};
}"""

def needs_login(page):
    from bb_watch import is_login_url
    return is_login_url(page.url) or page.locator('input[type="password"]').count() > 0

def ensure_login(page):
    from bb_watch import BASE, BB_USER, BB_PASS
    page.goto(BASE + '/ultra/course', wait_until='domcontentloaded', timeout=45000)
    try:
        page.wait_for_url('**/ultra/**', timeout=10000)
    except Exception:
        pass
    if not needs_login(page):
        return True
    user, password = page.locator('#user_id'), page.locator('#password')
    if user.count() and password.count():
        if not user.input_value() and BB_USER:
            user.fill(BB_USER)
        if not password.input_value() and BB_PASS:
            password.fill(BB_PASS)
        if user.input_value() and password.input_value():
            page.locator('#entry-login').click(timeout=5000)
            try:
                page.wait_for_url('**/ultra/**', timeout=30000)
            except Exception:
                pass
    return not needs_login(page)

def scan_courses(page, courses):
    from bb_watch import BASE
    results = []
    for course in courses:
        failure = None
        for attempt in range(2):
            try:
                page.goto(f"{BASE}/ultra/courses/{course['id']}/grades", wait_until='domcontentloaded', timeout=45000)
                if needs_login(page):
                    failure = {'course': course, 'status': 'LOGIN_REQUIRED'}
                    break
                page.wait_for_function("""() => document.querySelector('table tbody tr td, [role="gridcell"]') || /no (items|grades|results)|Kick back and relax|instructor.{0,20}assigned work yet|لا توجد (عناصر|تقديرات|درجات)/i.test(document.body.innerText)""", timeout=20000)
                page.wait_for_timeout(750)
                if needs_login(page):
                    failure = {'course': course, 'status': 'LOGIN_REQUIRED'}
                    break
                payload = page.evaluate(EXTRACT_ROWS)
                rows = parse_rows(course, payload)
                if not rows and not payload['empty']:
                    raise ValueError('Grade table was not verified')
                results.append({'course': course, 'status': 'OK', 'items': rows})
                failure = None
                break
            except Exception:
                if needs_login(page):
                    failure = {'course': course, 'status': 'LOGIN_REQUIRED'}
                    break
                failure = {'course': course, 'status': 'ERROR', 'message': 'لم يكتمل استخراج التقديرات؛ ستبقى البيانات السابقة.'}
                if attempt == 0:
                    page.wait_for_timeout(1000)
        if failure:
            results.append(failure)
    return results

def run_sync():
    from bb_watch import COURSES, ensure_chrome_debug, CDP_URL
    courses = [dict(id=cid, name=name, code=code) for cid, name, code, _ in COURSES]
    with sync_lock('grades'):
        previous = load_snapshot()
        try:
            ensure_chrome_debug()
            from playwright.sync_api import sync_playwright
            with sync_playwright() as playwright:
                browser = playwright.chromium.connect_over_cdp(CDP_URL, timeout=20000)
                if not browser.contexts:
                    raise RuntimeError('No browser context')
                page = browser.contexts[0].new_page()
                try:
                    if ensure_login(page):
                        results = scan_courses(page, courses)
                    else:
                        results = [{'course': c, 'status': 'LOGIN_REQUIRED'} for c in courses]
                finally:
                    page.close()
        except Exception:
            results = [{'course': c, 'status': 'ERROR'} for c in courses]
        updated = merge_results(previous, results, timestamp())
        atomic_json(SNAPSHOT, updated)
        lines = []
        for change in updated['changes']:
            label = 'درجة جديدة' if change['kind'] == 'new' else 'تعديل تقدير'
            value = change['new'] or 'أُلغي التقدير / لم يُرصد'
            lines.append(f"{label}: {change['course']} — {change['item']}: {value}")
        updated['report'] = '\n'.join(lines)
        atomic_json(REPORT, {'status': updated['status'], 'message': updated['message'],
                            'lastAttemptAt': updated['lastAttemptAt'], 'changes': updated['changes'], 'report': updated['report']})
        # Existing OpenClaw notification job reads this compatibility report.
        # It is ignored by git and never added by the publisher.
        atomic_json(HERE / 'bb_grades_report.json', {'status': updated['status'], 'report': updated['report'],
                    'message': updated['message'], 'scanned_at': updated['lastAttemptAt'],
                    'new': [x for x in updated['changes'] if x['kind'] == 'new'],
                    'changed': [x for x in updated['changes'] if x['kind'] == 'changed']})
        return updated

def public_grades(snapshot):
    """User explicitly approved displaying grades on the published dashboard."""
    fields = ('id','courseId','course','code','item','due','status','grade','score','maximum','pct','checkedAt')
    return {key: snapshot.get(key) for key in ('status','message','lastAttemptAt','lastSuccessAt','courses','changes')} | {
        'items': [{key: item.get(key) for key in fields} for item in snapshot.get('items', [])],
        'source': 'Blackboard Ultra'}

def main():
    parser = argparse.ArgumentParser(description='Read-only Blackboard grade review; saved privately on this device.')
    parser.add_argument('--update-dashboard', action='store_true', help='Also export approved grade fields to the published dashboard.')
    parser.add_argument('--no-push', action='store_true', help='Update local files without pushing to GitHub.')
    args = parser.parse_args()
    try:
        result = run_sync()
    except RuntimeError as error:
        print(json.dumps({'status': 'BUSY', 'message': str(error)}, ensure_ascii=False))
        return 3
    if args.update_dashboard:
        from bb_watch import read_datajs, write_datajs, git_push
        with sync_lock('dashboard'):
            data = read_datajs()
            data['grades'] = public_grades(result)
            write_datajs(data)
            if not args.no_push:
                git_push('sync Blackboard grade review')
    print(json.dumps({'status': result['status'], 'message': result['message'],
                      'items': len(result['items']), 'changes': len(result['changes'])}, ensure_ascii=False))
    return 0 if result['status'] == 'OK' else 2

if __name__ == '__main__':
    raise SystemExit(main())
