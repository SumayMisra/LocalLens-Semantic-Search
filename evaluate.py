"""Run the unchanged 12-query evaluation with the real Python CPU model."""
import hashlib
import importlib.metadata
import json
import platform
import time
from pathlib import Path
from engine import ModelEngine
from search import MODEL_ID, MODEL_REVISION, QUERIES, SAMPLES, keyword_search, recall_at_3, MIN_SEMANTIC_SCORE


def main():
    engine = ModelEngine()
    engine.start()
    previous = ''
    deadline = time.monotonic() + 600
    while engine.status()['state'] not in ('ready', 'error'):
        state = engine.status()
        if state['message'] != previous:
            print(state['message'], flush=True)
            previous = state['message']
        if time.monotonic() > deadline:
            raise RuntimeError('Model initialization timed out.')
        time.sleep(0.25)
    if engine.status()['state'] == 'error':
        raise RuntimeError(engine.status()['message'])
    rows = []
    for q in QUERIES:
        semantic = engine.search(q['text'], [])
        keyword = keyword_search(q['text'], SAMPLES)
        rows.append(dict(**q, semantic=[p['id'] for p in semantic], keyword=[p['id'] for p in keyword],
                         semantic_recall=recall_at_3(semantic, q['relevant']),
                         keyword_recall=recall_at_3(keyword, q['relevant']),
                         semantic_scores=[p['score'] for p in semantic], keyword_scores=[p['score'] for p in keyword]))
    groups = {}
    for group in ('exact', 'paraphrase', 'all'):
        subset = [r for r in rows if group == 'all' or r['kind'] == group]
        groups[group] = dict(queries=len(subset), semantic_recall=sum(r['semantic_recall'] for r in subset)/len(subset),
                             keyword_recall=sum(r['keyword_recall'] for r in subset)/len(subset))
    # Additional questions are recorded separately; do not change original judgments.
    negatives = json.loads((Path(__file__).parent / 'data/no-answer-queries.json').read_text())
    negative_rows = []
    for q in negatives:
        semantic, keyword = engine.search(q['text'], []), keyword_search(q['text'], SAMPLES)
        negative_rows.append(dict(**q, semantic=[dict(id=p['id'], score=p['score']) for p in semantic],
                                  keyword=[dict(id=p['id'], score=p['score']) for p in keyword],
                                  semantic_abstained=not semantic, keyword_abstained=not keyword))
    quality = {}
    for method in ('semantic', 'keyword'):
        returned = sum(len(r[method]) for r in rows)
        labeled_relevant = sum(len(set(r[method]) & set(r['relevant'])) for r in rows)
        quality[method] = dict(returned=returned, labeled_relevant=labeled_relevant,
                               precision_among_returned=labeled_relevant/returned if returned else 0,
                               rank_1_hits=sum(bool(r[method]) and r[method][0] in r['relevant'] for r in rows),
                               no_answer_abstentions=sum(r[method + '_abstained'] for r in negative_rows),
                               no_answer_queries=len(negative_rows))
    result = dict(model=MODEL_ID, revision=MODEL_REVISION, backend='Sentence Transformers / PyTorch CPU float32',
                  python=platform.python_version(), platform=platform.system(), architecture=platform.machine(),
                  versions={name: importlib.metadata.version(name) for name in ('sentence-transformers', 'torch', 'transformers', 'numpy')},
                  corpus_sha256=hashlib.sha256(json.dumps(SAMPLES, sort_keys=True).encode()).hexdigest(),
                  queries_sha256=hashlib.sha256(json.dumps(QUERIES, sort_keys=True).encode()).hexdigest(),
                  passages=len(SAMPLES), semantic_cutoff=MIN_SEMANTIC_SCORE, keyword_method='BM25 with fixed English stop words',
                  groups=groups, quality=quality, rows=rows, no_answer_rows=negative_rows)
    target = Path(__file__).parent / 'docs/evaluation-results.json'
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(groups=groups,quality=quality,no_answer_rows=negative_rows), indent=2))
    print(f'Wrote {target.name}')


if __name__ == '__main__':
    main()
