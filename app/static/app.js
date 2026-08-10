// Real-time Chatbot WebSocket Client
let socket = null;
const wsUri = `ws://${window.location.host}/ws`;

const messagesContainer = document.getElementById('chat-messages');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const statusBar = document.getElementById('chat-status-bar');
const statusText = document.getElementById('chat-status-text');
const wsStatusPill = document.getElementById('ws-status');

// Init connection
function connectWs() {
    updateWsStatus('connecting');
    socket = new WebSocket(wsUri);

    socket.onopen = () => {
        updateWsStatus('connected');
    };

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'status') {
            showStatusBar(data.content);
        } else if (data.type === 'answer') {
            hideStatusBar();
            appendMessage('bot', data.content);
        }
    };

    socket.onclose = () => {
        updateWsStatus('disconnected');
        // Try reconnecting in 3 seconds
        setTimeout(connectWs, 3000);
    };

    socket.onerror = (err) => {
        console.error("WebSocket encountered an error:", err);
        socket.close();
    };
}

function updateWsStatus(status) {
    wsStatusPill.className = 'status-pill';
    if (status === 'connected') {
        wsStatusPill.classList.add('status-connected');
        wsStatusPill.textContent = 'Live';
    } else if (status === 'connecting') {
        wsStatusPill.classList.add('status-loading');
        wsStatusPill.textContent = 'Connecting...';
    } else {
        wsStatusPill.classList.add('status-disconnected');
        wsStatusPill.textContent = 'Offline';
    }
}

function showStatusBar(text) {
    statusText.textContent = text;
    statusBar.style.display = 'flex';
}

function hideStatusBar() {
    statusBar.style.display = 'none';
}

function suggestQuery(text) {
    chatInput.value = text;
    chatInput.focus();
}

function formatContent(text) {
    // Simple markdown formatting helper
    let formatted = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");

    // Formats bold tags (**bold**) to HTML strong
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Formats bullet lines (- item) or (* item) to bullet tags
    const lines = formatted.split('\n');
    let inList = false;
    const processedLines = [];

    for (let line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
            if (!inList) {
                processedLines.push('<ul>');
                inList = true;
            }
            processedLines.push(`<li>${trimmed.substring(2)}</li>`);
        } else {
            if (inList) {
                processedLines.push('</ul>');
                inList = false;
            }
            processedLines.push(line);
        }
    }
    if (inList) {
        processedLines.push('</ul>');
    }
    
    return processedLines.join('<br>').replace(/<\/ul><br>/g, '</ul>').replace(/<ul><br>/g, '<ul>');
}

function appendMessage(sender, text) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', `${sender}-message`);

    const contentDiv = document.createElement('div');
    contentDiv.classList.add('message-content');
    
    if (sender === 'bot') {
        contentDiv.innerHTML = formatContent(text);
    } else {
        contentDiv.textContent = text;
    }

    messageDiv.appendChild(contentDiv);
    messagesContainer.appendChild(messageDiv);
    
    // Auto Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Form Submission
chatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;

    if (socket && socket.readyState === WebSocket.OPEN) {
        appendMessage('user', message);
        socket.send(JSON.stringify({ question: message }));
        chatInput.value = '';
        showStatusBar('Sending query...');
    } else {
        alert("Cannot send message. Server is currently disconnected.");
    }
});

// Run connection on load
connectWs();
