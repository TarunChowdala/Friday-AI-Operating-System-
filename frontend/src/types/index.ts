export type AssistantState = 'idle' | 'listening' | 'thinking' | 'speaking';

export type NavItemId =
  | 'home'
  | 'conversations'
  | 'knowledge'
  | 'memory'
  | 'agents'
  | 'tools'
  | 'dashboard'
  | 'settings';

export interface Task {
  id: string;
  title: string;
  priority: 'high' | 'medium' | 'low';
  completed: boolean;
  time?: string;
  tag?: string;
}

export interface Conversation {
  id: string;
  title: string;
  preview: string;
  time: string;
  active?: boolean;
  model?: string;
}

export interface SystemStat {
  label: string;
  value: number;
  unit: string;
  color: string;
}

export interface AgentInfo {
  name: string;
  status: 'active' | 'idle' | 'standby' | 'offline';
  description: string;
}

export interface MousePosition {
  x: number;
  y: number;
  nx: number; // normalized -1 to 1
  ny: number;
}
