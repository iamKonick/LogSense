from types import SimpleNamespace
from unittest.mock import Mock
from dataclasses import replace
import pytest
from app.api import main
from app.domain.models import Question

@pytest.mark.parametrize('provider', ['openai', 'ollama', 'evidence'])
def test_request_provider_does_not_mutate_server_configuration(monkeypatch, provider):
    defaults = replace(main.settings, openai_model='server-model', openai_api_key='server-key', ollama_model='local-model')
    monkeypatch.setattr(main, 'settings', defaults)
    factory = Mock()
    factory.return_value.answer.return_value = {'generated': False}
    monkeypatch.setattr(main, 'Assistant', factory)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(repo=Mock(), assistant=Mock())))
    main.assistant(Question(question='Investigate failure', provider=provider, model='chosen-model'), request, 'request-key')
    selected = factory.call_args.args[1]
    assert selected.openai_model == ('chosen-model' if provider == 'openai' else '')
    assert selected.ollama_model == ('chosen-model' if provider == 'ollama' else '')
    if provider == 'openai': assert selected.openai_api_key == 'request-key'
    assert main.settings.openai_api_key == 'server-key'
    assert main.settings.openai_model == 'server-model'
