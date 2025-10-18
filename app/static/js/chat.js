/**
 * Aynux Chat - Frontend JavaScript
 * Handles chat messaging, streaming, and UI interactions
 */

class AynuxChat {
    constructor() {
        // Configuration
        this.apiBaseUrl = window.location.origin;
        this.chatEndpoint = '/api/v1/chat/message';
        this.streamEndpoint = '/api/v1/chat/message/stream';
        this.historyEndpoint = '/api/v1/chat/history';

        // State
        this.userId = this.generateUserId();
        this.sessionId = this.generateSessionId();
        this.messageCount = 0;
        this.isStreaming = false;
        this.streamingEnabled = false;
        this.currentDomain = 'auto';

        // DOM Elements
        this.messagesContainer = document.getElementById('messagesContainer');
        this.messageForm = document.getElementById('messageForm');
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.typingIndicator = document.getElementById('typingIndicator');
        this.domainSelector = document.getElementById('domainSelector');
        this.debugPanel = document.getElementById('debugPanel');
        this.streamingToggle = document.getElementById('streamingToggle');

        // Initialize
        this.init();
    }

    init() {
        console.log('🚀 Initializing Aynux Chat...');
        this.setupEventListeners();
        this.updateDebugInfo();
        this.checkServerStatus();
        this.loadConversationHistory();
        console.log('✅ Chat initialized');
    }

