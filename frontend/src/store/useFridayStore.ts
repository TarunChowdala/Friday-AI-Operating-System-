import { create } from 'zustand';
import type { AssistantState } from '../types';

interface FridayStore {
  assistantState: AssistantState;
  isMicActive: boolean;
  isMuted: boolean;
  isConnected: boolean;
  isBooted: boolean;

  setAssistantState: (state: AssistantState) => void;
  toggleMic: () => void;
  toggleMute: () => void;
  setBooted: () => void;
}

const getGreeting = (): string => {
  const h = new Date().getHours();
  if (h < 12) return 'Good Morning, Boss.';
  if (h < 17) return 'Good Afternoon, Boss.';
  if (h < 21) return 'Good Evening, Boss.';
  return 'Working Late, Boss?';
};

export { getGreeting };

export const useFridayStore = create<FridayStore>((set) => ({
  assistantState: 'idle',
  isMicActive: false,
  isMuted: false,
  isConnected: true,
  isBooted: false,

  setAssistantState: (state) => set({ assistantState: state }),
  toggleMic: () =>
    set((s) => ({
      isMicActive: !s.isMicActive,
      assistantState: !s.isMicActive ? 'listening' : 'idle',
    })),
  toggleMute: () => set((s) => ({ isMuted: !s.isMuted })),
  setBooted: () => set({ isBooted: true }),
}));
