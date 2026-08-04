import { useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { AssistantState } from '../../types';

interface Props {
  state: AssistantState;
}

const STATE_COLOR: Record<AssistantState, string> = {
  idle: '#00BFFF',
  listening: '#00D4FF',
  thinking: '#7A5FFF',
  speaking: '#FF8A00', // warm amber-orange (reference)
};

const PARTICLE_COUNT = 280;

function hash(i: number) {
  const x = Math.sin(i * 127.1) * 43758.5453;
  return x - Math.floor(x);
}

function SkeletonSphere({ state }: Props) {
  const outer = useRef<THREE.Mesh>(null);
  const inner = useRef<THREE.Mesh>(null);
  const points = useRef<THREE.Points>(null);
  const stateRef = useRef(state);
  stateRef.current = state;

  const liveColor = useRef(new THREE.Color(STATE_COLOR.idle));
  const targetColor = useRef(new THREE.Color(STATE_COLOR.idle));

  const { positions, phases, speeds, radii } = useMemo(() => {
    const positions = new Float32Array(PARTICLE_COUNT * 3);
    const phases = new Float32Array(PARTICLE_COUNT);
    const speeds = new Float32Array(PARTICLE_COUNT);
    const radii = new Float32Array(PARTICLE_COUNT);

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const r = 1.9 + hash(i) * 1.8;
      const theta = hash(i + 1) * Math.PI * 2;
      const phi = Math.acos(2 * hash(i + 2) - 1);
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = r * Math.cos(phi);
      phases[i] = hash(i + 3) * Math.PI * 2;
      speeds[i] = 0.15 + hash(i + 4) * 0.45;
      radii[i] = r;
    }
    return { positions, phases, speeds, radii };
  }, []);

  useFrame((clockState, dt) => {
    const t = clockState.clock.elapsedTime;
    const speaking = stateRef.current === 'speaking';

    targetColor.current.set(STATE_COLOR[stateRef.current]);
    liveColor.current.lerp(targetColor.current, 1 - Math.exp(-6 * dt));

    if (outer.current) {
      outer.current.rotation.y += dt * (speaking ? 0.35 : 0.12);
      (outer.current.material as THREE.MeshBasicMaterial).color.copy(liveColor.current);
    }
    if (inner.current) {
      inner.current.rotation.y -= dt * (speaking ? 0.45 : 0.18);
      inner.current.rotation.x += dt * (speaking ? 0.15 : 0.06);
      (inner.current.material as THREE.MeshBasicMaterial).color.copy(liveColor.current);
    }

    if (points.current) {
      const arr = points.current.geometry.attributes.position.array as Float32Array;
      const speedBoost = speaking ? 2.2 : 1;
      const radiusBoost = speaking ? 1.15 : 1;

      for (let i = 0; i < PARTICLE_COUNT; i++) {
        const base = radii[i] * radiusBoost;
        const sp = speeds[i] * speedBoost;
        const ph = phases[i];
        const angle = t * sp + ph;
        const tilt = Math.sin(t * sp * 0.7 + ph) * 0.25;
        const r = base + Math.sin(t * sp + ph) * (speaking ? 0.22 : 0.12);
        const lat = (ph % Math.PI) - Math.PI / 2 + tilt;
        arr[i * 3] = r * Math.cos(lat) * Math.cos(angle);
        arr[i * 3 + 1] = r * Math.sin(lat);
        arr[i * 3 + 2] = r * Math.cos(lat) * Math.sin(angle);
      }
      points.current.geometry.attributes.position.needsUpdate = true;
      const mat = points.current.material as THREE.PointsMaterial;
      mat.color.copy(liveColor.current);
      mat.size = speaking ? 0.05 : 0.035;
      mat.opacity = speaking ? 0.95 : 0.75;
    }
  });

  return (
    <group>
      <mesh ref={outer}>
        <sphereGeometry args={[1.6, 32, 24]} />
        <meshBasicMaterial color={STATE_COLOR.idle} wireframe />
      </mesh>
      <mesh ref={inner} scale={0.72}>
        <sphereGeometry args={[1.6, 16, 12]} />
        <meshBasicMaterial color={STATE_COLOR.idle} wireframe opacity={0.45} transparent />
      </mesh>

      <points ref={points} frustumCulled={false}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        </bufferGeometry>
        <pointsMaterial
          size={0.035}
          color={STATE_COLOR.idle}
          transparent
          opacity={0.75}
          sizeAttenuation
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </points>
    </group>
  );
}

export default function AIScene({ state }: Props) {
  return (
    <Canvas
      camera={{ position: [0, 0, 5], fov: 45 }}
      gl={{ antialias: true, alpha: true }}
      className="!absolute inset-0 h-full w-full"
      style={{ width: '100%', height: '100%' }}
    >
      <SkeletonSphere state={state} />
    </Canvas>
  );
}
