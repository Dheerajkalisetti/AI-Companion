/**
 * OmniCompanion v2 — Main Application
 *
 * Voice-first multimodal AI companion interface.
 * Three screens: Onboarding → Main Experience → Chat Fallback
 *
 * The agent speaks first, the chatbox is hidden,
 * and voice is the default interaction mode.
 */

import React, { useState, useCallback, useEffect, useRef } from 'react';
import { Onboarding } from './components/Onboarding';
import { ReactiveOrb } from './components/ReactiveOrb';
import { VoiceEngine } from './components/VoiceEngine';
import { ActivityFeed } from './components/ActivityFeed';
import { ChatPanel } from './components/ChatPanel';
import './styles_v2.css';

type AgentState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'acting';

const WS_URL = 'ws://127.0.0.1:8765';

const App: React.FC = () => {
    // ─── State ───────────────────────────────────────
    const [screen, setScreen] = useState<'onboarding' | 'main'>('onboarding');
    const [agentState, setAgentState] = useState<AgentState>('idle');
    const [connected, setConnected] = useState(false);
    const [lastResponse, setLastResponse] = useState('');
    const [interimText, setInterimText] = useState('');
    const [chatOpen, setChatOpen] = useState(false);
    const [voiceActive, setVoiceActive] = useState(false);
    const [isListening, setIsListening] = useState(false);
    const [isSpeaking, setIsSpeaking] = useState(false);
    const [selectedTheme, setSelectedTheme] = useState('friendly');
    const [colorPrimary, setColorPrimary] = useState('#7b68ee');
    const [colorAccent, setColorAccent] = useState('#00d4aa');

    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimerRef = useRef<number | null>(null);
    const handleWSMessageRef = useRef<(data: any) => void>(() => {});

    // ─── Handle incoming WS messages ─────────────────
    // Using a ref to avoid stale closures in WebSocket callbacks
    handleWSMessageRef.current = (data: any) => {
        switch (data.type) {
            case 'status':
                const stateMap: Record<string, AgentState> = {
                    idle: 'idle',
                    listening: 'listening',
                    thinking: 'thinking',
                    speaking: 'speaking',
                    acting: 'acting',
                    active: 'acting',
                };
                const newState = stateMap[data.state] || 'idle';
                setAgentState(newState);
                break;

            case 'companion_message':
                setLastResponse(data.text || '');
                break;

            case 'theme_applied':
                if (data.colors) {
                    setColorPrimary(data.colors.primary || '#7b68ee');
                    setColorAccent(data.colors.accent || '#00d4aa');
                }
                break;

            case 'welcome':
                // Engine connected — set initial listening state
                setAgentState('listening');
                break;
        }
    };

    // ─── WebSocket Connection ────────────────────────
    const connectWS = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return;

        const ws = new WebSocket(WS_URL);

        ws.onopen = () => {
            setConnected(true);
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                handleWSMessageRef.current(data);
            } catch (e) {
                console.error('Invalid WS message:', event.data);
            }
        };

        ws.onclose = () => {
            setConnected(false);
            setAgentState('idle');
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

    // ─── Derive display state (merge listening/speaking overlay) ──
    const displayState: AgentState = isSpeaking ? 'speaking' : isListening && agentState === 'idle' ? 'listening' : agentState;

    // ─── Agent state label ───────────────────────────
    const stateLabels: Record<AgentState, string> = {
        idle: 'Ready',
        listening: 'Listening...',
        thinking: 'Thinking...',
        speaking: 'Speaking...',
        acting: 'Executing...',
    };

    // ─── Theme Selection ─────────────────────────────
    const handleThemeSelected = useCallback((theme: string) => {
        setSelectedTheme(theme);
        setScreen('main');
        setVoiceActive(true);

        // Tell backend about theme selection
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({
                type: 'select_theme',
                theme,
            }));
        }
    }, []);

    // ─── Toggle mic ──────────────────────────────────
    const handleMicToggle = useCallback(() => {
        setVoiceActive(prev => !prev);
    }, []);

    // ─── Render ──────────────────────────────────────
    if (screen === 'onboarding') {
        return <Onboarding onThemeSelected={handleThemeSelected} />;
    }

    return (
        <div className="main-container">
            {/* Voice Engine (invisible component) */}
            <VoiceEngine
                isActive={voiceActive}
                wsRef={wsRef}
                onListeningChange={setIsListening}
                onSpeakingChange={setIsSpeaking}
                onInterimTranscript={setInterimText}
            />

            {/* Status Bar */}
            <div className="status-bar">
                <span className="status-bar-title">OMNICOMPANION</span>
                <div className="status-indicator">
                    <div className={`status-dot ${connected ? 'connected' : 'disconnected'}`} />
                    <span>{connected ? 'Connected' : 'Connecting...'}</span>
                </div>
            </div>

            {/* Orb + State Display */}
            <div className="orb-container">
                <div className="orb-wrapper">
                    <ReactiveOrb
                        state={displayState}
                        colorPrimary={colorPrimary}
                        colorAccent={colorAccent}
                    />
                </div>

                <div className="orb-state-label" style={{
                    color: displayState === 'speaking' ? colorAccent :
                        displayState === 'thinking' ? '#9b59b6' :
                            displayState === 'acting' ? '#e67e22' :
                                displayState === 'listening' ? colorAccent :
                                    'rgba(255,255,255,0.4)'
                }}>
                    {stateLabels[displayState]}
                </div>

                {/* Last response or interim transcript */}
                {(lastResponse || interimText) && (
                    <div className="orb-response-text">
                        {interimText ? (
                            <span style={{ color: 'rgba(255,255,255,0.5)', fontStyle: 'italic' }}>
                                {interimText}
                            </span>
                        ) : (
                            lastResponse
                        )}
                    </div>
                )}
            </div>

            {/* Mic Area */}
            <div className="mic-area">
                <button
                    className={`mic-button ${voiceActive && isListening ? 'active' : ''}`}
                    onClick={handleMicToggle}
                    title={voiceActive ? 'Mute microphone' : 'Unmute microphone'}
                >
                    {voiceActive ? (
                        <svg className="mic-icon" viewBox="0 0 24 24">
                            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                            <line x1="12" y1="19" x2="12" y2="23" />
                            <line x1="8" y1="23" x2="16" y2="23" />
                        </svg>
                    ) : (
                        <svg className="mic-icon" viewBox="0 0 24 24">
                            <line x1="1" y1="1" x2="23" y2="23" />
                            <path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6" />
                            <path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2c0 .31-.02.61-.06.91" />
                            <line x1="12" y1="19" x2="12" y2="23" />
                            <line x1="8" y1="23" x2="16" y2="23" />
                        </svg>
                    )}
                </button>

                {/* Waveform when listening */}
                {voiceActive && isListening && (
                    <WaveformBars />
                )}

                <span className="mic-label">
                    {voiceActive
                        ? (isListening ? 'Listening — speak now' : 'Mic active')
                        : 'Tap to unmute'
                    }
                </span>
            </div>

            {/* Activity Feed */}
            <ActivityFeed wsRef={wsRef} />

            {/* Chat Panel (hidden by default) */}
            <ChatPanel
                isOpen={chatOpen}
                onToggle={() => setChatOpen(!chatOpen)}
                wsRef={wsRef}
                connected={connected}
            />
        </div>
    );
};

/* Simple waveform visualization */
const WaveformBars: React.FC = () => {
    const [bars, setBars] = useState<number[]>([3, 6, 4, 8, 5, 7, 3, 5, 6, 4]);

    useEffect(() => {
        const interval = setInterval(() => {
            setBars(prev =>
                prev.map(() => 3 + Math.random() * 17)
            );
        }, 100);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="waveform">
            {bars.map((h, i) => (
                <div
                    key={i}
                    className="waveform-bar"
                    style={{ height: `${h}px` }}
                />
            ))}
        </div>
    );
};

export default App;
