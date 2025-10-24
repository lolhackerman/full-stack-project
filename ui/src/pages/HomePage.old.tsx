import { ChangeEvent, DragEvent, FormEvent, useEffect, useMemo, useRef, useState } from 'react';

type ChatRole = 'user' | 'assistant';

type ChatDownload = {
  id: string;
  label: string;
  filename: string;
  mimeType: string;
  data: string;
};

type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  downloads?: ChatDownload[];
};

type ChatSummary = {
  id: string;
  title: string;
  lastActive?: string;
};

type UploadedFileSummary = {
  id: string;
  name: string;
  size: number;
  mimeType: string;
  uploadedAt: number;
  hasText?: boolean;
};

type ChatResponsePayload = {
  reply: string;
  model?: string;
  coverLetterId?: string;
  downloads?: ChatDownload[];
};

type ChatThreadInfo = {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
};

const THREAD_STORAGE_KEY = 'chatAW:threadId';
const THREADS_INDEX_KEY = 'chatAW:threads';

const createThreadId = () => `thread_${Date.now().toString(36)}${Math.random().toString(16).slice(2, 8)}`;

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:5050';

const TOKEN_STORAGE_KEY = 'chatAW:sessionToken';
const PROFILE_STORAGE_KEY = 'chatAW:profileId';
const createId = () => `${Date.now().toString(36)}-${Math.random().toString(16).slice(2, 10)}`;

const greetingMessage =
  'Hi! Share the job description and I will craft a tailored cover letter using any files you upload.';

const readFromStorage = (key: string) => {
  if (typeof window === 'undefined') {
    return null;
  }
  try {
    return window.localStorage.getItem(key);
  } catch (err) {
    console.warn('Unable to read from localStorage', err);
    return null;
  }
};

