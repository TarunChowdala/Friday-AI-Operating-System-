import { useEffect, useRef } from 'react';
import { useFridayStore } from '../../store/useFridayStore';
import { useMousePosition } from '../../hooks/useMousePosition';
import type { AssistantState } from '../../types';

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  opacity: number;
  baseOpacity: number;
  color: string;
  life: number;
  maxLife: number;
  orbit: boolean;
  orbitAngle: number;
  orbitRadius: number;
  orbitSpeed: number;
}

const PARTICLE_COUNT = 280;
const COLORS = [
  'rgba(0,180,255,', // cyan
  'rgba(0,100,255,', // blue
  'rgba(0,229,255,', // light cyan
  'rgba(100,180,255,', // soft blue
  'rgba(255,255,255,', // white
];

function createParticle(W: number, H: number, forceOrbit = false): Particle {
  const orbit = forceOrbit || Math.random() < 0.15;
  const color = COLORS[Math.floor(Math.random() * COLORS.length)];
  return {
    x: orbit ? W / 2 : Math.random() * W,
    y: orbit ? H / 2 : Math.random() * H,
    vx: (Math.random() - 0.5) * 0.4,
    vy: (Math.random() - 0.5) * 0.4,
    size: orbit ? Math.random() * 1.5 + 0.5 : Math.random() * 2 + 0.5,
    opacity: 0,
    baseOpacity: Math.random() * 0.5 + 0.15,
    color,
    life: 0,
    maxLife: Math.random() * 400 + 200,
    orbit,
    orbitAngle: Math.random() * Math.PI * 2,
    orbitRadius: Math.random() * 200 + 80,
    orbitSpeed: (Math.random() - 0.5) * 0.008,
  };
}

function getSpeedMult(state: AssistantState): number {
  switch (state) {
    case 'listening': return 1.4;
    case 'thinking': return 2.2;
    case 'speaking': return 1.8;
    default: return 1;
  }
}

export default function GlobalParticles() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particlesRef = useRef<Particle[]>([]);
  const animFrameRef = useRef<number>(0);
  const stateRef = useRef<AssistantState>('idle');
  const mouseRef = useMousePosition();

  // Subscribe to state changes
  const assistantState = useFridayStore((s) => s.assistantState);
  useEffect(() => { stateRef.current = assistantState; }, [assistantState]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let W = 0, H = 0;

    const resize = () => {
      W = canvas.width = window.innerWidth;
      H = canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    // Init particles
    particlesRef.current = Array.from({ length: PARTICLE_COUNT }, (_, i) =>
      createParticle(W, H, i < 40)
    );

    const draw = () => {
      const state = stateRef.current;
      const speedMult = getSpeedMult(state);
      const mouse = mouseRef.current;
      const cx = W / 2;
      const cy = H / 2;

      ctx.clearRect(0, 0, W, H);

      particlesRef.current.forEach((p, i) => {
        p.life++;

        // Fade in / fade out
        if (p.life < 60) {
          p.opacity = (p.life / 60) * p.baseOpacity;
        } else if (p.life > p.maxLife - 60) {
          p.opacity = ((p.maxLife - p.life) / 60) * p.baseOpacity;
        } else {
          p.opacity = p.baseOpacity;
        }

        // Respawn
        if (p.life >= p.maxLife) {
          particlesRef.current[i] = createParticle(W, H);
          return;
        }

        if (p.orbit) {
          // Orbit around center
          p.orbitAngle += p.orbitSpeed * speedMult;
          const orbitR = p.orbitRadius * (state === 'thinking' ? 0.6 : state === 'speaking' ? 1.3 : 1);
          p.x = cx + Math.cos(p.orbitAngle) * orbitR;
          p.y = cy + Math.sin(p.orbitAngle) * orbitR * 0.5;
        } else {
          // State-based movement
          if (state === 'thinking') {
            // Attract toward center
            const dx = cx - p.x;
            const dy = cy - p.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist > 5) {
              p.vx += (dx / dist) * 0.015;
              p.vy += (dy / dist) * 0.015;
            }
          } else if (state === 'speaking') {
            // Repel from center
            const dx = p.x - cx;
            const dy = p.y - cy;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < 300) {
              p.vx += (dx / (dist + 1)) * 0.01;
              p.vy += (dy / (dist + 1)) * 0.01;
            }
          }

          // Mouse attraction (gentle)
          if (mouse) {
            const mdx = mouse.x - p.x;
            const mdy = mouse.y - p.y;
            const mdist = Math.sqrt(mdx * mdx + mdy * mdy);
            if (mdist < 150 && mdist > 1) {
              p.vx += (mdx / mdist) * 0.03;
              p.vy += (mdy / mdist) * 0.03;
            }
          }

          // Apply velocity with damping
          p.vx *= 0.97;
          p.vy *= 0.97;
          p.x += p.vx * speedMult;
          p.y += p.vy * speedMult;

          // Wrap around screen
          if (p.x < -10) p.x = W + 10;
          if (p.x > W + 10) p.x = -10;
          if (p.y < -10) p.y = H + 10;
          if (p.y > H + 10) p.y = -10;
        }

        // Draw particle
        const alpha = Math.max(0, Math.min(1, p.opacity));
        if (alpha <= 0.01) return;

        ctx.beginPath();
        const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size * 2.5);
        gradient.addColorStop(0, `${p.color}${alpha})`);
        gradient.addColorStop(1, `${p.color}0)`);
        ctx.fillStyle = gradient;
        ctx.arc(p.x, p.y, p.size * 2.5, 0, Math.PI * 2);
        ctx.fill();
      });

      animFrameRef.current = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      cancelAnimationFrame(animFrameRef.current);
      window.removeEventListener('resize', resize);
    };
  }, []); // eslint-disable-line

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0"
      style={{ mixBlendMode: 'screen' }}
    />
  );
}
