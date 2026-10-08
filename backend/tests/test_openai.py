from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from app.assistant.service import Assistant


@pytest.mark.parametrize('case', ['success', 'offline', 'incomplete', 'empty', 'no_key', 'no_evidence'])
def test_openai_evidence_and_fallback(monkeypatch, case):
    repo = Mock()
    repo.retrieve.return_value = [] if case == 'no_evidence' else [dict(
        id='ref', kind='runbook', verified=True, score=.8,
        title='Database', content='Check connections', source='manual')]
    result = Mock()
    result.json.return_value = {
        'status': 'incomplete' if case == 'incomplete' else 'completed',
        'output': [] if case == 'empty' else [dict(type='message', content=[
            dict(type='output_text', text='Check connections [1].')])],
    }
    post = Mock(return_value=result)
    if case == 'offline':
        post.side_effect = httpx.ConnectError('offline')
    monkeypatch.setattr(httpx.Client, 'post', post)
    settings = SimpleNamespace(openai_model='test-model', openai_api_key='' if case == 'no_key' else 'test-key', ollama_model='')
    response = Assistant(repo, settings).answer('Database error')
    if case == 'success':
        assert response['mode'] == 'rag_openai'
        assert response['generated']
        assert '[1]' in response['answer']
        assert post.call_args.kwargs['json']['store'] is False
        assert 'numbered_evidence' in post.call_args.kwargs['json']['input']
    else:
        assert not response['generated']
        assert response['mode'] == 'evidence_only'
    if case in ('no_key', 'no_evidence'):
        post.assert_not_called()
