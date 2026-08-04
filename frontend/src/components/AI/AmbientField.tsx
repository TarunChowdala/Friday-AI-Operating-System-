import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { LiveEnergy } from './useEnergySpring';
import { DUST_COUNT, SPARK_COUNT } from './energyConfig';

function hash(i: number) {
  const x = Math.sin(i * 91.7 + 17.3) * 43758.5453;
  return x - Math.floor(x);
}

export function AmbientField({ energy }: { energy: React.MutableRefObject<LiveEnergy> }) {
  const dustRef = useRef<THREE.Points>(null);
  const sparkRef = useRef<THREE.Points>(null);

  const dust = useMemo(() => {
    const pos = new Float32Array(DUST_COUNT * 3);
    const spd = new Float32Array(DUST_COUNT);
    for (let i = 0; i < DUST_COUNT; i++) {
      const r = 2.2 + hash(i) * 4.5;
      const theta = hash(i + 1) * Math.PI * 2;
      const phi = Math.acos(2 * hash(i + 2) - 1);
      pos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      pos[i * 3 + 2] = r * Math.cos(phi);
      spd[i] = 0.05 + hash(i + 3) * 0.15;
    }
    return { pos, spd };
  }, []);

  const sparks = useMemo(() => {
    const pos = new Float32Array(SPARK_COUNT * 3);
    const vel = new Float32Array(SPARK_COUNT * 3);
    const life = new Float32Array(SPARK_COUNT);
    const size = new Float32Array(SPARK_COUNT);
    for (let i = 0; i < SPARK_COUNT; i++) {
      life[i] = hash(i + 10);
      size[i] = 0.5 + hash(i + 20) * 2.5;
      resetSpark(i, pos, vel, life, 0);
    }
    return { pos, vel, life, size };
  }, []);

  function resetSpark(
    i: number,
    pos: Float32Array,
    vel: Float32Array,
    life: Float32Array,
    outward: number,
  ) {
    const theta = hash(i * 3.1 + life[i] * 100) * Math.PI * 2;
    const phi = Math.acos(2 * hash(i * 5.7 + life[i] * 50) - 1);
    const r = 1.3 + hash(i + life[i] * 10) * 0.4;
    pos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
    pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
    pos[i * 3 + 2] = r * Math.cos(phi);
    const speed = 0.3 + outward * 1.8 + hash(i + 40) * 0.8;
    vel[i * 3] = Math.sin(phi) * Math.cos(theta) * speed;
    vel[i * 3 + 1] = Math.sin(phi) * Math.sin(theta) * speed;
    vel[i * 3 + 2] = Math.cos(phi) * speed;
    life[i] = 0;
  }

  useFrame((_, dt) => {
    const L = energy.current;
    const t = L.time;

    if (dustRef.current) {
      const arr = dustRef.current.geometry.attributes.position.array as Float32Array;
      for (let i = 0; i < DUST_COUNT; i++) {
        arr[i * 3 + 1] += Math.sin(t * dust.spd[i] + i) * dt * 0.08;
        arr[i * 3] += Math.cos(t * dust.spd[i] * 0.7 + i) * dt * 0.05;
      }
      dustRef.current.geometry.attributes.position.needsUpdate = true;
      const m = dustRef.current.material as THREE.PointsMaterial;
      m.color.copy(L.color);
      m.opacity = 0.04 + L.glow * 0.02;
    }

    if (sparkRef.current) {
      const arr = sparkRef.current.geometry.attributes.position.array as Float32Array;
      const { vel, life, size } = sparks;
      const emit = L.sparkRate * (0.4 + L.amplitude);

      for (let i = 0; i < SPARK_COUNT; i++) {
        life[i] += dt * (0.4 + emit);

        if (life[i] > 1 || (L.sparkRate < 0.2 && life[i] > 0.3)) {
          if (Math.random() < emit * dt * 8 || life[i] > 1) {
            resetSpark(i, arr, vel, life, L.outward);
          }
        } else {
          const push = 1 + L.outward * L.amplitude * 0.5;
          arr[i * 3] += vel[i * 3] * dt * push;
          arr[i * 3 + 1] += vel[i * 3 + 1] * dt * push;
          arr[i * 3 + 2] += vel[i * 3 + 2] * dt * push;
          vel[i * 3 + 1] += Math.sin(t + i) * dt * 0.2 * L.chaos;
        }
        size[i] = (0.5 + hash(i) * 2) * (1 - life[i]) * (0.6 + L.glow * 0.5);
      }

      sparkRef.current.geometry.attributes.position.needsUpdate = true;
      sparkRef.current.geometry.attributes.aSize.needsUpdate = true;
      const mat = sparkRef.current.material as THREE.ShaderMaterial;
      if (mat.uniforms) {
        mat.uniforms.uColor.value.copy(L.color);
        mat.uniforms.uGlow.value = L.glow;
      }
    }
  });

  const sparkMat = useMemo(
    () =>
      new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        uniforms: {
          uColor: { value: new THREE.Color('#00BFFF') },
          uGlow: { value: 1 },
        },
        vertexShader: /* glsl */ `
          attribute float aSize;
          void main() {
            vec4 mv = modelViewMatrix * vec4(position, 1.0);
            gl_PointSize = max(0.5, aSize) * (180.0 / -mv.z);
            gl_Position = projectionMatrix * mv;
          }
        `,
        fragmentShader: /* glsl */ `
          uniform vec3 uColor;
          uniform float uGlow;
          void main() {
            vec2 uv = gl_PointCoord - 0.5;
            float d = length(uv);
            if (d > 0.5) discard;
            float soft = smoothstep(0.5, 0.0, d);
            gl_FragColor = vec4(uColor * (0.8 + uGlow * 0.6) + vec3(0.4), soft * 0.7);
          }
        `,
      }),
    [],
  );

  return (
    <group>
      <points ref={dustRef} frustumCulled={false}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[dust.pos, 3]} />
        </bufferGeometry>
        <pointsMaterial
          size={0.035}
          transparent
          opacity={0.05}
          color="#88aacc"
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          sizeAttenuation
        />
      </points>

      <points ref={sparkRef} frustumCulled={false}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[sparks.pos, 3]} />
          <bufferAttribute attach="attributes-aSize" args={[sparks.size, 1]} />
        </bufferGeometry>
        <primitive object={sparkMat} attach="material" />
      </points>
    </group>
  );
}
