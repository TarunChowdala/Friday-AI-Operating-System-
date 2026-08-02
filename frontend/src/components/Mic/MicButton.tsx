import { motion, AnimatePresence } from 'framer-motion';
import { Mic, MicOff } from 'lucide-react';
import { useFridayStore } from '../../store/useFridayStore';

// ─── Waveform ───
function Waveform({ active }: { active: boolean }) {
  const bars = 36;
  return (
    <div className="flex items-center justify-center gap-[2px] h-8 w-48">
      {Array.from({ length: bars }, (_, i) => (
        <motion.div
          key={i}
          className="rounded-full"
          style={{
            width: '2.5px',
            background: 'linear-gradient(to top, #0066ff, #00b4ff, #00e5ff)',
          }}
          animate={active ? {
            scaleY: [
              0.15 + Math.random() * 0.35,
              0.5 + Math.random() * 0.5,
              0.15 + Math.random() * 0.35,
            ],
          } : { scaleY: 0.12 }}
          transition={active ? {
            duration: 0.45 + Math.random() * 0.4,
            repeat: Infinity,
            repeatType: 'mirror',
            ease: 'easeInOut',
            delay: (i / bars) * 0.25,
          } : { duration: 0.4 }}
          style={{ height: '100%', width: '2.5px', background: 'linear-gradient(to top, #0066ff, #00b4ff, #00e5ff)' }}
        />
      ))}
    </div>
  );
}

// ─── Listening rings ───
function ListeningRings() {
  return (
    <>
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          className="absolute inset-0 rounded-full border border-friday-cyan/40"
          initial={{ scale: 1, opacity: 0.6 }}
          animate={{ scale: 2.8, opacity: 0 }}
          transition={{ duration: 2, repeat: Infinity, delay: i * 0.65, ease: 'easeOut' }}
        />
      ))}
    </>
  );
}

// ─── Thinking arc ───
function ThinkingArc() {
  return (
    <motion.div
      className="absolute inset-[-3px] rounded-full"
      style={{
        background: 'conic-gradient(from 0deg, transparent 0deg, rgba(255,170,0,0.7) 60deg, transparent 120deg)',
        WebkitMask: 'radial-gradient(circle, transparent 57%, black 58%)',
        mask: 'radial-gradient(circle, transparent 57%, black 58%)',
      }}
      animate={{ rotate: 360 }}
      transition={{ duration: 1.1, repeat: Infinity, ease: 'linear' }}
    />
  );
}

export default function MicButton() {
  const { assistantState, isMicActive, toggleMic } = useFridayStore();
  const isListening = assistantState === 'listening';
  const isThinking = assistantState === 'thinking';
  const isSpeaking = assistantState === 'speaking';
  const isActive = isMicActive || isListening || isSpeaking;

  const buttonClass = isListening
    ? 'bg-friday-cyan/18 border-2 border-friday-cyan shadow-glow-cyan'
    : isThinking
    ? 'bg-yellow-400/12 border-2 border-yellow-400/70'
    : isSpeaking
    ? 'bg-friday-success/12 border-2 border-friday-success/70'
    : 'bg-friday-surface/60 border-2 border-friday-border hover:border-friday-cyan/40 hover:bg-friday-cyan/8';

  const iconColor = isListening ? 'text-friday-cyan drop-shadow-[0_0_8px_rgba(0,180,255,0.9)]'
    : isThinking ? 'text-yellow-400'
    : isSpeaking ? 'text-friday-success'
    : 'text-friday-muted';

  return (
    <div className="flex flex-col items-center gap-5">
      {/* Waveform above */}
      <AnimatePresence>
        {(isSpeaking || isListening) && (
          <motion.div
            initial={{ opacity: 0, y: 8, scaleX: 0.8 }}
            animate={{ opacity: 1, y: 0, scaleX: 1 }}
            exit={{ opacity: 0, y: 8 }}
            transition={{ duration: 0.4 }}
          >
            <Waveform active={isSpeaking || isListening} />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main button */}
      <div className="relative flex-center">
        {isListening && <ListeningRings />}

        <motion.button
          id="mic-main-btn"
          onClick={toggleMic}
          className={`relative w-[76px] h-[76px] rounded-full flex-center z-10 cursor-pointer transition-colors duration-300 ${buttonClass}`}
          whileHover={{ scale: 1.06 }}
          whileTap={{ scale: 0.93 }}
          transition={{ type: 'spring', stiffness: 400, damping: 17 }}
          aria-label={isMicActive ? 'Stop' : 'Start listening'}
        >
          {/* Thinking overlay */}
          {isThinking && <ThinkingArc />}

          {/* Idle pulse */}
          {!isActive && (
            <motion.div
              className="absolute inset-0 rounded-full bg-friday-cyan/5"
              animate={{ scale: [1, 1.18, 1], opacity: [0.3, 0.65, 0.3] }}
              transition={{ duration: 3.5, repeat: Infinity, ease: 'easeInOut' }}
            />
          )}

          <AnimatePresence mode="wait">
            <motion.div
              key={isMicActive ? 'on' : 'off'}
              initial={{ scale: 0, opacity: 0, rotate: -15 }}
              animate={{ scale: 1, opacity: 1, rotate: 0 }}
              exit={{ scale: 0, opacity: 0, rotate: 15 }}
              transition={{ duration: 0.2, type: 'spring', stiffness: 500 }}
            >
              {isMicActive
                ? <Mic size={28} className={iconColor} />
                : <MicOff size={28} className="text-friday-muted/60" />
              }
            </motion.div>
          </AnimatePresence>
        </motion.button>
      </div>

      {/* Quiet idle waveform */}
      {!isSpeaking && !isListening && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 0.35 }}>
          <Waveform active={false} />
        </motion.div>
      )}

      {/* Label */}
      <motion.p
        className={`text-[10px] font-mono tracking-widest ${
          isListening ? 'text-friday-cyan' : isThinking ? 'text-yellow-400' : isSpeaking ? 'text-friday-success' : 'text-friday-muted/50'
        }`}
        animate={{ opacity: [0.7, 1, 0.7] }}
        transition={{ duration: 2.5, repeat: Infinity }}
      >
        {isListening ? '● LISTENING' : isThinking ? '◌ PROCESSING' : isSpeaking ? '◈ SPEAKING' : '○ STANDBY'}
      </motion.p>
    </div>
  );
}
