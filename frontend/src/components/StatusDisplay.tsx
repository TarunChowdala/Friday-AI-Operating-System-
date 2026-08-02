import { motion, AnimatePresence } from 'framer-motion';
import { useEffect, useState } from 'react';
import { useFridayStore, getGreeting } from '../store/useFridayStore';

const idleMessages = [
  'All systems operational.',
  'Neural pathways synchronized.',
  'Awaiting your command.',
  'Quantum processors active.',
  'Ready, Boss.',
  'Knowledge base indexed.',
  'Voice synthesis calibrated.',
  'Background analysis complete.',
];

export default function StatusDisplay() {
  const { assistantState } = useFridayStore();
  const [idleMsg, setIdleMsg] = useState(idleMessages[0]);

  useEffect(() => {
    if (assistantState !== 'idle') return;
    const id = setInterval(() => {
      setIdleMsg((m) => {
        const next = idleMessages[(idleMessages.indexOf(m) + 1) % idleMessages.length];
        return next;
      });
    }, 4000);
    return () => clearInterval(id);
  }, [assistantState]);

  const activeStatus = () => {
    switch (assistantState) {
      case 'listening': return 'Listening...';
      case 'thinking': return 'Analyzing request...';
      case 'speaking': return 'Voice synthesis active...';
      default: return idleMsg;
    }
  };

  const statusColor = () => {
    switch (assistantState) {
      case 'listening': return 'text-friday-cyan text-glow-sm';
      case 'thinking': return 'text-yellow-400';
      case 'speaking': return 'text-friday-success';
      default: return 'text-friday-muted';
    }
  };

  return (
    <div className="flex flex-col items-center gap-3 select-none">
      {/* Greeting */}
      <motion.h1
        className="text-3xl md:text-[2.4rem] font-bold text-friday-text tracking-tight text-center"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
      >
        {getGreeting()}
      </motion.h1>

      {/* Status */}
      <AnimatePresence mode="wait">
        <motion.p
          key={activeStatus()}
          className={`text-base font-medium tracking-wide transition-colors ${statusColor()}`}
          initial={{ opacity: 0, y: 6, filter: 'blur(4px)' }}
          animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
          exit={{ opacity: 0, y: -6, filter: 'blur(4px)' }}
          transition={{ duration: 0.35, ease: 'easeOut' }}
        >
          {activeStatus()}
        </motion.p>
      </AnimatePresence>

      {/* Active state indicator dots */}
      <AnimatePresence>
        {assistantState !== 'idle' && (
          <motion.div
            className="flex items-center gap-1.5"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
          >
            {[0, 1, 2].map((i) => (
              <motion.div
                key={i}
                className={`h-1 rounded-full ${
                  assistantState === 'listening' ? 'bg-friday-cyan' :
                  assistantState === 'thinking' ? 'bg-yellow-400' : 'bg-friday-success'
                }`}
                animate={{ width: ['6px', '18px', '6px'] }}
                transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.18, ease: 'easeInOut' }}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
