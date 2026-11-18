// Page interactions only. Document parsing and semantic search run in Python.
const $ = id => document.getElementById(id);
const samples = JSON.parse($('library-data').textContent);
function sampleDocuments() {
  const grouped = new Map();
  samples.forEach(p => {
    if (!grouped.has(p.title)) grouped.set(p.title, {id: `sample-${grouped.size}`, title: p.title, sample: true, enabled: true, passages: []});
    grouped.get(p.title).passages.push(p);
  });
  return [...grouped.values()];
}
let documents = sampleDocuments(), generation = 0, controller = null, busy = false;
const status = text => { $('status-text').textContent = text; };
const importedDocuments = () => documents.filter(d => !d.sample);
const selectedDocuments = () => documents.filter(d => d.enabled);
function showError(text) { $('error').textContent = text; $('error').hidden = !text; }
function updateControls() {
  const enabled = selectedDocuments();
  $('search-button').disabled = busy || !enabled.length;
  document.querySelectorAll('.import-button, #retry').forEach(b => b.disabled = busy);
  document.querySelectorAll('.suggestion').forEach(b => {
    const available = enabled.some(d => d.sample);
    b.disabled = busy || !available;
    b.title = available ? 'Search the enabled documents' : 'Enable a sample document in the Library to try an example';
  });
  $('cancel').hidden = !busy;
  $('clear').hidden = !importedDocuments().length;
  $('corpus-count').textContent = `${enabled.length} of ${documents.length} documents enabled`;
  $('library-count').textContent = documents.length;
}
function setBusy(value) { busy = value; updateControls(); if (!value) $('progress').hidden = true; }
function cancel(message = 'Search cancelled.') {
  generation++; controller?.abort(); controller = null; setBusy(false); status(message);
}
function empty(title, text) {
  const box = document.createElement('div'); box.className = 'empty';
  const h = document.createElement('h3'); h.textContent = title;
  const p = document.createElement('p'); p.textContent = text; box.append(h, p);
  $('semantic-results').replaceChildren(box); $('result-count').textContent = 'Original passages';
}
function libraryChanged(message) {
  cancel(message); showError(''); $('searched').textContent = ''; $('searched').hidden = true;
  empty(selectedDocuments().length ? 'Your library changed' : 'No documents enabled', selectedDocuments().length ? 'Search again to use your updated selection.' : 'Check a document, restore the examples, or add your own text.');
  $('library-status').textContent = message; renderLibrary();
}
function renderLibrary() {
  const focusId = document.activeElement?.id;
  const list = $('document-list'); list.replaceChildren();
  if (!documents.length) {
    const p = document.createElement('p'); p.className = 'help'; p.textContent = 'Your library is empty. Add a document or restore the examples.'; list.append(p);
  }
  documents.forEach(doc => {
    const row = document.createElement('div'); row.className = `document ${doc.enabled ? '' : 'document-off'}`;
    const line = document.createElement('div'); line.className = 'document-row';
    const label = document.createElement('label'); label.className = 'document-label';
    const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.checked = doc.enabled; checkbox.id = `enable-${doc.id}`;
    const name = document.createElement('span'); name.textContent = `${doc.title}${doc.sample ? ' (Sample)' : ''}`;
    label.append(checkbox, name);
    checkbox.addEventListener('change', () => { doc.enabled = checkbox.checked; libraryChanged(`${doc.title} ${doc.enabled ? 'enabled' : 'disabled'}.`); });
    const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'delete-button'; remove.textContent = 'Delete'; remove.setAttribute('aria-label', `Delete ${doc.title}${doc.sample ? ' (Sample)' : ''}`);
    remove.addEventListener('click', () => {
      documents = documents.filter(d => d.id !== doc.id); libraryChanged(`${doc.title} removed from this tab.`);
      $('library-heading').focus();
    });
    line.append(label, remove);
    const preview = document.createElement('details'); preview.className = 'document-preview';
    const summary = document.createElement('summary'); summary.textContent = `${doc.passages.length} passage${doc.passages.length === 1 ? '' : 's'} · Preview`;
    preview.append(summary);
    doc.passages.forEach(p => { const text = document.createElement('p'); text.textContent = p.text; preview.append(text); });
    row.append(line, preview); list.append(row);
  });
  updateControls();
  if (focusId) document.getElementById(focusId)?.focus();
}
async function api(path, body, signal) {
  const options = {signal, headers: {'X-LocalLens': '1'}};
  if (body !== undefined) {
    options.method = 'POST';
    if (body instanceof FormData) options.body = body;
    else { options.headers['Content-Type'] = 'application/json'; options.body = JSON.stringify(body); }
  }
  const response = await fetch(path, options);
  let data; try { data = await response.json(); } catch { throw Error('The server did not respond as expected. Please try again.'); }
  if (!response.ok) throw Error(data.error || 'The request failed. Please try again.');
  return data;
}
function renderResults(passages) {
  if (!passages.length) { empty('No close match found', 'Try different wording or add a document about this topic.'); return; }
  $('semantic-results').replaceChildren(); $('result-count').textContent = `${passages.length} match${passages.length === 1 ? '' : 'es'}`;
  passages.forEach((p, i) => {
    const article = document.createElement('article'); article.className = 'passage';
    const meta = document.createElement('p'); meta.className = 'passage-meta'; meta.textContent = `0${i + 1} / ${p.title}${p.imported ? '' : ' (Sample)'}`;
    const h = document.createElement('h3'); h.textContent = p.heading;
    const excerpt = document.createElement('p'); excerpt.className = 'excerpt'; excerpt.textContent = p.text;
    article.append(meta, h, excerpt); $('semantic-results').append(article);
  });
}
async function ensureModel(signal, ticket) {
  let state = await api('/api/model', undefined, signal);
  if (state.state !== 'ready') state = await api('/api/model/load', {}, signal);
  const start = Date.now();
  while (state.state !== 'ready') {
    if (ticket !== generation || signal.aborted) throw new DOMException('Cancelled', 'AbortError');
    if (state.state === 'error') { $('retry').hidden = false; throw Error(state.message); }
    if (Date.now() - start > 300000) throw Error('Loading is taking longer than expected. Please try again.');
    status(state.message); $('progress').hidden = false;
    if (state.progress === null) $('progress').removeAttribute('value'); else $('progress').value = state.progress;
    await new Promise(resolve => setTimeout(resolve, 700));
    state = await api('/api/model', undefined, signal);
  }
  $('retry').hidden = true; $('progress').removeAttribute('value');
}
async function search() {
  if (busy || !$('query').value.trim()) return;
  const selected = selectedDocuments();
  if (!selected.length) { showError('Enable at least one document in the Library.'); return; }
  cancel(); const ticket = generation; controller = new AbortController(); const {signal} = controller;
  const query = $('query').value.trim();
  const sample_ids = selected.filter(d => d.sample).flatMap(d => d.passages.map(p => p.id));
  const imports = selected.filter(d => !d.sample).flatMap(d => d.passages);
  showError(''); setBusy(true); status('Getting search ready…');
  $('searched').hidden = false; $('searched').textContent = `Results for “${query}”`;
  empty('Searching your documents…', 'The first search may take a moment while the model loads.');
  try {
    await ensureModel(signal, ticket); status('Searching…');
    const result = await api('/api/search', {query, imports, sample_ids, scope: 'library', mode: 'semantic'}, signal);
    if (ticket !== generation) return;
    renderResults(result.semantic); status(`Search complete · ${selected.length} documents searched`);
  } catch (e) {
    if (e.name !== 'AbortError' && ticket === generation) { showError(e.message); status('Search did not finish.'); empty('Please try again', 'Your documents are still in the Library.'); }
  } finally { if (ticket === generation) {controller = null; setBusy(false);} }
}
async function importText(body, title = '') {
  if (busy) return;
  cancel(); const ticket = generation; controller = new AbortController(); setBusy(true); showError(''); status('Adding text…');
  try {
    const data = await api('/api/import', body, controller.signal);
    if (ticket !== generation) return;
    const current = importedDocuments().flatMap(d => d.passages);
    const next = current.concat(data.passages);
    if (next.length > 100 || next.reduce((n,p) => n + new TextEncoder().encode(p.text).length, 0) > 100000) throw Error('Limit: 100 passages / 100 KB total. Delete an imported document before adding more.');
    const grouped = new Map();
    data.passages.forEach(p => {
      const id = p.document_id;
      if (title) p.title = title;
      if (!grouped.has(id)) grouped.set(id, {id, title: p.title, sample: false, enabled: true, passages: []});
      grouped.get(id).passages.push(p);
    });
    documents.forEach(d => { if (d.sample) d.enabled = false; });
    documents.push(...grouped.values());
    $('paste').value = ''; $('files').value = ''; $('document-title').value = '';
    $('import-status').textContent = `${grouped.size} document${grouped.size === 1 ? '' : 's'} added.`;
    libraryChanged('Your text is ready. Samples are switched off; check them to include them.');
  } catch (e) { if (e.name !== 'AbortError' && ticket === generation) {showError(e.message); status('Could not add text.');} }
  finally { if (ticket === generation) {controller = null; setBusy(false);} }
}
$('search-form').addEventListener('submit', e => {e.preventDefault(); search();});
document.querySelectorAll('.suggestion').forEach(b => b.addEventListener('click', () => {$('query').value = b.dataset.query; search();}));
$('retry').addEventListener('click', search);
$('cancel').addEventListener('click', () => {cancel(); empty('Search cancelled', 'You can start a new search.');});
$('file-form').addEventListener('submit', e => {
  e.preventDefault(); const files = [...$('files').files];
  if (files.length > 10 || files.reduce((n,f) => n + f.size, 0) > 100000) {showError('Choose up to 10 files totaling at most 100 KB.'); return;}
  importText(new FormData(e.target));
});
$('paste-form').addEventListener('submit', e => {e.preventDefault(); importText({text: $('paste').value}, $('document-title').value.trim());});
$('restore').addEventListener('click', () => {documents = [...sampleDocuments(), ...importedDocuments()]; libraryChanged('Sample documents restored and enabled.');});
$('clear').addEventListener('click', () => {
  documents = documents.filter(d => d.sample); $('paste').value = ''; $('files').value = ''; $('document-title').value = ''; $('query').value = '';
  $('import-status').textContent = ''; libraryChanged('Imported data cleared from this tab.');
});
renderLibrary();
