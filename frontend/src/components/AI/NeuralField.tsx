import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { LiveEnergy } from './useEnergySpring';
import { NODE_COUNT, LINK_COUNT } from './energyConfig';

function fibSphere(i: number, n: number, radius: number, out: THREE.Vector3) {
  const phi = Math.acos(1 - (2 * (i + 0.5)) / n);
  const theta = Math.PI * (1 + Math.sqrt(5)) * i;
  out.set(
    Math.sin(phi) * Math.cos(theta) * radius,
    Math.sin(phi) * Math.sin(theta) * radius,
    Math.cos(phi) * radius,
  );
  return out;
}

function hash(i: number) {
  const x = Math.sin(i * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
}

type Node = {
  base: THREE.Vector3;
  phase: number;
  speed: number;
  size: number;
  opacity: number;
  jitter: number;
};

export function NeuralField({ energy }: { energy: React.MutableRefObject<LiveEnergy> }) {
  const pointsRef = useRef<THREE.Points>(null);
  const linesRef = useRef<THREE.LineSegments>(null);
  const groupRef = useRef<THREE.Group>(null);
  const tmp = useRef(new THREE.Vector3());
  const inwardTarget = useRef(new THREE.Vector3());

  const { nodes, positions, sizes, opacities, linkPairs, linePositions, pointsMat } = useMemo(() => {
    const nodes: Node[] = [];
    const positions = new Float32Array(NODE_COUNT * 3);
    const sizes = new Float32Array(NODE_COUNT);
    const opacities = new Float32Array(NODE_COUNT);
    const scratch = new THREE.Vector3();

    for (let i = 0; i < NODE_COUNT; i++) {
      // Keep particles on the outer shell band only — hollow center
      const r = 0.95 + hash(i) * 0.55;
      fibSphere(i, NODE_COUNT, r, scratch);
      scratch.multiplyScalar(0.92 + hash(i + 50) * 0.18);
      const base = scratch.clone();
      nodes.push({
        base,
        phase: hash(i + 9) * Math.PI * 2,
        speed: 0.4 + hash(i + 21) * 1.6,
        size: 0.8 + hash(i + 33) * 2.4,
        opacity: 0.25 + hash(i + 44) * 0.75,
        jitter: 0.02 + hash(i + 55) * 0.08,
      });
      positions[i * 3] = base.x;
      positions[i * 3 + 1] = base.y;
      positions[i * 3 + 2] = base.z;
      sizes[i] = nodes[i].size;
      opacities[i] = nodes[i].opacity;
    }

    const linkPairs: [number, number][] = [];
    const used = new Set<string>();
    for (let i = 0; i < NODE_COUNT && linkPairs.length < LINK_COUNT; i++) {
      const dists: { j: number; d: number }[] = [];
      for (let j = i + 1; j < NODE_COUNT; j++) {
        const d = nodes[i].base.distanceToSquared(nodes[j].base);
        if (d < 0.55) dists.push({ j, d });
      }
      dists.sort((a, b) => a.d - b.d);
      const take = 1 + Math.floor(hash(i + 70) * 2);
      for (let k = 0; k < Math.min(take, dists.length); k++) {
        const j = dists[k].j;
        const key = `${i}-${j}`;
        if (!used.has(key)) {
          used.add(key);
          linkPairs.push([i, j]);
        }
      }
    }

    while (linkPairs.length < LINK_COUNT) {
      const i = Math.floor(hash(linkPairs.length * 3.1) * NODE_COUNT);
      const j = Math.floor(hash(linkPairs.length * 7.7) * NODE_COUNT);
      if (i === j) continue;
      const a = Math.min(i, j);
      const b = Math.max(i, j);
      const key = `${a}-${b}`;
      if (used.has(key)) continue;
      if (nodes[a].base.distanceToSquared(nodes[b].base) > 1.2) continue;
      used.add(key);
      linkPairs.push([a, b]);
    }

    const linePositions = new Float32Array(linkPairs.length * 6);

    const pointsMat = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uColor: { value: new THREE.Color('#00BFFF') },
        uGlow: { value: 1 },
      },
      vertexShader: /* glsl */ `
        attribute float aSize;
        attribute float aOpacity;
        varying float vOpacity;
        void main() {
          vOpacity = aOpacity;
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          gl_PointSize = aSize * (380.0 / -mv.z);
          gl_Position = projectionMatrix * mv;
        }
      `,
      fragmentShader: /* glsl */ `
        uniform vec3 uColor;
        uniform float uGlow;
        varying float vOpacity;
        void main() {
          vec2 uv = gl_PointCoord - 0.5;
          float d = length(uv);
          if (d > 0.5) discard;
          float soft = smoothstep(0.5, 0.0, d);
          float core = smoothstep(0.2, 0.0, d);
          vec3 col = uColor * (0.7 + uGlow * 0.7) + vec3(core * 1.2);
          gl_FragColor = vec4(col, soft * vOpacity * (0.7 + uGlow * 0.3));
        }
      `,
    });

    return { nodes, positions, sizes, opacities, linkPairs, linePositions, pointsMat };
  }, []);

  useFrame((_, dt) => {
    const L = energy.current;
    const t = L.time;
    const points = pointsRef.current;
    const lines = linesRef.current;
    if (!points || !lines) return;

    const posArr = points.geometry.attributes.position.array as Float32Array;
    const sizeArr = points.geometry.attributes.aSize.array as Float32Array;
    const opacArr = points.geometry.attributes.aOpacity.array as Float32Array;
    const lineArr = lines.geometry.attributes.position.array as Float32Array;

    const breathScale = 1 + (L.breath - 0.5) * 0.04;
    const amp = L.amplitude;
    const v = tmp.current;
    const inv = inwardTarget.current;

    for (let i = 0; i < NODE_COUNT; i++) {
      const n = nodes[i];
      v.copy(n.base);

      const sp = L.particleSpeed * n.speed;
      v.x += Math.sin(t * sp + n.phase) * n.jitter;
      v.y += Math.cos(t * sp * 0.87 + n.phase * 1.3) * n.jitter;
      v.z += Math.sin(t * sp * 1.13 + n.phase * 0.7) * n.jitter;

      const c = L.chaos;
      v.x += Math.sin(t * 4.2 * sp + n.phase * 3) * n.jitter * 3.5 * c;
      v.y += Math.cos(t * 5.1 * sp + n.phase * 2) * n.jitter * 3.5 * c;
      v.z += Math.sin(t * 3.7 * sp + n.phase) * n.jitter * 3.5 * c;

      if (L.inward > 0.01) {
        // Condense toward mid-shell, never collapse into a center blob
        inv.copy(v).normalize().multiplyScalar(0.85);
        v.lerp(inv, L.inward * 0.45);
        v.multiplyScalar(1 - L.inward * 0.08);
      }

      if (L.outward > 0.01) {
        const push = 1 + L.outward * (0.18 + amp * 0.35) * (0.5 + hash(i) * 0.5);
        v.multiplyScalar(push);
      }

      const dens = L.density;
      const len = v.length();
      if (len > 0.001) {
        // Keep hollow — compress toward shell radius ~1.1, never toward origin
        const targetLen = THREE.MathUtils.lerp(len, 1.1, (dens - 0.75) * 0.4);
        v.multiplyScalar(Math.max(0.75, targetLen) / len);
      }

      v.multiplyScalar(breathScale * L.scale);

      posArr[i * 3] = v.x;
      posArr[i * 3 + 1] = v.y;
      posArr[i * 3 + 2] = v.z;

      sizeArr[i] = n.size * (0.7 + dens * 0.25) * (1 + amp * 0.35 * L.outward);
      opacArr[i] = Math.min(1, n.opacity * (0.45 + L.glow * 0.35) * (0.7 + amp * 0.4));
    }

    points.geometry.attributes.position.needsUpdate = true;
    points.geometry.attributes.aSize.needsUpdate = true;
    points.geometry.attributes.aOpacity.needsUpdate = true;

    for (let k = 0; k < linkPairs.length; k++) {
      const [a, b] = linkPairs[k];
      const o = k * 6;
      lineArr[o] = posArr[a * 3];
      lineArr[o + 1] = posArr[a * 3 + 1];
      lineArr[o + 2] = posArr[a * 3 + 2];
      lineArr[o + 3] = posArr[b * 3];
      lineArr[o + 4] = posArr[b * 3 + 1];
      lineArr[o + 5] = posArr[b * 3 + 2];
    }
    lines.geometry.attributes.position.needsUpdate = true;

    if (groupRef.current) {
      groupRef.current.rotation.y += L.rotationSpeed * dt;
      groupRef.current.rotation.x = Math.sin(t * 0.15) * 0.08;
    }

    pointsMat.uniforms.uColor.value.copy(L.color);
    pointsMat.uniforms.uGlow.value = L.glow;

    const lmat = lines.material as THREE.LineBasicMaterial;
    lmat.color.copy(L.color);
    lmat.opacity = 0.22 + L.glow * 0.18 + L.outward * 0.2 + L.chaos * 0.1;
  });

  return (
    <group ref={groupRef}>
      <points ref={pointsRef} frustumCulled={false}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[positions, 3]} />
          <bufferAttribute attach="attributes-aSize" args={[sizes, 1]} />
          <bufferAttribute attach="attributes-aOpacity" args={[opacities, 1]} />
        </bufferGeometry>
        <primitive object={pointsMat} attach="material" />
      </points>

      <lineSegments ref={linesRef} frustumCulled={false}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[linePositions, 3]} />
        </bufferGeometry>
        <lineBasicMaterial
          transparent
          opacity={0.2}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          color="#00BFFF"
        />
      </lineSegments>
    </group>
  );
}
