import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { AssistantState } from '../../types';
import { ENERGY_BY_STATE, type EnergyParams } from './energyConfig';

export type LiveEnergy = {
  color: THREE.Color;
  scale: number;
  glow: number;
  bloom: number;
  breathSpeed: number;
  pulseSpeed: number;
  particleSpeed: number;
  density: number;
  inward: number;
  outward: number;
  chaos: number;
  coreSize: number;
  sparkRate: number;
  rotationSpeed: number;
  amplitude: number;
  time: number;
  breath: number;
  pulse: number;
};

function cloneParams(p: EnergyParams): LiveEnergy {
  return {
    color: p.color.clone(),
    scale: p.scale,
    glow: p.glow,
    bloom: p.bloom,
    breathSpeed: p.breathSpeed,
    pulseSpeed: p.pulseSpeed,
    particleSpeed: p.particleSpeed,
    density: p.density,
    inward: p.inward,
    outward: p.outward,
    chaos: p.chaos,
    coreSize: p.coreSize,
    sparkRate: p.sparkRate,
    rotationSpeed: p.rotationSpeed,
    amplitude: 0.2,
    time: 0,
    breath: 0,
    pulse: 0,
  };
}

function spring(current: number, target: number, velocity: { v: number }, dt: number, stiffness = 6, damping = 8) {
  const force = (target - current) * stiffness;
  velocity.v = (velocity.v + force * dt) * Math.exp(-damping * dt);
  return current + velocity.v * dt * 60;
}

export function useEnergySpring(state: AssistantState) {
  const live = useRef<LiveEnergy>(cloneParams(ENERGY_BY_STATE.idle));
  const stateRef = useRef(state);
  stateRef.current = state;

  const vels = useRef({
    scale: { v: 0 },
    glow: { v: 0 },
    bloom: { v: 0 },
    breathSpeed: { v: 0 },
    pulseSpeed: { v: 0 },
    particleSpeed: { v: 0 },
    density: { v: 0 },
    inward: { v: 0 },
    outward: { v: 0 },
    chaos: { v: 0 },
    coreSize: { v: 0 },
    sparkRate: { v: 0 },
    rotationSpeed: { v: 0 },
    amp: { v: 0 },
  });

  useFrame((_, dt) => {
    const d = Math.min(dt, 0.05);
    const target = ENERGY_BY_STATE[stateRef.current];
    const L = live.current;
    const V = vels.current;

    L.color.lerp(target.color, 1 - Math.exp(-4.5 * d));
    L.scale = spring(L.scale, target.scale, V.scale, d, 8, 10);
    L.glow = spring(L.glow, target.glow, V.glow, d, 5, 8);
    L.bloom = spring(L.bloom, target.bloom, V.bloom, d, 4, 7);
    L.breathSpeed = spring(L.breathSpeed, target.breathSpeed, V.breathSpeed, d, 5, 8);
    L.pulseSpeed = spring(L.pulseSpeed, target.pulseSpeed, V.pulseSpeed, d, 5, 8);
    L.particleSpeed = spring(L.particleSpeed, target.particleSpeed, V.particleSpeed, d, 5, 8);
    L.density = spring(L.density, target.density, V.density, d, 6, 9);
    L.inward = spring(L.inward, target.inward, V.inward, d, 7, 10);
    L.outward = spring(L.outward, target.outward, V.outward, d, 7, 10);
    L.chaos = spring(L.chaos, target.chaos, V.chaos, d, 6, 9);
    L.coreSize = spring(L.coreSize, target.coreSize, V.coreSize, d, 8, 10);
    L.sparkRate = spring(L.sparkRate, target.sparkRate, V.sparkRate, d, 5, 8);
    L.rotationSpeed = spring(L.rotationSpeed, target.rotationSpeed, V.rotationSpeed, d, 4, 7);

    L.time += d;
    L.breath = Math.sin(L.time * L.breathSpeed * Math.PI * 2) * 0.5 + 0.5;
    L.pulse = Math.sin(L.time * L.pulseSpeed * Math.PI * 2) * 0.5 + 0.5;

    const s = stateRef.current;
    let ampTarget = 0.18 + L.breath * 0.12;
    if (s === 'speaking') {
      const t = L.time;
      ampTarget =
        0.35 +
        0.35 * Math.abs(Math.sin(t * 7.3)) * Math.abs(Math.sin(t * 3.1)) +
        0.2 * Math.abs(Math.sin(t * 11.7)) +
        0.15 * L.pulse;
    } else if (s === 'listening') {
      ampTarget = 0.25 + 0.2 * L.pulse + 0.1 * Math.abs(Math.sin(L.time * 5.2));
    } else if (s === 'thinking') {
      ampTarget = 0.4 + 0.35 * L.pulse + 0.15 * Math.abs(Math.sin(L.time * 13.0));
    }

    L.amplitude = spring(L.amplitude, ampTarget, V.amp, d, 14, 12);
  });

  return live;
}
