import { useState } from 'react';
import { motion } from 'framer-motion';

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [text, setText] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (text.trim() && !disabled) {
      onSend(text.trim());
      setText('');
    }
  };

  return (
    <motion.form 
      onSubmit={handleSubmit}
      className="flex items-center gap-2 w-full max-w-lg mt-4"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.8 }}
    >
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={disabled}
        placeholder="Type a message to FRIDAY..."
        className="flex-1 glass bg-black/20 border border-friday-cyan/30 rounded-full px-4 py-2 text-sm text-friday-text placeholder:text-friday-muted focus:outline-none focus:border-friday-cyan transition-colors"
      />
      <button
        type="submit"
        disabled={!text.trim() || disabled}
        className="px-4 py-2 bg-friday-cyan/20 hover:bg-friday-cyan/30 text-friday-cyan text-sm font-medium rounded-full transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Send
      </button>
    </motion.form>
  );
}
