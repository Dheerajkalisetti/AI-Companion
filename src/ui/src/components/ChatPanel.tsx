/**
 * OmniCompanion v2 — Chat Panel Component
 *
 * Slide-up chat panel for text fallback.
 * Hidden by default, toggled via floating button.
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';

interface ChatMessage {
    id: string;
    role: 'user' | 'companion' | 'system';
    text: string;
    timestamp: number;
}

interface ChatPanelProps {
    isOpen: boolean;
    onToggle: () => void;
    wsRef: React.MutableRefObject<WebSocket | null>;
    connected: boolean;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({
    isOpen,
    onToggle,
    wsRef,
    connected,
}) => {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [input, setInput] = useState('');
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // Auto-scroll
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    // Listen for companion messages
    useEffect(() => {
        const handleMessage = (event: MessageEvent) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'companion_message') {
                    setMessages(prev => [...prev, {
                        id: `comp-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
                        role: 'companion',
                        text: data.text || '',
                        timestamp: data.timestamp ? data.timestamp * 1000 : Date.now(),
                    }]);
                } else if (data.type === 'action_result') {
                    const icon = data.success ? '✅' : '❌';
                    setMessages(prev => [...prev, {
                        id: `sys-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
                        role: 'system',
                        text: `${icon} ${data.action}: ${data.detail || ''}`,
                        timestamp: Date.now(),
                    }]);
                }
            } catch (_) { }
        };

        const ws = wsRef.current;
        if (ws) {
            ws.addEventListener('message', handleMessage);
            return () => ws.removeEventListener('message', handleMessage);
        }
    }, [wsRef.current]);

    const handleSend = useCallback((e?: React.FormEvent) => {
        e?.preventDefault();
        const text = input.trim();
        if (!text || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

        // Send as text message
        wsRef.current.send(JSON.stringify({ type: 'message', text }));

        // Add to local messages
        setMessages(prev => [...prev, {
            id: `user-${Date.now()}`,
            role: 'user',
            text,
            timestamp: Date.now(),
        }]);

        setInput('');
    }, [input, wsRef]);

    return (
        <>
            {/* Toggle Button */}
            <button className="chat-toggle-btn" onClick={onToggle} title="Toggle chat">
                {isOpen ? '✕' : '💬'}
            </button>

            {/* Panel */}
            {isOpen && (
                <div className="chat-panel">
                    <div className="chat-panel-header">
                        <span className="chat-panel-title">Chat</span>
                        <button className="chat-close-btn" onClick={onToggle}>✕</button>
                    </div>

                    <div className="chat-messages">
                        {messages.length === 0 && (
                            <div className="chat-msg system">
                                Type a message or use voice instead
                            </div>
                        )}
                        {messages.map(msg => (
                            <div key={msg.id} className={`chat-msg ${msg.role}`}>
                                {msg.text}
                            </div>
                        ))}
                        <div ref={messagesEndRef} />
                    </div>

                    <div className="chat-input-area">
                        <form onSubmit={handleSend} style={{ margin: 0 }}>
                            <div className="chat-input-row">
                                <input
                                    type="text"
                                    className="chat-input"
                                    value={input}
                                    onChange={e => setInput(e.target.value)}
                                    placeholder={connected ? "Type a message..." : "Connecting..."}
                                    disabled={!connected}
                                    autoFocus
                                />
                                <button
                                    type="submit"
                                    className="chat-send-btn"
                                    disabled={!connected || !input.trim()}
                                >
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <line x1="22" y1="2" x2="11" y2="13"></line>
                                        <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                                    </svg>
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </>
    );
};
