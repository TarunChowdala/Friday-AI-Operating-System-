import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { AssistantState } from '../../types';

interface RingProps {
  radius: number;
  tube: number;
  color: string;
  emissive: string;
  emissiveIntensity: number;
  rotX: number;
  rotY: number;
  rotZ: number;
  speed: number;
  state: AssistantState;
  opacity: number;
}

function Ring({ radius, tube, color, emissive, emissiveIntensity, rotX, rotY, rotZ, speed, state, opacity }: RingProps) {
  const ref = useRef<THREE.Mesh>(null!);

  const mat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: new THREE.Color(color),
        emissive: new THREE.Color(emissive),
        emissiveIntensity,
        transparent: true,
        opacity,
        roughness: 0.0,
        metalness: 1.0,
        side: THREE.DoubleSide,
      }),
    [color, emissive, emissiveIntensity, opacity]
  );

  useFrame((_, delta) => {
    if (!ref.current) return;
    const speedMult = state === 'thinking' ? 3.5 : state === 'listening' ? 1.8 : state === 'speaking' ? 2.2 : 1;
    ref.current.rotation.z += delta * speed * speedMult;
  });

  return (
    <mesh ref={ref} rotation={[rotX, rotY, rotZ]} material={mat}>
      <torusGeometry args={[radius, tube, 16, 128]} />
    </mesh>
  );
}

export function CoreRings({ state }: { state: AssistantState }) {
  const brightnessMult = state === 'thinking' ? 2.0 : state === 'speaking' ? 2.5 : state === 'listening' ? 1.6 : 1;

  return (
    <group>
      <Ring
        radius={1.7} tube={0.018}
        color="#00b4ff" emissive="#00b4ff" emissiveIntensity={1.5 * brightnessMult}
        rotX={Math.PI / 2.5} rotY={0} rotZ={0}
        speed={0.5} state={state} opacity={0.85}
      />
      <Ring
        radius={2.05} tube={0.012}
        color="#0066ff" emissive="#0066ff" emissiveIntensity={1.2 * brightnessMult}
        rotX={Math.PI / 4} rotY={Math.PI / 6} rotZ={0}
        speed={-0.35} state={state} opacity={0.7}
      />
      <Ring
        radius={2.35} tube={0.009}
        color="#00e5ff" emissive="#00e5ff" emissiveIntensity={1.0 * brightnessMult}
        rotX={Math.PI / 2} rotY={Math.PI / 3} rotZ={Math.PI / 4}
        speed={0.25} state={state} opacity={0.6}
      />
      <Ring
        radius={2.6} tube={0.006}
        color="#003a88" emissive="#003a88" emissiveIntensity={0.8 * brightnessMult}
        rotX={Math.PI / 6} rotY={Math.PI / 2} rotZ={Math.PI / 5}
        speed={-0.18} state={state} opacity={0.5}
      />
      <Ring
        radius={1.45} tube={0.008}
        color="#00e5ff" emissive="#00e5ff" emissiveIntensity={0.9 * brightnessMult}
        rotX={Math.PI / 1.5} rotY={Math.PI / 5} rotZ={0}
        speed={0.7} state={state} opacity={0.65}
      />
    </group>
  );
}
