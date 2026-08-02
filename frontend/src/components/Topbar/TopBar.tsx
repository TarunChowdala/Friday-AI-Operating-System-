import { motion, AnimatePresence } from 'framer-motion';
import { Settings, Mic, MicOff, Wifi, WifiOff, Activity, Cpu, Volume2, VolumeX } from 'lucide-react';
import { useFridayStore } from '../../store/useFridayStore';

const stateConfig = {
  idle: { label: 'STANDBY', color: 'text-friday-muted', dot: 'bg-friday-muted/50' },
  listening: { label: 'ACTIVE LISTEN', color: 'text-friday-cyan', dot: 'bg-friday-cyan' },
  thinking: { label: 'PROCESSING', color: 'text-yellow-400', dot: 'bg-yellow-400' },
  speaking: { label: 'SYNTHESIZING', color: 'text-friday-success', dot: 'bg-friday-success' },
};

export default function TopBar() {
  const { assistantState, isMicActive, isMuted, isConnected, toggleMic, toggleMute } = useFridayStore();
  const cfg = stateConfig[assistantState];

  return (
    <motion.header
      initial={{ y: -50, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1], delay: 0.1 }}
      className="flex items-center justify-between h-[52px] px-5 glass-strong border-b border-friday-border z-30 flex-shrink-0"
    >
      {/* Left: Brand */}
      <div className="flex items-center gap-3 min-w-0">
        <span className="text-sm font-bold tracking-[0.28em] gradient-text">FRIDAY</span>
        <div className="w-px h-4 bg-friday-border/60" />
        <div className="flex items-center gap-1.5">
          <Cpu size={11} className="text-friday-muted/50" />
          <span className="text-[10px] font-mono text-friday-muted/50 tracking-widest hidden sm:block">OS v4.2.1</span>
        </div>
      </div>

      {/* Center: State pill */}
      <motion.div
        className="flex items-center gap-2.5 px-4 py-1.5 rounded-full glass border border-friday-border"
        animate={{ borderColor: assistantState !== 'idle' ? 'rgba(0,180,255,0.4)' : 'rgba(0,180,255,0.12)' }}
        transition={{ duration: 0.4 }}
      >
        <motion.div
          className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`}
          animate={{ scale: assistantState !== 'idle' ? [1, 1.5, 1] : [1, 1.15, 1], opacity: [1, 0.6, 1] }}
          transition={{ duration: 1.2, repeat: Infinity, ease: 'easeInOut' }}
        />
        <AnimatePresence mode="wait">
          <motion.span
            key={assistantState}
            className={`text-[11px] font-mono tracking-[0.15em] font-semibold ${cfg.color}`}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.25 }}
          >
            {cfg.label}
          </motion.span>
        </AnimatePresence>
        <Activity size={11} className={`${cfg.color} opacity-70`} />
      </motion.div>

      {/* Right: Controls */}
      <div className="flex items-center gap-1.5">
        {/* Mic toggle */}
        <motion.button
          id="topbar-mic"
          onClick={toggleMic}
          className={`w-8 h-8 rounded-lg flex-center border transition-colors ${
            isMicActive
              ? 'bg-friday-cyan/15 border-friday-cyan/40 text-friday-cyan'
              : 'bg-transparent border-friday-border text-friday-muted hover:border-friday-cyan/30 hover:text-friday-cyan'
          }`}
          whileHover={{ scale: 1.08 }}
          whileTap={{ scale: 0.9 }}
        >
          {isMicActive ? <Mic size={14} /> : <MicOff size={14} />}
        </motion.button>

        {/* Voice toggle */}
        <motion.button
          id="topbar-voice"
          onClick={toggleMute}
          className={`w-8 h-8 rounded-lg flex-center border transition-colors ${
            isMuted
              ? 'bg-friday-danger/12 border-friday-danger/30 text-friday-danger'
              : 'bg-transparent border-friday-border text-friday-muted hover:border-friday-cyan/30 hover:text-friday-cyan'
          }`}
          whileHover={{ scale: 1.08 }}
          whileTap={{ scale: 0.9 }}
        >
          {isMuted ? <VolumeX size={14} /> : <Volume2 size={14} />}
        </motion.button>

        {/* Connection */}
        <div className={`w-8 h-8 rounded-lg flex-center border ${
          isConnected
            ? 'border-friday-success/30 text-friday-success bg-friday-success/8'
            : 'border-friday-danger/30 text-friday-danger bg-friday-danger/8'
        }`}>
          {isConnected ? <Wifi size={14} /> : <WifiOff size={14} />}
        </div>

        <div className="w-px h-5 bg-friday-border/50 mx-0.5" />

        {/* Settings */}
        <motion.button
          id="topbar-settings"
          className="w-8 h-8 rounded-lg flex-center border border-friday-border text-friday-muted hover:text-friday-cyan hover:border-friday-cyan/30 transition-colors"
          whileHover={{ scale: 1.08, rotate: 45 }}
          whileTap={{ scale: 0.9 }}
          transition={{ type: 'spring', stiffness: 400, damping: 17 }}
        >
          <Settings size={14} />
        </motion.button>
      </div>
    </motion.header>
  );
}
