"""One lazily loaded CPU model; no user-document cache or shared user state."""
import os
import threading
from pathlib import Path
from search import MODEL_ID, MODEL_REVISION, SAMPLES, semantic_search, select_samples

# Only public model assets are cached. User inputs are never written here.
os.environ.setdefault('HF_HOME', str(Path(__file__).resolve().parent / '.cache/huggingface'))
os.environ.setdefault('HF_HUB_DISABLE_TELEMETRY', '1')
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')


class ModelEngine:
    def __init__(self):
        self._state_lock = threading.Lock()
        self._inference_lock = threading.Lock()
        self._status = dict(state='idle', message='Model loads on your first semantic search.', progress=None)
        self.model = None
        self.sample_embeddings = None

    def status(self):
        with self._state_lock:
            return self._status.copy()

    def _set(self, **values):
        with self._state_lock:
            self._status.update(values)

    def start(self):
        with self._state_lock:
            if self._status['state'] in ('loading', 'ready'):
                return
            self._status = dict(state='loading', message='Starting Python model libraries…', progress=None)
        threading.Thread(target=self._load, name='model-loader', daemon=True).start()

    def _load(self):
        try:
            import torch
            from huggingface_hub import snapshot_download
            from sentence_transformers import SentenceTransformer
            from tqdm.auto import tqdm

            torch.set_num_threads(2)
            owner = self

            class FileProgress(tqdm):
                """Label both file-count and byte progress from Hugging Face accurately."""
                def update(self, n=1):
                    result = super().update(n)
                    if self.total:
                        unit = 'bytes' if self.unit == 'B' or self.total > 1000 else 'files'
                        owner._set(message=f'Model download: {self.n:,.0f} / {self.total:,.0f} {unit}',
                                   progress=min(100, round(100 * self.n / self.total)))
                    return result

            self._set(message='Downloading model files (first run needs internet)…', progress=None)
            model_path = snapshot_download(
                MODEL_ID, revision=MODEL_REVISION,
                allow_patterns=['*.json', '*.txt', '*.safetensors'],
                ignore_patterns=['onnx/*', 'openvino/*'],
                tqdm_class=FileProgress,
            )
            self._set(message='Loading model into CPU memory…', progress=None)
            model = SentenceTransformer(model_path, device='cpu', local_files_only=True, trust_remote_code=False)
            self._set(message='Indexing the 18 sample passages…', progress=None)
            vectors = model.encode([p['text'] for p in SAMPLES], normalize_embeddings=True,
                                   show_progress_bar=False, batch_size=16)
            self.model, self.sample_embeddings = model, vectors
            self._set(state='ready', message='Model ready · Python / CPU', progress=100)
        except Exception:
            # Do not expose filesystem paths, tokens, or provider details to visitors.
            self._set(state='error', message='Model could not load. Check internet access, available memory, and the model cache. Please try loading it again.', progress=None)

    def search(self, query, imports, scope=None, sample_ids=None):
        scope = scope or ('imports' if imports else 'samples')
        if scope not in ('samples', 'imports', 'library'):
            raise ValueError('Unknown document collection.')
        if scope == 'imports' and not imports:
            raise ValueError('Import a document before searching your text.')
        samples = select_samples(sample_ids) if scope != 'imports' else []
        corpus = samples + imports if scope == 'library' else (samples if scope == 'samples' else imports)
        if not corpus:
            raise ValueError('Enable at least one document in the Library.')
        if self.status()['state'] != 'ready':
            raise RuntimeError('Model is not ready.')
        # Do not accumulate a queue of requests retaining personal documents.
        if not self._inference_lock.acquire(blocking=False):
            raise BlockingIOError('Another search is running. Please retry in a moment.')
        try:
            import numpy as np
            indices = [i for i, p in enumerate(SAMPLES) if p['id'] in {s['id'] for s in samples}]
            vectors = self.sample_embeddings[indices]
            if scope in ('imports', 'library') and imports:
                personal = self.model.encode([p['text'] for p in imports], normalize_embeddings=True,
                                             show_progress_bar=False, batch_size=16)
                vectors = np.concatenate([vectors, personal]) if len(vectors) else personal
            query_vector = self.model.encode(query, normalize_embeddings=True, show_progress_bar=False)
            return semantic_search(query_vector, corpus, vectors)
        finally:
            self._inference_lock.release()
