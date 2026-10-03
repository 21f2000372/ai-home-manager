import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";
import {
  FileText,
  Image as ImageIcon,
  LoaderCircle,
  Mic,
  Paperclip,
  Send,
  Square,
  X,
} from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/design-system/button";
import { Card } from "@/components/design-system/card";
import { ApiError } from "@/lib/api/request";
import {
  fileToAttachment,
  sendAgentMessage,
  type AgentMessageResponse,
} from "@/features/conversation/agent-api";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
};

/** A receipt/bill image or PDF the user attached but has not yet uploaded. */
type AttachedReceipt = {
  file: File;
  /** Object URL for an inline preview (images only); null for PDFs. */
  previewUrl: string | null;
};

const RECEIPT_MAX_BYTES = 10 * 1024 * 1024; // 10 MB
const RECEIPT_ACCEPT = "image/*,application/pdf,.pdf";

type SpeechRecognitionLike = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  onresult:
    | ((event: { results: ArrayLike<{ 0?: { transcript?: string } }> }) => void)
    | null;
  start: () => void;
  stop: () => void;
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

type HouseholdChatProps = {
  title?: string;
  description?: string;
  initialMessage?: string;
  fileAccept?: string;
  compact?: boolean;
  suggestions?: string[];
  showAttachments?: boolean;
  showVoice?: boolean;
  onMessageProcessed?: (result: AgentMessageResponse) => void | Promise<void>;
};

const defaultMessage =
  "Tell me about a household task, or attach a text file and I will help turn it into an actionable plan.";

const URL_PATTERN = /(https?:\/\/[^\s]+)/g;

/**
 * Render message text, turning any URL into a clickable "Download" link.
 * Used so document download links from the assistant are actionable.
 */
