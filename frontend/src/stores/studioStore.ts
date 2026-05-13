import { create } from 'zustand';
import type { ChatTurn, WorkflowV2, WSEventEnvelope } from '../types';

type StudioState = {
  baseUrl: string;
  workflowId: string;
  sessionId: string;
  authToken: string;
  workflow: WorkflowV2 | null;
  chatInput: string;
  turns: ChatTurn[];
  events: WSEventEnvelope[];
  wsState: 'idle' | 'open' | 'closed' | 'error';
  selectedNodeId: string | null;
  setBaseUrl: (v: string) => void;
  setWorkflowId: (v: string) => void;
  setSessionId: (v: string) => void;
  setAuthToken: (v: string) => void;
  setWorkflow: (w: WorkflowV2 | null) => void;
  setChatInput: (v: string) => void;
  addTurn: (t: ChatTurn) => void;
  addEvent: (e: WSEventEnvelope) => void;
  setWsState: (s: StudioState['wsState']) => void;
  setSelectedNodeId: (id: string | null) => void;
};

const runtimeDefaultBaseUrl =
  typeof window !== 'undefined' ? window.location.origin : 'http://127.0.0.1:8090';

export const useStudioStore = create<StudioState>((set) => ({
  baseUrl: runtimeDefaultBaseUrl,
  workflowId: '',
  sessionId: '',
  authToken: '',
  workflow: null,
  chatInput: '',
  turns: [],
  events: [],
  wsState: 'idle',
  selectedNodeId: null,
  setBaseUrl: (v) => set({ baseUrl: v }),
  setWorkflowId: (v) => set({ workflowId: v }),
  setSessionId: (v) => set({ sessionId: v }),
  setAuthToken: (v) => set({ authToken: v }),
  setWorkflow: (w) => set({ workflow: w }),
  setChatInput: (v) => set({ chatInput: v }),
  addTurn: (t) => set((s) => ({ turns: [...s.turns, t] })),
  addEvent: (e) => set((s) => ({ events: [e, ...s.events].slice(0, 80) })),
  setWsState: (wsState) => set({ wsState }),
  setSelectedNodeId: (selectedNodeId) => set({ selectedNodeId }),
}));
