/**
 * useChat Hook
 * Manages chat messages, threads, and conversation logic
 */

import { FormEvent, useEffect, useMemo, useState } from 'react';
import { ChatMessage, ChatThreadInfo, ChatResponsePayload } from '../types/chat.types';
import { createId, createThreadId, readFromStorage, writeToStorage, removeFromStorage } from '../utils/helpers';
import { GREETING_MESSAGE, THREAD_STORAGE_KEY, THREADS_INDEX_KEY } from '../utils/constants';

type UseChatProps = {
  sessionToken: string | null;
  apiBaseUrl: string;
  uploadedFileIds: string[];
  onAuthError: () => void;
};

type UseChatReturn = {
  messages: ChatMessage[];
  pendingMessage: string;
  isLoading: boolean;
  chatError: string | null;
  activeThreadId: string | null;
  threadSummaries: ChatThreadInfo[];
  latestCoverLetterId: string | null;
  isSubmitDisabled: boolean;
  setPendingMessage: (message: string) => void;
  handleChatSubmit: (event: FormEvent<HTMLFormElement>) => void;
  handleSelectThread: (threadId: string) => void;
  resetConversation: (options?: { force?: boolean }) => void;
  deleteThread: (threadId: string) => Promise<void>;
};

/**
 * Custom hook for managing chat state and operations
 * Handles message sending, thread management, and history persistence
 */
