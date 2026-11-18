"""Fast tests require no model download; real-model checks live in scripts/smoke_model.py."""
import io
import numpy as np
import pytest
from app import create_app
from engine import ModelEngine
from search import SAMPLES, QUERIES, chunk_text, keyword_search, semantic_search, recall_at_3

HEADERS = {'X-LocalLens': '1'}


class FakeEngine:
    def __init__(self):
        self.seen = []
        self.state = 'ready'
    def start(self):
        self.state = 'ready'
    def status(self):
        return dict(state=self.state, message='test model', progress=100)
    def search(self, query, imports, scope=None, sample_ids=None):
        self.seen = imports
        from search import select_samples
        selected = select_samples(sample_ids)
        corpus = selected + imports if scope == 'library' else (imports if scope == 'imports' else selected)
        return [dict(corpus[0], score=0.9)] if corpus else []


@pytest.fixture
def client():
    app = create_app(FakeEngine())
    app.config['TESTING'] = True
    return app.test_client()


def test_page_and_headers(client):
    page = client.get('/')
    assert page.status_code == 200
    assert 'LocalLens — Semantic Document Search'.encode() in page.data
    assert b'hosted site' in page.data
    assert page.headers['Cache-Control'] == 'no-store'
    assert "script-src 'self'" in page.headers['Content-Security-Policy']
    assert client.get('/static/app.js').status_code == 200
    assert client.get('/health').json == {'status': 'ok'}


def test_dataset_is_frozen_and_judgments_valid():
    assert len(SAMPLES) == 18 and len(QUERIES) == 12
    assert len({p['id'] for p in SAMPLES}) == 18
    assert [q['kind'] for q in QUERIES].count('exact') == 6
    for q in QUERIES:
        assert set(q['relevant']) <= {p['id'] for p in SAMPLES}


def test_rankings_and_recall():
    passages = [dict(id='b', text='cat cat dog'), dict(id='a', text='CAT'), dict(id='c', text='catalog')]
    result = keyword_search('cat CAT', passages)
    assert [p['id'] for p in result] == ['a', 'b']
    assert result[0]['score'] > 0
    assert result[0]['matched_terms'] == ['cat']
    assert keyword_search('!!!', passages) == []
    assert keyword_search('café', [dict(id='x', text='CAFÉ')])[0]['matched_terms'] == ['café']
    semantic = semantic_search(np.array([1, 0]), passages, np.array([[1, 0], [1, 0], [0, 1]]))
    assert [p['id'] for p in semantic] == ['a', 'b']
    assert recall_at_3(semantic, ['a', 'missing']) == 0.5
    assert recall_at_3([{'id': str(i)} for i in range(4)], ['3']) == 0


def test_chunking_preserves_text():
    original = 'Original punctuation! ' * 90
    chunks = chunk_text(original, 'Title', 'test')
    assert all(len(p['text']) <= 600 and p['text'] in original for p in chunks)
    assert ' '.join(p['text'] for p in chunks) == original.strip()
    assert chunk_text(' \n\n ', 'T', 'x') == []


def test_import_and_search_isolation(client):
    response = client.post('/api/import', json={'text': 'A unique marmalade protocol.'}, headers=HEADERS)
    assert response.status_code == 200
    passages = response.json['passages']
    result = client.post('/api/search', json={'query': 'marmalade', 'imports': passages}, headers=HEADERS)
    assert result.status_code == 200
    assert result.json['semantic'][0]['imported']
    assert result.json['keyword'][0]['text'] == 'A unique marmalade protocol.'
    # Clearing the browser's list means the next request has no imported content.
    fresh = client.post('/api/search', json={'query': 'marmalade', 'imports': []}, headers=HEADERS)
    assert fresh.json['keyword'] == []
    assert not fresh.json['semantic'][0]['imported']
    other = client.application.test_client()
    assert other.post('/api/search', json={'query': 'marmalade', 'mode': 'keyword'}, headers=HEADERS).json['keyword'] == []


