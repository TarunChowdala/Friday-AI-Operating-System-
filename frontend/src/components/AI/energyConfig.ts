import type { AssistantState } from '../../types';
import * as THREE from 'three';

export interface EnergyParams {
  color: THREE.Color;
  colorHex: string;
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
}

export const ENERGY_BY_STATE: Record<AssistantState, EnergyParams> = {
  idle: {
    color: new THREE.Color('#00BFFF'),
    colorHex: '#00BFFF',
    scale: 1.0,
    glow: 1.1,
    bloom: 0.85,
    breathSpeed: 0.35,
    pulseSpeed: 0.45,
    particleSpeed: 0.28,
    density: 0.85,
    inward: 0,
    outward: 0.08,
    chaos: 0.05,
    coreSize: 0.1,
    sparkRate: 0.2,
    rotationSpeed: 0.1,
  },
  listening: {
    color: new THREE.Color('#00D4FF'),
    colorHex: '#00D4FF',
    scale: 0.88,
    glow: 1.45,
    bloom: 1.15,
    breathSpeed: 0.7,
    pulseSpeed: 1.1,
    particleSpeed: 0.9,
    density: 1.35,
    inward: 1.0,
    outward: 0,
    chaos: 0.15,
    coreSize: 0.12,
    sparkRate: 0.3,
    rotationSpeed: 0.2,
  },
  thinking: {
    color: new THREE.Color('#7A5FFF'),
    colorHex: '#7A5FFF',
    scale: 1.0,
    glow: 1.6,
    bloom: 1.35,
    breathSpeed: 1.4,
    pulseSpeed: 2.4,
    particleSpeed: 2.3,
    density: 1.05,
    inward: 0.25,
    outward: 0.15,
    chaos: 1.0,
    coreSize: 0.11,
    sparkRate: 0.6,
    rotationSpeed: 0.5,
  },
  speaking: {
    color: new THREE.Color('#FF7A00'),
    colorHex: '#FF7A00',
    scale: 1.14,
    glow: 2.1,
    bloom: 1.7,
    breathSpeed: 1.15,
    pulseSpeed: 1.85,
    particleSpeed: 1.55,
    density: 0.9,
    inward: 0,
    outward: 1.0,
    chaos: 0.35,
    coreSize: 0.16,
    sparkRate: 1.0,
    rotationSpeed: 0.3,
  },
};

export const NODE_COUNT = 720;
export const LINK_COUNT = 980;
export const DUST_COUNT = 180;
export const SPARK_COUNT = 140;
