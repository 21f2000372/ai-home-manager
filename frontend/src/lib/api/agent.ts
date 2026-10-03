import { request } from './request';

export type AgentMessageResponse = {
  response: string | null;
  planned_actions: Array<Record<string, unknown>>;
  interaction_id: string | null;
  conversation_id: string | null;
  error: string | null;
};

function requestContext() {
  return { correlationId: crypto.randomUUID() };
}

export function sendAgentMessage(message: string, sessionId?: string, conversationId?: string | null) {
  return request<AgentMessageResponse>('/api/agent/message', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      conversation_id: conversationId,
    }),
  }, requestContext());
}
