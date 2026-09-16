const state = { file: null, sessionId: null, busy: false };
const $ = (id) => document.getElementById(id);
const input = $('pdfInput');
const dropzone = $('dropzone');
const uploadButton = $('uploadButton');
const uploadStatus = $('uploadStatus');
const messages = $('messages');

function setFile(file) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith('.pdf')) return setStatus('Please choose a PDF file.', true);
  if (file.size > 25 * 1024 * 1024) return setStatus('The PDF must be 25 MB or smaller.', true);
  state.file = file;
  dropzone.classList.add('has-file');
  dropzone.querySelector('strong').textContent = file.name;
  dropzone.querySelector('span:last-child').textContent = `${(file.size / 1024 / 1024).toFixed(1)} MB · ready to upload`;
  uploadButton.disabled = false;
  setStatus('');
}

function setStatus(text, error = false) {
  uploadStatus.textContent = text;
  uploadStatus.classList.toggle('error', error);
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  if (response.ok) return response.status === 204 ? null : response.json();
  let message = 'Something went wrong.';
  try { message = (await response.json()).detail || message; } catch (_) {}
  throw new Error(message);
}

input.addEventListener('change', () => setFile(input.files[0]));
['dragenter', 'dragover'].forEach((name) => dropzone.addEventListener(name, (event) => { event.preventDefault(); dropzone.classList.add('dragging'); }));
['dragleave', 'drop'].forEach((name) => dropzone.addEventListener(name, (event) => { event.preventDefault(); dropzone.classList.remove('dragging'); }));
dropzone.addEventListener('drop', (event) => setFile(event.dataTransfer.files[0]));

uploadButton.addEventListener('click', async () => {
  if (!state.file || state.busy) return;
  state.busy = true; uploadButton.disabled = true; setStatus('Reading, chunking, and indexing your PDF…');
  const data = new FormData(); data.append('file', state.file);
  try {
    const result = await api('/api/documents', { method: 'POST', body: data });
    state.sessionId = result.session_id;
    $('fileName').textContent = result.filename;
    $('fileMeta').textContent = `${result.pages} pages · ${result.chunks} searchable sections`;
    $('uploadView').classList.add('hidden'); $('chatView').classList.remove('hidden');
    $('question').focus();
  } catch (error) { setStatus(error.message, true); uploadButton.disabled = false; }
  finally { state.busy = false; }
});

function addMessage(role, text, sources = []) {
  const article = document.createElement('article'); article.className = `message ${role}`;
  if (role === 'assistant') { const avatar = document.createElement('div'); avatar.className = 'avatar'; avatar.textContent = 'AI'; article.appendChild(avatar); }
  const bubble = document.createElement('div');
  if (role === 'assistant') renderMarkdown(bubble, text); else { const paragraph = document.createElement('p'); paragraph.textContent = text; bubble.appendChild(paragraph); }
  if (sources.length) {
    const sourceList = document.createElement('div'); sourceList.className = 'sources';
    sources.forEach((source) => { const item = document.createElement('span'); item.className = 'source'; item.textContent = `Page ${source.page}`; item.title = source.excerpt; sourceList.appendChild(item); });
    bubble.appendChild(sourceList);
  }
  article.appendChild(bubble); messages.appendChild(article); messages.scrollTop = messages.scrollHeight; return article;
}

function appendInline(parent, text) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  parts.filter(Boolean).forEach((part) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      const strong = document.createElement('strong'); strong.textContent = part.slice(2, -2); parent.appendChild(strong);
    } else { parent.appendChild(document.createTextNode(part)); }
  });
}

function renderMarkdown(parent, text) {
  const lines = text.split(/\r?\n/); let list = null;
  const closeList = () => { list = null; };
  lines.forEach((line) => {
    const bullet = line.match(/^\s*[-*•]\s+(.+)$/);
    if (bullet) {
      if (!list) { list = document.createElement('ul'); parent.appendChild(list); }
      const item = document.createElement('li'); appendInline(item, bullet[1]); list.appendChild(item); return;
    }
    closeList();
    const clean = line.trim(); if (!clean) return;
    const heading = clean.match(/^#{1,3}\s+(.+)$/);
    const element = document.createElement(heading ? 'h3' : 'p'); appendInline(element, heading ? heading[1] : clean); parent.appendChild(element);
  });
}

$('chatForm').addEventListener('submit', async (event) => {
  event.preventDefault(); const field = $('question'); const question = field.value.trim(); if (!question || state.busy) return;
  addMessage('user', question); field.value = ''; state.busy = true; $('sendButton').disabled = true;
  const pending = addMessage('assistant', 'Searching the document…');
  try {
    const result = await api('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: state.sessionId, question }) });
    pending.remove(); addMessage('assistant', result.answer, result.sources);
  } catch (error) { pending.querySelector('p').textContent = error.message; }
  finally { state.busy = false; $('sendButton').disabled = false; field.focus(); }
});

$('question').addEventListener('keydown', (event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); $('chatForm').requestSubmit(); } });
$('question').addEventListener('input', (event) => { event.target.style.height = 'auto'; event.target.style.height = `${event.target.scrollHeight}px`; });

$('newDocument').addEventListener('click', async () => {
  if (state.sessionId) { try { await api(`/api/documents/${state.sessionId}`, { method: 'DELETE' }); } catch (_) {} }
  window.location.reload();
});
