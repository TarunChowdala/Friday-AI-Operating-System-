import { motion } from 'framer-motion';
import { MessageSquare } from 'lucide-react';
import { useFridayStore } from '../../store/useFridayStore';

export default function ConversationCard() {
  const { conversations } = useFridayStore();

  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-[10px] font-bold tracking-[0.18em] uppercase text-friday-muted">Recent Conversations</h3>

      <div className="flex flex-col gap-1.5">
        {conversations.map((conv, i) => (
          <motion.div
            key={conv.id}
            id={`conv-item-${conv.id}`}
            initial={{ opacity: 0, x: 8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.05 }}
            className={`flex items-start gap-2.5 px-3 py-2.5 rounded-xl border cursor-pointer transition-all ${
              conv.active
                ? 'bg-friday-cyan/8 border-friday-cyan/25'
                : 'bg-friday-surface/20 border-friday-border/50 hover:border-friday-cyan/20 hover:bg-friday-cyan/4'
            }`}
            whileHover={{ x: 2 }}
          >
            <div className={`w-7 h-7 rounded-lg flex-center flex-shrink-0 border mt-0.5 ${
              conv.active ? 'bg-friday-cyan/15 border-friday-cyan/30' : 'bg-friday-surface/60 border-friday-border/50'
            }`}>
              <MessageSquare size={11} className={conv.active ? 'text-friday-cyan' : 'text-friday-muted'} />
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between gap-1">
                <p className={`text-[11px] font-semibold truncate ${conv.active ? 'text-friday-cyan' : 'text-friday-text'}`}>
                  {conv.title}
                </p>
                <span className="text-[9px] text-friday-muted/60 font-mono flex-shrink-0">{conv.time}</span>
              </div>
              <p className="text-[10px] text-friday-muted truncate mt-0.5">{conv.preview}</p>
              {conv.model && (
                <span className="text-[9px] font-mono text-friday-blue/60 mt-1 block">{conv.model}</span>
              )}
            </div>

            {conv.active && (
              <motion.div
                className="w-1.5 h-1.5 rounded-full bg-friday-cyan flex-shrink-0 mt-2"
                animate={{ opacity: [1, 0.3, 1] }}
                transition={{ duration: 1.8, repeat: Infinity }}
              />
            )}
          </motion.div>
        ))}
      </div>
    </div>
  );
}
