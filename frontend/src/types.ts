export type Position = { x: number; y: number };

export type NodeV2 = {
  id: string;
  type: string;
  config: Record<string, unknown>;
  position: Position;
  ui?: Record<string, unknown>;
  disabled?: boolean;
  schema_version?: number;
};

export type EdgeKind = 'data' | 'image' | 'mask' | 'control' | 'reference';

export type EdgeV2 = {
  id: string;
  source: string;
  target: string;
  source_port?: string | null;
  target_port?: string | null;
  kind?: EdgeKind;
};

export type WorkflowV2 = {
  id: string;
  name: string;
  version: number;
  nodes: NodeV2[];
  edges: EdgeV2[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  session_id?: string | null;
};

export type ChatSession = {
  id: string;
  workflow_id?: string | null;
  title?: string | null;
  created_at: string;
  updated_at: string;
};

export type ChatTurn = {
  id: string;
  session_id: string;
  user_message: string;
  agent_response?: string | null;
  status: string;
  created_at: string;
  completed_at?: string | null;
};

export type WSEventEnvelope<T = Record<string, unknown>> = {
  id: string;
  version: number;
  type: string;
  seq: number;
  timestamp: string;
  sessionId?: string;
  workflowId?: string;
  turnId?: string;
  runId?: string;
  payload?: T;
};
