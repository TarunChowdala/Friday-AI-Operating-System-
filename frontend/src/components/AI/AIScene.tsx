import { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { AdaptiveDpr, AdaptiveEvents, Float } from '@react-three/drei';
import { EffectComposer, Bloom } from '@react-three/postprocessing';
import * as THREE from 'three';

import type { AssistantState } from '../../types';
import { ENERGY_BY_STATE } from './energyConfig';
import { useEnergySpring } from './useEnergySpring';
import { NeuralField } from './NeuralField';
import { AmbientField } from './AmbientField';

interface Props {
  state: AssistantState;
}

function LivingCore({ state }: Props) {
  const energy = useEnergySpring(state);
  const bloom = ENERGY_BY_STATE[state].bloom;

  return (
    <>
      <ambientLight intensity={0.08} />
      <pointLight position={[3, 2, 4]} intensity={0.5} color="#88ccff" />
      <pointLight position={[-3, -2, 2]} intensity={0.3} color="#4466ff" />

      <Float speed={0.55} rotationIntensity={0.1} floatIntensity={0.2}>
        <NeuralField energy={energy} />
      </Float>

      <AmbientField energy={energy} />

      <EffectComposer multisampling={0}>
        <Bloom
          luminanceThreshold={0.35}
          luminanceSmoothing={0.6}
          intensity={bloom}
          mipmapBlur
          radius={0.55}
        />
      </EffectComposer>
    </>
  );
}

function FallbackCore() {
  return (
    <div className="w-full h-full flex items-center justify-center bg-[#050505]">
      <div
        className="w-44 h-44 rounded-full animate-pulse"
        style={{
          background:
            'radial-gradient(circle, rgba(0,191,255,0.5) 0%, rgba(0,80,160,0.18) 50%, transparent 100%)',
          boxShadow: '0 0 90px rgba(0,191,255,0.4)',
        }}
      />
    </div>
  );
}

export default function AIScene({ state }: Props) {
  return (
    <Suspense fallback={<FallbackCore />}>
      <Canvas
        camera={{ position: [0, 0, 4.6], fov: 42 }}
        gl={{
          antialias: true,
          alpha: true,
          powerPreference: 'high-performance',
          toneMapping: THREE.ACESFilmicToneMapping,
          toneMappingExposure: 1.05,
        }}
        onCreated={({ gl }) => {
          gl.setClearColor(0x000000, 0);
        }}
        style={{ background: 'transparent', width: '100%', height: '100%' }}
        dpr={[1, 1.75]}
      >
        <AdaptiveDpr pixelated />
        <AdaptiveEvents />
        <LivingCore state={state} />
      </Canvas>
    </Suspense>
  );
}
