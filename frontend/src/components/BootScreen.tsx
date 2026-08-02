import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useFridayStore, getGreeting } from '../store/useFridayStore';

const bootSequence = [
  { text: 'FRIDAY OS v4.2.1', delay: 200, type: 'title' },
  { text: '─────────────────────────────────', delay: 700, type: 'divider' },
  { text: '▸ Initializing AI Core...', delay: 1000, type: 'info' },
  { text: '▸ Loading Memory Banks...', delay: 1600, type: 'info' },
  { text: '▸ Starting Voice Engine...', delay: 2100, type: 'info' },
  { text: '▸ Loading Local Model...', delay: 2600, type: 'info' },
  { text: '▸ Establishing Neural Links...', delay: 3100, type: 'info' },
  { text: '▸ Loading Dashboard...', delay: 3500, type: 'info' },
  { text: '─────────────────────────────────', delay: 4000, type: 'divider' },
  { text: '✓ All Systems Operational.', delay: 4300, type: 'success' },
  { text: getGreeting(), delay: 4800, type: 'greeting' },
];

const TOTAL_DURATION = 5800;

export default function BootScreen() {
  const setBooted = useFridayStore((s) => s.setBooted);
  const [visibleLines, setVisibleLines] = useState<number[]>([]);
  const [exiting, setExiting] = useState(false);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    // Schedule each line to appear
    const timeouts = bootSequence.map((item, i) =>
      setTimeout(() => setVisibleLines((prev) => [...prev, i]), item.delay)
    );

    // Animate progress bar
    const progressInterval = setInterval(() => {
      setProgress((p) => Math.min(p + 1.5, 100));
    }, 40);

    // Start exit after total duration
    const exitTimeout = setTimeout(() => {
      setExiting(true);
      clearInterval(progressInterval);
      setProgress(100);
    }, TOTAL_DURATION);

    // Unmount after exit animation
    const unmountTimeout = setTimeout(() => {
      setBooted();
    }, TOTAL_DURATION + 900);

    return () => {
      timeouts.forEach(clearTimeout);
      clearTimeout(exitTimeout);
      clearTimeout(unmountTimeout);
      clearInterval(progressInterval);
    };
  }, [setBooted]);

  const getLineColor = (type: string) => {
    switch (type) {
      case 'title': return 'text-friday-cyan font-bold text-lg tracking-[0.3em]';
      case 'divider': return 'text-friday-cyan/20 text-xs';
      case 'info': return 'text-friday-text/70 font-mono text-sm';
      case 'success': return 'text-friday-success font-medium text-sm';
      case 'greeting': return 'text-friday-cyan text-xl font-bold mt-4 text-glow';
      default: return 'text-friday-text/60 text-sm font-mono';
    }
  };

  return (
    <AnimatePresence>
      {!exiting && (
        <motion.div
          className="fixed inset-0 z-[100] flex flex-col items-center justify-center"
          style={{ background: '#040404' }}
          initial={{ opacity: 1 }}
          exit={{ opacity: 0, filter: 'blur(12px)', scale: 1.02 }}
          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
        >
          {/* Scanlines */}
          <div className="absolute inset-0 scanlines pointer-events-none" />

          {/* Ambient glow */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] rounded-full bg-friday-cyan/5 blur-3xl pointer-events-none" />

          {/* Terminal window */}
          <motion.div
            className="relative glass-strong rounded-2xl p-8 w-[520px] max-w-[90vw] border border-friday-cyan/20"
            initial={{ scale: 0.92, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
          >
            {/* Window chrome */}
            <div className="flex items-center gap-2 mb-6 pb-4 border-b border-friday-border">
              <div className="flex gap-1.5">
                <div className="w-3 h-3 rounded-full bg-friday-danger/60" />
                <div className="w-3 h-3 rounded-full bg-friday-warning/60" />
                <div className="w-3 h-3 rounded-full bg-friday-success/60" />
              </div>
              <span className="flex-1 text-center text-[10px] font-mono text-friday-muted tracking-widest">
                FRIDAY — SYSTEM TERMINAL
              </span>
            </div>

            {/* Boot lines */}
            <div className="flex flex-col gap-2 min-h-[240px]">
              {bootSequence.map((item, i) => (
                <AnimatePresence key={i}>
                  {visibleLines.includes(i) && (
                    <motion.div
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.3, ease: 'easeOut' }}
                      className={getLineColor(item.type)}
                    >
                      {item.type === 'info' && visibleLines[visibleLines.length - 1] === i && (
                        <span className="inline-block w-2 h-4 bg-friday-cyan/80 animate-pulse ml-1 align-middle" />
                      )}
                      {item.text}
                    </motion.div>
                  )}
                </AnimatePresence>
              ))}
            </div>

            {/* Progress bar */}
            <div className="mt-6 pt-4 border-t border-friday-border/40">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-mono text-friday-muted">SYSTEM INITIALIZATION</span>
                <span className="text-[10px] font-mono text-friday-cyan">{Math.round(progress)}%</span>
              </div>
              <div className="h-1 bg-friday-cyan/10 rounded-full overflow-hidden">
                <motion.div
                  className="h-full rounded-full"
                  style={{
                    background: 'linear-gradient(90deg, #0066ff, #00b4ff, #00e5ff)',
                    width: `${progress}%`,
                    boxShadow: '0 0 10px rgba(0,180,255,0.6)',
                  }}
                  transition={{ duration: 0.1 }}
                />
              </div>
            </div>
          </motion.div>

          {/* Bottom signature */}
          <motion.p
            className="absolute bottom-8 text-[10px] font-mono text-friday-muted/40 tracking-widest"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1 }}
          >
            FRIDAY AI OPERATING SYSTEM • CLASSIFIED
          </motion.p>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
