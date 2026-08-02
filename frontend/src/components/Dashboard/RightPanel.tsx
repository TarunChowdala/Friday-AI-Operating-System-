import { motion } from 'framer-motion';
import { useEffect, useState } from 'react';
import TaskCard from '../Cards/TaskCard';
import ConversationCard from '../Cards/ConversationCard';
import SystemHealthCard from '../Cards/SystemHealthCard';
import { slideInRight } from '../../animations/variants';

function LiveClock() {
  const [time, setTime] = useState(() => new Date());

  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex flex-col items-center py-3 border-b border-friday-border/30">
      <span className="text-2xl font-bold font-mono gradient-text tracking-wider">
        {time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })}
      </span>
      <span className="text-[10px] font-mono text-friday-muted/60 mt-1 tracking-widest">
        {time.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }).toUpperCase()}
      </span>
    </div>
  );
}

export default function RightPanel() {
  return (
    <motion.aside
      className="w-[300px] flex-shrink-0 h-full glass-strong border-l border-friday-border z-20 flex flex-col overflow-hidden relative"
      variants={slideInRight}
      initial="hidden"
      animate="visible"
    >
      {/* Ambient strip */}
      <div className="absolute top-0 left-0 w-px h-full bg-gradient-to-b from-transparent via-friday-cyan/25 to-transparent pointer-events-none" />

      {/* Corner glow */}
      <div className="absolute top-0 right-0 w-32 h-32 bg-friday-cyan/4 blur-3xl rounded-full -translate-y-1/2 translate-x-1/2 pointer-events-none" />

      {/* Header label */}
      <div className="px-4 pt-4 pb-2 flex-shrink-0">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-1 h-3.5 rounded-full bg-gradient-to-b from-friday-cyan to-friday-blue" />
          <span className="text-[9px] font-mono font-bold tracking-[0.25em] text-friday-cyan/70 uppercase">Diagnostics</span>
        </div>
        <LiveClock />
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-4 pb-4 flex flex-col gap-0">
        {/* Tasks */}
        <div className="py-4 border-b border-friday-border/25">
          <TaskCard />
        </div>

        {/* Conversations */}
        <div className="py-4 border-b border-friday-border/25">
          <ConversationCard />
        </div>

        {/* System Health */}
        <div className="py-4">
          <SystemHealthCard />
        </div>
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-friday-border/40 flex items-center justify-between flex-shrink-0">
        <span className="text-[9px] font-mono text-friday-muted/40">FRIDAY OS</span>
        <div className="flex items-center gap-1.5">
          <motion.div
            className="w-1.5 h-1.5 rounded-full bg-friday-success"
            animate={{ opacity: [1, 0.3, 1] }}
            transition={{ duration: 2, repeat: Infinity }}
          />
          <span className="text-[9px] font-mono text-friday-success/70">ONLINE</span>
        </div>
      </div>
    </motion.aside>
  );
}
