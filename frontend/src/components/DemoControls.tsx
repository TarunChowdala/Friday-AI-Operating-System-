import { motion } from 'framer-motion';
import { useFridayStore } from '../store/useFridayStore';
import type { AssistantState } from '../types';

const demos: { state: AssistantState; label: string }[] = [
  { state: 'idle', label: 'Idle' },
  { state: 'listening', label: 'Listen' },
  { state: 'thinking', label: 'Think' },
  { state: 'speaking', label: 'Speak' },
];

const stateColor: Record<AssistantState, string> = {
  idle: 'border-friday-muted/30 text-friday-muted hover:border-friday-cyan/40 hover:text-friday-cyan',
  listening: 'border-friday-cyan/50 text-friday-cyan hover:bg-friday-cyan/8',
  thinking: 'border-yellow-400/50 text-yellow-400 hover:bg-yellow-400/8',
  speaking: 'border-friday-success/50 text-friday-success hover:bg-friday-success/8',
};

export default function DemoControls() {
  const { assistantState, setAssistantState } = useFridayStore();

  return (
    <motion.div
      className="flex items-center gap-2 glass rounded-2xl px-4 py-2 border border-friday-border/50"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 1.0 }}
    >
      <span className="text-[9px] font-mono text-friday-muted/50 tracking-widest mr-1">DEMO</span>
      {demos.map(({ state, label }) => (
        <motion.button
          key={state}
          id={`demo-${state}`}
          onClick={() => setAssistantState(state)}
          className={`text-[10px] font-mono font-medium px-2.5 py-1.5 rounded-lg border transition-all ${stateColor[state]} ${
            assistantState === state ? 'ring-1 ring-offset-0 ring-current/40 bg-current/6' : ''
          }`}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
        >
          {label}
        </motion.button>
      ))}
    </motion.div>
  );
}
