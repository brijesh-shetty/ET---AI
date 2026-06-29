import { useEffect, useRef, useState } from 'react';
import { postChat, type ChatMessage } from '@/lib/api';
import { useAppStore } from '@/lib/store';

const SUGGESTIONS: string[] = [
  'What is our current exposure to Hormuz?',
  'If Red Sea closes, what is the best alternative for crude?',
  'Why is the South China Sea risk score elevated?',
  'Compare Hormuz partial closure vs Australia coking coal disruption',
];

export function ChatDrawer() {
  const isOpen = useAppStore((s) => s.isChatOpen);
  const setOpen = useAppStore((s) => s.setChatOpen);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function send(text: string) {
    const question = text.trim();
    if (!question || sending) return;
    setSending(true);
    setError(null);

    const userMsg: ChatMessage = { role: 'user', content: question };
    const history = [...messages, userMsg];
    setMessages(history);
    setInput('');

    try {
      const response = await postChat(question, messages);
      setMessages([...history, { role: 'assistant', content: response.answer }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to send message');
      setMessages(history);
    } finally {
      setSending(false);
    }
  }

  if (!isOpen) return null;

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-black/40"
        onClick={() => setOpen(false)}
        aria-hidden="true"
      />
      <aside className="fixed right-0 top-0 z-50 flex h-screen w-full max-w-md flex-col border-l border-slate-800 bg-slate-900 shadow-2xl">
        <header className="flex items-center justify-between border-b border-slate-800 px-5 py-3">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-indigo-400">Gemini-powered</div>
            <h2 className="font-serif italic text-lg text-slate-100">Ask the analyst</h2>
          </div>
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="text-slate-400 hover:text-slate-200"
            aria-label="Close chat"
          >
            ✕
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {messages.length === 0 && (
            <div>
              <p className="mb-3 text-sm text-slate-400">
                Ask about corridors, scenarios, sourcing, or specific commodities. Answers cite
                live data from the dashboard.
              </p>
              <div className="space-y-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => send(s)}
                    className="block w-full rounded border border-slate-800 bg-slate-950/50 px-3 py-2 text-left text-xs text-slate-300 hover:border-indigo-500/60 hover:text-slate-100"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="flex flex-col gap-4">
            {messages.map((m, i) => (
              <div key={i} className="flex flex-col gap-1">
                <span className="text-[10px] uppercase tracking-wider text-slate-500">
                  {m.role === 'user' ? 'You' : 'Analyst'}
                </span>
                <div
                  className={
                    m.role === 'user'
                      ? 'rounded border border-slate-700 bg-slate-950/40 px-3 py-2 text-sm text-slate-100'
                      : 'rounded border border-indigo-500/30 bg-indigo-500/5 px-3 py-2 text-sm leading-relaxed text-slate-200 whitespace-pre-line'
                  }
                >
                  {m.content}
                </div>
              </div>
            ))}
            {sending && (
              <div className="text-xs text-slate-500">Analyst is thinking...</div>
            )}
            {error && (
              <div className="rounded border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-300">
                {error}
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
          className="border-t border-slate-800 px-4 py-3"
        >
          <div className="flex items-end gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
              placeholder="Ask about corridors, scenarios, sourcing..."
              rows={2}
              className="flex-1 resize-none rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
            />
            <button
              type="submit"
              disabled={sending || !input.trim()}
              className="rounded border border-indigo-500/60 bg-indigo-500/20 px-3 py-2 text-sm font-semibold text-indigo-100 hover:bg-indigo-500/30 disabled:opacity-50"
            >
              Send
            </button>
          </div>
          <div className="mt-1 text-[10px] text-slate-500">
            Enter to send · Shift+Enter for newline
          </div>
        </form>
      </aside>
    </>
  );
}

export default ChatDrawer;
