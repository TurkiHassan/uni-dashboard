from playwright.sync_api import sync_playwright
INIT = "try{sessionStorage.setItem('ok','1')}catch(err){}"
with sync_playwright() as p:
    b = p.chromium.launch()
    # light
    pg = b.new_page(viewport={'width':1280,'height':900})
    pg.add_init_script(INIT)
    pg.goto('file:///C:/Users/ASUS/.openclaw/workspace/uni_dashboard/index.html')
    pg.wait_for_timeout(2600)
    pg.screenshot(path=r'C:\Users\ASUS\.openclaw\workspace\uni_dashboard_qa_v2_light.png', full_page=True)
    # dark
    pg.evaluate("()=>{localStorage.setItem('uni-theme','dark');location.reload()}")
    pg.wait_for_timeout(2600)
    pg.screenshot(path=r'C:\Users\ASUS\.openclaw\workspace\uni_dashboard_qa_v2_dark.png', full_page=True)
    # mobile
    m = b.new_page(viewport={'width':390,'height':844})
    m.add_init_script(INIT)
    m.goto('file:///C:/Users/ASUS/.openclaw/workspace/uni_dashboard/index.html')
    m.wait_for_timeout(2600)
    m.screenshot(path=r'C:\Users\ASUS\.openclaw\workspace\uni_dashboard_qa_v2_mobile.png', full_page=True)
    b.close()
print('V2 SHOTS OK')