const HomePage = () => {
  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    {
      id: createId(),
      role: 'assistant',
      content: greetingMessage,
      downloads: [],
    },
  ]);
  const [pendingMessage, setPendingMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFileSummary[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [latestCoverLetterId, setLatestCoverLetterId] = useState<string | null>(null);
  const [deletingFiles, setDeletingFiles] = useState<Record<string, boolean>>({});
  const [hasLoadedMongoThreads, setHasLoadedMongoThreads] = useState(false);

  const [sessionToken, setSessionToken] = useState<string | null>(() => {
    const token = readFromStorage(TOKEN_STORAGE_KEY);
    // Don't automatically trust stored tokens - they will be validated on mount
    return token || null;
  });
  const [profileId, setProfileId] = useState<string | null>(() => readFromStorage(PROFILE_STORAGE_KEY));
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(() => {
    const token = readFromStorage(TOKEN_STORAGE_KEY);
    // Show modal if no token exists
    return !token;
  });
  const [codeInput, setCodeInput] = useState('');
  const [isRequestingCode, setIsRequestingCode] = useState(false);
  const [isVerifyingCode, setIsVerifyingCode] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(() => readFromStorage(THREAD_STORAGE_KEY));
  const [threadSummaries, setThreadSummaries] = useState<ChatThreadInfo[]>(() => {
    const raw = readFromStorage(THREADS_INDEX_KEY);
    if (!raw) {
      return [];
    }
    try {
      const parsed = JSON.parse(raw) as ChatThreadInfo[];
      return Array.isArray(parsed) ? parsed : [];
    } catch (err) {
      console.warn('Unable to parse thread index', err);
      return [];
    }
  });

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const chatHistory = useMemo<ChatSummary[]>(() => {
    return threadSummaries
      .slice()
      .sort((a, b) => b.updatedAt - a.updatedAt)
      .map((thread) => ({
        id: thread.id,
        title: thread.title,
        lastActive: new Date(thread.updatedAt).toLocaleString(),
      }));
  }, [threadSummaries]);

  const isSubmitDisabled = useMemo(
    () => !pendingMessage.trim() || isLoading || !sessionToken,
    [pendingMessage, isLoading, sessionToken],
  );

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    if (sessionToken) {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, sessionToken);
    } else {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  }, [sessionToken]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    if (profileId) {
      window.localStorage.setItem(PROFILE_STORAGE_KEY, profileId);
    } else {
      window.localStorage.removeItem(PROFILE_STORAGE_KEY);
    }
  }, [profileId]);

  useEffect(() => {
    if (!sessionToken) {
      setIsAuthModalOpen(true);
    }
  }, [sessionToken]);

  // Check session validity on mount and when token changes
  useEffect(() => {
    if (!sessionToken) {
      return;
    }

    const controller = new AbortController();

    const validateSession = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/auth/session`, {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${sessionToken}`,
          },
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error('Session invalid');
        }
        
        // Session is valid, now load uploaded files
        loadUploadedFiles();
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          return;
        }
        setSessionToken(null);
        setProfileId(null);
        setIsAuthModalOpen(true);
        setAuthError('Session expired. Please enter a new access code.');
      }
    };

    void validateSession();

    return () => {
      controller.abort();
    };
  }, [sessionToken]);

  // Load thread summaries from MongoDB
  useEffect(() => {
    if (!sessionToken) {
      setHasLoadedMongoThreads(true);
      return;
    }

    const controller = new AbortController();

    const loadThreadsFromMongoDB = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/chat/threads`, {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${sessionToken}`,
          },
          signal: controller.signal,
        });

        if (response.ok) {
          const data = await response.json();
          if (data.threads && Array.isArray(data.threads)) {
            // Convert MongoDB threads to ChatThreadInfo format
            const mongoThreads: ChatThreadInfo[] = data.threads.map((thread: any) => ({
              id: thread.thread_id,
              title: `Thread ${thread.thread_id}`,
              createdAt: new Date(thread.last_message_at).getTime(),
              updatedAt: new Date(thread.last_message_at).getTime(),
            }));
            
            // Merge with existing local threads (keep both, MongoDB as source of truth)
            if (mongoThreads.length > 0) {
              setThreadSummaries((prev) => {
                // Create a map of existing threads by ID
                const existingMap = new Map(prev.map((t) => [t.id, t]));
                
                // Add MongoDB threads, preserving local titles if they exist
                mongoThreads.forEach((mongoThread) => {
                  const existing = existingMap.get(mongoThread.id);
                  if (existing) {
                    // Keep the local title if it's more descriptive
                    mongoThread.title = existing.title !== 'New conversation' ? existing.title : mongoThread.title;
                  }
                  existingMap.set(mongoThread.id, mongoThread);
                });
                
                return Array.from(existingMap.values());
              });
            }
          }
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          return;
        }
        console.warn('Failed to load threads from MongoDB (may not be enabled):', err);
      } finally {
        setHasLoadedMongoThreads(true);
      }
    };

    void loadThreadsFromMongoDB();

    return () => {
      controller.abort();
    };
  }, [sessionToken]);

  const resetConversation = ({ force = false }: { force?: boolean } = {}) => {
    const activeThreadSummary = threadSummaries.find((thread) => thread.id === activeThreadId);
    const hasUserMessages = messages.some((message) => message.role === 'user');
    const hasPriorConversation = activeThreadSummary ? activeThreadSummary.title !== 'New conversation' : false;

    if (!force && activeThreadId && !hasUserMessages && !hasPriorConversation) {
      setChatError('Send a message before starting a new conversation.');
      return;
    }

    const newThreadId = createThreadId();
    const createdAt = Date.now();
    const newThread: ChatThreadInfo = {
      id: newThreadId,
      title: 'New conversation',
      createdAt,
      updatedAt: createdAt,
    };
    setActiveThreadId(newThreadId);
    setThreadSummaries((prev) => {
      const remaining = prev.filter((thread) => thread.id !== newThreadId);
      const next = [...remaining, newThread];
      try {
        window.localStorage.setItem(THREADS_INDEX_KEY, JSON.stringify(next));
      } catch (err) {
        console.warn('Unable to persist thread index', err);
      }
      return next;
    });
    setMessages([
      {
        id: createId(),
        role: 'assistant',
        content: greetingMessage,
        downloads: [],
      },
    ]);
    setPendingMessage('');
    setChatError(null);
    setLatestCoverLetterId(null);
    try {
      window.localStorage.setItem(THREAD_STORAGE_KEY, newThreadId);
    } catch (err) {
      console.warn('Unable to persist thread id', err);
    }
  };

  const clearChatHistory = () => {
    if (typeof window === 'undefined') {
      return;
    }

    // Clear from MongoDB if available
    if (sessionToken) {
      fetch(`${API_BASE_URL}/api/chat/history`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${sessionToken}`,
        },
      })
        .then((response) => response.json())
        .then((data) => {
          console.log('Cleared MongoDB history:', data);
        })
        .catch((err) => {
          console.warn('Failed to clear MongoDB history (may not be enabled):', err);
        });
    }

    // Clear local storage
    try {
      window.localStorage.removeItem(THREADS_INDEX_KEY);
      window.localStorage.removeItem(THREAD_STORAGE_KEY);
    } catch (err) {
      console.warn('Unable to clear stored thread data', err);
    }

    setThreadSummaries([]);
    setActiveThreadId(null);
    setChatError(null);
    resetConversation({ force: true });
  };

  const handleChatSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const trimmed = pendingMessage.trim();
    if (!trimmed) {
      return;
    }

    if (!sessionToken) {
      setIsAuthModalOpen(true);
      setChatError('Enter your access code to continue chatting.');
      return;
    }

    const userMessage: ChatMessage = {
      id: createId(),
      role: 'user',
      content: trimmed,
      downloads: [],
    };

    setMessages((prev) => [...prev, userMessage]);
    setPendingMessage('');
    setChatError(null);

    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${sessionToken}`,
        },
        body: JSON.stringify({
          message: trimmed,
          fileIds: uploadedFiles.map((file) => file.id),
          threadId: activeThreadId,
        }),
      });

      if (!response.ok) {
        if (response.status === 401) {
          setSessionToken(null);
          setIsAuthModalOpen(true);
          setAuthError('Session expired. Please enter a new access code.');
        }
        const problem = await response.json().catch(() => ({}));
        throw new Error(problem.error ?? 'Request failed');
      }

      const data: ChatResponsePayload = await response.json();

      const assistantMessage: ChatMessage = {
        id: createId(),
        role: 'assistant',
        content: data.reply ?? 'No response received.',
        downloads: data.downloads ?? [],
      };

      setMessages((prev) => [...prev, assistantMessage]);
      const newLetterId = data.coverLetterId ?? null;
      setLatestCoverLetterId(newLetterId);
      const updatedAt = Date.now();
      if (activeThreadId) {
        setThreadSummaries((prev) => {
          const existing = prev.find((thread) => thread.id === activeThreadId);
          const baseTitle = trimmed.slice(0, 60) || 'Conversation';
          const threadTitle = existing?.title && existing.title !== 'New conversation' ? existing.title : baseTitle;
          const nextThread: ChatThreadInfo = existing
            ? { ...existing, title: threadTitle, updatedAt }
            : {
                id: activeThreadId,
                title: baseTitle,
                createdAt: updatedAt,
                updatedAt,
              };
          const next = [...prev.filter((thread) => thread.id !== activeThreadId), nextThread];
          try {
            window.localStorage.setItem(THREADS_INDEX_KEY, JSON.stringify(next));
          } catch (err) {
            console.warn('Unable to persist thread index', err);
          }
          return next;
        });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setChatError(message);
      setLatestCoverLetterId(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectThread = async (threadId: string) => {
    if (threadId === activeThreadId) {
      return;
    }

    setActiveThreadId(threadId);
    try {
      window.localStorage.setItem(THREAD_STORAGE_KEY, threadId);
    } catch (err) {
      console.warn('Unable to persist thread id', err);
    }

    // Try to load messages from MongoDB
    if (sessionToken) {
      try {
        const response = await fetch(`${API_BASE_URL}/api/chat/history?threadId=${threadId}`, {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${sessionToken}`,
          },
        });

        if (response.ok) {
          const data = await response.json();
          if (data.messages && Array.isArray(data.messages) && data.messages.length > 0) {
            // Convert MongoDB messages to chat messages
            const loadedMessages: ChatMessage[] = data.messages.map((msg: any) => ({
              id: msg._id || createId(),
              role: msg.role as ChatRole,
              content: msg.content,
              downloads: [],
            }));
            setMessages(loadedMessages);
            setPendingMessage('');
            setChatError(null);
            setLatestCoverLetterId(null);
            return;
          }
        }
      } catch (err) {
        console.warn('Failed to load thread history from MongoDB (may not be enabled):', err);
      }
    }

    // Fallback to empty conversation if MongoDB not available
    setMessages([
      {
        id: createId(),
        role: 'assistant',
        content: greetingMessage,
        downloads: [],
      },
    ]);
    setPendingMessage('');
    setChatError(null);
    setLatestCoverLetterId(null);
  };

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    if (activeThreadId) {
      window.localStorage.setItem(THREAD_STORAGE_KEY, activeThreadId);
    } else {
      window.localStorage.removeItem(THREAD_STORAGE_KEY);
    }
  }, [activeThreadId]);

  // Load messages from MongoDB when the active thread changes
  useEffect(() => {
    if (!sessionToken || !activeThreadId) {
      return;
    }

    const controller = new AbortController();

    const loadThreadMessages = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/chat/history?threadId=${activeThreadId}`, {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${sessionToken}`,
          },
          signal: controller.signal,
        });

        if (response.ok) {
          const data = await response.json();
          if (data.messages && Array.isArray(data.messages) && data.messages.length > 0) {
            // Convert MongoDB messages to chat messages
            const loadedMessages: ChatMessage[] = data.messages.map((msg: any) => ({
              id: msg._id || createId(),
              role: msg.role as ChatRole,
              content: msg.content,
              downloads: [],
            }));
            
            // Only update if we don't have messages yet or if the first message is just the greeting
            const hasOnlyGreeting = messages.length === 1 && messages[0].content === greetingMessage;
            if (messages.length === 0 || hasOnlyGreeting) {
              setMessages(loadedMessages);
            }
          }
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          return;
        }
        console.warn('Failed to load thread messages from MongoDB:', err);
      }
    };

    void loadThreadMessages();

    return () => {
      controller.abort();
    };
  }, [sessionToken, activeThreadId]);

  useEffect(() => {
    // Wait for MongoDB threads to load before initializing
    if (!hasLoadedMongoThreads) {
      return;
    }

    if (!activeThreadId && threadSummaries.length === 0) {
      resetConversation({ force: true });
    } else if (!activeThreadId && threadSummaries.length > 0) {
      const latestThread = threadSummaries.reduce((latest, thread) =>
        thread.updatedAt > (latest?.updatedAt ?? 0) ? thread : latest,
      undefined as ChatThreadInfo | undefined);
      if (latestThread) {
        setActiveThreadId(latestThread.id);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasLoadedMongoThreads]);

  const loadUploadedFiles = async () => {
    const token = sessionToken;
    if (!token) {
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/uploads`, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        // Silently fail - not critical if uploads don't load
        console.warn('Failed to load uploaded files');
        return;
      }

      const payload: { files: UploadedFileSummary[] } = await response.json();
      if (payload.files && Array.isArray(payload.files)) {
        setUploadedFiles(payload.files.sort((a, b) => b.uploadedAt - a.uploadedAt));
      }
    } catch (err) {
      console.warn('Error loading uploaded files:', err);
    }
  };

  const uploadFiles = async (files: FileList | File[]) => {
    const token = sessionToken;
    if (!token) {
      setIsAuthModalOpen(true);
      setAuthError('Enter your access code to upload files.');
      return;
    }

    const fileArray = Array.isArray(files) ? files : Array.from(files);
    if (!fileArray.length) {
      return;
    }

    const formData = new FormData();
    fileArray.forEach((file) => {
      formData.append('files', file);
    });

    setIsUploading(true);
    setUploadError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/uploads`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      if (!response.ok) {
        if (response.status === 401) {
          setSessionToken(null);
          setIsAuthModalOpen(true);
          setAuthError('Session expired. Request a new access code to continue.');
        }
        const problem = await response.json().catch(() => ({}));
        throw new Error(problem.error ?? 'Upload failed');
      }

      const payload: { files: UploadedFileSummary[] } = await response.json();
      setUploadedFiles((prev) => {
        const merged = new Map(prev.map((file) => [file.id, file]));
        payload.files.forEach((file) => {
          merged.set(file.id, file);
        });
        return Array.from(merged.values()).sort((a, b) => b.uploadedAt - a.uploadedAt);
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown upload error';
      setUploadError(message);
    } finally {
      setIsUploading(false);
    }
  };

  const handleDeleteFile = async (fileId: string) => {
    if (!sessionToken) {
      setIsAuthModalOpen(true);
      setAuthError('Enter your access code to manage files.');
      return;
    }

    setDeletingFiles((prev) => ({ ...prev, [fileId]: true }));
    setUploadError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/uploads/${fileId}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${sessionToken}`,
        },
      });

      if (!response.ok) {
        if (response.status === 401) {
          setSessionToken(null);
          setIsAuthModalOpen(true);
          setAuthError('Session expired. Please enter a new access code.');
        }
        const problem = await response.json().catch(() => ({}));
        throw new Error(problem.error ?? 'Unable to delete file');
      }

      setUploadedFiles((prev) => prev.filter((file) => file.id !== fileId));
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown delete error';
      setUploadError(message);
    } finally {
      setDeletingFiles((prev) => {
        const next = { ...prev };
        delete next[fileId];
        return next;
      });
    }
  };

  const handleFileInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files && files.length > 0) {
      void uploadFiles(files);
    }
    // Reset value so the same file can be selected twice if needed.
    event.target.value = '';
  };

  const handleDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragOver(false);
    void uploadFiles(event.dataTransfer.files);
  };

  const handleDragOver = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleRequestCode = async () => {
    if (isRequestingCode) {
      return;
    }

    setIsRequestingCode(true);
    setAuthError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/request-code`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ profileId }),
      });

      if (!response.ok) {
        const problem = await response.json().catch(() => ({}));
        throw new Error(problem.error ?? 'Unable to generate code');
      }

  const data: { code: string; profileId: string; expiresAt: number } = await response.json();
      setProfileId(data.profileId);
      setCodeInput(data.code);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error requesting code';
      setAuthError(message);
    } finally {
      setIsRequestingCode(false);
    }
  };

  const handleVerifyCode = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const trimmed = codeInput.trim();
    if (!trimmed) {
      setAuthError('Enter the one-time code you received.');
      return;
    }

    setIsVerifyingCode(true);
    setAuthError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/verify`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ code: trimmed }),
      });

      if (!response.ok) {
        const problem = await response.json().catch(() => ({}));
        throw new Error(problem.error ?? 'Unable to verify code');
      }

  const data: { token: string; profileId: string; expiresAt: number } = await response.json();
      setSessionToken(data.token);
      setProfileId(data.profileId);
      setIsAuthModalOpen(false);
      setCodeInput('');
      setAuthError(null);
      setLatestCoverLetterId(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown verification error';
      setAuthError(message);
    } finally {
      setIsVerifyingCode(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-950 pt-16 text-slate-100">
      <header className="fixed inset-x-0 top-0 z-40 border-b border-emerald-400/70 bg-slate-950 text-emerald-300">
  <div className="mx-auto flex w-full items-center justify-start px-4 py-2 md:px-8 lg:grid lg:grid-cols-[280px_minmax(0,1fr)_280px] lg:px-0">
          <span className="text-lg font-semibold tracking-tight lg:col-start-1 lg:justify-self-center">ApplyWise</span>
        </div>
      </header>
      {isAuthModalOpen && (
        <section className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 px-4">
          <div className="w-full max-w-md rounded-3xl border border-slate-800/80 bg-slate-900/90 p-6 shadow-2xl shadow-emerald-500/20">
            <header className="mb-4 flex flex-col gap-1">
              <h2 className="text-xl font-semibold text-emerald-300">Access your workspace</h2>
              <p className="text-sm text-slate-400">
                Enter your 6-character workspace code to access your conversations and files. Don't have one? Generate a new code to create your workspace.
              </p>
            </header>

            <form className="flex flex-col gap-4" onSubmit={handleVerifyCode}>
              <label className="text-xs font-medium uppercase tracking-[0.3em] text-slate-500" htmlFor="access-code">
                Workspace Code
              </label>
              <input
                id="access-code"
                type="text"
                inputMode="text"
                autoComplete="off"
                maxLength={6}
                className="w-full rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-sm tracking-[0.4em] text-slate-100 placeholder:text-slate-500 focus:border-emerald-400 focus:outline-none uppercase"
                placeholder="ABC123"
                value={codeInput}
                onChange={(event) => setCodeInput(event.target.value.toUpperCase())}
              />

              <button
                type="submit"
                disabled={isVerifyingCode}
                className="flex h-11 items-center justify-center rounded-xl bg-emerald-500 font-semibold text-emerald-950 transition hover:bg-emerald-400 disabled:opacity-60"
              >
                {isVerifyingCode ? 'Accessing workspace…' : 'Access workspace'}
              </button>

              <button
                type="button"
                onClick={handleRequestCode}
                disabled={isRequestingCode}
                className="h-11 rounded-xl border border-emerald-400/60 text-sm font-semibold text-emerald-200 transition hover:border-emerald-300 hover:text-emerald-100 disabled:opacity-60"
              >
                {isRequestingCode ? 'Creating workspace…' : 'Create new workspace'}
              </button>
              {authError && (
                <p className="rounded-xl border border-rose-600/40 bg-rose-500/10 px-4 py-3 text-xs text-rose-200">
                  {authError}
                </p>
              )}
              <div className="rounded-lg border border-slate-700/50 bg-slate-800/30 p-3">
                <p className="text-xs text-slate-400">
                  💡 <strong className="text-slate-300">Tip:</strong> Your workspace code is like a password. Save it somewhere safe! You'll need it to access this workspace from another device.
                </p>
              </div>
            </form>
          </div>
        </section>
      )}

      <section className="flex w-full flex-col gap-6 pb-16 pt-4">
  <div className="grid items-start gap-6 px-4 md:px-8 lg:px-0 lg:grid-cols-[280px_minmax(0,1fr)_280px] lg:items-stretch">
          <div className="hidden lg:block" />
          <header className="flex flex-col gap-2 lg:items-center lg:text-center">
          <h1 className="text-4xl font-bold tracking-tight md:text-5xl">
            Your personal job application assistant
          </h1>
          <p className="max-w-2xl text-base text-slate-300">
            Upload your resume or portfolio, and let ApplyWise review your documents and generate a tailored cover letter in seconds.
          </p>
          </header>
          <div className="hidden lg:block" />
        </div>

        <div className="grid w-full items-start gap-6 px-4 md:px-8 lg:px-0 lg:grid-cols-[280px_minmax(0,1fr)_280px] lg:items-stretch">
          <aside className="lg:sticky lg:top-16 lg:h-[calc(100vh-4rem)] flex flex-col gap-4 rounded-2xl border border-slate-800/60 bg-slate-900/60 p-6 shadow-lg shadow-emerald-500/10">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Workspace</p>
              {sessionToken ? (
                <>
                  <p className="mt-1 text-sm font-semibold text-emerald-300">✓ Active</p>
                  {profileId && (
                    <div className="mt-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3">
                      <p className="text-[10px] uppercase tracking-wide text-emerald-300/80">Your workspace code:</p>
                      <p className="mt-1 font-mono text-2xl font-bold tracking-widest text-emerald-300">{profileId}</p>
                      <p className="mt-2 text-[10px] text-slate-400">
                        💾 Save this code! Use it on any device to access your workspace and conversation history.
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
                    onClick={() => setIsAuthModalOpen(true)}
                  >
                    Access workspace
                  </button>
                </>
              )}
            </div>

            <button
              type="button"
              className="rounded-xl bg-emerald-500/90 px-4 py-2 text-sm font-semibold text-emerald-950 transition hover:bg-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-200"
              onClick={() => resetConversation()}
            >
              New chat
            </button>

            <button
              type="button"
              className="rounded-xl border border-slate-800/80 bg-slate-900/70 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-rose-500/60 hover:bg-rose-500/10 hover:text-rose-100 focus:outline-none focus:ring-2 focus:ring-rose-300/60"
              onClick={clearChatHistory}
            >
              Clear history
            </button>

            <div className="flex flex-1 flex-col gap-3">
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Chat history</p>
              <ul className="flex-1 space-y-2 overflow-y-auto pr-1 text-sm text-slate-300">
                {chatHistory.map((chat) => (
                  <li
                    key={chat.id}
                    className={`rounded-xl border px-3 py-3 transition ${
                      chat.id === activeThreadId
                        ? 'border-emerald-500/70 bg-emerald-500/10 text-emerald-100'
                        : 'border-slate-800/80 bg-slate-900/70 text-slate-300 hover:border-emerald-400/60 hover:text-emerald-200'
                    }`}
                    onClick={() => handleSelectThread(chat.id)}
                  >
                    <p className="font-medium text-slate-100">{chat.title}</p>
                    {chat.lastActive && <p className="text-[11px] text-slate-500">{chat.lastActive}</p>}
                  </li>
                ))}
              </ul>
            </div>
            {latestCoverLetterId && (
              <div className="rounded-2xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-xs text-emerald-100">
                Latest draft ready. Ask for edits or generate a PDF when you&apos;re happy.
              </div>
            )}
          </aside>

          <div className="flex min-h-[520px] flex-col rounded-2xl border border-slate-800/60 bg-slate-900/60 shadow-lg shadow-emerald-500/10 backdrop-blur">
            <div className="border-b border-slate-800/70 bg-slate-900/80 px-6 py-4">
              <h2 className="text-lg font-semibold text-emerald-300">ChatAW</h2>
              <p className="text-xs text-slate-400">
                Copy and paste a job description for a tailored cover letter.
              </p>
              {chatError && (
                <p className="mt-2 rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
                  {chatError}
                </p>
              )}
            </div>

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
                  {message.downloads && message.downloads.length > 0 && (
                    <div className="mt-3 space-y-2">
                      {message.downloads.map((download) => (
                        <a
                          key={download.id}
                          href={`data:${download.mimeType};base64,${download.data}`}
                          download={download.filename}
                          className="inline-flex items-center justify-center gap-2 rounded-lg border border-emerald-400/60 bg-emerald-500/10 px-3 py-2 text-xs font-semibold text-emerald-200 transition hover:bg-emerald-400/20 focus:outline-none focus:ring-2 focus:ring-emerald-300"
                        >
                          Download {download.label}
                        </a>
                      ))}
                    </div>
                  )}
                </article>
              ))}

              {isLoading && (
                <article className="max-w-[75%] rounded-bl-md rounded-2xl bg-slate-800/80 px-4 py-3 text-sm text-slate-100 shadow-sm">
                  <span className="block text-[11px] uppercase tracking-wide opacity-75">ChatAW</span>
                  <p className="mt-1 animate-pulse text-slate-400">Thinking…</p>
                </article>
              )}
            </div>

            <form
              className="sticky bottom-0 z-10 border-t border-slate-800/70 bg-slate-900/95 px-4 py-4 backdrop-blur"
              onSubmit={handleChatSubmit}
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
                  onChange={(event) => setPendingMessage(event.target.value)}
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

          <aside className="lg:sticky lg:top-16 flex h-fit lg:self-stretch flex-col gap-4 rounded-2xl border border-slate-800/60 bg-slate-900/60 p-6 shadow-lg shadow-emerald-500/10">
            <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-400">
              Upload resume or relevant files
            </h2>
            <label
              htmlFor="file-upload"
              className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border border-dashed px-6 py-10 text-center text-sm transition focus:outline-none focus:ring-2 focus:ring-emerald-300/70 md:text-base ${
                isDragOver ? 'border-emerald-400/80 bg-emerald-500/10 text-emerald-200' : 'border-slate-700/70 text-slate-300'
              }`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <input
                id="file-upload"
                ref={fileInputRef}
                type="file"
                multiple
                className="hidden"
                onChange={handleFileInputChange}
              />
              <span className="text-xs font-semibold uppercase tracking-[0.3em] text-emerald-400/80">
                Drop files here
              </span>
              <p className="max-w-[220px] text-xs text-slate-400">
                Drag and drop your resume, job description PDFs, or click to browse. Files upload securely to this
                session and will feed future cover letter drafts.
              </p>
              <button
                type="button"
                className="rounded-full bg-emerald-400/90 px-4 py-2 text-xs font-semibold text-emerald-950 shadow transition hover:bg-emerald-300"
                onClick={() => fileInputRef.current?.click()}
              >
                Browse files
              </button>
            </label>

            {!!uploadedFiles.length && (
              <ul className="space-y-2 text-sm text-slate-300">
                {uploadedFiles.map((file) => {
                  const isDeleting = Boolean(deletingFiles[file.id]);
                  return (
                    <li
                      key={file.id}
                      className="flex items-center justify-between rounded-xl border border-slate-800/80 bg-slate-900/70 px-4 py-2"
                    >
                      <div>
                        <p className="font-medium text-slate-100">{file.name}</p>
                        <p className="text-xs text-slate-500">
                          {(file.size / 1024).toFixed(1)} KB · {new Date(file.uploadedAt).toLocaleTimeString()}
                        </p>
                      </div>
                      <div className="flex items-center gap-3">
                        <span
                          className={`flex h-6 w-6 items-center justify-center ${
                            isDeleting ? 'text-rose-300' : 'text-emerald-400'
                          }`}
                          aria-live="polite"
                        >
                          {isDeleting ? (
                            'Removing…'
                          ) : (
                            <svg
                              className="h-4 w-4"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              aria-hidden="true"
                            >
                              <path d="M20 6L9 17l-5-5" />
                            </svg>
                          )}
                          <span className="sr-only">{isDeleting ? 'Removing file' : 'Uploaded'}</span>
                        </span>
                        <button
                          type="button"
                          className="flex h-8 w-8 items-center justify-center rounded-full border border-slate-700 text-slate-400 transition hover:border-rose-400 hover:text-rose-300 disabled:opacity-50"
                          onClick={() => {
                            void handleDeleteFile(file.id);
                          }}
                          disabled={isDeleting}
                          aria-label={`Remove ${file.name}`}
                        >
                          <svg
                            className="h-4 w-4"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.5"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            aria-hidden="true"
                          >
                            <path d="M3 6h18" />
                            <path d="M8.25 6V4.5A1.5 1.5 0 0 1 9.75 3h4.5a1.5 1.5 0 0 1 1.5 1.5V6" />
                            <path d="M18 6v13.5a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 6 19.5V6" />
                            <path d="M10 11v6" />
                            <path d="M14 11v6" />
                          </svg>
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}

            {isUploading && (
              <p className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-xs text-emerald-200">
                Uploading files… they will be available to the assistant in a moment.
              </p>
            )}

            <p className="text-xs text-slate-500">
              This panel will eventually sync with the backend to persist resumes and supporting docs alongside your
              conversations.
            </p>
            {uploadError && (
              <p className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-xs text-rose-200">
                {uploadError}
              </p>
            )}

            <div className="mt-2 rounded-2xl border border-slate-800/70 bg-slate-900/70 px-4 py-4 text-xs text-slate-400">
              Ask the assistant for a PDF to receive a styled download link right in the conversation.
            </div>
          </aside>
        </div>
      </section>
    </main>
  );
};

export default HomePage;
