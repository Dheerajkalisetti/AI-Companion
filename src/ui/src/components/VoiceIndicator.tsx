/**
 * OmniCompanion — Voice Indicator Component
 *
 * Animated waveform visualization during speech.
 */

import React, { useState, useEffect } from 'react';

export const VoiceIndicator: React.FC = () => {
    const [bars, setBars] = useState<number[]>([0.3, 0.6, 0.9, 0.5, 0.7]);

    useEffect(() => {
        const interval = setInterval(() => {
            setBars(prev => prev.map(() => 0.2 + Math.random() * 0.8));
        }, 100);
        return () => clearInterval(interval);
    }, []);

    return (
        <div style={{
            position: 'absolute',
            bottom: '8px',
            display: 'flex',
            gap: '2px',
            alignItems: 'flex-end',
            height: '16px',
        }}>
            {bars.map((height, i) => (
                <div
                    key={i}
                    style={{
                        width: '3px',
                        height: `${height * 16}px`,
                        borderRadius: '1.5px',
                        background: '#00d4aa',
                        transition: 'height 0.1s ease',
                    }}
                />
            ))}
        </div>
    );
};
