# LocalLens — Semantic Document Search

A Python portfolio project for semantic passage search, with a reproducible keyword comparison in its evaluation. Built with **Flask + Hugging Face Sentence Transformers**, HTML/CSS, and a small JavaScript file for page interactions. No React, Node.js, npm, paid inference API, or database is required.

Try the six bundled original documents without uploading anything. Choose a suggested query and see up to three original passages. The **Library** lists every document, with **(Sample)** beside bundled titles. Check documents to include them in search, uncheck to exclude them, or delete them from the current tab. Restore sample documents with the dedicated button. Import `.txt` / `.md` files or paste text under **Add your own text**; importing switches samples off so your own text is searched first. You can re-enable any samples to search a mixed library. Clear imported data removes all imports. Refresh resets the library; these changes never delete files on your computer.

The main interface uses semantic search only. BM25 remains in the reproducible evaluation and compatibility API, not as a second result column. Privacy and the small benchmark sit together in collapsible panels below the search workspace.

## Start on your Mac

Python **3.14** is the tested version. Download or clone this repository, then from its parent directory run:

```bash
cd LocalLens
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000**. Keep the terminal running; **Ctrl+C** stops the app. On later runs, from the repository’s parent directory:

```bash
cd LocalLens
source .venv/bin/activate
python app.py
```

If port 5000 is occupied (for example by macOS AirPlay Receiver), use `PORT=5055 python app.py` and open http://127.0.0.1:5055. The server binds to your computer's loopback address by default; it is not exposed to your network.

The first install downloads substantial Python dependencies. The first semantic search downloads approximately 92 MB of model assets from Hugging Face and loads the model on **CPU**. No GPU or Hugging Face account/token is required. The page shows loading stages and available download progress. Loading happens on a background thread so the page and status endpoint remain available. Model errors show a retry option; semantic search requires the model to finish loading.

## What happens to your text?

**This is server-side Python inference, not browser inference.** When you run it locally, the server is your computer. On a publicly hosted version, document text and queries are sent to the hosting server. Do not describe the hosted version as keeping documents on the visitor's device.

- The browser holds imported passages in memory between searches. No localStorage, IndexedDB, document cookies, or database.
- Python parses imports in memory and returns passages. Each search sends that tab's passage list; the server never uses a shared collection of visitor documents.
- Personal text and embeddings are request-local, not saved to disk or cached between requests. Only the public model and bundled sample embeddings are reused. Inputs and request bodies are not logged by this app.
- **Clear imported data** removes tab-held text, query, results, paste draft, and file selection, and ignores/aborts pending browser requests. An already-running server operation may finish before its temporary input is released. This is not forensic memory erasure. Reloading also clears tab-held imports.
- The host/proxy may maintain its own network logs and infrastructure policies. Hugging Face receives model-download requests and network metadata; the app does not send it your documents or queries. Dependency downloads also need network access. Model caching uses ignored `.cache/`.
- **Offline operation has not been verified.** There is no offline guarantee or installable offline web app.

Use non-sensitive text on a public demo. Uploaded Markdown is treated as plain text, never executed. The renderer uses `textContent`, not HTML injection.

## Architecture

```text
HTML/CSS + small JavaScript UI
   │ POST query / imported text (same-origin HTTP)
   ▼
Flask app.py: validation, imports, status and search routes
   ├─ search.py: original-text chunking + exact-token keyword ranking
   └─ engine.py: Sentence Transformers → normalized embeddings → cosine ranking
   ▲
