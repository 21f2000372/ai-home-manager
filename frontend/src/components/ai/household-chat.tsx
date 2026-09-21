import { ChangeEvent, FormEvent, useRef, useState } from 'react';
import { FileText, LoaderCircle, Mic, Paperclip, Send, Square } from 'lucide-react';
import { useMutation } from '@tanstack/react-query';
import { Button } from '@/components/design-system/button';
import { Card } from '@/components/design-system/card';
import { ApiError } from '@/lib/api/request';
import { sendAgentMessage, type AgentMessageResponse } from '@/lib/api/agent';

type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
};

type SpeechRecognitionLike = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  onresult: ((event: { results: ArrayLike<{ 0?: { transcript?: string } }> }) => void) | null;
  start: () => void;
  stop: () => void;
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

type HouseholdChatProps = {
  title?: string;
  description?: string;
  initialMessage?: string;
  fileAccept?: string;
  onMessageProcessed?: (result: AgentMessageResponse) => void | Promise<void>;
};

const defaultMessage = 'Tell me about a household task, or attach a text file and I will help turn it into an actionable plan.';

export function HouseholdChat({
  title = 'Household assistant',
  description = 'Type, attach readable text, or dictate a request.',
  initialMessage = defaultMessage,
  fileAccept = '.txt,.md,.csv,.json,text/plain,text/markdown,text/csv,application/json',
  onMessageProcessed,
}: HouseholdChatProps) {
  const [draft, setDraft] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([{ id: 'assistant-welcome', role: 'assistant', text: initialMessage }]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isListening, setIsListening] = useState(false);
  const [inputError, setInputError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const chatMutation = useMutation({
    mutationFn: (message: string) => sendAgentMessage(message, undefined, conversationId),
    onSuccess: (result: AgentMessageResponse, message: string) => {
      if (result.conversation_id) setConversationId(result.conversation_id);
      void onMessageProcessed?.(result);
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: 'user', text: message },
        { id: crypto.randomUUID(), role: 'assistant', text: result.error ?? result.response ?? 'I could not produce a response.' },
      ]);
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || chatMutation.isPending) return;
    setDraft('');
    setInputError(null);
    chatMutation.mutate(message);
  }

  async function readFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;

    try {
      const text = (await file.text()).trim();
      if (!text) throw new Error('empty');
      setDraft((current) => current ? `${current}\n\n${text}` : text);
      setInputError(null);
    } catch {
      setInputError('This file could not be read as text. Try a TXT, Markdown, CSV, or JSON file.');
    }
  }

  function toggleVoiceInput() {
    const speechWindow = window as Window & {
      SpeechRecognition?: SpeechRecognitionConstructor;
      webkitSpeechRecognition?: SpeechRecognitionConstructor;
    };
    const Recognition = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
    if (!Recognition) {
      setInputError('Voice input is not supported by this browser.');
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
      setInputError('Voice input could not be captured. Check microphone permission and try again.');
    };
    recognition.onresult = (event) => {
      setDraft(Array.from(event.results).map((result) => result[0]?.transcript ?? '').join(''));
    };
    recognitionRef.current = recognition;
    recognition.start();
  }

  const requestError = chatMutation.error;
  const errorMessage = requestError instanceof ApiError ? requestError.message : requestError ? 'The assistant could not process that message.' : inputError;

  return (
    <Card className="p-4 sm:p-6">
      <div className="flex items-start gap-3 sm:gap-4">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#D19A4C]">Household assistant</p>
          <h2 className="mt-2 text-lg font-bold text-[var(--ink)] sm:text-xl">{title}</h2>
          <p className="mt-1 text-sm leading-6 muted">{description}</p>
        </div>
        <FileText className="mt-1 shrink-0 text-[#5E9278]" size={20} />
      </div>

      <div className="mt-5 max-h-64 space-y-3 overflow-y-auto pr-1" aria-live="polite">
        {messages.map((message) => (
          <div key={message.id} className={`max-w-[92%] rounded-2xl p-3 text-sm leading-6 sm:max-w-2xl ${message.role === 'user' ? 'ml-auto bg-[#27736d] text-white' : 'bg-[#ECEAE4] text-[var(--ink)]'}`}>
            {message.text}
          </div>
        ))}
        {chatMutation.isPending && <div className="flex items-center gap-2 text-sm muted"><LoaderCircle className="animate-spin" size={16} />Thinking...</div>}
      </div>

      <form className="mt-5" onSubmit={submit}>
        <textarea value={draft} onChange={(event) => setDraft(event.target.value)} className="task-input min-h-20 w-full resize-y py-3" placeholder="e.g. Remind Priya to buy vegetables tomorrow" aria-label="Message household assistant" />
        <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap gap-2">
            <input ref={fileInputRef} type="file" accept={fileAccept} onChange={readFile} className="sr-only" />
            <Button type="button" tone="neutral" onClick={() => fileInputRef.current?.click()} aria-label="Attach a text file" title="Attach a text file"><Paperclip size={16} /><span className="hidden sm:inline">Attach file</span><span className="sm:hidden">File</span></Button>
            <Button type="button" tone={isListening ? 'danger' : 'neutral'} onClick={toggleVoiceInput} aria-label={isListening ? 'Stop voice input' : 'Start voice input'} title={isListening ? 'Stop voice input' : 'Start voice input'}>{isListening ? <Square size={16} /> : <Mic size={16} />}{isListening ? 'Stop' : 'Voice'}</Button>
          </div>
          <Button type="submit" disabled={!draft.trim() || chatMutation.isPending} className="w-full sm:w-auto"><Send size={16} />Send</Button>
        </div>
        {errorMessage && <p role="alert" className="mt-3 text-sm text-[#8B3F36]">{errorMessage}</p>}
      </form>
    </Card>
  );
}
