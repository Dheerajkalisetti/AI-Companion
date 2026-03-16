/**
 * OmniCompanion — Main React Application
 *
 * Connects to the Python backend via WebSocket. The UI is now
 * a conversational interface representing the companion's brain,
 * supporting natural chat, action feedback, and agent statuses.
 */

import React, { useState, useCallback, useEffect, useRef } from 'react';
import { PiPWindow } from './components/PiPWindow';
import { Avatar } from './components/Avatar';
import { VoiceIndicator } from './components/VoiceIndicator';

interface Message {
    id: string;
    role: 'user' | 'companion' | 'system';
    text: string;
    hasAction?: boolean;
    timestamp: number;
}

const WS_URL = 'ws://127.0.0.1:8765';

const App: React.FC = () => {
    const [avatarState, setAvatarState] = useState<'idle' | 'active' | 'speaking' | 'thinking'>('idle');
    const [isListening, setIsListening] = useState(false);
    const [goalInput, setGoalInput] = useState('');
    const [connected, setConnected] = useState(false);
    const [messages, setMessages] = useState<Message[]>([
        {
            id: 'init-1',
            role: 'system',
            text: 'OmniCompanion UI ready — waiting for engine connection...',
            timestamp: Date.now(),
        }
    ]);

    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimerRef = useRef<number | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom of chat
    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    // ─── WebSocket Connection ────────────────────────────
    const connectWS = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return;

        const ws = new WebSocket(WS_URL);

        ws.onopen = () => {
            setConnected(true);
            setMessages(prev => [...prev.filter(m => m.role !== 'system'), {
                id: `sys-${Date.now()}`,
                role: 'system',
                text: '🟢 Connected to OmniCompanion Engine',
                timestamp: Date.now(),
            }]);
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                handleWSMessage(data);
            } catch (e) {
                console.error('Invalid WS message:', event.data);
            }
        };

        ws.onclose = () => {
            setConnected(false);
            setAvatarState('idle');
            // Auto-reconnect every 3 seconds
            if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
            reconnectTimerRef.current = window.setTimeout(connectWS, 3000);
        };

        ws.onerror = () => {
            ws.close();
        };

        wsRef.current = ws;
    }, []);

    useEffect(() => {
        connectWS();
        return () => {
            if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
            wsRef.current?.close();
        };
    }, [connectWS]);

    // ─── Handle incoming messages ────────────────────────
    const handleWSMessage = useCallback((data: any) => {
        switch (data.type) {
            case 'companion_message':
                setMessages(prev => [...prev, {
                    id: `comp-${Date.now()}-${Math.random()}`,
                    role: 'companion',
                    text: data.text || '',
                    hasAction: data.has_action,
                    timestamp: data.timestamp ? data.timestamp * 1000 : Date.now(),
                }]);
                break;

            case 'action_result':
                const icon = data.success ? '✅' : '❌';
                setMessages(prev => [...prev, {
                    id: `sys-${Date.now()}-${Math.random()}`,
                    role: 'system',
                    text: `${icon} Action '${data.action}': ${data.detail}`,
                    timestamp: data.timestamp ? data.timestamp * 1000 : Date.now(),
                }]);
                break;

            case 'status':
                if (['idle', 'active', 'speaking', 'thinking'].includes(data.state)) {
                    setAvatarState(data.state);
                }
                break;

            case 'log':
                // Optional: You could show logs in a separate debug window or inline for major errors
                if (data.status === 'error') {
                    setMessages(prev => [...prev, {
                        id: `sys-${Date.now()}-${Math.random()}`,
                        role: 'system',
                        text: `⚠️ System Error: ${data.message}`,
                        timestamp: data.timestamp ? data.timestamp * 1000 : Date.now(),
                    }]);
                }
                break;
        }
    }, []);

    // ─── Send message to engine ──────────────────────────
    const handleGoalSubmit = useCallback((e?: React.FormEvent) => {
        e?.preventDefault();
        const text = goalInput.trim();
        if (!text || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

        wsRef.current.send(JSON.stringify({ type: 'message', text }));

        setMessages(prev => [...prev, {
            id: `user-${Date.now()}`,
            role: 'user',
            text: text,
            timestamp: Date.now(),
        }]);

        setGoalInput('');
        setAvatarState('thinking'); // Optimistic UI update
    }, [goalInput]);

    return (
        <PiPWindow>
            <div style={{
                display: 'flex',
                flexDirection: 'column',
                height: '100%',
                background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
                borderRadius: '16px',
                overflow: 'hidden',
                fontFamily: "'Inter', -apple-system, sans-serif",
                color: '#e0e0e0',
            }}>
                {/* Connection status bar */}
                <div style={{
                    padding: '6px 16px',
                    fontSize: '11px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    background: 'rgba(0,0,0,0.2)',
                    backdropFilter: 'blur(5px)',
                    borderBottom: '1px solid rgba(255,255,255,0.05)',
                    ...({ WebkitAppRegion: 'drag' } as any),
                }}>
                    <span style={{ fontWeight: 600, color: 'rgba(255,255,255,0.8)' }}>OmniCompanion</span>
                    <span style={{ color: connected ? '#00d4aa' : '#ff6b6b' }}>
                        {connected ? '● Connected' : '○ Connecting...'}
                    </span>
                </div>

                {/* Avatar Header section */}
                <div style={{
                    padding: '20px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    position: 'relative',
                    borderBottom: '1px solid rgba(255,255,255,0.05)',
                }}>
                    <Avatar state={avatarState === 'thinking' ? 'active' : avatarState} />
                    {isListening && <VoiceIndicator />}
                    {avatarState === 'thinking' && (
                        <div style={{
                            position: 'absolute',
                            right: '25%',
                            top: '25%',
                            fontSize: '20px',
                            animation: 'bounce 1.5s infinite',
                        }}>
                            💭
                        </div>
                    )}
                </div>

                {/* Chat History */}
                <div style={{
                    flex: 1,
                    overflowY: 'auto',
                    padding: '16px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px',
                    scrollBehavior: 'smooth',
                }}>
                    {messages.map(msg => (
                        <div key={msg.id} style={{
                            alignSelf: msg.role === 'user' ? 'flex-end' : (msg.role === 'system' ? 'center' : 'flex-start'),
                            maxWidth: msg.role === 'system' ? '90%' : '85%',
                            padding: msg.role === 'system' ? '6px 12px' : '10px 14px',
                            borderRadius: msg.role === 'user' ? '16px 16px 4px 16px' : (msg.role === 'system' ? '8px' : '16px 16px 16px 4px'),
                            background: msg.role === 'user' ? 'linear-gradient(135deg, #7b68ee, #4a90d9)' : (msg.role === 'system' ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.1)'),
                            border: msg.role === 'system' ? '1px solid rgba(255,255,255,0.1)' : 'none',
                            color: msg.role === 'system' ? 'rgba(255,255,255,0.6)' : '#fff',
                            fontSize: msg.role === 'system' ? '11px' : '13px',
                            lineHeight: 1.4,
                            boxShadow: msg.role === 'system' ? 'none' : '0 4px 12px rgba(0,0,0,0.1)',
                            wordBreak: 'break-word',
                        }}>
                            {msg.text}
                            {msg.hasAction && (
                                <div style={{
                                    marginTop: '6px',
                                    fontSize: '11px',
                                    color: 'rgba(255,255,255,0.6)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '4px'
                                }}>
                                    <span>⚡ Executing action...</span>
                                </div>
                            )}
                        </div>
                    ))}
                    <div ref={messagesEndRef} />
                </div>

                {/* Input Area */}
                <div style={{ padding: '16px', background: 'rgba(0,0,0,0.2)' }}>
                    <form onSubmit={handleGoalSubmit} style={{ margin: 0 }}>
                        <div style={{
                            display: 'flex',
                            gap: '10px',
                            background: 'rgba(255,255,255,0.05)',
                            padding: '6px',
                            borderRadius: '24px',
                            border: '1px solid rgba(255,255,255,0.1)',
                        }}>
                            <input
                                type="text"
                                value={goalInput}
                                onChange={(e) => setGoalInput(e.target.value)}
                                placeholder={connected ? "Ask me anything..." : "Waiting for connection..."}
                                disabled={!connected}
                                style={{
                                    flex: 1,
                                    padding: '8px 16px',
                                    background: 'transparent',
                                    border: 'none',
                                    color: '#e0e0e0',
                                    fontSize: '14px',
                                    outline: 'none',
                                    ...({ WebkitAppRegion: 'no-drag' } as any),
                                }}
                            />
                            <button
                                type="submit"
                                disabled={!connected || !goalInput.trim()}
                                style={{
                                    width: '36px',
                                    height: '36px',
                                    borderRadius: '50%',
                                    background: connected ? (goalInput.trim() ? '#00d4aa' : 'rgba(255,255,255,0.1)') : 'rgba(255,255,255,0.05)',
                                    border: 'none',
                                    color: '#fff',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    cursor: connected && goalInput.trim() ? 'pointer' : 'default',
                                    transition: 'background 0.2s',
                                    ...({ WebkitAppRegion: 'no-drag' } as any),
                                }}
                            >
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <line x1="22" y1="2" x2="11" y2="13"></line>
                                    <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                                </svg>
                            </button>
                        </div>
                    </form>
                </div>

                {/* CSS for think animation */}
                <style dangerouslySetInnerHTML={{
                    __html: `
                    @keyframes bounce {
                        0%, 100% { transform: translateY(0); }
                        50% { transform: translateY(-10px); }
                    }
                `}} />
            </div>
        </PiPWindow>
    );
};

export default App;
