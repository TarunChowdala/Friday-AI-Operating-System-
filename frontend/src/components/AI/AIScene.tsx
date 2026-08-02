import { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { Float, AdaptiveDpr, AdaptiveEvents } from '@react-three/drei';
import { EffectComposer, Bloom } from '@react-three/postprocessing';

import { CoreRings } from './CoreRings';
import { CoreParticles } from './CoreParticles';
import type { AssistantState } from '../../types';

interface Props {
  state: AssistantState;
}

function Lights() {
  return (
    <>
      <ambientLight intensity={0.06} />
      <pointLight position={[5, 5, 5]} color="#0044ff" intensity={2} distance={15} />
      <pointLight position={[-5, -3, -4]} color="#00b4ff" intensity={1.5} distance={12} />
      <pointLight position={[0, 6, -4]} color="#00e5ff" intensity={1} distance={10} />
    </>
  );
}

function Scene({ state }: Props) {
  return (
    <>
      <Lights />

      <Float speed={1.2} rotationIntensity={0.25} floatIntensity={0.5}>

        <CoreRings state={state} />
        <CoreParticles state={state} />
      </Float>

      <EffectComposer>
        <Bloom
          luminanceThreshold={0.15}
          luminanceSmoothing={0.9}
          intensity={state === 'speaking' ? 2.8 : state === 'thinking' ? 2.2 : state === 'listening' ? 1.8 : 1.2}
          mipmapBlur
        />
      </EffectComposer>
    </>
  );
}

function FallbackCore() {
  return (
    <div className="w-full h-full flex-center">
      <div
        className="w-40 h-40 rounded-full animate-pulse"
        style={{
          background: 'radial-gradient(circle, rgba(0,180,255,0.4) 0%, rgba(0,50,150,0.2) 60%, transparent 100%)',
          boxShadow: '0 0 60px rgba(0,180,255,0.4)',
        }}
      />
    </div>
  );
}

export default function AIScene({ state }: Props) {
  return (
    <Suspense fallback={<FallbackCore />}>
      <Canvas
        camera={{ position: [0, 0, 6.5], fov: 42 }}
        gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
        style={{ background: 'transparent', width: '100%', height: '100%' }}
        dpr={[1, 2]}
      >
        <AdaptiveDpr pixelated />
        <AdaptiveEvents />
        <Scene state={state} />
      </Canvas>
    </Suspense>
  );
}
