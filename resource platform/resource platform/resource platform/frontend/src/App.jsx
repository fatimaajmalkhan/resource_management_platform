import React, { useState, useEffect, useRef } from 'react';
import ChatSidebar from './components/ChatSidebar';
import ChatArea from './components/ChatArea';
import FunnelDashboard from './components/FunnelDashboard';
import ResourceMaster from './components/ResourceMaster';
import OverviewDashboard from './components/OverviewDashboard';
import FloatingAssistant from './components/FloatingAssistant';

export default function App() {
    // Session state
    const [sessions, setSessions] = useState(() => {
        const saved = localStorage.getItem('resource_chat_sessions');
        return saved ? JSON.parse(saved) : [];
    });
    
    const [currentSessionId, setCurrentSessionId] = useState(() => {
        const savedId = localStorage.getItem('resource_chat_current_id');
        return savedId || null;
    });

    const [statusMessage, setStatusMessage] = useState('');
    const [suggestedQuery, setSuggestedQuery] = useState(null);
    const [isConnected, setIsConnected] = useState(false);
    const [reconnectCount, setReconnectCount] = useState(0);
    const [activeView, setActiveView] = useState(() => {
        const savedView = localStorage.getItem('resource_chat_active_view');
        return savedView || 'overview';
    });
    
    const socketRef = useRef(null);
    // Live mirror of the active session id so the WebSocket handler can read it
    // without the socket effect depending on it (avoids reconnecting on every switch).
    const currentSessionIdRef = useRef(currentSessionId);
    useEffect(() => {
        currentSessionIdRef.current = currentSessionId;
    }, [currentSessionId]);

    // Save sessions to localStorage
    useEffect(() => {
        localStorage.setItem('resource_chat_sessions', JSON.stringify(sessions));
    }, [sessions]);

    // Save current active session ID
    useEffect(() => {
        if (currentSessionId) {
            localStorage.setItem('resource_chat_current_id', currentSessionId);
        } else {
            localStorage.removeItem('resource_chat_current_id');
        }
    }, [currentSessionId]);

    // Save active view
    useEffect(() => {
        localStorage.setItem('resource_chat_active_view', activeView);
    }, [activeView]);

    // Ensure there is an active session on mount, without piling up empty ones.
    useEffect(() => {
        if (sessions.length === 0) {
            handleNewChat();
        } else if (!currentSessionId) {
            setCurrentSessionId(sessions[0].id);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // WebSocket Management
    useEffect(() => {
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        // Connect to same host
        const wsUri = `${wsProtocol}//${window.location.host}/ws`;
        
        let ws = new WebSocket(wsUri);
        socketRef.current = ws;

        ws.onopen = () => {
            setIsConnected(true);
        };

        ws.onmessage = (event) => {
            let data;
            try {
                data = JSON.parse(event.data);
            } catch {
                return;
            }

            // Route to the session that actually asked, not whichever session
            // happens to be on screen right now -- the user may have switched
            // chats while this request was still in flight.
            const targetId = data.session_id || currentSessionIdRef.current;
            const isForActiveSession = targetId === currentSessionIdRef.current;

            if (data.type === 'status') {
                if (isForActiveSession) setStatusMessage(data.content);
            } else if (data.type === 'answer') {
                if (isForActiveSession) setStatusMessage('');

                setSessions(prev => prev.map(session => {
                    if (session.id === targetId) {
                        return {
                            ...session,
                            messages: [...session.messages, { sender: 'bot', text: data.content }]
                        };
                    }
                    return session;
                }));
            }
        };

        let reconnectTimer = null;
        ws.onclose = () => {
            setIsConnected(false);
            setStatusMessage('');

            // If a question was still awaiting an answer when the connection
            // dropped, say so instead of leaving it silently unanswered --
            // check every session, not just whichever one is on screen now,
            // since the in-flight request may belong to a different one.
            setSessions(prev => prev.map(session => {
                const last = session.messages[session.messages.length - 1];
                if (last && last.sender === 'user') {
                    return {
                        ...session,
                        messages: [...session.messages, { sender: 'bot', text: 'Connection lost. Please resend your message.' }]
                    };
                }
                return session;
            }));

            // Reconnect logic
            reconnectTimer = setTimeout(() => {
                setReconnectCount(prev => prev + 1);
            }, 3000);
        };

        ws.onerror = (err) => {
            console.error("WebSocket encountered an error:", err);
            ws.close();
        };

        return () => {
            if (reconnectTimer) clearTimeout(reconnectTimer);
            ws.onopen = null;
            ws.onmessage = null;
            ws.onclose = null;
            ws.onerror = null;
            ws.close();
        };
    }, [reconnectCount]); // Reconnect only on retry; session switches are read via ref

    const createSession = () => ({
        id: 'session_' + Date.now() + '_' + Math.random().toString(36).slice(2, 11),
        title: 'New Chat',
        messages: []
    });

    const handleNewChat = () => {
        const newSession = createSession();
        setSessions(prev => [newSession, ...prev]);
        setCurrentSessionId(newSession.id);
        setStatusMessage('');
    };

    const handleDeleteSession = (id) => {
        const updated = sessions.filter(s => s.id !== id);
        setSessions(updated);
        
        if (currentSessionId === id) {
            if (updated.length > 0) {
                setCurrentSessionId(updated[0].id);
            } else {
                // If we deleted the last session, create a new empty one
                const newSession = createSession();
                setSessions([newSession]);
                setCurrentSessionId(newSession.id);
            }
        }
    };

    const handleSendMessage = (text) => {
        const ws = socketRef.current;
        if (!currentSessionId || !ws || ws.readyState !== WebSocket.OPEN) return;

        // 1. Add user message
        let firstQuery = false;
        let sessionTitle = 'New Chat';
        
        // Grab current history before updating state
        const activeSession = sessions.find(s => s.id === currentSessionId);
        const history = activeSession ? activeSession.messages : [];
        
        setSessions(prev => prev.map(session => {
            if (session.id === currentSessionId) {
                firstQuery = session.messages.length === 0;
                // If it's the first query, extract first 25 characters as the title
                sessionTitle = firstQuery ? (text.length > 25 ? text.substring(0, 22) + '...' : text) : session.title;
                
                return {
                    ...session,
                    title: sessionTitle,
                    messages: [...session.messages, { sender: 'user', text: text }]
                };
            }
            return session;
        }));

        // 2. Send via socket, tagged with the session that's asking -- so the
        // reply can be routed back to it even if the user switches sessions
        // before it arrives.
        ws.send(JSON.stringify({ question: text, history: history, session_id: currentSessionId }));
        setStatusMessage('Sending query…');
    };

    const handleSuggestQuery = (text) => {
        setActiveView('chat');
        setSuggestedQuery({ text, timestamp: Date.now() });
    };

    const activeSession = sessions.find(s => s.id === currentSessionId);

    return (
        <div className="app-container">
            <ChatSidebar
                sessions={sessions}
                currentSessionId={currentSessionId}
                onSelectSession={setCurrentSessionId}
                onNewChat={handleNewChat}
                onDeleteSession={handleDeleteSession}
                onSuggestQuery={handleSuggestQuery}
                isConnected={isConnected}
                activeView={activeView}
                onSelectView={setActiveView}
            />
            {activeView === 'chat' ? (
                <ChatArea
                    session={activeSession}
                    statusMessage={statusMessage}
                    onSendMessage={handleSendMessage}
                    isConnected={isConnected}
                    suggestedQuery={suggestedQuery}
                />
            ) : activeView === 'resources' ? (
                <ResourceMaster />
            ) : activeView === 'overview' ? (
                <OverviewDashboard />
            ) : (
                <FunnelDashboard />
            )}

            {activeView !== 'chat' && (
                <FloatingAssistant
                    session={activeSession}
                    statusMessage={statusMessage}
                    onSendMessage={handleSendMessage}
                    isConnected={isConnected}
                />
            )}
        </div>
    );
}
