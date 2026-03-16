/**
 * OmniCompanion v2 — Reactive Orb Component
 *
 * Three.js animated orb that replaces the basic avatar.
 * Responds to agent state with distinct visual treatments:
 * idle, listening, thinking, speaking, acting.
 */

import React, { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Sphere, MeshDistortMaterial } from '@react-three/drei';
import * as THREE from 'three';

type OrbState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'acting';

interface OrbMeshProps {
    state: OrbState;
    colorPrimary?: string;
    colorAccent?: string;
}

const OrbMesh: React.FC<OrbMeshProps> = ({
    state,
    colorPrimary = '#7b68ee',
    colorAccent = '#00d4aa',
}) => {
    const meshRef = useRef<THREE.Mesh>(null);
    const timeRef = useRef(0);

    const stateConfig = useMemo(() => {
        switch (state) {
            case 'idle':
                return {
                    color: colorPrimary,
                    emissive: colorPrimary,
                    emissiveIntensity: 0.15,
                    distort: 0.2,
                    speed: 0.8,
                    scale: 1.0,
                    rotationSpeed: 0.15,
                };
            case 'listening':
                return {
                    color: colorAccent,
                    emissive: colorAccent,
                    emissiveIntensity: 0.3,
                    distort: 0.35,
                    speed: 2.0,
                    scale: 1.05,
                    rotationSpeed: 0.3,
                };
            case 'thinking':
                return {
                    color: '#9b59b6',
                    emissive: '#8e44ad',
                    emissiveIntensity: 0.4,
                    distort: 0.5,
                    speed: 3.5,
                    scale: 1.08,
                    rotationSpeed: 0.6,
                };
            case 'speaking':
                return {
                    color: colorAccent,
                    emissive: colorAccent,
                    emissiveIntensity: 0.5,
                    distort: 0.6,
                    speed: 4.5,
                    scale: 1.12,
                    rotationSpeed: 0.4,
                };
            case 'acting':
                return {
                    color: '#e67e22',
                    emissive: '#f39c12',
                    emissiveIntensity: 0.5,
                    distort: 0.45,
                    speed: 5.0,
                    scale: 1.1,
                    rotationSpeed: 0.8,
                };
        }
    }, [state, colorPrimary, colorAccent]);

    useFrame((_, delta) => {
        timeRef.current += delta;
        if (meshRef.current) {
            // Smooth rotation
            meshRef.current.rotation.y += delta * stateConfig.rotationSpeed;
            meshRef.current.rotation.x = Math.sin(timeRef.current * 0.5) * 0.1;

            // Floating motion
            meshRef.current.position.y = Math.sin(timeRef.current * 0.8) * 0.12;

            // Scale breathing
            const breathe = 1 + Math.sin(timeRef.current * 1.5) * 0.02;
            const targetScale = stateConfig.scale * breathe;
            meshRef.current.scale.lerp(
                new THREE.Vector3(targetScale, targetScale, targetScale),
                delta * 3
            );
        }
    });

    return (
        <Sphere ref={meshRef} args={[1, 128, 128]} scale={stateConfig.scale}>
            <MeshDistortMaterial
                color={stateConfig.color}
                emissive={stateConfig.emissive}
                emissiveIntensity={stateConfig.emissiveIntensity}
                roughness={0.15}
                metalness={0.85}
                distort={stateConfig.distort}
                speed={stateConfig.speed}
                envMapIntensity={0.4}
                transparent
                opacity={0.92}
            />
        </Sphere>
    );
};

/* Orbital ring particle */
const OrbitalRing: React.FC<{ state: OrbState; colorAccent: string }> = ({ state, colorAccent }) => {
    const ringRef = useRef<THREE.Group>(null);

    const visible = state !== 'idle';

    useFrame((_, delta) => {
        if (ringRef.current) {
            ringRef.current.rotation.z += delta * 0.5;
            ringRef.current.rotation.x += delta * 0.2;
        }
    });

    if (!visible) return null;

    return (
        <group ref={ringRef}>
            <mesh>
                <torusGeometry args={[1.8, 0.015, 8, 64]} />
                <meshStandardMaterial
                    color={colorAccent}
                    emissive={colorAccent}
                    emissiveIntensity={0.8}
                    transparent
                    opacity={0.4}
                />
            </mesh>
        </group>
    );
};

/* Inner glow effect */
const InnerGlow: React.FC<{ state: OrbState; colorPrimary: string }> = ({ state, colorPrimary }) => {
    const glowRef = useRef<THREE.Mesh>(null);
    const timeRef = useRef(0);

    useFrame((_, delta) => {
        timeRef.current += delta;
        if (glowRef.current) {
            const pulse = state === 'idle' ? 0.02 : 0.06;
            const speed = state === 'thinking' ? 3 : 1.5;
            const scale = 0.6 + Math.sin(timeRef.current * speed) * pulse;
            glowRef.current.scale.set(scale, scale, scale);
        }
    });

    return (
        <mesh ref={glowRef}>
            <sphereGeometry args={[0.6, 32, 32]} />
            <meshStandardMaterial
                color="#ffffff"
                emissive={colorPrimary}
                emissiveIntensity={1.2}
                transparent
                opacity={0.15}
            />
        </mesh>
    );
};

interface ReactiveOrbProps {
    state: OrbState;
    colorPrimary?: string;
    colorAccent?: string;
}

export const ReactiveOrb: React.FC<ReactiveOrbProps> = ({
    state,
    colorPrimary = '#7b68ee',
    colorAccent = '#00d4aa',
}) => {
    return (
        <div style={{ width: '100%', height: '100%' }}>
            <Canvas camera={{ position: [0, 0, 4], fov: 45 }} gl={{ antialias: true, alpha: true }}>
                <ambientLight intensity={0.3} />
                <pointLight position={[5, 5, 5]} intensity={0.8} color="#ffffff" />
                <pointLight position={[-5, -3, 3]} intensity={0.4} color={colorPrimary} />
                <pointLight position={[0, -5, 0]} intensity={0.2} color={colorAccent} />

                <OrbMesh state={state} colorPrimary={colorPrimary} colorAccent={colorAccent} />
                <OrbitalRing state={state} colorAccent={colorAccent} />
                <InnerGlow state={state} colorPrimary={colorPrimary} />
            </Canvas>
        </div>
    );
};
