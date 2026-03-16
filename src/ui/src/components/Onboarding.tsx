/**
 * OmniCompanion v2 — Onboarding Component
 *
 * Agent personality selector with AI-themed animations.
 * User picks a theme → agent adopts that personality.
 */

import React, { useState, useMemo } from 'react';

interface OnboardingProps {
    onThemeSelected: (theme: string) => void;
}

const themes = [
    {
        id: 'professional',
        name: 'Professional',
        description: 'Clear, concise, and efficient. Like a senior executive assistant.',
        color: '#4a90d9',
        accent: '#00d4aa',
        emoji: '💼',
    },
    {
        id: 'friendly',
        name: 'Friendly',
        description: 'Warm, enthusiastic, and supportive. Like chatting with a helpful friend.',
        color: '#7b68ee',
        accent: '#ff6b9d',
        emoji: '😊',
    },
    {
        id: 'playful',
        name: 'Playful',
        description: 'Creative, witty, and fun. Every task is an adventure!',
        color: '#ff6b6b',
        accent: '#ffd93d',
        emoji: '🎮',
    },
    {
        id: 'minimal',
        name: 'Minimal',
        description: 'Ultra-concise. Maximum clarity, minimum words.',
        color: '#e0e0e0',
        accent: '#00d4aa',
        emoji: '⚡',
    },
];

const Particles: React.FC = () => {
    const particles = useMemo(() => {
        return Array.from({ length: 30 }, (_, i) => ({
            id: i,
            left: `${Math.random() * 100}%`,
            delay: `${Math.random() * 8}s`,
            duration: `${6 + Math.random() * 8}s`,
            size: `${2 + Math.random() * 3}px`,
            opacity: 0.2 + Math.random() * 0.4,
        }));
    }, []);

    return (
        <div className="onboarding-particles">
            {particles.map(p => (
                <div
                    key={p.id}
                    className="onboarding-particle"
                    style={{
                        left: p.left,
                        bottom: '-10px',
                        width: p.size,
                        height: p.size,
                        animationDelay: p.delay,
                        animationDuration: p.duration,
                        opacity: p.opacity,
                    }}
                />
            ))}
        </div>
    );
};

export const Onboarding: React.FC<OnboardingProps> = ({ onThemeSelected }) => {
    const [selectedTheme, setSelectedTheme] = useState<string | null>(null);
    const [transitioning, setTransitioning] = useState(false);

    const handleSelect = (themeId: string) => {
        setSelectedTheme(themeId);
    };

    const handleContinue = () => {
        if (!selectedTheme) return;
        setTransitioning(true);

        // Apply theme colors immediately
        const theme = themes.find(t => t.id === selectedTheme);
        if (theme) {
            document.documentElement.style.setProperty('--color-primary', theme.color);
            document.documentElement.style.setProperty('--color-accent', theme.accent);
            document.documentElement.style.setProperty('--glow-primary', `${theme.color}44`);
            document.documentElement.style.setProperty('--glow-accent', `${theme.accent}44`);
        }

        setTimeout(() => {
            onThemeSelected(selectedTheme);
        }, 600);
    };

    return (
        <div className={`onboarding-container ${transitioning ? 'transition-out' : ''}`}>
            <Particles />

            <h1 className="onboarding-title">OmniCompanion</h1>
            <p className="onboarding-subtitle">Choose your AI companion's personality</p>

            <div className="theme-grid">
                {themes.map(theme => (
                    <div
                        key={theme.id}
                        className={`theme-card ${selectedTheme === theme.id ? 'theme-card-selected' : ''}`}
                        onClick={() => handleSelect(theme.id)}
                        style={{
                            '--color-primary': theme.color,
                            '--glow-primary': `${theme.color}44`,
                        } as React.CSSProperties}
                    >
                        <div
                            className="theme-orb-preview"
                            style={{
                                background: `radial-gradient(circle at 30% 30%, ${theme.color}cc, ${theme.color}44)`,
                                boxShadow: `0 0 24px ${theme.color}55`,
                            }}
                        />

                        <div className="theme-name">
                            {theme.emoji} {theme.name}
                        </div>
                        <div className="theme-description">
                            {theme.description}
                        </div>
                    </div>
                ))}
            </div>

            <button
                className="onboarding-cta"
                onClick={handleContinue}
                disabled={!selectedTheme}
            >
                {selectedTheme ? "Let's Go →" : "Select a Personality"}
            </button>
        </div>
    );
};
