/**
 * Chat-related type definitions
 * These types define the structure of chat messages, threads, and related data
 */

export type ChatRole = 'user' | 'assistant';

export type ChatDownload = {
  id: string;
  label: string;
  filename: string;
  mimeType: string;
  data: string;
};

export type MessageFeedbackValue = 'up' | 'down';

export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  downloads?: ChatDownload[];
  assistantMessageId?: string | null;
  feedback?: MessageFeedbackValue | null;
};

export type ChatSummary = {
  id: string;
  title: string;
  lastActive?: string;
};

export type ChatResponsePayload = {
  reply: string;
  model?: string;
  coverLetterId?: string;
  downloads?: ChatDownload[];
  assistantMessageId?: string | null;
  feedback?: {
    status: MessageFeedbackValue;
    comment?: string;
  } | null;
};

export type ChatThreadInfo = {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
};
