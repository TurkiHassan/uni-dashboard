# -*- coding: utf-8 -*-
import json, sys, time
from playwright.sync_api import sync_playwright

OUT = {}

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222')
    ctx = browser.contexts[0]
    page = None
    for pg in ctx.pages:
        if 'lms.ut.edu.sa' in pg.url:
            page = pg
            break
    if not page:
        page = ctx.new_page()
        page.goto('https://lms.ut.edu.sa/ultra/stream', timeout=60000)
    page.wait_for_timeout(5000)

    if 'login' in page.url or 'sso' in page.url.lower():
        print(json.dumps({'status': 'LOGIN_REQUIRED'}))
        sys.exit(0)

    # go to courses page
    try:
        page.click("text=المقررات الدراسية", timeout=15000)
    except Exception:
        try:
            page.goto('https://lms.ut.edu.sa/ultra/course', timeout=60000)
        except Exception as e:
            pass
    page.wait_for_timeout(8000)
    OUT['url'] = page.url

    # check login again after nav
    content = page.content()
    if ('login' in page.url and 'ultra' not in page.url) or 'Sign in' == page.title().strip():
        print(json.dumps({'status': 'LOGIN_REQUIRED'}))
        sys.exit(0)

    # extract course cards text
    cards = []
    els = page.query_selector_all('div[id^="course_"], li.course, .courses-course-card')
    for e in els[:30]:
        cards.append(e.inner_text()[:400])
    OUT['cards_count'] = len(cards)
    OUT['cards'] = cards

    # Blackboard exposes course calendar events through a per-course API.
    # Read it explicitly instead of assuming that the general calendar feed
    # contains the weekly meeting timetable.  An empty result is valid: many
    # institutions keep the actual timetable in the academic portal.
    course_ids = page.locator("button[id^='more-info-']").evaluate_all(
        "els => els.map(e => e.id.replace(/^more-info-/, '')).filter(Boolean)"
    )
    OUT['week'] = []
    OUT['schedule_status'] = 'EMPTY'
    try:
        schedule_rows = page.evaluate("""
        async (ids) => {
          const out = [];
          for (const id of ids) {
            const r = await fetch(`/learn/api/v1/courses/${id}/schedule?limit=100`);
            if (!r.ok) continue;
            const body = await r.json();
            for (const event of (body.results || [])) {
              out.push({courseId: id, event});
            }
          }
          return out;
        }
        """, course_ids)
        OUT['schedule_events'] = schedule_rows
        if schedule_rows:
            OUT['schedule_status'] = 'FOUND'
            # Keep the dashboard's compact week contract while retaining the
            # raw events for the publisher to normalize dates/times safely.
            OUT['week'] = schedule_rows
    except Exception as exc:
        OUT['schedule_status'] = 'ERROR'
        OUT['schedule_error'] = str(exc)

    # fallback: grab main region text
    try:
        OUT['page_text'] = page.inner_text('main')[:6000]
    except Exception:
        OUT['page_text'] = page.inner_text('body')[:6000]

print(json.dumps(OUT, ensure_ascii=False))
