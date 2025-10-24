/**
 * Sidebar Component
 * Displays workspace status, chat history, and navigation controls
 */

import { useState } from 'react';
import { ChatSummary } from '../types/chat.types';

type SidebarProps = {
  sessionToken: string | null;
  profileId: string | null;
  chatHistory: ChatSummary[];
  activeThreadId: string | null;
  latestCoverLetterId: string | null;
  onNewChat: () => void;
  onDeleteThread: (threadId: string) => Promise<void>;
  onSelectThread: (threadId: string) => void;
  onOpenAuthModal: () => void;
  onSwitchWorkspace: (newCode: string) => void;
};

export const Sidebar = ({
  sessionToken,
  profileId,
  chatHistory,
  activeThreadId,
  latestCoverLetterId,
  onNewChat,
  onDeleteThread,
  onSelectThread,
  onOpenAuthModal,
  onSwitchWorkspace,
}: SidebarProps) => {
  const [editedCode, setEditedCode] = useState<string>('');
  const [showConfirmButton, setShowConfirmButton] = useState(false);

  const handleCodeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    setEditedCode(newValue);
    // Show confirm button only if the value is different from current profileId and not empty
    setShowConfirmButton(newValue !== profileId && newValue.trim() !== '');
  };

  const handleConfirmSwitch = () => {
    if (editedCode.trim()) {
      onSwitchWorkspace(editedCode.trim());
      setEditedCode('');
      setShowConfirmButton(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && showConfirmButton) {
      handleConfirmSwitch();
    } else if (e.key === 'Escape') {
      setEditedCode('');
      setShowConfirmButton(false);
    }
  };
  return (
    <aside className="lg:sticky lg:top-16 lg:h-[calc(100vh-4rem)] lg:self-start flex flex-col gap-4 rounded-2xl border border-slate-800/60 bg-slate-900/60 p-6 shadow-lg shadow-emerald-500/10">
      {/* Workspace Status Section */}
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Workspace</p>
        {sessionToken ? (
          <>
            <p className="mt-1 text-sm font-semibold text-emerald-300">✓ Active</p>
            {profileId && (
              <div className="mt-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3">
                <p className="text-[10px] uppercase tracking-wide text-emerald-300/80">Your workspace code:</p>
                <div className="mt-1 flex items-center gap-2">
                  <input
                    type="text"
                    value={editedCode || profileId}
                    onChange={handleCodeChange}
                    onKeyDown={handleKeyDown}
                    placeholder={profileId}
                    maxLength={6}
                    className="w-full rounded border border-emerald-500/40 bg-emerald-500/5 px-2 py-1 font-mono text-2xl font-bold tracking-widest text-emerald-300 outline-none transition focus:border-emerald-400 focus:bg-emerald-500/10"
                    style={{ width: 'calc(100% - 3rem)' }}
                  />
                  {showConfirmButton && (
                    <button
                      type="button"
                      onClick={handleConfirmSwitch}
                      className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded bg-emerald-500 text-emerald-950 transition hover:bg-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-300"
                      title="Switch to this workspace"
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 24 24"
                        strokeWidth={3}
                        stroke="currentColor"
                        className="h-6 w-6"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                      </svg>
                    </button>
                  )}
                </div>
                <p className="mt-2 text-[10px] text-slate-400">
                  💾 Save this code to log back in!
                </p>
              </div>
            )}
          </>
        ) : (
          <>
            <p className="mt-1 text-lg font-semibold text-rose-300">Not connected</p>
            <button
              type="button"
              className="mt-2 rounded-lg bg-emerald-500 px-3 py-2 text-sm font-semibold text-emerald-950 transition hover:bg-emerald-400"
              onClick={onOpenAuthModal}
            >
              Access workspace
            </button>
          </>
        )}
      </div>

      {/* Action Buttons */}
      <button
        type="button"
        className="rounded-xl bg-emerald-500/90 px-4 py-2 text-sm font-semibold text-emerald-950 transition hover:bg-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-200"
        onClick={onNewChat}
      >
        New chat
      </button>

      {/* Chat History List */}
      <div className="flex flex-1 flex-col gap-3 overflow-hidden">
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Chat history</p>
        <div className="relative flex-1 overflow-hidden rounded-xl border border-slate-800/60 bg-slate-900/40 p-3">
          <ul className="scrollbar-hover-only h-full space-y-2 overflow-y-auto pr-2 text-sm text-slate-300">
            {chatHistory.map((chat) => (
              <li
                key={chat.id}
                className={`rounded-xl border px-3 py-3 transition ${
                  chat.id === activeThreadId
                    ? 'border-emerald-500/70 bg-emerald-500/10 text-emerald-100'
                    : 'border-slate-800/80 bg-slate-900/70 text-slate-300 hover:border-emerald-400/60 hover:text-emerald-200'
                }`}
              >
                <div className="flex items-start gap-2">
                  <button
                    type="button"
                    className="flex-1 text-left"
                    onClick={() => onSelectThread(chat.id)}
                  >
                    <p className="font-medium text-slate-100">{chat.title}</p>
                    {chat.lastActive && <p className="text-[11px] text-slate-500">{chat.lastActive}</p>}
                  </button>
                  <button
                    type="button"
                    className={`flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg border border-transparent text-slate-500 transition hover:border-rose-500/60 hover:text-rose-200 focus:outline-none focus:ring-2 focus:ring-rose-400/40 ${
                      chat.id === activeThreadId ? 'text-emerald-100 hover:text-rose-100' : ''
                    }`}
                    onClick={(event) => {
                      event.stopPropagation();
                      void onDeleteThread(chat.id);
                    }}
                    title="Delete conversation"
                    aria-label="Delete conversation"
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth={2.5}
                      stroke="currentColor"
                      className="h-4 w-4"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M6 7h12m-9 4v6m6-6v6M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"
                      />
                    </svg>
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </aside>
  );
};
