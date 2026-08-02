import { motion, AnimatePresence } from 'framer-motion';
import BootScreen from './components/BootScreen';
import Sidebar from './components/Sidebar/Sidebar';
import TopBar from './components/Topbar/TopBar';
import RightPanel from './components/Dashboard/RightPanel';
import Home from './pages/Home';
import GlobalParticles from './components/Particles/GlobalParticles';
import { useFridayStore } from './store/useFridayStore';

export default function App() {
  const isBooted = useFridayStore((s) => s.isBooted);

  return (
    <div className="w-screen h-screen bg-friday-bg overflow-hidden relative flex flex-col">

      {/* ─── Full-screen particle layer (Canvas2D, z-0) ─── */}
      <GlobalParticles />

      {/* ─── Boot screen (z-100) ─── */}
      <AnimatePresence>
        {!isBooted && <BootScreen key="boot" />}
      </AnimatePresence>

      {/* ─── Ambient blooms ─── */}
      <div className="absolute inset-0 pointer-events-none z-0">
        <div className="absolute top-0 left-20 w-[500px] h-[500px] rounded-full bg-friday-cyan/4 blur-3xl" />
        <div className="absolute bottom-0 right-72 w-[400px] h-[400px] rounded-full bg-friday-blue/4 blur-3xl" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[700px] rounded-full bg-friday-cyan/3 blur-3xl" />
      </div>

      {/* ─── Top Bar ─── */}
      <TopBar />

      {/* ─── Main layout ─── */}
      <motion.div
        className="flex flex-1 min-h-0 relative z-10"
        initial={{ opacity: 0 }}
        animate={{ opacity: isBooted ? 1 : 0 }}
        transition={{ duration: 0.8, ease: 'easeOut' }}
      >
        <Sidebar />
        <Home />
        <RightPanel />
      </motion.div>

      {/* ─── Global bottom glow edge ─── */}
      <motion.div
        className="absolute bottom-0 left-0 right-0 h-px pointer-events-none z-20"
        style={{ background: 'linear-gradient(90deg, transparent, rgba(0,180,255,0.5) 30%, rgba(0,229,255,0.6) 50%, rgba(0,180,255,0.5) 70%, transparent)' }}
        animate={{ opacity: [0.3, 0.8, 0.3] }}
        transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
      />
    </div>
  );
}
