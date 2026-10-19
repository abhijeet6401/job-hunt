"""Local browser QA with explicitly synthetic jobs; never calls external APIs."""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[1]
out=root/'test-results';out.mkdir(exist_ok=True)
env={**os.environ,'PASSWORD':'local-ui-test-password','JOBHUNT_DATA_DIR':str(out/'storage'),'COOKIE_SECURE':'false','PUBLIC_ORIGIN':'http://127.0.0.1:8123','RENDER':'false'}
server=subprocess.Popen([sys.executable,'-m','uvicorn','main:app','--host','127.0.0.1','--port','8123'],cwd=root,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
jobs=[{'company':'Example Labs','role':'Associate Product Manager','location':'Bengaluru','source':'LinkedIn','url':'https://example.com/jobs/pm','summary':'Work with product, design, and data to improve customer onboarding.','match_score':88,'status':'Shortlisted','salary':'Not mentioned'},
      {'company':'Sample Analytics','role':'Business Analyst','location':'Remote','source':'Y Combinator','url':'https://example.com/jobs/analyst','summary':'Turn operational data into clear recommendations and experiments.','match_score':83,'status':'Saved','is_yc':True},
      {'company':'Demo Ventures','role':'Strategy Associate','location':'Mumbai','source':'Wellfound','url':'https://example.com/jobs/strategy','summary':'Support founders on market research, growth, and unit economics.','match_score':75,'status':'Interviewing','follow_up':'2026-11-01'}]
fixture={'ok':True,'jobs':jobs,'social_posts':[],'packages':[],'agent':[],'activity':[{'message':'Synthetic QA application pack prepared.','updated_at':'2026-10-19T08:00:00Z'}],'profile':{},'connections':{'provider':'xai','configured':False,'model':'grok-4.7','search':False,'sheets':False,'pdf':'ReportLab fallback','agent':False,'persistent_disk':False}}
errors=[]
try:
    for attempt in range(40):
        try:
            urllib.request.urlopen('http://127.0.0.1:8123/health',timeout=1);break
        except Exception:
            time.sleep(.25)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.route('**/api/workspace',lambda route:route.fulfill(json=fixture))
        page.goto('http://127.0.0.1:8123/')
        page.locator('#password').fill('local-ui-test-password');page.locator('#login button').click()
        page.locator('#app').wait_for(state='visible')
        page.locator('#stats strong').first.wait_for()
        page.screenshot(path=str(out/'overview-desktop.png'),full_page=True)
        page.locator('.nav[data-page=discover]').click()
        assert page.locator('.job-card').count()==3
        page.locator('#job-query').fill('analytics')
        assert page.locator('.job-card').count()==1
        page.locator('#job-query').fill('')
        page.locator('.job-card').first.click()
        assert page.locator('#detail').is_visible()
        page.locator('[data-action=tailor-selected]').click()
        assert page.locator('#company').input_value()=='Example Labs'
        assert page.locator('#jd').input_value()==''
        page.screenshot(path=str(out/'studio-desktop.png'),full_page=True)
        page.locator('.nav[data-page=pipeline]').click()
        assert page.locator('.column').count()==6
        page.screenshot(path=str(out/'pipeline-desktop.png'),full_page=True)
        for view in ('agent','profile','connections','overview'):
            page.locator('.nav[data-page='+view+']').click()
            assert page.locator('#'+view).is_visible()
        page.set_viewport_size({'width':390,'height':844})
        page.locator('#toasts').evaluate('(el)=>el.innerHTML=""')
        page.screenshot(path=str(out/'overview-mobile.png'),full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Mobile page overflows'
        page.locator('.nav[data-page=discover]').click()
        page.screenshot(path=str(out/'discover-mobile.png'),full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Mobile discovery overflows'
        assert not errors,errors
        browser.close()
    print(json.dumps({'browser_checks':'passed','synthetic_jobs':len(jobs),'javascript_errors':errors,'screenshots':str(out)}))
finally:
    server.terminate()
    try:server.wait(timeout=10)
    except subprocess.TimeoutExpired:server.kill()
