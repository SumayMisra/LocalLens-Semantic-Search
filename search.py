"""Pure retrieval functions, shared by Flask, tests, and evaluation."""
import json
import math
from collections import Counter
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SAMPLES = json.loads((ROOT / 'data/samples.json').read_text())
QUERIES = json.loads((ROOT / 'data/queries.json').read_text())
MODEL_ID = 'sentence-transformers/all-MiniLM-L6-v2'
MODEL_REVISION = '1110a243fdf4706b3f48f1d95db1a4f5529b4d41'
MAX_IMPORT_BYTES = 100_000
MAX_PASSAGES = 100


# Fixed display cutoff, not a calibrated probability or proof of relevance.
# Selected as a conservative demo heuristic, not optimized on the evaluation set.
MIN_SEMANTIC_SCORE = 0.35
# Common function/conversation words; keep negation (no/not/never) meaningful.
STOP_WORDS = frozenset("""a an the and or but if then than as at by for from in into
of on onto to with about above below between through during before after
is are was were be been being am do does did have has had having will would
can could should may might must shall i me my mine we us our ours you your yours
he him his she her hers it its they them their theirs this that these those
who whom whose what which when where why how any anyone anybody someone somebody
something anything each every all both some such other another up down out over
under again here there also just very really please help tell show find give get
want need know looking look like much many more most few own so too only""".split())


def token_list(text):
    return re.findall(r'[^\W_]+', text.lower(), flags=re.UNICODE)


def tokens(text):
    return set(token_list(text))


def keyword_search(query, passages):
    """BM25 exact-word baseline; ignore common words and explain actual matches."""
    terms = tokens(query) - STOP_WORDS
    if not terms or not passages:
        return []
    documents = [Counter(t for t in token_list(p['text']) if t not in STOP_WORDS) for p in passages]
    lengths = [sum(doc.values()) for doc in documents]
    average = sum(lengths) / len(lengths) or 1
    frequency = {term: sum(term in doc for doc in documents) for term in terms}
    scored = []
    for passage, doc, length in zip(passages, documents, lengths):
        matched = sorted(terms & doc.keys())
        if not matched:
            continue
        score = 0.0
        for term in matched:
            inverse_frequency = math.log(1 + (len(documents) - frequency[term] + 0.5) / (frequency[term] + 0.5))
            count = doc[term]
            score += inverse_frequency * (count * 2.5) / (count + 1.5 * (0.25 + 0.75 * length / average))
        scored.append(dict(passage, score=score, matched_terms=matched))
    return sorted(scored, key=lambda p: (-p['score'], p['id']))[:3]


def semantic_search(query_vector, passages, embeddings):
    # Normalized vectors: dot product = cosine similarity. Do not pad to three.
    scores = embeddings @ query_vector
    return sorted((dict(p, score=float(score)) for p, score in zip(passages, scores)
                   if float(score) >= MIN_SEMANTIC_SCORE),
                  key=lambda p: (-p['score'], p['id']))[:3]


def recall_at_3(results, relevant):
    found = {p['id'] for p in results[:3]}
    return len(found & set(relevant)) / len(set(relevant))


def chunk_text(text, title, prefix):
    """Preserve original wording, splitting paragraphs into <=600-character slices."""
    chunks = []
    for paragraph in re.split(r'\r?\n\s*\r?\n', text.strip()):
        rest = paragraph.strip()
        while rest:
            end = min(len(rest), 600)
            if end < len(rest):
                space = rest.rfind(' ', 0, end + 1)
                if space > 300:
                    end = space
            chunks.append(dict(id=f'{prefix}-{len(chunks)}', document_id=prefix, title=title,
                               heading=f'Passage {len(chunks) + 1}',
                               text=rest[:end], imported=True))
            rest = rest[end:].lstrip()
    return chunks


def validate_text(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Provide non-empty text.')
    if '\x00' in text:
        raise ValueError('Binary data is not supported. Use UTF-8 plain text.')
    return text


def validate_imports(items):
    """Treat browser-provided passage objects as untrusted, bounded input."""
    if not isinstance(items, list) or len(items) > MAX_PASSAGES:
        raise ValueError('Limit: 100 imported passages.')
    clean = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError('Invalid imported passage.')
        text = validate_text(item.get('text'))
        title = item.get('title', 'Imported document')
        if len(text) > 600 or not isinstance(title, str) or not 1 <= len(title) <= 160:
            raise ValueError('Invalid passage length or source title.')
        clean.append(dict(id=f'import-{i}', text=text, title=title,
                          heading=f'Passage {i + 1}', imported=True))
    if sum(len(p['text'].encode('utf-8')) for p in clean) > MAX_IMPORT_BYTES:
        raise ValueError('Limit: 100 KB of imported text total.')
    return clean


def select_samples(ids=None):
    """Validate request-local sample selection; never mutate bundled documents."""
    if ids is None:
        return SAMPLES
    if not isinstance(ids, list) or len(ids) > len(SAMPLES) or any(not isinstance(i, str) for i in ids):
        raise ValueError('Invalid library selection.')
    selected = set(ids)
    if not selected <= {p['id'] for p in SAMPLES}:
        raise ValueError('Unknown library passage.')
    return [p for p in SAMPLES if p['id'] in selected]
