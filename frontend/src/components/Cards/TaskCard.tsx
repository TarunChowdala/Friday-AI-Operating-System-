import { motion } from 'framer-motion';
import { CheckCircle2, Circle, Clock } from 'lucide-react';
import { useFridayStore } from '../../store/useFridayStore';
import { staggerContainer, staggerItem } from '../../animations/variants';

const priorityStyle = {
  high: { badge: 'text-friday-danger bg-friday-danger/10 border-friday-danger/30', dot: 'bg-friday-danger' },
  medium: { badge: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30', dot: 'bg-yellow-400' },
  low: { badge: 'text-friday-muted bg-friday-muted/10 border-friday-muted/20', dot: 'bg-friday-muted/50' },
};

export default function TaskCard() {
  const { tasks, completeTask } = useFridayStore();
  const done = tasks.filter((t) => t.completed).length;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="text-[10px] font-bold tracking-[0.18em] uppercase text-friday-muted">Today's Tasks</h3>
        <span className="text-xs font-mono text-friday-cyan">{done}/{tasks.length}</span>
      </div>

      {/* Progress */}
      <div className="h-[3px] rounded-full bg-friday-cyan/8 overflow-hidden">
        <motion.div
          className="h-full rounded-full bg-gradient-to-r from-friday-blue to-friday-cyan"
          animate={{ width: `${(done / tasks.length) * 100}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
          style={{ boxShadow: '0 0 8px rgba(0,180,255,0.5)' }}
        />
      </div>

      {/* Tasks */}
      <motion.div
        className="flex flex-col gap-1"
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
      >
        {tasks.map((task) => (
          <motion.div
            key={task.id}
            variants={staggerItem}
            layout
            className={`group flex items-start gap-2.5 px-3 py-2.5 rounded-xl border cursor-pointer transition-all ${
              task.completed
                ? 'bg-transparent border-friday-border/20 opacity-45'
                : 'bg-friday-surface/30 border-friday-border hover:border-friday-cyan/25 hover:bg-friday-cyan/4'
            }`}
            onClick={() => completeTask(task.id)}
            whileHover={{ x: 2 }}
          >
            <div className="mt-0.5 flex-shrink-0">
              {task.completed
                ? <CheckCircle2 size={14} className="text-friday-success" />
                : <Circle size={14} className="text-friday-muted/50 group-hover:text-friday-cyan transition-colors" />
              }
            </div>
            <div className="flex-1 min-w-0">
              <p className={`text-[11px] font-medium leading-relaxed ${task.completed ? 'line-through text-friday-muted' : 'text-friday-text'}`}>
                {task.title}
              </p>
              <div className="flex items-center gap-2 mt-1">
                {task.time && (
                  <div className="flex items-center gap-1">
                    <Clock size={9} className="text-friday-muted/50" />
                    <span className="text-[9px] text-friday-muted/60 font-mono">{task.time}</span>
                  </div>
                )}
                {task.tag && (
                  <span className="text-[9px] font-mono text-friday-cyan/60 bg-friday-cyan/6 px-1.5 py-0.5 rounded-md">
                    {task.tag}
                  </span>
                )}
              </div>
            </div>
            <span className={`text-[8px] font-bold tracking-widest px-1.5 py-0.5 rounded border uppercase flex-shrink-0 mt-0.5 ${priorityStyle[task.priority].badge}`}>
              {task.priority}
            </span>
          </motion.div>
        ))}
      </motion.div>
    </div>
  );
}
