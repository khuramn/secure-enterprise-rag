import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'app/ingestion/src'))
from app.backend.auth import Settings, TokenValidator, Forbidden
from app.backend.main import app
from identity import VerifiedIdentity

TENANT, API, CLIENT, GROUP, USER = [f'00000000-0000-4000-8000-{n:012d}' for n in range(1, 6)]
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def validator():
    v = TokenValidator(Settings(TENANT, API, 'Query.Read', frozenset([CLIENT]), {GROUP: ('employees',)}))
    v.keys = Mock()
    v.keys.get_signing_key_from_jwt.return_value = SimpleNamespace(key=KEY.public_key())
    return v


def token(**changes):
    now = int(time.time())
    claims = dict(iss=f'https://login.microsoftonline.com/{TENANT}/v2.0', aud=API,
                  tid=TENANT, oid=USER, sub=USER, ver='2.0', azp=CLIENT,
                  iat=now, nbf=now, exp=now+300, scp='Query.Read', groups=[GROUP])
    for k, v in changes.items():
        if v is None:
            claims.pop(k, None)
        else:
            claims[k] = v
    return jwt.encode(claims, KEY, algorithm='RS256', headers={'kid': 'test'})


def test_verified_mapping(validator):
    assert validator.validate(token()) == VerifiedIdentity(TENANT, USER, ('employees',))
    assert validator.keys.get_signing_key_from_jwt.called


@pytest.mark.parametrize('changes', [
    {'exp': 1}, {'exp': None}, {'nbf': int(time.time())+1000}, {'aud': CLIENT},
    {'iss': 'https://attacker.invalid'}, {'tid': CLIENT}, {'ver': '1.0'},
    {'oid': 'alice'}, {'scp': None}, {'scp': 'Other'}, {'scp': ['Query.Read']},
    {'groups': None}, {'groups': []}, {'groups': 'employees'}, {'groups': ['employees']},
    {'groups': [CLIENT]}, {'groups': [None]}, {'hasgroups': True},
    {'_claim_names': {'groups': 'src1'}}, {'_claim_sources': {}},
    {'azp': API}, {'idtyp': 'app'}, {'sub': None},
])
def test_rejected_claims(validator, changes):
    with pytest.raises((jwt.PyJWTError, Forbidden)):
        validator.validate(token(**changes))


def test_bad_signature_and_algorithm(validator):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    claims = jwt.decode(token(), options={'verify_signature': False})
    for bad in [jwt.encode(claims, other, algorithm='RS256', headers={'kid': 'test'}),
                jwt.encode(claims, 'x'*32, algorithm='HS256', headers={'kid': 'test'}), 'invalid']:
        with pytest.raises(jwt.PyJWTError):
            validator.validate(bad)


def test_key_failure(validator):
    validator.keys.get_signing_key_from_jwt.side_effect = jwt.PyJWKClientConnectionError('private failure')
    with pytest.raises(jwt.PyJWTError):
        validator.validate(token())


@pytest.fixture
def client(validator):
    app.state.validator = validator
    return TestClient(app, raise_server_exceptions=False)


def test_api_auth_and_validation(client, monkeypatch):
    import rag_pipeline
    pipeline = Mock(return_value='Safe answer')
    monkeypatch.setattr(rag_pipeline, 'answer_question', pipeline)
    assert client.get('/health').json() == {'status': 'ok'}
    assert client.post('/query', json={'question': 'secret'}).status_code == 401
    headers = {'Authorization': f'Bearer {token()}'}
    response = client.post('/query', headers=headers, json={'question': 'secret', 'username': 'alice'})
    assert response.status_code == 422
    assert 'secret' not in response.text
    pipeline.assert_not_called()
    response = client.post('/query', headers=headers, json={'question': 'question'})
    assert response.status_code == 200
    assert set(response.json()) == {'answer', 'request_id'}
    assert isinstance(pipeline.call_args.args[0], VerifiedIdentity)
    assert client.post('/query', headers={'Authorization': f'Bearer {token(groups=None)}'}, json={'question': 'q'}).status_code == 403
    pipeline.side_effect = RuntimeError('SECRET prompt and Azure details')
    response = client.post('/query', headers=headers, json={'question': 'q'})
    assert response.status_code == 503
    assert 'SECRET' not in response.text


