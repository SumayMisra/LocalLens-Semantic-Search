"""Opt-in integration: the real model through the Flask request handlers."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import io
import json
import time
import psutil
from app import create_app

app = create_app()
client = app.test_client()
headers = {'X-LocalLens': '1'}
assert client.post('/api/model/load', json={}, headers=headers).status_code == 202
start = time.monotonic()
while client.get('/api/model').json['state'] == 'loading':
    if time.monotonic() - start > 600:
        raise RuntimeError('Model load timed out.')
    time.sleep(0.25)
assert client.get('/api/model').json['state'] == 'ready', client.get('/api/model').json
result = client.post('/api/search', json={'query': 'How can someone in a wheelchair get inside the workspace?'}, headers=headers)
assert result.status_code == 200, result.json
assert result.json['semantic'][0]['id'] == 'studio-access'
imports = client.post('/api/import', data={'files': (io.BytesIO(b'Our lunar observatory opens at midnight for telescope demonstrations.'), 'observatory.md')}, headers=headers).json['passages']
result = client.post('/api/search', json={'query': 'lunar observatory', 'imports': imports}, headers=headers)
assert result.status_code == 200
assert result.json['semantic'][0]['imported']
assert result.json['keyword'][0]['imported']
cleared = client.post('/api/search', json={'query': 'observatory', 'imports': []}, headers=headers)
assert not any(p['imported'] for p in cleared.json['semantic'])
assert cleared.json['keyword'] == []
# Regression: unrelated questions must not be padded with sample matches.
for query in ('How do I reset my password?', 'Who won the football match yesterday?'):
    response = client.post('/api/search', json={'query': query, 'scope': 'samples'}, headers=headers)
    assert response.status_code == 200
    assert response.json['semantic'] == [] and response.json['keyword'] == []
shirt = client.post('/api/search', json={'query': 'Can somebody help stitch up my ripped shirt?', 'scope': 'samples'}, headers=headers)
assert [p['id'] for p in shirt.json['semantic']] == ['repair-cloth']
assert shirt.json['keyword'] == []
# Collection isolation: a query matching samples must not retrieve them in imports.
for mode in ('semantic', 'keyword'):
    personal = client.post('/api/search', json={'query': 'flat tire', 'imports': imports, 'scope': 'imports', 'mode': mode}, headers=headers)
    assert personal.json[mode] == []
    samples = client.post('/api/search', json={'query': 'flat tire', 'imports': imports, 'scope': 'samples', 'mode': mode}, headers=headers)
    assert samples.json[mode][0]['id'] == 'bike-flat'
# Library controls: selected passages must stay aligned with cached vectors.
subset = client.post('/api/search', json={'query': 'flat tire', 'scope': 'library', 'sample_ids': ['bike-flat'], 'imports': []}, headers=headers)
assert subset.status_code == 200 and subset.json['semantic'][0]['id'] == 'bike-flat'
excluded = client.post('/api/search', json={'query': 'flat tire', 'scope': 'library', 'sample_ids': ['repair-cloth'], 'imports': []}, headers=headers)
assert excluded.status_code == 200 and excluded.json['semantic'] == []
mixed = client.post('/api/search', json={'query': 'lunar observatory', 'scope': 'library', 'sample_ids': ['bike-flat'], 'imports': imports}, headers=headers)
assert mixed.status_code == 200 and mixed.json['semantic'][0]['imported']
empty = client.post('/api/search', json={'query': 'flat tire', 'scope': 'library', 'sample_ids': [], 'imports': []}, headers=headers)
assert empty.status_code == 400
print(json.dumps({'verified': ['real CPU model load', 'sample semantic ranking', 'text-file import', 'personal semantic and keyword ranking', 'empty-import reset', 'no-answer regressions', 'shirt-only match', 'collection isolation', 'selected library vector alignment', 'excluded sample absence', 'mixed library', 'empty library rejection'], 'rss_mib_after_search': round(psutil.Process().memory_info().rss / 1024**2, 1)}, indent=2))