    setupEventListeners() {
        // Message form
        this.messageForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.sendMessage();
        });

        // Quick action buttons
        document.querySelectorAll('.quick-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const message = btn.dataset.message;
                this.messageInput.value = message;
                this.sendMessage();
            });
        });

        // Domain selector
        this.domainSelector.addEventListener('change', (e) => {
            this.currentDomain = e.target.value;
            this.updateDebugInfo();
            this.showToast(`Dominio cambiado a: ${e.target.value}`, 'success');
        });

        // Debug panel
        document.getElementById('toggleDebug').addEventListener('click', () => {
            this.toggleDebugPanel();
        });

        document.getElementById('closeDebug').addEventListener('click', () => {
            this.toggleDebugPanel();
        });

        // Streaming toggle
        this.streamingToggle.addEventListener('change', (e) => {
            this.streamingEnabled = e.target.checked;
            document.getElementById('streamingStatus').textContent =
                this.streamingEnabled ? 'Activado' : 'Desactivado';
            this.showToast(
                `Streaming ${this.streamingEnabled ? 'activado' : 'desactivado'}`,
                'success'
            );
        });

        // Debug actions
        document.getElementById('clearChat').addEventListener('click', () => {
            this.clearChat();
        });

        document.getElementById('exportChat').addEventListener('click', () => {
            this.exportChat();
        });

        document.getElementById('clearHistory').addEventListener('click', () => {
            this.clearChat();
        });

        document.getElementById('refreshSession').addEventListener('click', () => {
            this.refreshSession();
        });
    }

    generateUserId() {
        let userId = localStorage.getItem('aynux_user_id');
        if (!userId) {
            userId = 'web_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('aynux_user_id', userId);
        }
        return userId;
    }

    generateSessionId() {
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        return `session_${timestamp}_${Math.random().toString(36).substr(2, 5)}`;
    }

    async checkServerStatus() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/v1/chat/health`);
            const data = await response.json();

            const statusIndicator = document.getElementById('statusIndicator');
            if (data.status === 'healthy') {
                statusIndicator.innerHTML = '<span class="status-dot status-online"></span> Conectado';
            } else {
                statusIndicator.innerHTML = '<span class="status-dot status-offline"></span> Desconectado';
                this.showToast('Servidor no disponible', 'error');
            }
        } catch (error) {
            console.error('Error checking server status:', error);
            const statusIndicator = document.getElementById('statusIndicator');
            statusIndicator.innerHTML = '<span class="status-dot status-offline"></span> Error';
        }
    }

    async loadConversationHistory() {
        try {
            const response = await fetch(
                `${this.apiBaseUrl}${this.historyEndpoint}?user_id=${this.userId}&session_id=${this.sessionId}&limit=50`
            );

            if (!response.ok) return;

            const data = await response.json();
            if (data.messages && data.messages.length > 0) {
                // Clear welcome message if exists
                const welcomeMsg = this.messagesContainer.querySelector('.welcome-message');
                if (welcomeMsg) {
                    welcomeMsg.remove();
                }

                // Render messages
                data.messages.forEach(msg => {
                    this.addMessageToUI(
                        msg.content,
                        msg.role === 'user' ? 'user' : 'bot',
                        msg.timestamp,
                        'restored'
                    );
                });

                this.messageCount = data.messages.length;
            }
        } catch (error) {
            console.error('Error loading history:', error);
        }
    }

    async sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message) return;

        // Clear input
        this.messageInput.value = '';
        this.messageInput.focus();

        // Remove welcome message if exists
        const welcomeMsg = this.messagesContainer.querySelector('.welcome-message');
        if (welcomeMsg) {
            welcomeMsg.remove();
        }

        // Add user message to UI
        this.addMessageToUI(message, 'user');

        // Send to API
        if (this.streamingEnabled) {
            await this.sendMessageStream(message);
        } else {
            await this.sendMessageNormal(message);
        }

        this.messageCount++;
        this.updateDebugInfo();
    }

    async sendMessageNormal(message) {
        this.showTypingIndicator();
        this.disableSendButton();

        try {
            const response = await fetch(`${this.apiBaseUrl}${this.chatEndpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    user_id: this.userId,
                    session_id: this.sessionId,
                    metadata: {
                        domain: this.currentDomain,
                        channel: 'web',
                        streaming: false,
                    },
                }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            // Add bot response to UI
            this.addMessageToUI(
                data.response,
                'bot',
                new Date().toISOString(),
                data.agent_used,
                data.metadata
            );

            // Update debug panel
            this.updateDebugMetadata(data);

        } catch (error) {
            console.error('Error sending message:', error);
            this.addMessageToUI(
                '❌ Error al procesar tu mensaje. Por favor, intenta nuevamente.',
                'bot',
                new Date().toISOString(),
                'error'
            );
            this.showToast('Error al enviar mensaje', 'error');
        } finally {
            this.hideTypingIndicator();
            this.enableSendButton();
        }
    }

    async sendMessageStream(message) {
        this.showTypingIndicator('Procesando con streaming...');
        this.disableSendButton();
        this.isStreaming = true;

        // Create placeholder for bot message
        const botMessageDiv = document.createElement('div');
        botMessageDiv.className = 'message bot';
        botMessageDiv.innerHTML = `
            <div class="message-bubble">
                <div class="message-content"></div>
                <div class="message-info">
                    <span class="agent-badge">Procesando...</span>
                    <span class="timestamp">${new Date().toLocaleTimeString()}</span>
                </div>
            </div>
        `;
        this.messagesContainer.appendChild(botMessageDiv);
        this.scrollToBottom();

        const messageContent = botMessageDiv.querySelector('.message-content');
        const agentBadge = botMessageDiv.querySelector('.agent-badge');

        try {
            const response = await fetch(`${this.apiBaseUrl}${this.streamEndpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    user_id: this.userId,
                    session_id: this.sessionId,
                    metadata: {
                        domain: this.currentDomain,
                        channel: 'web',
                        streaming: true,
                    },
                }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });

                // Process SSE events
                const lines = buffer.split('\n\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (!line.trim() || !line.startsWith('data: ')) continue;

                    try {
                        const data = JSON.parse(line.substring(6));

                        if (data.event_type === 'agent_start') {
                            agentBadge.textContent = `🤖 ${data.agent_current}`;
                            this.updateTypingText(`${data.message}`);
                        } else if (data.event_type === 'progress') {
                            this.updateTypingText(`${data.message} (${Math.round(data.progress * 100)}%)`);
                        } else if (data.event_type === 'complete') {
                            messageContent.textContent = data.message;
                            agentBadge.textContent = data.agent_current || 'bot';
                            break;
                        } else if (data.event_type === 'error') {
                            messageContent.textContent = data.message;
                            agentBadge.textContent = 'Error';
                            agentBadge.style.background = '#ef4444';
                        }

                        this.scrollToBottom();
                    } catch (e) {
                        console.error('Error parsing SSE event:', e);
                    }
                }
            }

        } catch (error) {
            console.error('Error in streaming:', error);
            messageContent.textContent = '❌ Error en la comunicación con el servidor.';
            agentBadge.textContent = 'Error';
            this.showToast('Error en streaming', 'error');
        } finally {
            this.hideTypingIndicator();
            this.enableSendButton();
            this.isStreaming = false;
        }
    }

    addMessageToUI(content, role, timestamp, agent, metadata) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;

        const time = timestamp ? new Date(timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
        const agentBadge = agent && role === 'bot' ? `<span class="agent-badge">${agent}</span>` : '';

        messageDiv.innerHTML = `
            <div class="message-bubble">
                <div class="message-content">${content}</div>
                <div class="message-info">
                    ${agentBadge}
                    <span class="timestamp">${time}</span>
                </div>
            </div>
        `;

        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();

        // Store metadata if available
        if (metadata) {
            messageDiv.dataset.metadata = JSON.stringify(metadata);
        }
    }

    showTypingIndicator(text = 'Procesando tu mensaje...') {
        this.typingIndicator.style.display = 'flex';
        this.updateTypingText(text);
    }

    hideTypingIndicator() {
        this.typingIndicator.style.display = 'none';
    }

    updateTypingText(text) {
        document.getElementById('typingText').textContent = text;
    }

    disableSendButton() {
        this.sendButton.disabled = true;
    }

    enableSendButton() {
        this.sendButton.disabled = false;
    }

    scrollToBottom() {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }

    toggleDebugPanel() {
        const isVisible = this.debugPanel.style.display !== 'none';
        this.debugPanel.style.display = isVisible ? 'none' : 'block';
    }

    updateDebugInfo() {
        document.getElementById('debugSessionId').textContent = this.sessionId.substring(0, 20) + '...';
        document.getElementById('debugUserId').textContent = this.userId;
        document.getElementById('debugMessageCount').textContent = this.messageCount;
        document.getElementById('debugDomain').textContent = this.currentDomain;
    }

    updateDebugMetadata(data) {
        document.getElementById('debugAgent').textContent = data.agent_used || 'unknown';
        document.getElementById('debugTime').textContent = `${data.metadata?.processing_time_ms || 0}ms`;
        document.getElementById('debugStatus').textContent = data.status || 'success';

        const metadataJson = JSON.stringify(data.metadata || {}, null, 2);
        document.getElementById('debugMetadata').innerHTML = `<pre>${metadataJson}</pre>`;
    }

    clearChat() {
        // Remove all messages except welcome
        const messages = this.messagesContainer.querySelectorAll('.message');
        messages.forEach(msg => msg.remove());

        // Add welcome message back
        this.messagesContainer.innerHTML = `
            <div class="welcome-message">
                <div class="welcome-icon">👋</div>
                <h2>¡Bienvenido a Aynux Chat!</h2>
                <p>Este chat se conecta al mismo sistema de IA que usa WhatsApp.</p>
                <div class="features">
                    <div class="feature-item">
                        <span class="feature-icon">🛒</span>
                        <span>E-commerce: Productos, pedidos, promociones</span>
                    </div>
                    <div class="feature-item">
                        <span class="feature-icon">🏥</span>
                        <span>Hospital: Citas médicas, pacientes</span>
                    </div>
                    <div class="feature-item">
                        <span class="feature-icon">💳</span>
                        <span>Crédito: Cuentas, pagos, cobranzas</span>
                    </div>
                </div>
                <p class="start-hint">Escribe un mensaje para comenzar...</p>
            </div>
        `;

        this.messageCount = 0;
        this.updateDebugInfo();
        this.showToast('Chat limpiado', 'success');
    }

    refreshSession() {
        this.sessionId = this.generateSessionId();
        this.clearChat();
        this.showToast('Nueva sesión creada', 'success');
    }

    exportChat() {
        const messages = [];
        this.messagesContainer.querySelectorAll('.message').forEach(msg => {
            const role = msg.classList.contains('user') ? 'user' : 'bot';
            const content = msg.querySelector('.message-content').textContent;
            const timestamp = msg.querySelector('.timestamp').textContent;
            const agent = msg.querySelector('.agent-badge')?.textContent || null;

            messages.push({ role, content, timestamp, agent });
        });

        const exportData = {
            session_id: this.sessionId,
            user_id: this.userId,
            domain: this.currentDomain,
            exported_at: new Date().toISOString(),
            message_count: messages.length,
            messages: messages,
        };

        const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `aynux-chat-${this.sessionId}.json`;
        a.click();
        URL.revokeObjectURL(url);

        this.showToast('Chat exportado exitosamente', 'success');
    }

    showToast(message, type = 'success') {
        const toastContainer = document.getElementById('toastContainer');

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;

        toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.style.animation = 'slideIn 0.3s ease reverse';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
}

// Initialize chat when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.aynuxChat = new AynuxChat();
});