JSON containing ranked original passages and source titles
```

| File | Responsibility |
|---|---|
| `app.py` | Flask routes and bounded, request-local input processing |
| `search.py` | Chunking, validation, keyword ranking, cosine ranking, Recall@3 |
| `engine.py` | Lazy CPU model loading, progress, single-inference lock, sample embeddings |
| `templates/index.html` | Accessible page structure and original sample library |
| `static/style.css` | Responsive layout, focus styles, reduced-motion support |
| `static/app.js` | Form submissions, polling, result rendering, cancellation and clear |
| `data/` | Original passages and fixed relevance judgments |
| `evaluate.py` | Real-model Python evaluation |
| `tests/` | Fast tests without model download |
| `scripts/smoke_model.py` | Opt-in real-model Flask integration check |

The keyword baseline uses BM25 (k1=1.5, b=0.75) over lowercase Unicode word tokens, ignoring a fixed list of common English/function/conversation words. No stemming or synonym expansion. Each result lists the actual matched words. A query containing only ignored words produces no keyword results. This fixes accidental matches on words such as “the,” “can,” and “up.”

Semantic ranking uses dot products of normalized 384-dimensional embeddings, equivalent to cosine similarity. Passages below **0.35** are omitted; results are never padded to three. This is a fixed, uncalibrated demo heuristic chosen before running the revised evaluation, informed by the observed weak-match problem—not an independently validated relevance detector. It can reject useful passages or keep irrelevant ones. A high score can indicate a related topic without an answer. “No close passage found” means no passage cleared that cutoff, not proof the answer is absent.

Both methods rank passage text only, search exactly the selected collection, break ties by passage ID, and return up to three results. Scores are not confidence percentages and are not comparable across methods.

Imports are limited to 100 KB of text and 100 passages total, ten files per batch, and 20,000 characters per paste. Paragraphs are split into at most 600-character slices, favoring spaces and preserving original wording. Token-dense input can still exceed the model's truncation limit. An inference lock rejects overlapping model searches with a retry message rather than building an unbounded queue of personal text. The configured Gunicorn process uses one model instance and four request threads.

## Evaluation: actual Python results

The original 18 passages and 12 queries/relevance labels were preserved from the earlier version. They were not tuned after observing these results. Six queries use exact terms and six use paraphrases. Each has one manually specified relevant passage. Recall@3 is the fraction of labeled relevant passages in the first three results; with one relevant passage, it equals hit rate. Each query has equal weight in the mean.

| Group | Queries | Semantic Recall@3 | Keyword Recall@3 |
|---|---:|---:|---:|
| Exact-term | 6 | 1.000 | 1.000 |
| Paraphrased | 6 | 1.000 | 0.000 |
| All | 12 | **1.000** | **0.500** |

Actual Python run: macOS arm64, Python 3.14.6, Sentence Transformers 6.3.0, PyTorch 2.15.0, CPU float32. See [full rankings and environment metadata](docs/evaluation-results.json). These are newly measured results from the revised Python implementation. The [pre-fix report](docs/evaluation-before-fix.json) is preserved separately: its keyword Recall@3 was 0.75. Removing common-word matches loses accidental top-three hits on this tiny paraphrase set; this decrease is reported rather than hiding it. Corpus and query checksums are included for reproducibility.

**Recall is not result quality.** Of 15 semantic passages returned across the 12 answerable queries, 12 were labeled relevant (80% precision among returned passages); the model ranked the labeled passage first on all 12. Keyword search returned 10 passages, six labeled relevant (60%). These figures use the existing labels, which identify one relevant passage per query and may not exhaust every loosely related passage.

Eight additional, fixed queries in `data/no-answer-queries.json` have no answers in the sample corpus. Semantic search returned no matches on **7/8**; keyword search on **6/8**. Both still return the borrowing policy for **“How much does a library membership cost?”** even though it states no price. Keyword search also returns studio quiet hours for the Wi-Fi password query because “studio” matches. Those failures remain in the report. The previously reported generic password-reset and football-score queries now return no results in either method. These are developer-authored regression checks, not a blind held-out benchmark.

**Small developer-authored evaluation, not an independent benchmark.** The corpus is small, top-three retrieval is forgiving, the baseline is deliberately simple, and there is no external test set or statistical significance claim. This does not establish superiority over BM25 or generalize to arbitrary documents. No labels were changed to make the model win.

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python evaluate.py
python scripts/smoke_model.py
```

The evaluator writes `docs/evaluation-results.json`. Test fixtures use only original synthetic text. `requirements.txt` pins principal runtime packages; `requirements.lock.txt` records the complete tested macOS environment, including test tools. Cross-platform dependency resolution can differ, particularly CPU PyTorch wheels on Linux.

## Verification

- **37 automated tests passed:** fixed data, ranking, Recall@3, chunking, input limits, file validation, request isolation, keyword fallback, busy/error handling, HTTP headers, document selection, mixed libraries, empty-library rejection, and duplicate-filename identity.
- **Real CPU model passed:** the 12-query evaluation and Flask integration checks for sample search, file import, imported-document ranking, selected-sample vector alignment, excluded-sample absence, mixed libraries, and empty-library rejection.
- Python compilation, dependency compatibility (`pip check`), JavaScript syntax, and Gunicorn configuration checks passed.
- **Gunicorn HTTP smoke test passed** from the final project directory: page/health endpoints, model loading, keyword and real semantic search, pasted-text import/ranking, and a subsequent request without imports.
- Browser verification of this redesign remains incomplete: native Chrome exposed only browser controls and returned a blank screenshot. Full visual/mobile checks, interactive library/search/import/clear, keyboard/screen-reader behavior, and screenshots remain unverified. See [browser QA checklist](docs/BROWSER_QA.md).
- No live deployment has been performed. Docker configuration is supplied, but Docker image building was not verified because the local Docker daemon was unavailable.

