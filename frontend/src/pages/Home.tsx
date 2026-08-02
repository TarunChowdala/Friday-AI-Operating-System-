import { motion } from 'framer-motion';
import StatusDisplay from '../components/StatusDisplay';
import MicButton from '../components/Mic/MicButton';
import DemoControls from '../components/DemoControls';
import { fadeIn } from '../animations/variants';



export default function Home() {

  return (
    <motion.main
      className="flex-1 flex flex-col items-center justify-between py-6 px-4 relative overflow-hidden min-h-0"
      variants={fadeIn}
      initial="hidden"
      animate="visible"
    >
      {/* Background grid */}
      <div
        className="absolute inset-0 pointer-events-none opacity-40"
        style={{
          backgroundImage: 'linear-gradient(rgba(0,180,255,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(0,180,255,0.04) 1px, transparent 1px)',
          backgroundSize: '48px 48px',
        }}
      />

      {/* Radial gradient center bloom */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at 50% 46%, rgba(0,100,255,0.07) 0%, transparent 65%)' }}
      />

      {/* HUD overlay */}

      {/* ─── STATUS TEXT ─── */}
      <motion.div
        className="flex-shrink-0 w-full flex justify-center"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, delay: 0.5 }}
      >
        <StatusDisplay />
      </motion.div>

      {/* ─── MIC ─── */}
      <motion.div
        className="flex-shrink-0 flex flex-col items-center gap-4"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, delay: 0.7 }}
      >
        <MicButton />
        <DemoControls />
      </motion.div>

      {/* Bottom edge line */}
      <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-friday-cyan/20 to-transparent" />
    </motion.main>
  );
}
