/**
 * OmniCompanion — Execution Log Component
 *
 * Real-time scrolling log of agent actions and decisions.
 */

import React, { useRef, useEffect } from 'react';

interface LogEntry {
    timestamp: string;
    agent: string;
    action: string;
    status: 'info' | 'success' | 'error' | 'warning';
}

interface ExecutionLogProps {
    entries: LogEntry[];
}

const statusColors: Record<string, string> = {
    info: '#888',
    success: '#00d4aa',
    error: '#ff4757',
    warning: '#ffa502',
};

const agentColors: Record<string, string> = {
    system: '#888',
    planner: '#7b68ee',
    vision: '#4a90d9',
    executor: '#ff6b81',
    browser: '#1dd1a1',
    memory: '#feca57',
    verifier: '#54a0ff',
    safety: '#ff6348',
};

export const ExecutionLog: React.FC<ExecutionLogProps> = ({ entries }) => {
    const scrollRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom on new entries
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [entries.length]);

    return (
        <div style={{
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
        }}>
            <div style={{
                fontSize: '9px',
                color: '#666',
                textTransform: 'uppercase',
                letterSpacing: '1px',
                marginBottom: '4px',
            }}>
                Execution Log
            </div>

            <div
                ref={scrollRef}
                style={{
                    flex: 1,
                    overflowY: 'auto',
                    overflowX: 'hidden',
                    fontSize: '10px',
                    lineHeight: '1.5',
                    scrollbarWidth: 'thin',
                }}
            >
                {entries.map((entry, i) => (
                    <div key={i} style={{
                        display: 'flex',
                        padding: '1px 0',
                        borderBottom: '1px solid rgba(255,255,255,0.03)',
                    }}>
                        {/* Timestamp */}
                        <span style={{
                            color: '#555',
                            fontSize: '9px',
                            minWidth: '50px',
                            flexShrink: 0,
                        }}>
                            {new Date(entry.timestamp).toLocaleTimeString('en-US', {
                                hour12: false,
                                hour: '2-digit',
                                minute: '2-digit',
                                second: '2-digit',
                            })}
                        </span>

                        {/* Agent tag */}
                        <span style={{
                            color: agentColors[entry.agent] || '#888',
                            minWidth: '55px',
                            flexShrink: 0,
                            fontWeight: 600,
                            fontSize: '9px',
                        }}>
                            {entry.agent}
                        </span>

                        {/* Action */}
                        <span style={{
                            color: statusColors[entry.status],
                            flex: 1,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                        }}>
                            {entry.action}
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
};
