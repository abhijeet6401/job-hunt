"""Bounded ATS browser runner. Unsupported forms stop for manual completion.

Preparation never submits. Submission requires a prepared browser session and a
separate explicit submit call. No CAPTCHA bypass or inferred consent answers.
"""
import asyncio
import os
import re
import time
import uuid
from urllib.parse import urlsplit
from services import workspace_store as store

SESSIONS = {}
PREPARATION_LOCK = asyncio.Lock()
ALLOWED = {'jobs.lever.co', 'boards.greenhouse.io', 'job-boards.greenhouse.io'}

def validate_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in ALLOWED or parsed.username or parsed.password or parsed.port:
        raise ValueError('Automatic applications currently support HTTPS Lever and Greenhouse job links only. Other portals must be completed manually.')
    if len(parsed.path.strip('/').split('/')) < 2:
        raise ValueError('Use a direct job posting, not a company jobs directory.')
    return parsed

async def cleanup():
    for key, session in list(SESSIONS.items()):
        if time.time() - session['created'] > 600:
            await session['browser'].close()
            await session['playwright'].stop()
            SESSIONS.pop(key, None)
            item = store.get('agent', key)
            if item and item.get('status') == 'Ready to submit':
                store.put('agent', {**item, 'status': 'Expired', 'message': 'Browser session expired. Prepare again.'}, key)

async def prepare(url, profile, resume_id, company, role):
    validate_url(url)
    if os.getenv('ENABLE_APPLICATION_AGENT', '').lower() != 'true':
        raise ValueError('Application agent is disabled. Enable it in the server environment after installing Chromium.')
    await cleanup()
    if len(SESSIONS) >= 3:
        raise ValueError('Three applications are already prepared. Submit or cancel one first.')
    path, _ = store.artifact_path(resume_id)
    if path.suffix != '.pdf':
        raise ValueError('Choose a generated PDF resume.')
    if not all(profile.get(k) for k in ('name', 'email', 'phone')):
        raise ValueError('Save your full name, email, and phone in Profile first.')
    from playwright.async_api import async_playwright
    playwright = await async_playwright().start()
    browser = None
    try:
        browser = await playwright.chromium.launch(headless=True, args=['--disable-dev-shm-usage'])
        context = await browser.new_context(accept_downloads=False)
        async def allow_request(route):
            parsed = urlsplit(route.request.url)
            # Navigation stays on known ATS domains; no internal-network requests.
            host = parsed.hostname or ''
            if parsed.scheme not in ('https', 'data', 'blob') or host in ('localhost', '127.0.0.1','169.254.169.254') or re.match(r'^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)', host):
                return await route.abort()
            if route.request.is_navigation_request() and host not in ALLOWED:
                return await route.abort()
            await route.continue_()
        await context.route('**/*', allow_request)
        page = await context.new_page()
        page.set_default_timeout(8000)
        await page.goto(url, wait_until='domcontentloaded', timeout=45000)
        apply = page.get_by_role('link', name=re.compile(r'^Apply for this job$|^Apply now$', re.I))
        if await apply.count():
            await apply.first.click()
        names = profile['name'].split(' ', 1)
        mappings = [(r'^Full name|^Name$', profile['name']), (r'^First name', names[0]), (r'^Last name', names[-1]),
                    (r'^Email', profile['email']), (r'^Phone', profile['phone']), (r'LinkedIn', profile.get('linkedin','')), (r'Portfolio|Website', profile.get('website',''))]
        filled = []
        for label, value in mappings:
            if not value:
                continue
            field = page.get_by_label(re.compile(label, re.I))
            if await field.count() == 1:
                try:
                    await field.fill(value)
                    filled.append(label)
                except Exception:
                    pass
        if 'jobs.lever.co' in url:
            for selector, value in [('input[name="name"]',profile['name']),('input[name="email"]',profile['email']),('input[name="phone"]',profile['phone'])]:
                field = page.locator(selector)
                if await field.count() == 1:
                    await field.fill(value)
                    filled.append(selector)
        uploads = page.locator('input[type=file]')
        if not await uploads.count():
            raise ValueError('No supported resume upload was found. Complete this portal manually.')
        await uploads.first.set_input_files(str(path))
        required = await page.locator('input[required]:not([type=hidden]):not([type=file]),select[required],textarea[required],[aria-required=true]').evaluate_all("els=>els.filter(e=>e.offsetParent!==null && ((e.type==='checkbox'||e.type==='radio')?!e.checked:!e.value)).map(e=>({label:e.labels?.[0]?.innerText||e.getAttribute('aria-label')||e.name||e.id,type:e.type||e.tagName})).slice(0,30)")
        challenges = await page.locator('iframe[src*="recaptcha"],iframe[src*="hcaptcha"],iframe[src*="turnstile"],input[type=password]').count()
        # Unknown custom questions are never answered from guesses.
        custom = await page.locator('textarea').evaluate_all("els=>els.filter(e=>e.offsetParent!==null && !e.value).map(e=>e.labels?.[0]?.innerText||e.name||'Unanswered text question')")
        missing = [x['label'] for x in required] + custom
        if challenges:
            missing.append('This portal requires a CAPTCHA or login; complete it manually.')
        screenshot = store.artifact(await page.screenshot(full_page=True), '.png', 'Application preview')
        key = uuid.uuid4().hex
        item = store.put('agent', {'url':url,'company':company,'role':role,'resume_id':resume_id,'filled':filled,'missing':missing,'screenshot':screenshot,
                                'status':'Needs manual completion' if missing else 'Ready to submit', 'message':'Review the filled form screenshot before submitting.'}, key)
        if missing:
            await browser.close()
            await playwright.stop()
        else:
            SESSIONS[key] = {'page':page,'browser':browser,'playwright':playwright,'created':time.time(),'lock':asyncio.Lock()}
        return item
    except Exception:
        if browser:
            await browser.close()
        await playwright.stop()
        raise

