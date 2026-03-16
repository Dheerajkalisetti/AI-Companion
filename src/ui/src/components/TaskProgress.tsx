/**
 * OmniCompanion — Task Progress Component
 *
 * Shows current goal and step-by-step execution progress.
 */

import React from 'react';

interface TaskStep {
    id: string;
    description: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
}

interface TaskProgressProps {
    goal: string;
    steps: TaskStep[];
}

const stepIcons: Record<string, string> = {
    pending: '○',
    running: '◉',
    completed: '✓',
    failed: '✗',
};

const stepColors: Record<string, string> = {
    pending: '#666',
    running: '#7b68ee',
    completed: '#00d4aa',
    failed: '#ff4757',
};

export const TaskProgress: React.FC<TaskProgressProps> = ({ goal, steps }) => {
    if (!goal) return null;

    const completedCount = steps.filter(s => s.status === 'completed').length;
    const progress = steps.length > 0 ? (completedCount / steps.length) * 100 : 0;

    return (
        <div style={{
            borderRadius: '8px',
            background: 'rgba(255, 255, 255, 0.05)',
            padding: '8px 10px',
            marginBottom: '8px',
        }}>
            {/* Goal */}
            <div style={{
                fontSize: '11px',
                fontWeight: 600,
                color: '#ccc',
                marginBottom: '6px',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
            }}>
                {goal}
            </div>

            {/* Progress bar */}
            <div style={{
                height: '3px',
                borderRadius: '2px',
                background: 'rgba(255, 255, 255, 0.1)',
                marginBottom: '6px',
                overflow: 'hidden',
            }}>
                <div style={{
                    height: '100%',
                    width: `${progress}%`,
                    borderRadius: '2px',
                    background: 'linear-gradient(90deg, #7b68ee, #00d4aa)',
                    transition: 'width 0.3s ease',
                }} />
            </div>

            {/* Steps */}
            {steps.slice(0, 4).map((step) => (
                <div key={step.id} style={{
                    display: 'flex',
                    alignItems: 'center',
                    fontSize: '10px',
                    padding: '2px 0',
                    color: stepColors[step.status],
                }}>
                    <span style={{ marginRight: '6px', fontSize: '8px' }}>
                        {stepIcons[step.status]}
                    </span>
                    <span style={{
                        flex: 1,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                    }}>
                        {step.description}
                    </span>
                </div>
            ))}

            {steps.length > 4 && (
                <div style={{ fontSize: '9px', color: '#666', marginTop: '2px' }}>
                    +{steps.length - 4} more steps
                </div>
            )}
        </div>
    );
};
