// ── DOM refs ──────────────────────────────────────────────────
const fileInput   = document.getElementById('file-input');
const uploadZone  = document.getElementById('upload-zone');
const pdfViewer   = document.getElementById('pdf-viewer');
const pdfFrame    = document.getElementById('pdf-frame');
const fileLabel   = document.getElementById('file-label');
const chatInput   = document.getElementById('chat-input');
const sendBtn     = document.getElementById('send-btn');
const messagesEl  = document.getElementById('messages');
const emptyState  = document.getElementById('empty-state');

const WEBHOOK_URL = 'https://robinkhatwani.app.n8n.cloud/webhook-test/32af8baf-b763-427b-8613-d27e0d72c8c6';

let objectURL   = null;
let currentFile = null;

// ── File upload ───────────────────────────────────────────────
fileInput.addEventListener('change', () => {
  const file = fileInput.files[0];
  if (file) loadPDF(file);
});

uploadZone.addEventListener('click', () => fileInput.click());

uploadZone.addEventListener('dragover', e => {
  e.preventDefault();
  uploadZone.classList.add('dragover');
});

uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));

uploadZone.addEventListener('drop', e => {
  e.preventDefault();
  uploadZone.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file?.type === 'application/pdf') loadPDF(file);
});

function loadPDF(file) {
  if (objectURL) URL.revokeObjectURL(objectURL);
  currentFile = file;
  objectURL = URL.createObjectURL(file);
  pdfFrame.src = objectURL;
  fileLabel.textContent = file.name;
  uploadZone.style.display = 'none';
  pdfViewer.style.display  = 'flex';
}

function removeFile() {
  pdfFrame.src = '';
  if (objectURL) { URL.revokeObjectURL(objectURL); objectURL = null; }
  currentFile = null;
  fileInput.value = '';
  pdfViewer.style.display  = 'none';
  uploadZone.style.display = 'flex';
}

// ── Chat ──────────────────────────────────────────────────────
chatInput.addEventListener('input', () => {
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
  sendBtn.disabled = chatInput.value.trim() === '';
});

chatInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (!sendBtn.disabled) sendMessage();
  }
});

async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text) return;

  hideEmptyState();
  appendMessage('user', text);
  chatInput.value = '';
  chatInput.style.height = 'auto';
  sendBtn.disabled = true;

  const typingEl = appendTyping();

  try {
    const body = new FormData();
    body.append('message', text);
    if (currentFile) body.append('contract', currentFile, currentFile.name);

    const res = await fetch(WEBHOOK_URL, { method: 'POST', body });

    let reply;
    const contentType = res.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const data = await res.json();
      // Accept common envelope shapes the webhook might return
      reply = data.reply ?? data.response ?? data.message ?? data.output ?? JSON.stringify(data);
    } else {
      reply = (await res.text()).trim();
    }

    typingEl.remove();
    appendMessage('ai', reply || 'Received an empty response from the server.');
  } catch (err) {
    typingEl.remove();
    appendMessage('ai', 'Something went wrong reaching the server. Please try again.');
    console.error('Webhook error:', err);
  }
}

// Called from suggestion chips
function useSuggestion(text) {
  chatInput.value = text;
  chatInput.dispatchEvent(new Event('input'));
  chatInput.focus();
}

function hideEmptyState() {
  if (emptyState) emptyState.style.display = 'none';
}

function appendMessage(role, text) {
  const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  const msg    = document.createElement('div');
  msg.className = `msg ${role}`;

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;

  const meta = document.createElement('div');
  meta.className = 'msg-time';
  meta.textContent = time;

  msg.appendChild(bubble);
  msg.appendChild(meta);
  messagesEl.appendChild(msg);
  scrollToBottom();
}

function appendTyping() {
  const msg    = document.createElement('div');
  msg.className = 'msg ai typing';

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.innerHTML = '<div class="dot"></div><div class="dot"></div><div class="dot"></div>';

  msg.appendChild(bubble);
  messagesEl.appendChild(msg);
  scrollToBottom();
  return msg;
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}