def test_retrieval_acl_defense():
    from hybrid_search import retrieve
    client = Mock()
    client.search.return_value = [{'document_id': 'FIN-001', 'allowed_groups': ['finance-team']}]
    with pytest.raises(PermissionError):
        retrieve(client, ['employees'], 'q', 'keyword')


@pytest.mark.parametrize('finish,content,expected', [
    ('content_filter', 'secret', 'filtering policy'),
    ('length', 'partial answer', 'sufficient information'),
    ('stop', '', None), ('stop', 'Safe [HR-001]', 'Safe [HR-001]'),
])
def test_model_safety(monkeypatch, finish, content, expected):
    import rag_pipeline as p
    monkeypatch.setattr(p, 'hybrid_search', lambda *a: [{'document_id': 'HR-001', 'title': 'HR', 'content': 'untrusted'}])
    monkeypatch.setattr(p, 'audit_event', Mock())
    model = Mock()
    model.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish, message=SimpleNamespace(content=content))])
    monkeypatch.setattr(p, 'get_chat_client', lambda: model)
    if expected is None:
        with pytest.raises(RuntimeError):
            p.answer_question(VerifiedIdentity(TENANT, USER, ('employees',)), 'question')
    else:
        assert expected in p.answer_question(VerifiedIdentity(TENANT, USER, ('employees',)), 'question')


def test_no_documents_skips_model(monkeypatch):
    import rag_pipeline as p
    monkeypatch.setattr(p, 'hybrid_search', lambda *a: [])
    model = Mock()
    monkeypatch.setattr(p, 'get_chat_client', model)
    assert p.answer_question('bob', 'q') == p.INSUFFICIENT_INFORMATION
    model.assert_not_called()


def test_content_filter_exception_and_audit(monkeypatch):
    import rag_pipeline as p
    import httpx
    from openai import BadRequestError
    monkeypatch.setattr(p, 'hybrid_search', lambda *a: [{'document_id': 'HR-001', 'title': 'HR', 'content': 'PRIVATE DOCUMENT'}])
    audit = Mock()
    monkeypatch.setattr(p, 'audit_event', audit)
    model = Mock()
    model.chat.completions.create.side_effect = BadRequestError('PRIVATE PROMPT', response=httpx.Response(400, request=httpx.Request('POST', 'https://example.invalid')), body={'code': 'content_filter'})
    monkeypatch.setattr(p, 'get_chat_client', lambda: model)
    assert p.answer_question(VerifiedIdentity(TENANT, USER, ('employees',)), 'PRIVATE QUESTION') == p.CONTENT_FILTER_MESSAGE
    assert audit.call_args.args[2] == f'{TENANT}:{USER}'
    assert 'PRIVATE' not in str(audit.call_args_list)


def test_jwks_selection_and_rotation():
    import json
    settings = Settings(TENANT, API, 'Query.Read', frozenset([CLIENT]), {GROUP: ('employees',)})
    v = TokenValidator(settings)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(KEY.public_key()))
    jwk.update(kid='test', use='sig', alg='RS256')
    v.keys.fetch_data = Mock(side_effect=[{'keys': [dict(jwk, kid='old')]}, {'keys': [jwk]}])
    assert v.validate(token()).acl_labels == ('employees',)
    assert v.keys.fetch_data.call_count == 2


def test_missing_choices(monkeypatch):
    import rag_pipeline as p
    monkeypatch.setattr(p, 'hybrid_search', lambda *a: [{'document_id': 'HR-001', 'title': 'HR', 'content': 'data'}])
    model = Mock()
    model.chat.completions.create.return_value = SimpleNamespace(choices=[])
    monkeypatch.setattr(p, 'get_chat_client', lambda: model)
    with pytest.raises(RuntimeError):
        p.answer_question('bob', 'q')
