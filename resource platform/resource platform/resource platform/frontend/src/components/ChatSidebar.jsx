import React from 'react';
import {
    IconOverview, IconAssistant, IconFunnel, IconResources, IconPlus, IconChat,
    IconTrash, IconPractice, IconEmail, IconFlag, IconHistory,
} from './icons';

const VIEWS = [
    { key: 'overview', label: 'Overview', Icon: IconOverview },
    { key: 'chat', label: 'AI Assistant', Icon: IconAssistant },
    { key: 'funnel', label: 'Demand Funnel', Icon: IconFunnel },
    { key: 'resources', label: 'Resource Master', Icon: IconResources },
];

const QUICK_TOOLS = [
    { label: 'Analytics Practice', Icon: IconPractice, query: 'who is in Analytics & Insights?' },
    { label: 'Email Lookups', Icon: IconEmail, query: 'what is the email of Ehsan Ismail?' },
    { label: 'Flagged Issues', Icon: IconFlag, query: 'list flagged resources' },
    { label: 'Change History', Icon: IconHistory, query: 'what is the grade change history of Ali?' },
];

export default function ChatSidebar({
    sessions,
    currentSessionId,
    onSelectSession,
    onNewChat,
    onDeleteSession,
    onSuggestQuery,
    isConnected,
    activeView,
    onSelectView
}) {
    return (
        <aside className="sidebar">
            <div className="sidebar-header">
                <div className="logo">
                    <svg width="32" height="32" viewBox="0 0 100 100" className="jw-logo-svg" style={{ flexShrink: 0 }}>
                        <defs>
                            <linearGradient id="jwGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                                <stop offset="0%" stopColor="#e3002b" />
                                <stop offset="100%" stopColor="#960058" />
                            </linearGradient>
                        </defs>
                        <circle cx="50" cy="50" r="48" fill="url(#jwGrad)" />
                        <path
                            d="M 32 38 L 32 68 C 32 78 22 82 17 76 C 14 72 18 68 21 68 C 26 68 30 72 32 64 L 40 46 C 42 58 46 66 52 66 C 58 66 60 56 60 46 C 62 58 66 66 72 66 C 78 66 80 56 80 46 C 80 43 83 42 86 45"
                            fill="none"
                            stroke="white"
                            strokeWidth="7.5"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                        />
                        <circle cx="32" cy="27" r="5" fill="white" />
                    </svg>
                    <div className="logo-text">
                        <h1>JazzWorld</h1>
                        <p className="subtitle">Resource Management</p>
                    </div>
                </div>
            </div>

            <nav className="primary-nav" aria-label="Workspaces">
                {VIEWS.map(({ key, label, Icon }) => (
                    <button
                        key={key}
                        className={`nav-item ${activeView === key ? 'active' : ''}`}
                        onClick={() => onSelectView(key)}
                        aria-current={activeView === key ? 'page' : undefined}
                    >
                        <span className="nav-rail" aria-hidden="true" />
                        <Icon className="nav-item-icon" />
                        <span className="nav-item-label">{label}</span>
                    </button>
                ))}
            </nav>

            <div className="sidebar-scroll">
                {activeView === 'chat' && (
                    <>
                        <button className="new-chat-btn" onClick={onNewChat}>
                            <IconPlus width={16} height={16} />
                            <span>New chat</span>
                        </button>

                        <section className="nav-section chat-history-section">
                            <h2>Recent chats</h2>
                            <ul className="session-list">
                                {sessions.length === 0 ? (
                                    <li className="session-empty">No chats yet. Start one above.</li>
                                ) : (
                                    sessions.map((session) => (
                                        <li
                                            key={session.id}
                                            className={`session-item ${session.id === currentSessionId ? 'active' : ''}`}
                                            onClick={() => onSelectSession(session.id)}
                                            onKeyDown={(e) => {
                                                if (e.key === 'Enter' || e.key === ' ') {
                                                    e.preventDefault();
                                                    onSelectSession(session.id);
                                                }
                                            }}
                                            data-testid={`session-item-${session.id}`}
                                            role="button"
                                            tabIndex={0}
                                        >
                                            <IconChat className="session-icon" width={15} height={15} />
                                            <span className="session-title-text">{session.title}</span>
                                            <button
                                                className="delete-session-btn"
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    onDeleteSession(session.id);
                                                }}
                                                title="Delete chat"
                                                aria-label="Delete chat"
                                            >
                                                <IconTrash width={15} height={15} />
                                            </button>
                                        </li>
                                    ))
                                )}
                            </ul>
                        </section>
                    </>
                )}

                <section className="nav-section">
                    <h2>Quick queries</h2>
                    <ul className="quick-list">
                        {QUICK_TOOLS.map(({ label, Icon, query }) => (
                            <li key={label}>
                                <button className="quick-item" onClick={() => onSuggestQuery(query)}>
                                    <Icon className="quick-icon" width={16} height={16} />
                                    <span>{label}</span>
                                </button>
                            </li>
                        ))}
                    </ul>
                </section>

            </div>

            <div className="sidebar-footer">
                <span className={`status-indicator ${isConnected ? 'online' : 'offline'}`} aria-hidden="true"></span>
                <span className="status-text">{isConnected ? 'Connected' : 'Reconnecting…'}</span>
            </div>
        </aside>
    );
}
