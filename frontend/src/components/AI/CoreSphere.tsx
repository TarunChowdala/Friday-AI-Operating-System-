import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { AssistantState } from '../../types';

interface Props {
  state: AssistantState;
}

interface SkeletonProps {
  radius: number;
  wSeg: number;
  hSeg: number;
  color: string;
  opacity: number;
  rotSpeedY: number;
  rotSpeedX: number;
  rotSpeedZ: number;
  initRotation?: [number, number, number];
}

function SkeletonMesh({
  radius, wSeg, hSeg, color, opacity,
  rotSpeedY, rotSpeedX, rotSpeedZ,
  initRotation = [0, 0, 0],
}: SkeletonProps) {
  const ref = useRef<THREE.Mesh>(null!);

  const mat = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: new THREE.Color(color),
        wireframe: true,
        transparent: true,
        opacity,
      }),
    [color, opacity]
  );

  useFrame((_, delta) => {
    if (!ref.current) return;
    ref.current.rotation.y += delta * rotSpeedY;
    ref.current.rotation.x += delta * rotSpeedX;
    ref.current.rotation.z += delta * rotSpeedZ;
  });

  return (
    <mesh ref={ref} rotation={initRotation} material={mat}>
      <sphereGeometry args={[radius, wSeg, hSeg]} />
    </mesh>
  );
}

export function CoreSphere({ state }: Props) {
  // Color per state
  const color =
    state === 'thinking' ? '#ffaa00'
    : state === 'speaking' ? '#00ff88'
    : '#00b4ff';

  // Speed multiplier per state
  const sm =
    state === 'thinking' ? 3.2
    : state === 'speaking' ? 2.2
    : state === 'listening' ? 1.6
    : 0.55;

  const baseOpacity = state === 'idle' ? 0.32 : 0.50;

  return (
    <group>
      {/* ─── Innermost skeleton — tightest grid, fastest spin ─── */}
      <SkeletonMesh
        radius={0.72}
        wSeg={12} hSeg={8}
        color={color}
        opacity={baseOpacity}
        rotSpeedY={sm * 0.9}
        rotSpeedX={sm * 0.18}
        rotSpeedZ={0}
        initRotation={[0.3, 0, 0]}
      />

      {/* ─── Mid skeleton — slightly looser grid, counter-spin ─── */}
      <SkeletonMesh
        radius={1.05}
        wSeg={10} hSeg={7}
        color={color}
        opacity={baseOpacity * 0.65}
        rotSpeedY={-sm * 0.55}
        rotSpeedX={sm * 0.1}
        rotSpeedZ={sm * 0.25}
        initRotation={[Math.PI / 5, Math.PI / 6, 0]}
      />

      {/* ─── Outer skeleton — sparse, slow, different tilt ─── */}
      <SkeletonMesh
        radius={1.38}
        wSeg={8} hSeg={6}
        color={color}
        opacity={baseOpacity * 0.35}
        rotSpeedY={sm * 0.3}
        rotSpeedX={-sm * 0.08}
        rotSpeedZ={-sm * 0.15}
        initRotation={[Math.PI / 3, 0, Math.PI / 4]}
      />

      {/* ─── Center glow light ─── */}
      <pointLight
        position={[0, 0, 0]}
        color={color}
        intensity={state === 'idle' ? 2.5 : state === 'thinking' ? 7 : state === 'speaking' ? 8 : 5}
        distance={8}
      />

      {/* ─── Tiny bright core dot ─── */}
      <mesh>
        <sphereGeometry args={[0.06, 8, 8]} />
        <meshBasicMaterial color={color} />
      </mesh>
    </group>
  );
}
