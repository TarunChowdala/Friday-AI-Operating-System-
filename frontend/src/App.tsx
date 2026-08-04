import { motion, AnimatePresence } from 'framer-motion';
import BootScreen from './components/BootScreen';
import TopBar from './components/Topbar/TopBar';
import Home from './pages/Home';
import { useFridayStore } from './store/useFridayStore';

export default function App() {
  const isBooted = useFridayStore((s) => s.isBooted);

  return (
    <div className="w-screen h-screen bg-[#050505] overflow-hidden relative flex flex-col">
      <AnimatePresence>
        {!isBooted && <BootScreen key="boot" />}
      </AnimatePresence>

      <TopBar />

      <motion.div
        className="flex-1 min-h-0 relative z-10"
        initial={{ opacity: 0 }}
        animate={{ opacity: isBooted ? 1 : 0 }}
        transition={{ duration: 0.8, ease: 'easeOut' }}
      >
        <Home />
      </motion.div>
    </div>
  );
}