There is no frontend production build step anymore. For production serving, use Gunicorn rather than Flask's development server:

```bash
gunicorn --config gunicorn.conf.py app:app
```

This also binds to localhost by default. `BIND_HOST=0.0.0.0` is an explicit opt-in for a separate hosting environment; the Docker and Render configurations set it there. Do not expose your personal computer through port forwarding or a public tunnel.

## Deployment and cost limits

Static Netlify hosting cannot run this Python version. A server/container host with sufficient RAM is required. A local smoke test measured **528.2 MiB resident memory after search** on this Mac; that is neither a peak-memory measurement nor a guarantee for Linux. Allow additional memory for imports and concurrent HTTP requests.

An **experimental** `render.yaml` requests Render's **free** Python web-service plan and installs the CPU-only Linux PyTorch wheel. Current [Flask deployment guidance](https://render.com/docs/deploy-flask), [Blueprint specification](https://render.com/docs/blueprint-spec), and [free-plan limits](https://render.com/docs/free) were checked during this conversion. Free services sleep after inactivity and have usage limits. **Memory suitability has not been verified; this model may exceed a small free instance.** Do not upgrade or pay automatically if deployment fails. A public GitHub source repository plus a recorded local demo is the no-hosting-cost fallback.

`Dockerfile` is also included for a suitable existing container host. It runs as a non-root user, serves on port 7860, and copies only application assets. Docker Spaces on Hugging Face are not assumed to be free: [current Spaces documentation](https://huggingface.co/docs/hub/en/spaces-overview) says creating Docker compute Spaces requires a paid plan. No account, paid plan, or deployment was created here.

Before publication: provide the intended GitHub repository and hosting destination, review the free-account limits, deploy only the Python source, then verify the actual HTTPS URL and browser checklist. Never publish `.venv/`, `.cache/`, `.legacy-browser/`, imported documents, environment secrets, or personal files. The local `.legacy-browser/` folder preserves the previous browser implementation for rollback and is ignored by Git.

## Attribution and limitations

Model: [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2), **Apache-2.0**, immutable revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. Uses the model's sentence-transformer pooling and normalized output. Weights are downloaded separately, not committed. Sentence Transformers is Apache-2.0; Flask is BSD-3-Clause; PyTorch is BSD-style. Dependencies retain their own licenses. This project's source and original sample texts are [MIT](LICENSE).

English-focused model; slow cold starts; substantial dependency and RAM requirements; small corpus limits; unrelated semantic results can still rank highly. The app retrieves passages, not answers or verified facts. This is a bounded portfolio demo, not an authenticated or abuse-hardened multi-user service. PDF, IndexedDB, authentication, chat, persistent document storage, and larger-corpus indexing remain deferred.

## Factual résumé bullet

- Built LocalLens with Python, Flask, and Sentence Transformers; verified document-import and search endpoints with 37 automated tests and real CPU-model integration checks, and evaluated retrieval and no-match behavior on 12 answerable and eight unanswerable developer-authored queries, documenting both improvements and remaining false positives.

## Try the fixed behavior

Restart the server after updating (`Ctrl+C`, then `python app.py`) and refresh the page.

1. With samples checked in **Library**, search **Can somebody help stitch up my ripped shirt?** The expected result is **Mending clothes**.
2. Uncheck or delete its source document and repeat. That passage must not appear. Restore sample documents to reset the sample collection.
3. Search **How do I reset my password?** Expected: no matches.
4. Expand **Add your own text**, paste the following and select **Add text**:

   > Remote working arrangements: Employees may perform their duties from home two days per week with manager approval.

5. Samples switch off. Search **Can I work from home?** The imported policy should appear. Search **flat tire**: the sample bicycle document must not appear unless you check it again.
6. Uncheck the imported document; with no documents enabled, search is disabled. Re-enable it or restore samples. Delete removes just that document; **Clear imported data** removes all imports.

Real CPU-model integration verifies retrieval and library selection through Flask. The interactive browser checklist remains to be completed. Earlier search-quality evidence is retained in [search-regressions.json](docs/search-regressions.json).

## Source publication and device boundaries

Publishing this repository shares the included source files; it does not run a server on the author's computer or grant visitors access to that computer. A reader who downloads and runs the Python app runs Flask and the model on their own computer. This is not a browser-only website. Initial dependency and model downloads use network access. The frontend uses relative, same-origin API paths, with no callback to the author's device.

Only intentionally selected files should be committed. Ignore rules exclude model caches, environments, imports, private folders, and common secret files; they do not detect every possible secret or remove already committed data. The source review and automated checks are not a security certification. See [publication review](docs/PUBLICATION_REVIEW.md).