def test_files_and_safe_text(client):
    result = client.post('/api/import', data={'files': (io.BytesIO(b'<script>alert(1)</script>'), '../../notes.md')}, headers=HEADERS)
    assert result.status_code == 200
    assert result.json['passages'][0]['title'] == 'notes.md'
    assert result.json['passages'][0]['text'] == '<script>alert(1)</script>'
    # JS renderer uses textContent, not HTML interpolation.
    assert b'innerHTML' not in client.get('/static/app.js').data


@pytest.mark.parametrize('name,content', [('x.pdf', b'text'), ('x.txt', b'\xff'), ('x.md', b'\0'), ('x.txt', b''), ('x.txt', b'a'*100001)])
def test_bad_files(client, name, content):
    assert client.post('/api/import', data={'files': (io.BytesIO(content), name)}, headers=HEADERS).status_code == 400


@pytest.mark.parametrize('body', [{}, [], {'query': ''}, {'query': 'a'*401}, {'query': 'ok', 'imports': [None]}, {'query': 'ok', 'mode': 'chat'}, {'query': 'ok', 'imports': [{'text':'x'*601}]}])
def test_invalid_search(client, body):
    assert client.post('/api/search', json=body, headers=HEADERS).status_code == 400


def test_limits_and_request_guard(client):
    assert client.post('/api/import', json={'text': 'a'*20001}, headers=HEADERS).status_code == 400
    assert client.post('/api/import', data='x'*200001, headers=HEADERS).status_code == 413
    assert client.post('/api/model/load', json={}).status_code == 403
    assert client.post('/api/model/load', json={}, headers={**HEADERS, 'Sec-Fetch-Site': 'cross-site'}).status_code == 403
    assert client.post('/api/model/load', json={}, headers=HEADERS).status_code == 202


def test_keyword_available_without_model():
    app = create_app(ModelEngine())
    client = app.test_client()
    assert client.post('/api/search', json={'query': 'flat tire', 'mode': 'keyword'}, headers=HEADERS).json['keyword'][0]['id'] == 'bike-flat'
    assert client.post('/api/search', json={'query': 'flat tire'}, headers=HEADERS).status_code == 503


def test_busy_and_error_responses(client, monkeypatch):
    def fail(*args, **kwargs):
        raise BlockingIOError('Please retry.')
    engine = client.application.extensions['model_engine']
    monkeypatch.setattr(engine, 'search', fail)
    assert client.post('/api/search', json={'query': 'hello'}, headers=HEADERS).status_code == 429
    def fail_private(*args, **kwargs):
        raise Exception('SECRET INTERNAL PATH')
    monkeypatch.setattr(engine, 'search', fail_private)
    response = client.post('/api/search', json={'query': 'hello'}, headers=HEADERS)
    assert response.status_code == 503
    assert b'SECRET' not in response.data


def test_stop_words_do_not_produce_random_results():
    assert keyword_search('the can up do somebody help', SAMPLES) == []
    assert keyword_search('How do I reset my password?', SAMPLES) == []
    assert keyword_search('Can somebody help stitch up my ripped shirt?', SAMPLES) == []


def test_semantic_cutoff_does_not_pad_results():
    passages = [dict(id='match'), dict(id='weak'), dict(id='unrelated')]
    result = semantic_search(np.array([1., 0.]), passages, np.array([[0.8, 0.6], [0.2, 0.98], [0., 1.]]))
    assert [p['id'] for p in result] == ['match']
    assert semantic_search(np.array([0., -1.]), passages, np.array([[0.8, 0.6], [0.2, 0.98], [0., 1.]])) == []


def test_import_scope_excludes_samples(client):
    imports = [dict(text='The nebula observatory opens at midnight.', title='Observatory')]
    for scope in ('imports', None):
        body = dict(query='flat tire', imports=imports)
        if scope: body['scope'] = scope
        response = client.post('/api/search', json=body, headers=HEADERS)
        assert response.status_code == 200
        assert response.json['scope'] == 'imports'
        assert response.json['keyword'] == []
        assert all(p['imported'] for p in response.json['semantic'])
    response = client.post('/api/search', json=dict(query='nebula', imports=imports, scope='samples'), headers=HEADERS)
    assert response.json['keyword'] == []
    assert all(not p['imported'] for p in response.json['semantic'])
    assert response.json['passage_count'] == 18


