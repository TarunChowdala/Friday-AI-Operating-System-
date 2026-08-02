import { motion } from 'framer-motion';
import { useEffect, useState } from 'react';
import { Cpu, MemoryStick, Brain, Volume2, Server, Bot } from 'lucide-react';

interface BarStatProps {
  label: string;
  value: number;
  unit: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
}

function BarStat({ label, value, unit, icon: Icon }: BarStatProps) {
  const color = value > 80 ? '#ff3366' : value > 65 ? '#ffaa00' : '#00b4ff';

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Icon size={11} style={{ color }} />
          <span className="text-[10px] font-medium text-friday-muted">{label}</span>
        </div>
        <span className="text-[10px] font-mono font-bold" style={{ color }}>
          {value.toFixed(0)}{unit}
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-white/5 overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          animate={{ width: `${value}%` }}
          transition={{ duration: 1.5, ease: 'easeOut' }}
          style={{ background: `linear-gradient(90deg, ${color}aa, ${color})`, boxShadow: `0 0 6px ${color}88` }}
        />
      </div>
    </div>
  );
}

interface StatusBadgeProps {
  label: string;
  status: 'active' | 'ready' | 'standby' | 'offline';
  icon: React.ComponentType<{ size?: number; className?: string }>;
}

function StatusBadge({ label, status, icon: Icon }: StatusBadgeProps) {
  const cfg = {
    active: { dot: 'bg-friday-success', text: 'text-friday-success', bg: 'bg-friday-success/8 border-friday-success/20' },
    ready: { dot: 'bg-friday-cyan', text: 'text-friday-cyan', bg: 'bg-friday-cyan/8 border-friday-cyan/20' },
    standby: { dot: 'bg-yellow-400', text: 'text-yellow-400', bg: 'bg-yellow-400/8 border-yellow-400/20' },
    offline: { dot: 'bg-friday-danger', text: 'text-friday-danger', bg: 'bg-friday-danger/8 border-friday-danger/20' },
  }[status];

  return (
    <div className={`flex items-center gap-2 px-2.5 py-2 rounded-xl border ${cfg.bg} transition-all`}>
      <Icon size={11} className={cfg.text} />
      <span className="text-[10px] font-medium text-friday-muted flex-1">{label}</span>
      <div className="flex items-center gap-1">
        <motion.div
          className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`}
          animate={{ opacity: status === 'offline' || status === 'standby' ? 1 : [1, 0.4, 1] }}
          transition={{ duration: 1.5, repeat: Infinity }}
        />
        <span className={`text-[9px] font-mono capitalize ${cfg.text}`}>{status}</span>
      </div>
    </div>
  );
}

export default function SystemHealthCard() {
  const [stats, setStats] = useState({ cpu: 32, memory: 58 });

  useEffect(() => {
    const id = setInterval(() => {
      setStats({
        cpu: Math.max(12, Math.min(92, 32 + (Math.random() - 0.5) * 24)),
        memory: Math.max(35, Math.min(88, 58 + (Math.random() - 0.5) * 12)),
      });
    }, 3500);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h3 className="text-[10px] font-bold tracking-[0.18em] uppercase text-friday-muted">System Health</h3>
        <span className="text-[9px] font-mono text-friday-success/80 bg-friday-success/8 px-2 py-0.5 rounded-full border border-friday-success/20">
          NOMINAL
        </span>
      </div>

      <div className="flex flex-col gap-2.5">
        <BarStat label="CPU Load" value={stats.cpu} unit="%" icon={Cpu} />
        <BarStat label="Memory" value={stats.memory} unit="%" icon={MemoryStick} />
      </div>

      <div className="h-px bg-friday-border/30" />

      <div className="flex flex-col gap-1.5">
        <StatusBadge label="Model Loaded" status="ready" icon={Brain} />
        <StatusBadge label="Voice Engine" status="ready" icon={Volume2} />
        <StatusBadge label="Core Server" status="active" icon={Server} />
        <StatusBadge label="Agents (3)" status="active" icon={Bot} />
      </div>
    </div>
  );
}
