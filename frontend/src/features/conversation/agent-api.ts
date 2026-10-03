import { request } from "@/lib/api/request";

/**
 * A single action the planner produced for a chat turn, plus its outcome.
 * Mirrors the `planned_actions` entries returned by POST /api/agent/message.
 */
export type PlannedAction = {
  domain: string;
  intent: string;
  description: string;
  status: "pending" | "running" | "completed" | "unauthorized" | "failed";
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

/** A file attachment the backend accepts as base64 JSON on the agent message. */
export type AgentFileAttachment = {
  filename: string;
  content_type: string;
  data_base64: string;
};

export type SendAgentMessageInput = {
  message: string;
  /** Pass the previous turn's conversation_id to continue the same thread. */
  conversationId?: string | null;
  sessionId?: string | null;
  /** Optional document/receipt to upload with the message. */
  file?: AgentFileAttachment | null;
};

function requestContext() {
  return { correlationId: crypto.randomUUID() };
}

/**
 * Read a File into the base64 JSON attachment the backend expects
 * (POST /api/agent/message -> { file: { filename, content_type, data_base64 } }).
 */
export function fileToAttachment(file: File): Promise<AgentFileAttachment> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Could not read the file."));
    reader.onload = () => {
      const result = String(reader.result ?? "");
      // reader.result is a data URL (data:<mime>;base64,<data>); the backend
      // accepts the full data URL and strips the prefix itself.
      resolve({
        filename: file.name,
        content_type: file.type || "application/octet-stream",
        data_base64: result,
      });
    };
    reader.readAsDataURL(file);
  });
}

/**
 * Send a natural-language message (optionally with a document) through the
 * backend multi-agent pipeline. Requires an authenticated session; the
 * request helper attaches the JWT.
 */
export function sendAgentMessage(input: SendAgentMessageInput) {
  const body: Record<string, unknown> = { message: input.message };
  if (input.conversationId) body.conversation_id = input.conversationId;
  if (input.sessionId) body.session_id = input.sessionId;
  if (input.file) body.file = input.file;

  return request<AgentMessageResponse>(
    "/api/agent/message",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    requestContext(),
  );
}