function renderMessageText(text: string) {
  const parts = text.split(URL_PATTERN);
  return parts.map((part, index) => {
    if (URL_PATTERN.test(part)) {
      // Reset lastIndex because the regex is global and reused in .test().
      URL_PATTERN.lastIndex = 0;
      return (
        <a
          key={index}
          href={part}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 font-semibold text-[#27736d] underline underline-offset-2 hover:text-[#1f574f]"
        >
          Download here
        </a>
      );
    }
    return <span key={index}>{part}</span>;
  });
}

export function HouseholdChat({
  title = "Household assistant",
  description = "Type, attach readable text, or dictate a request.",
  initialMessage = defaultMessage,
  fileAccept = ".txt,.md,.csv,.json,text/plain,text/markdown,text/csv,application/json",
  compact = false,
  suggestions = [],
  showAttachments = true,
  showVoice = true,
  onMessageProcessed,
}: HouseholdChatProps) {
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: "assistant-welcome", role: "assistant", text: initialMessage },
  ]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isListening, setIsListening] = useState(false);
  const [inputError, setInputError] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<AttachedReceipt | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const receiptInputRef = useRef<HTMLInputElement>(null);
  const messageListRef = useRef<HTMLDivElement>(null);

  const chatMutation = useMutation({
    mutationFn: async (vars: { message: string; file: File | null }) => {
      const attachment = vars.file ? await fileToAttachment(vars.file) : null;
      return sendAgentMessage({ message: vars.message, conversationId, file: attachment });
    },
    onSuccess: (result: AgentMessageResponse, vars: { message: string; file: File | null }) => {
      if (result.conversation_id) setConversationId(result.conversation_id);
      if (result.session_id)setConversationId(result.conversation_id);
      void onMessageProcessed?.(result);
      // Clear the attached receipt once it's been sent.
      if (receipt?.previewUrl) URL.revokeObjectURL(receipt.previewUrl);
      setReceipt(null);
      const userText = vars.file ? `${vars.message}  📎 ${vars.file.name}` : vars.message;

      let assistantText = result.error ?? result.response ?? "I could not produce a response.";

      // The LLM sometimes drops/placeholders a document download URL in its
      // prose. Pull the real URL from the raw tool results (planned_actions)
      // and append it so the download link is always clickable.
      const toolText = (result.planned_actions ?? [])
        .map((action) => action.result ?? "")
        .join("\n");
      const urlMatch = toolText.match(/https?:\/\/[^\s)]+/);
      if (urlMatch && !/https?:\/\//.test(assistantText)) {
        assistantText += `\n\nDownload link: ${urlMatch[0]}`;
      }

      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: "user", text: userText },
        {
          id: crypto.randomUUID(),
          role: "assistant",
          text: assistantText,
        },
      ]);
    },
  });

  useEffect(() => {
    const messageList = messageListRef.current;
    if (!messageList) return;
    messageList.scrollTo({ top: messageList.scrollHeight, behavior: "smooth" });
  }, [messages, chatMutation.isPending]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const typed = draft.trim();
    // Allow sending if there's text OR an attached receipt.
    if ((!typed && !receipt) || chatMutation.isPending) return;
    // The backend requires a non-empty message, so default one when only a file is sent.
    const message = typed || "Please review this document.";
    setDraft("");
    setInputError(null);
    chatMutation.mutate({ message, file: receipt?.file ?? null });
  }

  async function readFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    try {
      const text = (await file.text()).trim();
      if (!text) throw new Error("empty");
      setDraft((current) => (current ? `${current}\n\n${text}` : text));
      setInputError(null);
    } catch {
      setInputError(
        "This file could not be read as text. Try a TXT, Markdown, CSV, or JSON file.",
      );
    }
  }

  function selectReceipt(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    const isImage = file.type.startsWith("image/");
    const isPdf =
      file.type === "application/pdf" ||
      file.name.toLowerCase().endsWith(".pdf");

    if (!isImage && !isPdf) {
      setInputError("Attach a receipt as an image (JPG/PNG) or a PDF.");
      return;
    }
    if (file.size > RECEIPT_MAX_BYTES) {
      setInputError("Receipt is too large. Maximum size is 10 MB.");
      return;
    }

    // Release any previous preview URL before replacing it.
    if (receipt?.previewUrl) URL.revokeObjectURL(receipt.previewUrl);

    setReceipt({
      file,
      previewUrl: isImage ? URL.createObjectURL(file) : null,
    });
    setInputError(null);
  }

  function removeReceipt() {
    if (receipt?.previewUrl) URL.revokeObjectURL(receipt.previewUrl);
    setReceipt(null);
  }

  // TODO(backend): once the document-upload endpoint is ready, upload
  // `receipt.file` here (e.g. via multipart POST to /api/documents/upload),
  // then pass the returned document reference/URL into the agent message so
  // it can extract fields (merchant, total, date) and create the record.
  // For now the receipt is only held in state and previewed in the UI.

  function toggleVoiceInput() {
    const speechWindow = window as Window & {
      SpeechRecognition?: SpeechRecognitionConstructor;
      webkitSpeechRecognition?: SpeechRecognitionConstructor;
    };
    const Recognition =
      speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
    if (!Recognition) {
      setInputError("Voice input is not supported by this browser.");
      return;
    }

    if (isListening) {
      recognitionRef.current?.stop();
      return;
    }

    setInputError(null);
    const recognition = new Recognition();
    recognition.lang = navigator.language;
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.onstart = () => setIsListening(true);
    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => {
      setIsListening(false);
      setInputError(
        "Voice input could not be captured. Check microphone permission and try again.",
      );
    };
    recognition.onresult = (event) => {
      setDraft(
        Array.from(event.results)
          .map((result) => result[0]?.transcript ?? "")
          .join(""),
      );
    };
    recognitionRef.current = recognition;
    recognition.start();
  }

  const requestError = chatMutation.error;
  const errorMessage =
    requestError instanceof ApiError
      ? requestError.message
      : requestError
        ? "The assistant could not process that message."
        : inputError;
  const visibleMessages = compact
    ? messages.filter((message) => message.id !== "assistant-welcome")
    : messages;
  const shouldShowMessages = visibleMessages.length > 0 || chatMutation.isPending;

  return (
    <Card className={compact ? "p-4" : "p-4 sm:p-6"}>
      <div className="flex items-start gap-3 sm:gap-4">
        <div className="min-w-0 flex-1">
          {!compact && <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#D19A4C]">
            Household assistant
          </p>}
          <h2 className={compact ? "text-base font-bold text-[var(--ink)]" : "mt-2 text-lg font-bold text-[var(--ink)] sm:text-xl"}>
            {title}
          </h2>
          {!compact && <p className="mt-1 text-sm leading-6 muted">{description}</p>}
        </div>
        <FileText className="mt-1 shrink-0 text-[#5E9278]" size={20} />
      </div>

      {shouldShowMessages && <div
        ref={messageListRef}
        className={compact ? "mt-3 max-h-40 space-y-2 overflow-y-auto pr-1" : "mt-5 max-h-64 space-y-3 overflow-y-auto pr-1"}
        aria-live="polite"
      >
        {visibleMessages.map((message) => (
          <div
            key={message.id}
            className={`max-w-[92%] whitespace-pre-wrap rounded-2xl p-3 text-sm leading-6 sm:max-w-2xl ${message.role === "user" ? "ml-auto bg-[#27736d] text-white" : "bg-[#ECEAE4] text-[var(--ink)]"}`}
          >
            {message.role === "assistant" ? renderMessageText(message.text) : message.text}
          </div>
        ))}
        {chatMutation.isPending && (
          <div className="flex items-center gap-2 text-sm muted">
            <LoaderCircle className="animate-spin" size={16} />
            Thinking...
          </div>
        )}
      </div>}

      <form className={compact ? "mt-3" : "mt-5"} onSubmit={submit}>
        {suggestions.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-2">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => setDraft(suggestion)}
                className="rounded-full border border-[var(--line)] bg-[var(--surface)] px-3 py-1.5 text-xs font-semibold text-[#3D7C63] transition hover:bg-[#E4F0E8]"
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          rows={compact ? 1 : undefined}
          className={`task-input w-full resize-y ${compact ? 'min-h-11 max-h-20 py-2.5' : 'min-h-20 py-3'}`}
          placeholder={compact ? "Ask about your household" : "e.g. Remind Priya to buy vegetables tomorrow"}
          aria-label="Message household assistant"
        />
        {receipt && (
          <div className="mt-3 flex items-center gap-3 rounded-xl border border-[var(--line)] bg-[var(--surface-muted)] p-3">
            {receipt.previewUrl ? (
              <img
                src={receipt.previewUrl}
                alt="Attached receipt preview"
                className="size-12 shrink-0 rounded-lg object-cover"
              />
            ) : (
              <div className="grid size-12 shrink-0 place-items-center rounded-lg bg-[#e3edf8] text-[#346b8e]">
                <FileText size={18} />
              </div>
            )}
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-[var(--ink)]">
                {receipt.file.name}
              </p>
              <p className="text-xs muted">
                {(receipt.file.size / 1024).toFixed(0)} KB · will be sent with your message
              </p>
            </div>
            <button
              type="button"
              onClick={removeReceipt}
              aria-label="Remove attached receipt"
              title="Remove attached receipt"
              className="grid size-8 shrink-0 place-items-center rounded-full text-[var(--muted)] hover:bg-[var(--surface)] hover:text-[#8B3F36]"
            >
              <X size={16} />
            </button>
          </div>
        )}
        <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap gap-2">
            {showAttachments && <>
            <input
              ref={fileInputRef}
              type="file"
              accept={fileAccept}
              onChange={readFile}
              className="sr-only"
            />
            <Button
              type="button"
              tone="neutral"
              onClick={() => fileInputRef.current?.click()}
              aria-label="Attach a text file"
              title="Attach a text file"
            >
              <Paperclip size={16} />
              <span className="hidden sm:inline">Attach file</span>
              <span className="sm:hidden">File</span>
            </Button>
            <input
              ref={receiptInputRef}
              type="file"
              accept={RECEIPT_ACCEPT}
              onChange={selectReceipt}
              className="sr-only"
            />
            <Button
              type="button"
              tone="neutral"
              onClick={() => receiptInputRef.current?.click()}
              aria-label="Attach a receipt image or PDF"
              title="Attach a receipt image or PDF"
            >
              <ImageIcon size={16} />
              <span className="hidden sm:inline">Attach receipt</span>
              <span className="sm:hidden">Receipt</span>
            </Button>
            </>}
            {showVoice && <Button
              type="button"
              tone={isListening ? "danger" : "neutral"}
              onClick={toggleVoiceInput}
              aria-label={
                isListening ? "Stop voice input" : "Start voice input"
              }
              title={isListening ? "Stop voice input" : "Start voice input"}
            >
              {isListening ? <Square size={16} /> : <Mic size={16} />}
              {isListening ? "Stop" : "Voice"}
            </Button>}
          </div>
          <Button
            type="submit"
            disabled={(!draft.trim() && !receipt) || chatMutation.isPending}
            className="w-full sm:w-auto"
          >
            <Send size={16} />
            Send
          </Button>
        </div>
        {errorMessage && (
          <p role="alert" className="mt-3 text-sm text-[#8B3F36]">
            {errorMessage}
          </p>
        )}
      </form>
    </Card>
  );
}
