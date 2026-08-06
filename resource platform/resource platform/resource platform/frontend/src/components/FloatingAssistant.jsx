import React, { useEffect, useRef, useState } from 'react';
import { formatContent } from '../utils/formatContent';
import { IconAssistant, IconClose, IconSend } from './icons';

// Memoized message item to prevent re-formatting and re-rendering on every keystroke
const MessageItem = React.memo(({ msg }) => {
    return (
        <div className={`message ${msg.sender}-message`}>
            <div
                className="message-content"
                dangerouslySetInnerHTML={{
                    __html: msg.sender === 'bot' ? formatContent(msg.text) : msg.text
                }}
            />
        </div>
    );
});

export default function FloatingAssistant({
    session,
    statusMessage,
    onSendMessage,
    isConnected
}) {
    const [isOpen, setIsOpen] = useState(false);
    const [inputVal, setInputVal] = useState('');
    const messagesEndRef = useRef(null);

    const messages = session ? session.messages : [];

    // Auto-scroll to the newest message while the panel is open
    useEffect(() => {
        if (isOpen && messagesEndRef.current) {
            messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [messages.length, statusMessage, isOpen]);

    const handleSubmit = (e) => {
        e.preventDefault();
        const msg = inputVal.trim();
        if (!msg) return;
        onSendMessage(msg);
        setInputVal('');
    };

    return (
        <div className="floating-assistant">
            {isOpen && (
                <div className="fa-panel">
                    <header className="fa-panel-header">
                        <div className="fa-header-info">
                            <h3>AI Assistant</h3>
                            <span className={`status-pill ${isConnected ? 'status-connected' : 'status-loading'}`}>
                                {isConnected ? 'Live' : 'Connecting...'}
                            </span>
                        </div>
                        <button className="fa-close-btn" onClick={() => setIsOpen(false)} title="Minimize" aria-label="Minimize assistant">
                            <IconClose width={16} height={16} />
                        </button>
                    </header>

                    <div className="fa-messages chat-messages">
                        {messages.length === 0 && (
                            <div className="message system-message">
                                <div className="message-content">
                                    <strong>Ask the assistant anything.</strong><br />
                                    e.g. <em>"Who is in Software - TSF?"</em> or <em>"What is the email of Ehsan Ismail?"</em>
                                </div>
                            </div>
                        )}

                        {messages.map((msg, index) => (
                            <MessageItem key={index} msg={msg} />
                        ))}
                        <div ref={messagesEndRef} />
                    </div>

                    {statusMessage && (
                        <div className="chat-status-bar" style={{ display: 'flex' }}>
                            <span className="typing-indicator-dots">
                                <span></span>
                                <span></span>
                                <span></span>
                            </span>
                            <span>{statusMessage}</span>
                        </div>
                    )}

                    <footer className="fa-footer">
                        <form className="chat-form" onSubmit={handleSubmit}>
                            <input
                                type="text"
                                placeholder="Ask a question..."
                                value={inputVal}
                                onChange={(e) => setInputVal(e.target.value)}
                                autoComplete="off"
                                disabled={!isConnected}
                                required
                            />
                            <button type="submit" disabled={!isConnected} aria-label="Send message">
                                <IconSend width={16} height={16} />
                            </button>
                        </form>
                    </footer>
                </div>
            )}

            <button
                className={`fa-toggle-btn ${isOpen ? 'open' : ''}`}
                onClick={() => setIsOpen(prev => !prev)}
                title={isOpen ? 'Minimize assistant' : 'Open assistant'}
                aria-label={isOpen ? 'Minimize assistant' : 'Open assistant'}
            >
                {isOpen ? <IconClose width={20} height={20} /> : <IconAssistant width={22} height={22} />}
            </button>
        </div>
    );
}
