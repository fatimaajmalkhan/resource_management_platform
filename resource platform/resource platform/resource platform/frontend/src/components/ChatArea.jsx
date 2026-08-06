import React, { useEffect, useRef, useState } from 'react';
import { formatContent } from '../utils/formatContent';
import { IconSend } from './icons';
import '../chat.css';

// Memoized message item to prevent re-formatting and re-rendering on every keystroke
const MessageItem = React.memo(({ msg }) => {
    return (
        <div className={`message ${msg.sender}-message`}>
            {msg.sender === 'bot' ? (
                <div
                    className="message-content"
                    dangerouslySetInnerHTML={{ __html: formatContent(msg.text) }}
                />
            ) : (
                <div className="message-content">{msg.text}</div>
            )}
        </div>
    );
});

export default function ChatArea({
    session,
    statusMessage,
    onSendMessage,
    isConnected,
    suggestedQuery
}) {
    const [inputVal, setInputVal] = useState('');
    const messagesEndRef = useRef(null);

    // Auto-scroll to bottom of messages container
    useEffect(() => {
        if (messagesEndRef.current) {
            messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [session?.messages, statusMessage]);

    // Update local input state when a suggested query is clicked in the parent
    useEffect(() => {
        if (suggestedQuery) {
            setInputVal(suggestedQuery.text);
        }
    }, [suggestedQuery]);

    const handleSubmit = (e) => {
        e.preventDefault();
        const msg = inputVal.trim();
        if (!msg) return;
        
        onSendMessage(msg);
        setInputVal('');
    };

    const messages = session ? session.messages : [];

    return (
        <main className="chat-main">
            <header className="chat-header">
                <div className="header-info">
                    <h2>{session ? session.title : 'Interactive Assistant'}</h2>
                    <p>Ask questions about team resources, emails, practices, or propose database edits.</p>
                </div>
                <div className="system-status">
                    <span className={`status-pill ${isConnected ? 'status-connected' : 'status-loading'}`}>
                        {isConnected ? 'Live' : 'Connecting…'}
                    </span>
                </div>
            </header>

            <div className="chat-messages">
                {messages.length === 0 && (
                    <div className="message system-message">
                        <div className="message-content">
                            <strong>Welcome to the resource assistant.</strong><br />
                            Try asking:<br />
                            • <em>"Who is in Software - TSF?"</em><br />
                            • <em>"What is the email and job title of Ehsan Ismail?"</em><br />
                            • <em>"Propose changing Usman's grade to L3"</em>
                        </div>
                    </div>
                )}

                {messages.map((msg, index) => (
                    <MessageItem key={index} msg={msg} />
                ))}
                <div ref={messagesEndRef} />
            </div>

            {/* Status bar */}
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

            <footer className="chat-footer">
                <form className="chat-form" onSubmit={handleSubmit}>
                    <input
                        type="text"
                        placeholder="Ask about resources, emails, practices, or propose an edit…"
                        value={inputVal}
                        onChange={(e) => setInputVal(e.target.value)}
                        autoComplete="off"
                        disabled={!isConnected}
                        aria-label="Message the assistant"
                        required
                    />
                    <button type="submit" disabled={!isConnected}>
                        <span className="btn-text">Send</span>
                        <IconSend width={16} height={16} />
                    </button>
                </form>
            </footer>
        </main>
    );
}
