"""Offline integration tests: no live searches, AI charges, or applications."""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch
from unittest.mock import AsyncMock
import asyncio
import pytest
from fastapi.testclient import TestClient
os.environ.setdefault('PASSWORD','workspace-test-password')
import main
from services import workspace_store as store
from services.application_agent import validate_url

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('JOBHUNT_DATA_DIR',str(tmp_path))
    monkeypatch.setenv('PASSWORD','workspace-test-password')
    for key in ('GOOGLE_SERVICE_ACCOUNT_JSON','XAI_API_KEY','GROQ_API_KEY','TAVILY_API_KEY'):
        monkeypatch.delenv(key,raising=False)
    from services import sheets
    monkeypatch.setattr(sheets,'LOCAL_DB_FILE',str(tmp_path/'sheets.json'))
    sheets._save_local_db({tab:[headers] for tab,headers in sheets.TAB_HEADERS.items()})
    main.app.state.login_attempts={}
    with TestClient(main.app) as c:
        yield c

def login(client):
    assert client.post('/auth/login',data={'password':'workspace-test-password'}).status_code==200

def test_private_routes_require_login(client):
    for path in ['/api/workspace','/api/jobs','/api/placements/analytics','/api/placements/students','/data/placed_students.json']:
        assert client.get(path).status_code==401

def test_login_cookie_is_random_signed_and_timed(client):
    login(client);token=client.cookies.get('jh_session')
    assert token!=main._hash_password('workspace-test-password')
    assert main._is_authenticated(token)
    assert not main._is_authenticated(token+'changed')
    with patch('main.time.time',return_value=time.time()+main.SESSION_DURATION_SECONDS+1):
        assert not main._is_authenticated(token)
    login(client);assert client.cookies.get('jh_session')!=token

def test_missing_password_fails_closed(client,monkeypatch):
    monkeypatch.delenv('PASSWORD')
    assert client.post('/auth/login',data={'password':'kgp2026'}).status_code==503

def test_login_throttles_failures(client):
    for _ in range(10):
        assert client.post('/auth/login',data={'password':'wrong'}).status_code==401
    assert client.post('/auth/login',data={'password':'wrong'}).status_code==429

def test_home_renders_new_workspace(client):
    assert 'Your next chapter' in client.get('/').text
    login(client);assert '/static/workspace.js' in client.get('/').text

def test_cross_origin_write_rejected(client):
    login(client);assert client.post('/api/profile',json={'name':'Me'},headers={'Origin':'https://evil.test'}).status_code==403

def test_workspace_no_secrets_and_profile_persists(client):
    login(client)
    response=client.get('/api/workspace');assert response.status_code==200
    assert response.json()['connections']['configured'] is False
    assert 'workspace-test-password' not in response.text
    data={'name':'Test User','email':'test@example.com','phone':'1234567890'}
    assert client.post('/api/profile',json=data).status_code==200
    assert client.get('/api/workspace').json()['profile']['name']=='Test User'
    assert client.post('/api/profile',json={'email':'invalid'}).status_code==400

def test_storage_roundtrip_and_atomic_updates(client):
    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(lambda n:store.put('activity',{'message':str(n)}),range(20)))
    assert len(store.all_records('activity'))==20
    a=store.artifact(b'%PDF-1.4 test','.pdf','Test resume')
    path,item=store.artifact_path(a);assert path.read_bytes()==b'%PDF-1.4 test'
    with pytest.raises(FileNotFoundError):store.artifact_path('../../etc/passwd')

def test_documents_auth_and_inline_preview(client):
    a=store.artifact(b'%PDF-1.4 test','.pdf','Test resume')
    assert client.get('/api/documents/'+a).status_code==401
    login(client)
    assert client.get('/api/documents/'+a).headers['content-disposition'].startswith('inline')
    assert client.get('/api/documents/'+a+'?download=true').headers['content-disposition'].startswith('attachment')
    assert client.get('/api/documents/missing').status_code==404

def test_search_missing_credentials_is_explicit(client):
    login(client);assert client.get('/api/search').status_code==503

def test_multiple_roles_at_one_company_are_kept():
    from services.search import _company_deduplicate
    jobs=[{'company':'Acme','role':'PM','url':'https://example.com/1','match_score':50},{'company':'Acme','role':'Analyst','url':'https://example.com/2','match_score':80}]
    assert len(_company_deduplicate(jobs))==2

@pytest.mark.parametrize('url',['http://jobs.lever.co/company/id','https://evil.test/job','https://jobs.lever.co.evil.test/c/id','https://jobs.lever.co@evil.test/c/id','https://127.0.0.1/a/b'])
def test_agent_rejects_unsupported_targets(url):
    with pytest.raises(ValueError):validate_url(url)

def test_agent_requires_pack_and_confirmation(client):
    login(client)
    assert client.post('/api/agent/prepare',json={'package_id':'missing'}).status_code==404
    assert client.post('/api/agent/nope/submit',json={}).status_code==400