export const useChat = ({ sessionToken, apiBaseUrl, uploadedFileIds, onAuthError }: UseChatProps): UseChatReturn => {
  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    { id: createId(), role: 'assistant', content: GREETING_MESSAGE, downloads: [] },
  ]);
  const [pendingMessage, setPendingMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [latestCoverLetterId, setLatestCoverLetterId] = useState<string | null>(null);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [threadSummaries, setThreadSummaries] = useState<ChatThreadInfo[]>([]);
  const [hasLoadedMongoThreads, setHasLoadedMongoThreads] = useState(false);
  const [lastThreadRefresh, setLastThreadRefresh] = useState<number>(0);

  const isSubmitDisabled = useMemo(
    () => !pendingMessage.trim() || isLoading || !sessionToken,
    [pendingMessage, isLoading, sessionToken],
  );

  // Clear local storage and reset state when session token changes (user logs in/out)
  useEffect(() => {
    if (!sessionToken) {
      // User logged out - clear everything
      removeFromStorage(THREADS_INDEX_KEY);
      removeFromStorage(THREAD_STORAGE_KEY);
      setThreadSummaries([]);
      setActiveThreadId(null);
      setMessages([{ id: createId(), role: 'assistant', content: GREETING_MESSAGE, downloads: [] }]);
      setHasLoadedMongoThreads(true);
      return;
    }

    // User logged in - clear any existing localStorage data to ensure fresh start
    removeFromStorage(THREADS_INDEX_KEY);
    removeFromStorage(THREAD_STORAGE_KEY);
    setHasLoadedMongoThreads(false);
  }, [sessionToken]);

  // Load thread summaries from MongoDB (ONLY source of truth)
  useEffect(() => {
    if (!sessionToken) {
      return;
    }

    const controller = new AbortController();

    const loadThreadsFromMongoDB = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/api/chat/threads`, {
          method: 'GET',
          headers: { Authorization: `Bearer ${sessionToken}` },
          signal: controller.signal,
        });

        if (response.ok) {
          const data = await response.json();
          if (data.threads && Array.isArray(data.threads)) {
            const mongoThreads: ChatThreadInfo[] = data.threads.map((thread: any) => ({
              id: thread.thread_id,
              title: thread.title || `Thread ${thread.thread_id}`,
              createdAt: new Date(thread.last_message_at).getTime(),
              updatedAt: new Date(thread.last_message_at).getTime(),
            }));

            // Sort by updatedAt descending (newest first) - backend already sorts, but ensure it
            mongoThreads.sort((a, b) => b.updatedAt - a.updatedAt);
            setThreadSummaries(mongoThreads);
          }
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        console.warn('Failed to load threads from MongoDB:', err);
      } finally {
        setHasLoadedMongoThreads(true);
      }
    };

    void loadThreadsFromMongoDB();
    return () => controller.abort();
  }, [sessionToken, apiBaseUrl, lastThreadRefresh]);

  // Poll for thread updates every 5 seconds to sync across tabs
  useEffect(() => {
    if (!sessionToken || !hasLoadedMongoThreads) {
      return;
    }

    const intervalId = setInterval(() => {
      // Trigger a refresh of thread list
      setLastThreadRefresh(Date.now());
    }, 5000); // Poll every 5 seconds

    return () => clearInterval(intervalId);
  }, [sessionToken, hasLoadedMongoThreads]);

  // Initialize thread if needed
  useEffect(() => {
    if (!hasLoadedMongoThreads) return;

    if (!activeThreadId && threadSummaries.length === 0) {
      resetConversation({ force: true });
    } else if (!activeThreadId && threadSummaries.length > 0) {
      const latestThread = threadSummaries.reduce(
        (latest, thread) => (thread.updatedAt > (latest?.updatedAt ?? 0) ? thread : latest),
        undefined as ChatThreadInfo | undefined,
      );
      if (latestThread) {
        setActiveThreadId(latestThread.id);
      }
    }
  }, [hasLoadedMongoThreads, activeThreadId, threadSummaries]);

  // Load messages from MongoDB when thread changes
  useEffect(() => {
    if (!sessionToken || !activeThreadId) return;

    const controller = new AbortController();

    const loadThreadMessages = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/api/chat/history?threadId=${activeThreadId}`, {
          method: 'GET',
          headers: { Authorization: `Bearer ${sessionToken}` },
          signal: controller.signal,
        });

        if (response.ok) {
          const data = await response.json();
          if (data.messages && Array.isArray(data.messages) && data.messages.length > 0) {
            const loadedMessages: ChatMessage[] = data.messages.map((msg: any) => ({
              id: msg._id || createId(),
              role: msg.role,
              content: msg.content,
              downloads: [],
            }));

            const hasOnlyGreeting = messages.length === 1 && messages[0].content === GREETING_MESSAGE;
            if (messages.length === 0 || hasOnlyGreeting) {
              setMessages(loadedMessages);
            }
          }
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        console.warn('Failed to load thread messages:', err);
      }
    };

    void loadThreadMessages();
    return () => controller.abort();
  }, [sessionToken, activeThreadId, apiBaseUrl]);

  /**
   * Starts a new conversation thread
   */
  const resetConversation = ({ force = false }: { force?: boolean } = {}) => {
    const activeThreadSummary = threadSummaries.find((thread) => thread.id === activeThreadId);
    const hasUserMessages = messages.some((message) => message.role === 'user');
    const hasPriorConversation = activeThreadSummary ? activeThreadSummary.title !== 'New conversation' : false;

    if (!force && activeThreadId && !hasUserMessages && !hasPriorConversation) {
      setChatError('Send a message before starting a new conversation.');
      return;
    }

    const newThreadId = createThreadId();

    setActiveThreadId(newThreadId);
    // Remove any stale placeholder entry for this threadId without adding
    // a new summary until the backend persists the conversation.
    setThreadSummaries((prev) => prev.filter((thread) => thread.id !== newThreadId));
    setMessages([{ id: createId(), role: 'assistant', content: GREETING_MESSAGE, downloads: [] }]);
    setPendingMessage('');
    setChatError(null);
    setLatestCoverLetterId(null);
  };

  /**
   * Deletes a single thread from MongoDB and local state.
   */
  const deleteThread = async (threadId: string) => {
    setChatError(null);

    const targetThread = threadSummaries.find((thread) => thread.id === threadId);
    if (!targetThread) {
      return;
    }

    if (sessionToken) {
      try {
        const response = await fetch(`${apiBaseUrl}/api/chat/history/${threadId}`, {
          method: 'DELETE',
          headers: { Authorization: `Bearer ${sessionToken}` },
        });

        if (!response.ok) {
          const problem = await response.json().catch(() => ({}));
          throw new Error(problem.error ?? 'Failed to delete chat thread');
        }
      } catch (err) {
        console.warn('Failed to delete thread history:', err);
        setChatError('Unable to delete this conversation. Please try again.');
        return;
      }
    }

    setThreadSummaries((prev) => prev.filter((thread) => thread.id !== threadId));

    if (activeThreadId === threadId) {
      setActiveThreadId(null);
      setMessages([{ id: createId(), role: 'assistant', content: GREETING_MESSAGE, downloads: [] }]);
      setPendingMessage('');
      setLatestCoverLetterId(null);
    }

    if (sessionToken) {
      setLastThreadRefresh(Date.now());
    }
  };

  /**
   * Handles chat message submission
   */
  const handleChatSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const trimmed = pendingMessage.trim();
    if (!trimmed) return;

    if (!sessionToken) {
      onAuthError();
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
      const response = await fetch(`${apiBaseUrl}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${sessionToken}`,
        },
        body: JSON.stringify({
          message: trimmed,
          fileIds: uploadedFileIds,
          threadId: activeThreadId,
        }),
      });

      if (!response.ok) {
        if (response.status === 401) {
          onAuthError();
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
      setLatestCoverLetterId(data.coverLetterId ?? null);

      // Refresh thread list from backend to ensure proper sorting across tabs
      // The backend will have the updated timestamp from save_message
      // and will generate the title from the first user message
      setLastThreadRefresh(Date.now());
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setChatError(message);
      setLatestCoverLetterId(null);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Switches to a different conversation thread
   */
  const handleSelectThread = async (threadId: string) => {
    if (threadId === activeThreadId) return;

    setActiveThreadId(threadId);

    if (sessionToken) {
      try {
        const response = await fetch(`${apiBaseUrl}/api/chat/history?threadId=${threadId}`, {
          method: 'GET',
          headers: { Authorization: `Bearer ${sessionToken}` },
        });

        if (response.ok) {
          const data = await response.json();
          if (data.messages && Array.isArray(data.messages) && data.messages.length > 0) {
            const loadedMessages: ChatMessage[] = data.messages.map((msg: any) => ({
              id: msg._id || createId(),
              role: msg.role,
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
        console.warn('Failed to load thread history:', err);
      }
    }

    setMessages([{ id: createId(), role: 'assistant', content: GREETING_MESSAGE, downloads: [] }]);
    setPendingMessage('');
    setChatError(null);
    setLatestCoverLetterId(null);
  };

  return {
    messages,
    pendingMessage,
    isLoading,
    chatError,
    activeThreadId,
    threadSummaries,
    latestCoverLetterId,
    isSubmitDisabled,
    setPendingMessage,
    handleChatSubmit,
    handleSelectThread,
    resetConversation,
    deleteThread,
  };
};
