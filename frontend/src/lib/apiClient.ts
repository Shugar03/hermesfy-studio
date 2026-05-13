import type { ChatSession, ChatTurn, WorkflowV2 } from '../types';

const DEFAULT_BASE = 'http://127.0.0.1:8090';

export class ApiClient {
  readonly baseUrl: string;
  readonly authToken?: string;

  constructor(baseUrl = DEFAULT_BASE, authToken?: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.authToken = authToken?.trim() || undefined;
  }

  private async req<T>(path: string, init?: RequestInit): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(init?.headers as Record<string, string> | undefined),
    };

    if (this.authToken) {
      headers.Authorization = `Bearer ${this.authToken}`;
    }

    const res = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers,
    });

    if (!res.ok) {
      const body = await res.text();
      throw new Error(`${res.status} ${res.statusText}: ${body}`);
    }

    return (await res.json()) as T;
  }

  getWorkflow(workflowId: string): Promise<WorkflowV2> {
    return this.req(`/api/dag/${workflowId}`);
  }

  createSession(title = 'Hermesfy Live Session', workflowId?: string): Promise<ChatSession> {
    return this.req('/api/chat/sessions', {
      method: 'POST',
      body: JSON.stringify({ title, workflow_id: workflowId }),
    });
  }

  sendMessage(sessionId: string, message: string): Promise<ChatTurn> {
    return this.req(`/api/chat/sessions/${sessionId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
  }
}
