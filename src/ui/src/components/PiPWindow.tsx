/**
 * OmniCompanion — PiP Window Component
 *
 * Draggable, resizable container for the companion overlay.
 */

import React, { useRef, useState, useCallback, useEffect } from 'react';

interface PiPWindowProps {
    children: React.ReactNode;
}

export const PiPWindow: React.FC<PiPWindowProps> = ({ children }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const [isDragging, setIsDragging] = useState(false);
    const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });

    const handleMouseDown = useCallback((e: React.MouseEvent) => {
        if ((e.target as HTMLElement).classList.contains('drag-handle')) {
            setIsDragging(true);
            setDragOffset({
                x: e.clientX,
                y: e.clientY,
            });
        }
    }, []);

    return (
        <div
            ref={containerRef}
            style={{
                width: '100%',
                height: '100vh',
                userSelect: 'none',
                cursor: isDragging ? 'grabbing' : 'default',
            }}
            onMouseDown={handleMouseDown}
        >
            {/* Drag Handle */}
            <div
                className="drag-handle"
                style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    height: '24px',
                    cursor: 'grab',
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    zIndex: 100,
                }}
            >
                <div style={{
                    width: '40px',
                    height: '4px',
                    borderRadius: '2px',
                    background: 'rgba(255, 255, 255, 0.3)',
                }} />
            </div>

            {/* Content */}
            {children}
        </div>
    );
};
