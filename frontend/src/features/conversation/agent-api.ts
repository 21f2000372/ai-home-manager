import { request } from '@/lib/api/request';

/**
 * A single action the planner produced for a chat turn, plus its outcome.
 * Mirrors the `planned_actions` entries returned by POST /api/agent/message.
 */
export type PlannedAction = {
  domain: string;
  intent: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'unauthorized' | 'failed'| 'needs_clarification';
  result: string | null;
  tool_name?: string;
  tool_args?: Record<string, unknown>;
};

/** Shape of the backend agent response. */
export type AgentMessageResponse = {
  response: string;
  planned_actions: PlannedAction[];
  interaction_id: string | null;

  conversation_id: string | null;
  session_id: string | null;

  awaiting_confirmation?: boolean;
  error: string | null;
};

export type SendAgentMessageInput = {
  message: string;
  /** Pass the previous turn's conversation_id to continue the same thread. */
  conversationId?: string | null;
  sessionId?: string | null;
};

function requestContext() {
  return { correlationId: crypto.randomUUID() };
}

/**
 * Send a natural-language message through the backend multi-agent pipeline
 * (router -> planner -> specialist -> authorize -> execute -> save/embed).
 * Requires an authenticated session; the request helper attaches the JWT.
 */
export function sendAgentMessage(input: SendAgentMessageInput) {
  const body: Record<string, unknown> = { message: input.message };
  if (input.conversationId) body.conversation_id = input.conversationId;
  if (input.sessionId) body.session_id = input.sessionId;

  return request<AgentMessageResponse>(
    '/api/agent/message',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
    requestContext(),
  );
}
