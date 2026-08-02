import { create } from 'zustand';
import type { AssistantState, NavItemId, Task, Conversation } from '../types';

interface FridayStore {
  // Core state
  assistantState: AssistantState;
  activeNav: NavItemId;
  isMicActive: boolean;
  isMuted: boolean;
  isConnected: boolean;
  isBooted: boolean;
  sidebarCollapsed: boolean;

  // Content
  tasks: Task[];
  conversations: Conversation[];

  // Mouse (updated frequently - use refs in components, not this)
  mouseNX: number;
  mouseNY: number;

  // Actions
  setAssistantState: (state: AssistantState) => void;
  setActiveNav: (nav: NavItemId) => void;
  toggleMic: () => void;
  toggleMute: () => void;
  toggleSidebar: () => void;
  setBooted: () => void;
  setMousePosition: (nx: number, ny: number) => void;
  completeTask: (id: string) => void;
}

const getGreeting = (): string => {
  const h = new Date().getHours();
  if (h < 12) return 'Good Morning, Boss.';
  if (h < 17) return 'Good Afternoon, Boss.';
  if (h < 21) return 'Good Evening, Boss.';
  return 'Working Late, Boss?';
};

export { getGreeting };

const defaultTasks: Task[] = [
  { id: '1', title: 'Review neural network architecture proposal', priority: 'high', completed: false, time: '09:00', tag: 'AI' },
  { id: '2', title: 'Analyze Q3 market sentiment data', priority: 'high', completed: false, time: '11:30', tag: 'Analytics' },
  { id: '3', title: 'Compile autonomous agent report', priority: 'medium', completed: true, time: '14:00', tag: 'Agents' },
  { id: '4', title: 'Deploy updated model to staging', priority: 'medium', completed: false, time: '15:30', tag: 'DevOps' },
  { id: '5', title: 'Security protocol audit', priority: 'low', completed: false, time: '17:00', tag: 'Security' },
];

const defaultConversations: Conversation[] = [
  { id: '1', title: 'System Architecture Review', preview: 'Analyzing distributed computing patterns...', time: '2m ago', active: true, model: 'FRIDAY-4o' },
  { id: '2', title: 'Market Research Brief', preview: 'Q3 performance metrics analyzed...', time: '1h ago', model: 'FRIDAY-4o' },
  { id: '3', title: 'Codebase Review Session', preview: 'Authentication module reviewed...', time: '3h ago', model: 'FRIDAY-4o' },
  { id: '4', title: 'Board Presentation Prep', preview: 'Key points for quarterly review...', time: 'Yesterday', model: 'FRIDAY-mini' },
];

export const useFridayStore = create<FridayStore>((set) => ({
  assistantState: 'idle',
  activeNav: 'home',
  isMicActive: false,
  isMuted: false,
  isConnected: true,
  isBooted: false,
  sidebarCollapsed: false,
  tasks: defaultTasks,
  conversations: defaultConversations,
  mouseNX: 0,
  mouseNY: 0,

  setAssistantState: (state) => set({ assistantState: state }),
  setActiveNav: (nav) => set({ activeNav: nav }),
  toggleMic: () =>
    set((s) => ({
      isMicActive: !s.isMicActive,
      assistantState: !s.isMicActive ? 'listening' : 'idle',
    })),
  toggleMute: () => set((s) => ({ isMuted: !s.isMuted })),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setBooted: () => set({ isBooted: true }),
  setMousePosition: (nx, ny) => set({ mouseNX: nx, mouseNY: ny }),
  completeTask: (id) =>
    set((s) => ({
      tasks: s.tasks.map((t) => (t.id === id ? { ...t, completed: !t.completed } : t)),
    })),
}));
