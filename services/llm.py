"""One compatibility client for existing Groq calls and xAI Responses API."""
import os
from types import SimpleNamespace
import httpx

def provider():
    selected=os.getenv('LLM_PROVIDER', 'xai' if os.getenv('XAI_API_KEY') else 'groq').lower()
    if selected not in ('xai','groq'):
        raise RuntimeError('LLM_PROVIDER must be xai or groq.')
    return selected

def configuration():
    selected = provider()
    return {'provider': selected, 'configured': bool(os.getenv('XAI_API_KEY' if selected == 'xai' else 'GROQ_API_KEY')),
            'model': os.getenv('XAI_MODEL', 'grok-4.7') if selected == 'xai' else os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')}

class LLMClient:
    def __init__(self, api_key='', **kwargs):
        self.selected = provider()
        self.key = os.getenv('XAI_API_KEY', '') if self.selected == 'xai' else (api_key or os.getenv('GROQ_API_KEY', ''))
        if not self.key:
            raise RuntimeError(f'{self.selected.upper()} API key is not configured. Open Connections for setup status.')
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        config = configuration()
        if self.selected == 'groq':
            from groq import Groq
            return Groq(api_key=self.key, timeout=90, max_retries=1).chat.completions.create(**{**kwargs, 'model': config['model']})
        messages = kwargs.get('messages', [])
        system = '\n'.join(m['content'] for m in messages if m['role'] == 'system')
        inputs = [m for m in messages if m['role'] != 'system']
        payload = {'model': config['model'], 'input': inputs, 'store': False,
                   'max_output_tokens': max(512, kwargs.get('max_tokens', 2000))}
        if system:
            payload['instructions'] = system
        if kwargs.get('response_format', {}).get('type') == 'json_object':
            payload['instructions'] = (payload.get('instructions', '') + '\nReturn only a valid JSON object, without Markdown fences.').strip()
        try:
            response = httpx.post('https://api.x.ai/v1/responses', headers={'Authorization': f'Bearer {self.key}'}, json=payload, timeout=120)
            if response.status_code >= 400:
                raise RuntimeError(f'xAI request failed ({response.status_code}). Check model access, API credits, and the server key.')
            data = response.json()
            text = '\n'.join(c.get('text', '') for o in data.get('output', []) for c in o.get('content', []) if c.get('type') == 'output_text')
            if not text:
                raise RuntimeError('xAI returned no text. Please retry or choose another XAI_MODEL.')
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])
        except httpx.HTTPError as exc:
            raise RuntimeError('Could not reach xAI. Please retry.') from exc