def test_empty_and_invalid_scope_are_rejected(client):
    for scope in ('imports', 'all', 'internet'):
        response = client.post('/api/search', json=dict(query='hello', scope=scope), headers=HEADERS)
        assert response.status_code == 400


def test_library_selection_excludes_disabled_and_deleted_samples(client):
    response = client.post('/api/search', json=dict(query='flat tire', scope='library', sample_ids=['garden-water']), headers=HEADERS)
    assert response.status_code == 200
    assert response.json['passage_count'] == 1
    assert response.json['keyword'] == []
    assert response.json['semantic'][0]['id'] == 'garden-water'
    # The change is request-local, not a mutation affecting other visitors.
    fresh = client.post('/api/search', json=dict(query='flat tire'), headers=HEADERS)
    assert fresh.json['passage_count'] == 18
    assert fresh.json['keyword'][0]['id'] == 'bike-flat'


def test_library_combines_only_explicit_selections(client):
    items = [dict(text='A nebula observatory opens at midnight.', title='Observatory')]
    response = client.post('/api/search', json=dict(query='nebula', scope='library', sample_ids=['garden-water'], imports=items), headers=HEADERS)
    assert response.status_code == 200 and response.json['passage_count'] == 2
    assert response.json['keyword'][0]['imported']
    response = client.post('/api/search', json=dict(query='nebula', scope='library', sample_ids=[], imports=items), headers=HEADERS)
    assert response.json['semantic'][0]['imported']
    assert response.json['passage_count'] == 1


def test_empty_library_does_not_fall_back_to_samples(client):
    response = client.post('/api/search', json=dict(query='hello', scope='library', sample_ids=[], imports=[]), headers=HEADERS)
    assert response.status_code == 400
    assert 'Enable at least one' in response.json['error']


@pytest.mark.parametrize('selection', [['unknown'], 'bike-flat', [None], ['bike-flat'] * 19])
def test_invalid_sample_selection(client, selection):
    assert client.post('/api/search', json=dict(query='hello', scope='library', sample_ids=selection), headers=HEADERS).status_code == 400


def test_duplicate_filenames_have_separate_document_ids(client):
    response = client.post('/api/import', data={'files': [(io.BytesIO(b'First original text.'), 'notes.txt'), (io.BytesIO(b'Second original text.'), 'notes.txt')]}, headers=HEADERS)
    passages = response.json['passages']
    assert passages[0]['document_id'] != passages[1]['document_id']
    assert passages[0]['title'] == passages[1]['title'] == 'notes.txt'


def test_page_focuses_on_semantic_search_and_collapsible_information(client):
    page = client.get('/').data.decode()
    assert 'keyword-results' not in page and 'Compare searches' not in page
    assert 'Small model. Meaningful matches.' not in page
    assert '<details id="privacy"' in page
    assert 'id="document-list"' in page and 'id="library-data"' in page
    assert 'Your text. Clear boundaries.' in page


def test_private_project_files_are_not_served(client):
    for path in ('/.env', '/.git/config', '/engine.py', '/private/notes.txt', '/static/../app.py'):
        assert client.get(path).status_code == 404


def test_cross_origin_requests_are_not_enabled(client):
    response = client.options('/api/import', headers={'Origin': 'https://example.invalid', 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'X-LocalLens'})
    assert 'Access-Control-Allow-Origin' not in response.headers


def test_gunicorn_defaults_to_loopback(monkeypatch):
    import runpy
    from pathlib import Path
    monkeypatch.delenv('BIND_HOST', raising=False)
    monkeypatch.setenv('PORT', '5000')
    config = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'gunicorn.conf.py'))
    assert config['bind'] == '127.0.0.1:5000'
