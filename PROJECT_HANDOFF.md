# LocalLens handoff for ChatGPT

## Current project

**LocalLens — Semantic Document Search** is now primarily Python. The user chose Python so they can understand and explain the code in interviews. This is an internship portfolio build, not a weekend learning exercise.

Location: the standalone `Desktop/Projects/LocalLens` folder, outside Vizuara, with its own Git repository. The previous React/Transformers.js files are preserved in ignored `.legacy-browser/`; do not teach that implementation as the current app. No Node.js or npm is needed now.

## Start and explain

From the project: create/activate `.venv`, install `requirements.txt`, then `python app.py`. Open http://127.0.0.1:5000. Use `PORT=5055 python app.py` if port 5000 is busy. The implementation was verified using Python 3.14.6 on macOS arm64.

Teach in this order:

1. `data/samples.json` and `queries.json`: original passages, stable IDs and manual relevance labels.
2. `search.py`: word-token overlap, chunking, vector dot products/cosine, top-three ranking and Recall@3.
3. `engine.py`: SentenceTransformer, normalized embeddings, background model loading and progress, CPU inference, public sample cache, one inference at a time.
4. `app.py`: Flask routes, request/response JSON, validation, file parsing in memory, no shared personal-document session.
5. `templates/index.html` and `static/`: HTML/CSS interface, small JS controller for requests, polling, safe result rendering, abort and clear. All search logic is Python.
6. `evaluate.py` and tests: distinguish real-model evidence from fast tests that inject a fake model engine.
7. Deployment: Gunicorn and optional Docker; server hosting differs from a static website.

## Privacy change — essential

Local operation processes documents on the user's computer. A public hosted instance receives documents and queries on its server. Never call the Python app browser-only or claim hosted documents stay on the visitor's device.

The browser holds imports in tab memory between requests. The server uses request-local inputs and imported embeddings; it does not save or log them, share them between visitors, or keep a document database. Only public model files and sample embeddings are cached. Clear removes tab references and aborts/ignores pending browser responses; an already-running Python request finishes before its temporary text is released. No secure-erasure claim. Host infrastructure may have separate logs. Offline operation is unverified.

## Evidence

- 37 fast tests passed in the final project directory; Python compilation, JS syntax, dependency compatibility, and Gunicorn configuration passed.
- The final app also passed a real HTTP smoke test under Gunicorn: page, health, keyword, model loading, semantic search, paste import, imported ranking, and empty-import reset.
- Revised real-model evaluation: semantic Recall@3 12/12, BM25 keyword 6/12. Exact-term: both 6/6; paraphrase: semantic 6/6, keyword 0/6. Original labels unchanged. Old results preserved in `docs/evaluation-before-fix.json`.
- Semantic returned 15 passages, 12 labeled relevant (80% precision among returned). Keyword returned 10, six labeled relevant (60%). Recall alone must not be described as overall accuracy.
- Eight added no-answer checks: semantic abstained on 7/8, keyword on 6/8. Library membership cost still produces a borrowing-policy result without the requested fact; disclose this limitation.
- JSON report has full rankings, versions, immutable model revision, corpus/query hashes. This is a small developer-authored evaluation; no benchmark generalization.
- Real-model Flask integration passed for sample search, synthetic file import, imported-text retrieval, and searching with imports cleared.
- One measured process RSS after integration was 528.2 MiB on this Mac; not a peak or Linux capacity guarantee.
- The updated page loaded in Chrome and accessible controls/text were inspected. Interactive commands subsequently timed out or were interrupted. Full browser interaction, visual/mobile, screen-reader and screenshot QA remain unverified.
- Docker daemon unavailable; image build unverified. No live URL or deployment.

## Publication

README, MIT license, pinned runtime dependencies, tested-environment freeze, GitHub Actions, Gunicorn config, Dockerfile and experimental Render free-plan configuration are prepared. Render memory suitability is unverified; do not automatically purchase an upgrade. Current Hugging Face docs say Docker Spaces require a paid plan to create, so do not promise free HF Docker hosting.

Only original fictional corpus and synthetic tests were used. Ignore `.legacy-browser/`, `.cache/`, `.venv/`, imported/personal files and secrets. No GitHub destination or host was supplied. Ask for those when publishing is requested; never claim a deployment without a verified live URL. The README includes the factual résumé bullet.

## Search-quality fixes

The user found irrelevant results confusing. The prior implementation always returned three semantic passages and matched common words in keyword search. These were genuine product flaws even though a narrow Recall@3 evaluation passed.

Current keyword method: BM25, k1=1.5/b=0.75, fixed English stop-word list, with matched-word explanations. Current semantic method: omit cosine scores below 0.35; return zero to three results. This heuristic is not a calibrated relevance test and cannot reliably recognize missing facts on a related topic. Do not promise that all remaining results answer the question.

The UI now has one Library with per-document checkboxes and Delete buttons, sample titles marked (Sample), and a Restore sample documents button. Importing disables samples and enables new imports; users can check any combination. The UI sends scope=library plus selected sample IDs and enabled imported passages. The engine subsets cached sample vectors in corpus order. Clear removes imports but preserves sample choices. Deleting only removes tab-memory documents, never disk files. Refresh restores samples. Keyword results are removed from the interface; retain BM25 for the honest offline evaluation. Privacy and benchmark are adjacent collapsible panels. The logo is circular; the unused model slogan is removed. Green/white styling includes terracotta, blue, and amber accents.

Real HTTP regressions in `docs/search-regressions.json` verify the shirt, password and football queries plus a synthetic remote-working handbook example and collection isolation. Explain real-world value as finding original passages in a supplied collection, never web search or generated answers.

## Current revision checks

Real CPU integration covers selected-sample vector alignment, excluded sample absence, mixed sample/import libraries, and empty library rejection. Browser automation for this redesign returned only browser chrome and a blank screenshot; visual and interactive QA are not verified. No GitHub operations or deployment were requested or performed.
