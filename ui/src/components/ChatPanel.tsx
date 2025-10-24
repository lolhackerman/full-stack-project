/**
 * ChatPanel Component
 * Main chat interface displaying messages and input form
 */

import { DragEvent, FormEvent } from 'react';
import { ChatMessage } from '../types/chat.types';

type ChatPanelProps = {
  messages: ChatMessage[];
  pendingMessage: string;
  isLoading: boolean;
  chatError: string | null;
  isSubmitDisabled: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onMessageChange: (message: string) => void;
};

export const ChatPanel = ({
  messages,
  pendingMessage,
  isLoading,
  chatError,
  isSubmitDisabled,
  onSubmit,
  onMessageChange,
}: ChatPanelProps) => {
  return (
    <div className="flex min-h-[520px] flex-col rounded-2xl border border-slate-800/60 bg-slate-900/60 shadow-lg shadow-emerald-500/10 backdrop-blur">
      {/* Chat Header */}
      <div className="border-b border-slate-800/70 bg-slate-900/80 px-6 py-4">
        <h2 className="text-lg font-semibold text-emerald-300">ChatAW</h2>
        <p className="text-xs text-slate-400">Copy and paste a job description for a tailored cover letter.</p>
        {chatError && (
          <p className="mt-2 rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
            {chatError}
          </p>
        )}
      </div>

      {/* Messages Container */}
      <div className="flex-1 space-y-4 overflow-y-auto px-6 py-6">
        {messages.map((message) => (
          <article
            key={message.id}
            className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm transition ${
              message.role === 'user'
                ? 'ml-auto rounded-br-md bg-emerald-500/90 text-emerald-950'
                : 'rounded-bl-md bg-slate-800/80 text-slate-100'
            }`}
          >
            <span className="block text-[11px] uppercase tracking-wide opacity-75">
              {message.role === 'user' ? 'You' : 'ChatAW'}
            </span>
            <p className="mt-1 whitespace-pre-line">{message.content}</p>

            {/* Download Links */}
            {message.downloads && message.downloads.length > 0 && (
              <div className="mt-3 space-y-2">
                {message.downloads.map((download) => {
                  const handleDragStart = (e: DragEvent<HTMLDivElement>) => {
                    try {
                      // Convert base64 to binary data
                      const byteCharacters = atob(download.data);
                      const byteNumbers = new Array(byteCharacters.length);
                      for (let i = 0; i < byteCharacters.length; i++) {
                        byteNumbers[i] = byteCharacters.charCodeAt(i);
                      }
                      const byteArray = new Uint8Array(byteNumbers);
                      const blob = new Blob([byteArray], { type: download.mimeType });

                      // Build a File to expose name + type to the OS drag target
                      const file = new File([blob], download.filename, { type: download.mimeType });

                      e.dataTransfer.effectAllowed = 'copy';
                      if (e.dataTransfer.items && e.dataTransfer.items.add) {
                        try {
                          e.dataTransfer.items.add(file);
                        } catch (err) {
                          console.warn('Unable to attach file to drag dataTransfer.items', err);
                        }
                      }

                      const blobUrl = URL.createObjectURL(file);
                      e.dataTransfer.setData(
                        'DownloadURL',
                        `${download.mimeType}:${download.filename}:${blobUrl}`
                      );
                      e.dataTransfer.setData('text/uri-list', blobUrl);
                      e.dataTransfer.setData('text/plain', blobUrl);

                      e.currentTarget.dataset.dragUrl = blobUrl;
                    } catch (error) {
                      console.error('Error preparing file for drag:', error);
                    }
                  };

                  const handleDragEnd = (e: DragEvent<HTMLDivElement>) => {
                    const { dragUrl } = e.currentTarget.dataset;
                    if (dragUrl) {
                      URL.revokeObjectURL(dragUrl);
                      delete e.currentTarget.dataset.dragUrl;
                    }
                  };

                  return (
                    <div key={download.id} className="flex items-center gap-2">
                      {/* Draggable File Icon */}
                      <div
                        draggable="true"
                        onDragStart={handleDragStart}
                        onDragEnd={handleDragEnd}
                        className="flex h-10 w-10 flex-shrink-0 cursor-move items-center justify-center rounded-lg border border-emerald-400/40 bg-emerald-500/5 text-emerald-300 transition hover:border-emerald-400/60 hover:bg-emerald-500/10 active:scale-95"
                        title="Drag this to your desktop or folder"
                      >
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          className="h-5 w-5"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                          strokeWidth={2}
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
                          />
                        </svg>
                      </div>

                      {/* Download Button */}
                      <a
                        href={`data:${download.mimeType};base64,${download.data}`}
                        download={download.filename}
                        className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg border border-emerald-400/60 bg-emerald-500/10 px-3 py-2 text-xs font-semibold text-emerald-200 transition hover:bg-emerald-400/20 focus:outline-none focus:ring-2 focus:ring-emerald-300"
                      >
                        Download {download.label}
                      </a>
                    </div>
                  );
                })}
              </div>
            )}
          </article>
        ))}

        {/* Loading Indicator */}
        {isLoading && (
          <article className="max-w-[75%] rounded-bl-md rounded-2xl bg-slate-800/80 px-4 py-3 text-sm text-slate-100 shadow-sm">
            <span className="block text-[11px] uppercase tracking-wide opacity-75">ChatAW</span>
            <p className="mt-1 animate-pulse text-slate-400">Thinking…</p>
          </article>
        )}
      </div>

      {/* Message Input Form */}
      <form
        className="sticky bottom-0 z-10 border-t border-slate-800/70 bg-slate-900/95 px-4 py-4 backdrop-blur"
        onSubmit={onSubmit}
      >
        <label className="sr-only" htmlFor="message">
          Message
        </label>
        <div className="flex items-center gap-3 rounded-full border border-slate-700 bg-slate-900/90 px-4 py-2 focus-within:border-emerald-400/80">
          <input
            id="message"
            name="message"
            type="text"
            placeholder="Ask the assistant to call a tool..."
            autoComplete="off"
            className="flex-1 border-none bg-transparent text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none"
            value={pendingMessage}
            onChange={(event) => onMessageChange(event.target.value)}
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isSubmitDisabled}
            className="rounded-full bg-emerald-400 px-4 py-2 text-sm font-semibold text-emerald-950 transition hover:bg-emerald-300 focus:outline-none focus:ring-2 focus:ring-emerald-200"
          >
            {isLoading ? 'Sending…' : 'Send'}
          </button>
        </div>
      </form>
    </div>
  );
};
