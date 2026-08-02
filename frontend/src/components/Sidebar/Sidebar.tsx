import { motion } from 'framer-motion';
import {
  Home, MessageSquare, BookOpen, Brain, Bot, Wrench,
  LayoutDashboard, Settings, ChevronLeft, ChevronRight, Zap,
} from 'lucide-react';
import { useFridayStore } from '../../store/useFridayStore';
import NavItem from './NavItem';
import type { NavItemId } from '../../types';

interface NavLink {
  id: NavItemId;
  label: string;
  icon: React.ReactNode;
}

const navLinks: NavLink[] = [
  { id: 'home', label: 'Home', icon: <Home size={18} /> },
  { id: 'conversations', label: 'Conversations', icon: <MessageSquare size={18} /> },
  { id: 'knowledge', label: 'Knowledge', icon: <BookOpen size={18} /> },
  { id: 'memory', label: 'Memory', icon: <Brain size={18} /> },
  { id: 'agents', label: 'Agents', icon: <Bot size={18} /> },
  { id: 'tools', label: 'Tools', icon: <Wrench size={18} /> },
  { id: 'dashboard', label: 'Dashboard', icon: <LayoutDashboard size={18} /> },
  { id: 'settings', label: 'Settings', icon: <Settings size={18} /> },
];

export default function Sidebar() {
  const { activeNav, setActiveNav, sidebarCollapsed, toggleSidebar } = useFridayStore();

  return (
    <motion.aside
      className="relative flex flex-col h-full glass-strong border-r border-friday-border z-20 flex-shrink-0 overflow-hidden"
      animate={{ width: sidebarCollapsed ? '68px' : '220px' }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
    >
      {/* Right ambient strip */}
      <div className="absolute top-0 right-0 w-px h-full bg-gradient-to-b from-transparent via-friday-cyan/30 to-transparent pointer-events-none" />

      {/* Logo */}
      <div className="flex items-center px-3.5 py-5 border-b border-friday-border/50 gap-3 overflow-hidden">
        {/* Hex icon */}
        <div className="flex-shrink-0 w-9 h-9 flex-center relative">
          <svg viewBox="0 0 36 36" fill="none" className="w-9 h-9">
            <path d="M18 2L33 10.5V26L18 34.5L3 26V10.5L18 2Z"
              stroke="url(#sg)" strokeWidth="1.4" fill="url(#sf)" />
            <text x="18" y="22.5" textAnchor="middle" fill="#00e5ff"
              fontSize="9.5" fontFamily="Space Grotesk" fontWeight="700">F</text>
            <defs>
              <linearGradient id="sg" x1="3" y1="2" x2="33" y2="34.5" gradientUnits="userSpaceOnUse">
                <stop stopColor="#00b4ff" />
                <stop offset="1" stopColor="#0066ff" />
              </linearGradient>
              <linearGradient id="sf" x1="3" y1="2" x2="33" y2="34.5" gradientUnits="userSpaceOnUse">
                <stop stopColor="rgba(0,180,255,0.12)" />
                <stop offset="1" stopColor="rgba(0,100,255,0.06)" />
              </linearGradient>
            </defs>
          </svg>
          <motion.div
            className="absolute inset-0 rounded-full bg-friday-cyan/8 blur-md"
            animate={{ opacity: [0.5, 1, 0.5] }}
            transition={{ duration: 3, repeat: Infinity }}
          />
        </div>

        <motion.div
          className="overflow-hidden flex flex-col"
          animate={{ opacity: sidebarCollapsed ? 0 : 1, width: sidebarCollapsed ? 0 : 'auto' }}
          transition={{ duration: 0.25 }}
        >
          <span className="text-sm font-bold tracking-[0.2em] gradient-text whitespace-nowrap">FRIDAY</span>
          <span className="text-[9px] font-mono text-friday-muted/60 tracking-widest whitespace-nowrap">AI OS v4.2</span>
        </motion.div>
      </div>

      {/* Navigation */}
      <nav className="flex flex-col gap-0.5 px-2.5 py-4 flex-1 overflow-y-auto overflow-x-hidden">
        <div className="mb-2 px-1">
          <motion.span
            className="text-[9px] font-bold tracking-[0.2em] text-friday-muted/40 uppercase"
            animate={{ opacity: sidebarCollapsed ? 0 : 1 }}
            transition={{ duration: 0.2 }}
          >
            Navigation
          </motion.span>
        </div>

        {navLinks.map((link) => (
          <NavItem
            key={link.id}
            id={link.id}
            label={link.label}
            icon={link.icon}
            isActive={activeNav === link.id}
            collapsed={sidebarCollapsed}
            onClick={() => setActiveNav(link.id)}
          />
        ))}
      </nav>

      {/* Status + collapse */}
      <div className="px-2.5 py-4 border-t border-friday-border/50 flex flex-col gap-3">
        {/* System status pill */}
        <motion.div
          className={`flex items-center gap-2.5 px-3 py-2 rounded-xl bg-friday-success/8 border border-friday-success/20 ${sidebarCollapsed ? 'justify-center' : ''}`}
        >
          <motion.div
            className="w-2 h-2 rounded-full bg-friday-success flex-shrink-0"
            animate={{ opacity: [1, 0.4, 1], scale: [1, 1.2, 1] }}
            transition={{ duration: 2, repeat: Infinity }}
          />
          <motion.span
            className="text-[10px] font-mono text-friday-success/80 whitespace-nowrap overflow-hidden"
            animate={{ opacity: sidebarCollapsed ? 0 : 1, width: sidebarCollapsed ? 0 : 'auto' }}
            transition={{ duration: 0.25 }}
          >
            SYSTEMS ONLINE
          </motion.span>
        </motion.div>

        {/* Collapse button */}
        <motion.button
          id="sidebar-collapse-btn"
          onClick={toggleSidebar}
          className={`flex items-center gap-2 px-3 py-2 rounded-xl border border-friday-border hover:border-friday-cyan/30 hover:bg-friday-cyan/6 text-friday-muted hover:text-friday-cyan transition-all ${sidebarCollapsed ? 'justify-center' : ''}`}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.97 }}
        >
          {sidebarCollapsed ? <ChevronRight size={15} /> : <ChevronLeft size={15} />}
          <motion.span
            className="text-[11px] font-medium whitespace-nowrap overflow-hidden"
            animate={{ opacity: sidebarCollapsed ? 0 : 1, width: sidebarCollapsed ? 0 : 'auto' }}
            transition={{ duration: 0.25 }}
          >
            Collapse
          </motion.span>
        </motion.button>
      </div>

      {/* Bottom power icon */}
      <div className="flex-center pb-3 opacity-30">
        <motion.div animate={{ rotate: [0, 360] }} transition={{ duration: 25, repeat: Infinity, ease: 'linear' }}>
          <Zap size={12} className="text-friday-cyan" />
        </motion.div>
      </div>
    </motion.aside>
  );
}
