/**
 * OmniCompanion v2 — Activity Feed Component
 *
 * Floating overlay showing real-time agent activity.
 * Auto-dismissing entries with fade animation.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';

interface ActivityItem {
    id: string;
    icon: string;
    text: string;
    level: 'info' | 'success' | 'error';
    timestamp: number;
    fading?: boolean;
}

interface ActivityFeedProps {
    wsRef: React.MutableRefObject<WebSocket | null>;
}

export const ActivityFeed: React.FC<ActivityFeedProps> = ({ wsRef }) => {
    const [items, setItems] = useState<ActivityItem[]>([]);
    const timersRef = useRef<Map<string, number>>(new Map());

    const addItem = useCallback((icon: string, text: string, level: string = 'info') => {
        const id = `act-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

        setItems(prev => {
            // Keep max 5 items
            const updated = [...prev, { id, icon, text, level: level as any, timestamp: Date.now() }];
            return updated.slice(-5);
        });

        // Auto-fade after 4 seconds
        const fadeTimer = window.setTimeout(() => {
            setItems(prev => prev.map(item =>
                item.id === id ? { ...item, fading: true } : item
            ));

            // Remove after fade animation
            const removeTimer = window.setTimeout(() => {
                setItems(prev => prev.filter(item => item.id !== id));
            }, 500);
            timersRef.current.set(`rm-${id}`, removeTimer);
        }, 4000);

        timersRef.current.set(id, fadeTimer);
    }, []);

    // Listen for activity events from WebSocket
    useEffect(() => {
        const handleMessage = (event: MessageEvent) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'activity') {
                    addItem(data.icon || '⚡', data.text || '', data.level || 'info');
                }
            } catch (_) { }
        };

        const ws = wsRef.current;
        if (ws) {
            ws.addEventListener('message', handleMessage);
            return () => ws.removeEventListener('message', handleMessage);
        }
    }, [wsRef.current, addItem]);

    // Cleanup timers on unmount
    useEffect(() => {
        return () => {
            timersRef.current.forEach(timer => clearTimeout(timer));
        };
    }, []);

    if (items.length === 0) return null;

    return (
        <div className="activity-feed">
            {items.map(item => (
                <div
                    key={item.id}
                    className={`activity-item ${item.level} ${item.fading ? 'fading' : ''}`}
                >
                    <span className="activity-icon">{item.icon}</span>
                    <span>{item.text}</span>
                </div>
            ))}
        </div>
    );
};
