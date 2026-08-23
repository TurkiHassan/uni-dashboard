from playwright.sync_api import sync_playwright
errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={'width':1280,'height':900})
    pg.on('console', lambda m: errors.append(m.type + ': ' + m.text) if m.type in ('error','warning') else None)
    pg.on('pageerror', lambda e: errors.append('pageerror: ' + str(e)))
    reqs = []
    pg.on('response', lambda r: reqs.append((r.url.split('/')[-1], r.status)) if r.url.endswith(('.js','.css')) else None)
    pg.goto('https://turkihassan.github.io/uni-dashboard/')
    pg.wait_for_timeout(3000)
    # enter password
    try:
        pg.fill('#pw', 'tabuk1448')
        pg.click('button')
        pg.wait_for_timeout(2500)
        visible = pg.evaluate("()=>{const a=document.getElementById('app');return {hidden:a.hidden, courses:document.getElementById('courses').children.length}}")
        print('APP:', visible)
    except Exception as ex:
        print('EXC:', ex)
    print('REQS:', reqs)
    print('ERRORS:', errors[:6])
    b.close()
