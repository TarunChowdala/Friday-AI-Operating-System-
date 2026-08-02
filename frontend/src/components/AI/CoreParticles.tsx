import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { AssistantState } from '../../types';

interface Particle {
  theta: number;
  phi: number;
  radius: number;
  speed: number;
  phase: number;
  size: number;
  brightness: number;
}

const PARTICLE_COUNT = 180;

export function CoreParticles({ state }: { state: AssistantState }) {
  const meshRef = useRef<THREE.InstancedMesh>(null!);
  const dummy = useMemo(() => new THREE.Object3D(), []);

  const particles: Particle[] = useMemo(() =>
    Array.from({ length: PARTICLE_COUNT }, () => ({
      theta: Math.random() * Math.PI * 2,
      phi: Math.acos(2 * Math.random() - 1),
      radius: Math.random() * 2.5 + 1.4,
      speed: (Math.random() - 0.5) * 0.6 + 0.15,
      phase: Math.random() * Math.PI * 2,
      size: Math.random() * 0.04 + 0.02,
      brightness: Math.random() * 0.6 + 0.4,
    })),
  []);

  const mat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: '#00b4ff',
        emissive: '#00b4ff',
        emissiveIntensity: 3,
        transparent: true,
        opacity: 0.9,
        roughness: 0,
        metalness: 1,
      }),
    []
  );

  useFrame(({ clock }) => {
    if (!meshRef.current) return;
    const t = clock.getElapsedTime();

    const speedMult = state === 'thinking' ? 2.5 : state === 'speaking' ? 1.8 : state === 'listening' ? 1.3 : 1;
    const radiusMult = state === 'thinking' ? 0.55 : state === 'speaking' ? 1.4 : 1;

    particles.forEach((p, i) => {
      const angle = p.phase + t * p.speed * speedMult;
      const r = p.radius * radiusMult + Math.sin(angle * 2.3 + p.phase) * 0.15;

      dummy.position.set(
        r * Math.sin(p.phi) * Math.cos(p.theta + angle * 0.3),
        r * Math.cos(p.phi),
        r * Math.sin(p.phi) * Math.sin(p.theta + angle * 0.3)
      );

      const scale = p.size * (1 + Math.sin(angle * 4 + p.phase) * 0.3);
      dummy.scale.setScalar(scale);
      dummy.updateMatrix();
      meshRef.current.setMatrixAt(i, dummy.matrix);
    });

    meshRef.current.instanceMatrix.needsUpdate = true;
  });

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, PARTICLE_COUNT]} material={mat}>
      <sphereGeometry args={[1, 6, 6]} />
    </instancedMesh>
  );
}