def test_package_validation_and_complete_flow(client,monkeypatch):
    login(client);assert client.post('/api/package',json={'jd':'tiny'}).status_code==400
    from services import tailor,workspace
    monkeypatch.setattr(tailor,'tailor_resume',lambda *a,**k:{'pdf_bytes':b'%PDF-1.4 example','latex':'source','keywords':['SQL'],'diff':[],'role_type':'product'})
    monkeypatch.setattr(tailor,'_load_resume',lambda role:'Verified resume facts.')
    letters={'cover_letter':'A factual letter.','outreach':'A short draft.','fit_notes':['Supported skill','Gap','Emphasis']}
    fake=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw:SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(letters)))]))))
    monkeypatch.setattr(workspace,'LLMClient',lambda **kw:fake)
    response=client.post('/api/package',json={'jd':'A product manager role with analytics and cross-functional execution responsibilities.','company':'Acme','role':'PM'})
    assert response.status_code==200,response.text
    pack=response.json()['package'];assert pack['status']=='Prepared'
    assert len(store.all_records('package'))==1
    assert store.get('package',pack['id'])['cover_letter']==letters['cover_letter']
    assert client.get('/api/documents/'+pack['resume_id']).content.startswith(b'%PDF')

def test_resume_rewrites_reject_changed_numbers():
    from services.tailor import _rewrite_bullets
    original=r'\item Built a platform serving 300 users with SQL.'
    data={'diff':[{'before':'Built a platform serving 300 users with SQL.','after':'Built a platform serving 900 users with SQL.'}]}
    client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw:SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(data)))]))))
    modified,diff=_rewrite_bullets(client,original,['SQL'],'Analyst role')
    assert modified==original
    assert diff[0]['rejected']

def test_resume_bullets_preserve_nested_latex():
    from services.tailor import _resume_bullets
    assert _resume_bullets(r'\achieve{Built a \textbf{SQL} tool for 300 users.}')==[r'Built a \textbf{SQL} tool for 300 users.']

def test_xai_adapter_uses_responses(monkeypatch):
    from services.llm import LLMClient
    monkeypatch.setenv('LLM_PROVIDER','xai');monkeypatch.setenv('XAI_API_KEY','not-a-real-key');monkeypatch.setenv('XAI_MODEL','selected-model')
    def post(url,**kwargs):
        assert url=='https://api.x.ai/v1/responses';assert kwargs['json']['model']=='selected-model';assert kwargs['json']['store'] is False
        return SimpleNamespace(status_code=200,json=lambda:{'output':[{'content':[{'type':'output_text','text':'Hello'}]}]})
    monkeypatch.setattr('services.llm.httpx.post',post)
    assert LLMClient().chat.completions.create(model='groq-model',messages=[{'role':'user','content':'Hi'}]).choices[0].message.content=='Hello'

@pytest.mark.parametrize('confirmed',[True,False])
def test_agent_submits_once_and_never_invents_success(client,confirmed):
    from services import application_agent as agent
    async def scenario():
        key='test-submission'
        item=store.put('agent',{'status':'Ready to submit','company':'Example','role':'PM','url':'https://jobs.lever.co/example/id'},key)
        button=SimpleNamespace(count=AsyncMock(return_value=1),click=AsyncMock())
        success=SimpleNamespace(first=SimpleNamespace(wait_for=AsyncMock(side_effect=None if confirmed else TimeoutError())))
        page=SimpleNamespace(get_by_role=lambda *a,**k:button,get_by_text=lambda *a,**k:success,screenshot=AsyncMock(return_value=b'PNG test'))
        agent.SESSIONS[key]={'page':page,'browser':SimpleNamespace(close=AsyncMock()),'playwright':SimpleNamespace(stop=AsyncMock()),'created':time.time(),'lock':asyncio.Lock()}
        result=await agent.submit(key)
        assert result['status']==('Submitted' if confirmed else 'Unconfirmed')
        assert button.click.await_count==1
        assert key not in agent.SESSIONS
        with pytest.raises(ValueError):await agent.submit(key)
    asyncio.run(scenario())

def test_pipeline_notes_and_csv_export(client):
    login(client)
    from services.sheets import append_row
    append_row('Jobs',['2026-10-19','Unknown','=FORMULA','Analyst','','Remote','Manual','https://example.com/job','','A real job','data_analyst','New','Job Board','80'])
    response=client.post('/api/workspace/job',json={'url':'https://example.com/job','status':'Shortlisted','notes':'Follow up with recruiter','follow_up':'2026-11-01'})
    assert response.status_code==200
    jobs=client.get('/api/workspace').json()['jobs']
    tracked=next(j for j in jobs if j['url']=='https://example.com/job')
    assert tracked['status']=='Shortlisted' and tracked['notes']=='Follow up with recruiter'
    exported=client.get('/api/export').text
    assert "'=FORMULA" in exported and 'Follow up with recruiter' in exported
