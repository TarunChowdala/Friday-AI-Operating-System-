import { motion } from 'framer-motion';
import type { NavItemId } from '../../types';

interface NavItemProps {
  id: NavItemId;
  label: string;
  icon: React.ReactNode;
  isActive: boolean;
  collapsed: boolean;
  onClick: () => void;
}

export default function NavItem({ id, label, icon, isActive, collapsed, onClick }: NavItemProps) {
  return (
    <motion.button
      id={`nav-${id}`}
      onClick={onClick}
      className={`nav-item group relative w-full flex items-center gap-3 px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-300 text-left overflow-hidden ${
        isActive
          ? 'bg-friday-cyan/12 border border-friday-cyan/30 shadow-glow-sm'
          : 'border border-transparent hover:bg-friday-cyan/6 hover:border-friday-cyan/15'
      }`}
      whileHover={{ x: 2 }}
      whileTap={{ scale: 0.97 }}
      title={collapsed ? label : undefined}
    >
      {/* Active indicator */}
      {isActive && (
        <motion.div
          layoutId="navActiveBar"
          className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-gradient-to-b from-friday-cyan to-friday-blue"
          transition={{ type: 'spring', stiffness: 500, damping: 35 }}
        />
      )}

      {/* Icon */}
      <span className={`flex-shrink-0 transition-all duration-300 ${isActive ? 'text-friday-cyan drop-shadow-[0_0_6px_rgba(0,180,255,0.8)]' : 'text-friday-muted group-hover:text-friday-cyan'}`}>
        {icon}
      </span>

      {/* Label */}
      <motion.span
        className={`text-sm font-medium whitespace-nowrap overflow-hidden ${isActive ? 'text-friday-text' : 'text-friday-muted group-hover:text-friday-text'}`}
        animate={{ opacity: collapsed ? 0 : 1, width: collapsed ? 0 : 'auto' }}
        transition={{ duration: 0.25 }}
      >
        {label}
      </motion.span>

      {/* Collapsed tooltip */}
      {collapsed && (
        <div className="absolute left-full ml-3 px-3 py-1.5 glass-strong rounded-lg text-xs font-medium text-friday-text whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-all duration-200 z-50 border border-friday-cyan/20 shadow-glow-sm">
          {label}
        </div>
      )}
    </motion.button>
  );
}
