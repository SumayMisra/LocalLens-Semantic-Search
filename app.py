"""LocalLens Flask app. Run with `python app.py`; no Node.js required."""
import os
import uuid
from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException
from engine import ModelEngine
from search import SAMPLES, QUERIES, MAX_IMPORT_BYTES, MAX_PASSAGES, chunk_text, keyword_search, validate_imports, validate_text, MIN_SEMANTIC_SCORE, STOP_WORDS, tokens, select_samples


def create_app(engine=None):
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=200_000, MAX_FORM_MEMORY_SIZE=120_000, MAX_FORM_PARTS=12)
    model = engine if engine is not None else ModelEngine()
    app.extensions['model_engine'] = model

    @app.before_request
    def same_origin():
        if request.method == 'POST':
            # JSON's custom header prevents cross-origin simple-form submissions;
            # no CORS is enabled. Never rely on a global shared document session.
            if request.headers.get('X-LocalLens') != '1':
                return jsonify(error='Use the LocalLens page to submit a request.'), 403
            if request.headers.get('Sec-Fetch-Site') == 'cross-site':
                return jsonify(error='Cross-site requests are not allowed.'), 403

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response

    @app.errorhandler(ValueError)
    def invalid(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(HTTPException)
    def http_error(error):
        message = 'Request too large. Limit: 100 KB of text.' if error.code == 413 else error.description
        return jsonify(error=message), error.code

    @app.get('/')
    def index():
        return render_template('index.html', samples=SAMPLES, suggested=[QUERIES[6], QUERIES[2], QUERIES[10]], cutoff=MIN_SEMANTIC_SCORE)

    @app.get('/health')
    def health():
        return jsonify(status='ok')

    @app.get('/api/model')
    def model_status():
        return jsonify(model.status())

    @app.post('/api/model/load')
    def load_model():
        model.start()
        return jsonify(model.status()), 202

    @app.post('/api/import')
    def import_text():
        documents = []
        if request.is_json:
            body = request.get_json()
            if not isinstance(body, dict):
                raise ValueError('Expected a JSON object.')
            text = validate_text(body.get('text'))
            if len(text) > 20_000:
                raise ValueError('Paste up to 20,000 characters.')
            documents.append(('Pasted document', text))
        else:
            files = request.files.getlist('files')
            if not 1 <= len(files) <= 10:
                raise ValueError('Choose between 1 and 10 text files.')
            for file in files:
                name = (file.filename or '').replace('\\', '/').rsplit('/', 1)[-1]
                if not name.lower().endswith(('.txt', '.md')):
                    raise ValueError('Only .txt and .md files are supported.')
                try:
                    text = file.read(MAX_IMPORT_BYTES + 1).decode('utf-8-sig')
                except UnicodeDecodeError as error:
                    raise ValueError('Files must contain UTF-8 plain text.') from error
                documents.append((name[:160], validate_text(text)))
        if sum(len(text.encode('utf-8')) for _, text in documents) > MAX_IMPORT_BYTES:
            raise ValueError('Limit: 100 KB per import.')
        passages = [p for title, text in documents for p in chunk_text(text, title, uuid.uuid4().hex)]
        if len(passages) > MAX_PASSAGES:
            raise ValueError('Limit: 100 imported passages. Try a smaller document.')
        return jsonify(passages=passages)

    @app.post('/api/search')
    def search():
        body = request.get_json()
        if not isinstance(body, dict):
            raise ValueError('Expected a JSON object.')
        query = validate_text(body.get('query')).strip()
        if len(query) > 400:
            raise ValueError('Queries must be 400 characters or fewer.')
        imports = validate_imports(body.get('imports', []))
        scope = body.get('scope', 'imports' if imports else 'samples')
        if scope not in ('samples', 'imports', 'library'):
            raise ValueError('Choose the sample library or your documents.')
        if scope == 'imports' and not imports:
            raise ValueError('Import a document before searching your text.')
        selected = select_samples(body.get('sample_ids'))
        corpus = selected + imports if scope == 'library' else (selected if scope == 'samples' else imports)
        if not corpus:
            raise ValueError('Enable at least one document in the Library.')
        mode = body.get('mode', 'semantic')
        if mode not in ('keyword', 'semantic'):
            raise ValueError('Unknown search mode.')
        result = dict(keyword=keyword_search(query, corpus), scope=scope, passage_count=len(corpus),
                      semantic_cutoff=MIN_SEMANTIC_SCORE, keyword_terms=sorted(tokens(query) - STOP_WORDS))
        if mode == 'semantic':
            try:
                if scope == 'library' or 'sample_ids' in body:
                    result['semantic'] = model.search(query, imports, scope=scope, sample_ids=[p['id'] for p in selected])
                else:
                    result['semantic'] = model.search(query, imports, scope=scope)
            except BlockingIOError as error:
                return jsonify(error=str(error)), 429
            except RuntimeError:
                return jsonify(error='Model is not ready. Load or retry it first.'), 503
            except Exception:
                return jsonify(error='Semantic inference failed. Please retry with a smaller document.'), 503
        return jsonify(result)

    return app


app = create_app()
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', '5000')), debug=False, threaded=True)