async def submit(key):
    await cleanup()
    item = store.get('agent', key)
    session = SESSIONS.get(key)
    if not item or not session:
        raise ValueError('Prepared browser session is unavailable or expired. Prepare this application again.')
    async with session['lock']:
        if item.get('status') != 'Ready to submit':
            raise ValueError('This application is not ready to submit.')
        store.put('agent', {**item, 'status':'Submitting'}, key)
        try:
            page = session['page']
            button = page.get_by_role('button', name=re.compile(r'^Submit application$|^Submit Application$|^Apply$', re.I))
            if await button.count() != 1:
                raise ValueError('A unique submit button was not found. Complete the application manually.')
            # Exactly one click. Never retry a submission with uncertain outcome.
            await button.click(timeout=15000)
            success = page.get_by_text(re.compile(r'Thank you for applying|application (has been|was) (received|submitted)|successfully submitted', re.I))
            confirmed = False
            try:
                await success.first.wait_for(state='visible', timeout=15000)
                confirmed = True
            except Exception:
                pass
            screenshot = store.artifact(await page.screenshot(full_page=True), '.png', 'Application result')
            return store.put('agent', {**item,'status':'Submitted' if confirmed else 'Unconfirmed','screenshot':screenshot,
                            'message':'Portal confirmed receipt.' if confirmed else 'Submission was attempted, but receipt could not be confirmed. Check the portal before trying again.'},key)
        except Exception:
            store.put('agent',{**item,'status':'Unconfirmed','message':'Submission outcome is uncertain. Check the portal before retrying.'},key)
            raise
        finally:
            SESSIONS.pop(key,None)
            await session['browser'].close()
            await session['playwright'].stop()

async def cancel(key):
    session = SESSIONS.pop(key,None)
    if session:
        await session['browser'].close()
        await session['playwright'].stop()
    item = store.get('agent',key)
    if item and item.get('status') not in ('Submitted','Unconfirmed'):
        store.put('agent',{**item,'status':'Cancelled'},key)
