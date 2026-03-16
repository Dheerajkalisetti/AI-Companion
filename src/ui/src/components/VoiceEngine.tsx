/**
 * OmniCompanion v2 — Voice Engine (Gemini Live Audio)
 *
 * Audio is now handled entirely by the Python backend via PyAudio
 * + Gemini Live API. This component is a THIN STATUS LISTENER only.
 *
 * It listens for status updates from the WebSocket to drive UI state.
 * No browser Speech API needed.
 */

import React, { useEffect } from 'react';

interface VoiceEngineProps {
    isActive: boolean;
    wsRef: React.MutableRefObject<WebSocket | null>;
    onListeningChange: (listening: boolean) => void;
    onSpeakingChange: (speaking: boolean) => void;
    onInterimTranscript: (text: string) => void;
}

export const VoiceEngine: React.FC<VoiceEngineProps> = ({
    isActive,
    wsRef,
    onListeningChange,
    onSpeakingChange,
    onInterimTranscript,
}) => {
    useEffect(() => {
        const handleWSMessage = (event: MessageEvent) => {
            try {
                const data = JSON.parse(event.data);

                if (data.type === 'status') {
                    const state = data.state || 'idle';
                    onListeningChange(state === 'listening');
                    onSpeakingChange(state === 'speaking');
                }

                if (data.type === 'companion_message') {
                    // Show the text transcript of what the AI said
                    if (data.text) {
                        onInterimTranscript('');
                    }
                }
            } catch (_) { }
        };

        const ws = wsRef.current;
        if (ws) {
            ws.addEventListener('message', handleWSMessage);
            return () => ws.removeEventListener('message', handleWSMessage);
        }
    }, [wsRef.current, onListeningChange, onSpeakingChange, onInterimTranscript]);

    // This component is invisible — audio is handled by Python backend
    return null;
};
