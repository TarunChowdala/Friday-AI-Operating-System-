import { motion } from 'framer-motion';
import StatusDisplay from '../components/StatusDisplay';
import MicButton from '../components/Mic/MicButton';
import AIScene from '../components/AI/AIScene';
import DemoControls from '../components/DemoControls';
import { fadeIn } from '../animations/variants';
import { useFridayWebSocket } from '../hooks/useFridayWebSocket';
import { useFridayStore } from '../store/useFridayStore';

export default function Home() {
  const { toggleMic } = useFridayWebSocket();
  const assistantState = useFridayStore((s) => s.assistantState);

  return (
    <motion.main
      className="flex-1 flex flex-col items-center relative overflow-hidden min-h-0 bg-[#050505]"
      variants={fadeIn}
      initial="hidden"
      animate="visible"
    >
      <motion.div
        className="absolute top-8 left-0 right-0 z-20 flex flex-col items-center gap-3 pointer-events-none"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, delay: 0.4 }}
      >
        <StatusDisplay />
      </motion.div>

      <div className="absolute inset-0 z-0">
        <AIScene state={assistantState} />
      </div>

      <motion.div
        className="absolute bottom-6 left-0 right-0 z-20 flex flex-col items-center gap-3"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, delay: 0.6 }}
      >
        <DemoControls />
        <MicButton onStart={toggleMic} onStop={toggleMic} />
      </motion.div>
    </motion.main>
  );
}
