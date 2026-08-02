import { useEffect, useRef } from 'react';
import type { MousePosition } from '../types';

/**
 * Returns a ref containing the current normalized mouse position.
 * Using a ref avoids triggering re-renders on mouse move.
 */
export function useMousePosition(): React.RefObject<MousePosition> {
  const ref = useRef<MousePosition>({ x: 0, y: 0, nx: 0, ny: 0 });

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      const x = e.clientX;
      const y = e.clientY;
      const nx = (x / window.innerWidth) * 2 - 1;
      const ny = -((y / window.innerHeight) * 2 - 1);
      ref.current = { x, y, nx, ny };
    };
    window.addEventListener('mousemove', onMove);
    return () => window.removeEventListener('mousemove', onMove);
  }, []);

  return ref;
}
