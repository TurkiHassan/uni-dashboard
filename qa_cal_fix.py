# -*- coding: utf-8 -*-
"""Headless QA for the uni dashboard (local server, no CDP needed)."""
import threading, functools, http.server, socketserver, os
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 8904

Handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=HERE)


class Server(socketserver.TCPServer):
    allow_reuse_address = True


httpd = Server(("127.0.0.1", PORT), Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1280, 'height': 1600})
    errs = []
    pg.on('pageerror', lambda e: errs.append('PAGEERROR: %s' % e))
    pg.goto('http://127.0.0.1:%d/index.html' % PORT, timeout=60000)
    pg.wait_for_timeout(1200)
    try:
        pg.fill('#pw', 'tabuk1448', timeout=8000)
        pg.click('button.enter', timeout=8000)
        pg.wait_for_timeout(3000)
    except Exception as e:
        print('gate fill/click:', e)
    for sel in ['#semWeek', '#semLeft', '#semPct', '#semEnd']:
        print(sel, '=', pg.eval_on_selector_all(sel, 'els=>els.map(e=>e.textContent)'))
    print('events counts =', pg.eval_on_selector_all('#events', 'els=>els.map(e=>e.children.length)'))
    for e in errs[:10]:
        print(e)
    ev = pg.locator('#events').first
    if ev.is_visible():
        ev.scroll_into_view_if_needed()
        pg.wait_for_timeout(900)
        pg.screenshot(path=os.path.join(HERE, 'qa_cal_fix_events.png'))
    pg.evaluate("window.scrollTo(0,0)")
    pg.wait_for_timeout(600)
    pg.screenshot(path=os.path.join(HERE, 'qa_cal_fix_top.png'))
    b.close()

httpd.shutdown()
print('shot ok')
