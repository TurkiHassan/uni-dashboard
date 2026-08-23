from playwright.sync_api import sync_playwright
INIT = "try{sessionStorage.setItem('ok','1')}catch(err){}"
reqs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={'width':1280,'height':900})
    pg.on('response', lambda r: reqs.append((r.url.split('/')[-1], r.status)) if 'woff2' in r.url else None)
    pg.add_init_script(INIT)
    pg.goto('https://turkihassan.github.io/uni-dashboard/')
    pg.wait_for_timeout(6000)
    loaded = pg.evaluate("""async () => { await document.fonts.ready;
        const out=[]; document.fonts.forEach(f=>f.status==='loaded'&&out.push(f.family)); return out; }""")
    print('REQS:', reqs[:6])
    print('LOADED:', loaded[:6])
    pg.screenshot(path=r'C:\Users\ASUS\.openclaw\workspace\uni_dashboard_qa_live.png', full_page=True)
    b.close()
