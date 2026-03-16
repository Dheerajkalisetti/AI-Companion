/**
 * OmniCompanion — Avatar Component
 *
 * WebGL 2.5D character rendered via Three.js with
 * idle, active, and speaking animation states.
 */

import React, { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Sphere, MeshDistortMaterial } from '@react-three/drei';
import * as THREE from 'three';

interface AvatarMeshProps {
    state: 'idle' | 'active' | 'speaking';
}

const AvatarMesh: React.FC<AvatarMeshProps> = ({ state }) => {
    const meshRef = useRef<THREE.Mesh>(null);

    // Animation parameters based on state
    const distortSpeed = useMemo(() => {
        switch (state) {
            case 'idle': return 0.5;
            case 'active': return 2.0;
            case 'speaking': return 4.0;
        }
    }, [state]);

    const distortAmount = useMemo(() => {
        switch (state) {
            case 'idle': return 0.2;
            case 'active': return 0.4;
            case 'speaking': return 0.6;
        }
    }, [state]);

    const color = useMemo(() => {
        switch (state) {
            case 'idle': return '#4a90d9';
            case 'active': return '#7b68ee';
            case 'speaking': return '#00d4aa';
        }
    }, [state]);

    useFrame((_, delta) => {
        if (meshRef.current) {
            meshRef.current.rotation.y += delta * 0.3;

            // Gentle floating animation
            meshRef.current.position.y = Math.sin(Date.now() * 0.001) * 0.1;
        }
    });

    return (
        <Sphere ref={meshRef} args={[1, 64, 64]} scale={1.2}>
            <MeshDistortMaterial
                color={color}
                roughness={0.2}
                metalness={0.8}
                distort={distortAmount}
                speed={distortSpeed}
                envMapIntensity={0.5}
            />
        </Sphere>
    );
};

// Eye component
const Eye: React.FC<{ position: [number, number, number] }> = ({ position }) => {
    const meshRef = useRef<THREE.Mesh>(null);

    useFrame(() => {
        if (meshRef.current) {
            // Subtle eye movement
            meshRef.current.position.x = position[0] + Math.sin(Date.now() * 0.002) * 0.02;
        }
    });

    return (
        <mesh ref={meshRef} position={position}>
            <sphereGeometry args={[0.12, 16, 16]} />
            <meshStandardMaterial color="#ffffff" emissive="#ffffff" emissiveIntensity={0.5} />
        </mesh>
    );
};

interface AvatarProps {
    state: 'idle' | 'active' | 'speaking';
}

export const Avatar: React.FC<AvatarProps> = ({ state }) => {
    return (
        <div style={{ width: '100%', height: '100%' }}>
            <Canvas camera={{ position: [0, 0, 3], fov: 50 }}>
                <ambientLight intensity={0.4} />
                <pointLight position={[10, 10, 10]} intensity={1} />
                <pointLight position={[-10, -10, -10]} intensity={0.5} color="#7b68ee" />

                <AvatarMesh state={state} />
                <Eye position={[-0.3, 0.2, 0.9]} />
                <Eye position={[0.3, 0.2, 0.9]} />
            </Canvas>

            {/* State indicator */}
            <div style={{
                position: 'absolute',
                bottom: '4px',
                left: '50%',
                transform: 'translateX(-50%)',
                fontSize: '10px',
                color: state === 'idle' ? '#888' : state === 'active' ? '#7b68ee' : '#00d4aa',
                textTransform: 'uppercase',
                letterSpacing: '1px',
            }}>
                {state}
            </div>
        </div>
    );
};
