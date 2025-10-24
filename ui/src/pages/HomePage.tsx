/**
 * HomePage Component
 * Main application page that integrates authentication, chat, and file upload functionality
 * 
 * This component orchestrates:
 * - User authentication via workspace codes
 * - Chat interface with conversation threads
 * - File upload and management
 * - Integration with MongoDB for data persistence
 */

import { useMemo } from 'react';
import { AuthModal } from '../components/AuthModal';
import { Sidebar } from '../components/Sidebar';
import { ChatPanel } from '../components/ChatPanel';
import { FileUploadPanel } from '../components/FileUploadPanel';
import { useAuth } from '../hooks/useAuth';
import { useChat } from '../hooks/useChat';
import { useFileUpload } from '../hooks/useFileUpload';
import { API_BASE_URL } from '../utils/constants';
import { ChatSummary } from '../types/chat.types';

const HomePage = () => {
  // Authentication state and handlers
  const {
    sessionToken,
    profileId,
    isAuthModalOpen,
    authError,
    setSessionToken,
    setProfileId,
    setIsAuthModalOpen,
    setAuthError,
  } = useAuth(API_BASE_URL);

  /**
   * Handler for authentication errors that require re-login
   */
  const handleAuthError = () => {
    setSessionToken(null);
    setIsAuthModalOpen(true);
    setAuthError('Session expired. Please enter a new access code.');
  };

  /**
   * Handler for successful authentication
   */
  const handleAuthenticated = (token: string, id: string) => {
    setSessionToken(token);
    setProfileId(id);
    setIsAuthModalOpen(false);
    setAuthError(null);
  };

  /**
   * Handler for switching to a different workspace
   * Re-authenticates with the new workspace code
   */
  const handleSwitchWorkspace = async (newCode: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: newCode }),
      });

      if (!response.ok) {
        const problem = await response.json().catch(() => ({}));
        throw new Error(problem.error ?? 'Unable to verify workspace code');
      }

      const data: { token: string; profileId: string; expiresAt: number } = await response.json();
      
      // Update authentication state with new workspace
      setSessionToken(data.token);
      setProfileId(data.profileId);
      setAuthError(null);
      
      // Reload the page to reset all state for the new workspace
      window.location.reload();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to switch workspace';
      setAuthError(message);
      alert(`Failed to switch workspace: ${message}`);
    }
  };

  // File upload state and handlers
  const { uploadedFiles, uploadError, isUploading, deletingFiles, uploadFiles, handleDeleteFile } = useFileUpload({
    sessionToken,
    apiBaseUrl: API_BASE_URL,
    onAuthError: handleAuthError,
  });

  // Chat state and handlers
  const {
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
    handleMessageFeedback,
    feedbackPending,
  } = useChat({
    sessionToken,
    apiBaseUrl: API_BASE_URL,
    uploadedFileIds: uploadedFiles.map((file) => file.id),
    onAuthError: handleAuthError,
  });

  /**
   * Transform thread summaries into chat history format with sorted timestamps
   */
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

  return (
    <main className="min-h-screen bg-slate-950 pt-16 text-slate-100">
      {/* Application Header */}
      <header className="fixed inset-x-0 top-0 z-40 border-b border-emerald-400/70 bg-slate-950 text-emerald-300">
        <div className="mx-auto flex w-full items-center justify-start px-4 py-2 md:px-8 lg:grid lg:grid-cols-[280px_minmax(0,1fr)_280px] lg:px-0">
          <span className="text-lg font-semibold tracking-tight lg:col-start-1 lg:justify-self-center">
            ApplyWise
          </span>
        </div>
      </header>

      {/* Authentication Modal */}
      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        onAuthenticated={handleAuthenticated}
        apiBaseUrl={API_BASE_URL}
        authError={authError}
        setAuthError={setAuthError}
      />

  {/* Main Content Section */}
  <section className="flex w-full flex-col gap-6 pt-4 pb-8 lg:pb-4">
        {/* Hero Section */}
        <div className="grid items-start gap-6 px-4 md:px-8 lg:px-0 lg:grid-cols-[280px_minmax(0,1fr)_280px] lg:items-stretch">
          <div className="hidden lg:block" />
          <header className="flex flex-col gap-2 lg:items-center lg:text-center">
            <h1 className="text-4xl font-bold tracking-tight md:text-5xl">
              Your personal job application assistant
            </h1>
            <p className="max-w-2xl text-base text-slate-300">
              Upload your resume or portfolio, and let ApplyWise review your documents and generate a tailored cover
              letter in seconds.
            </p>
          </header>
          <div className="hidden lg:block" />
        </div>

        {/* Main Application Grid: Sidebar | Chat | File Upload */}
        <div className="grid w-full items-start gap-6 px-4 md:px-8 lg:px-0 lg:grid-cols-[280px_minmax(0,1fr)_280px] lg:items-stretch">
          {/* Left Sidebar - Workspace & Chat History */}
          <Sidebar
            sessionToken={sessionToken}
            profileId={profileId}
            chatHistory={chatHistory}
            activeThreadId={activeThreadId}
            latestCoverLetterId={latestCoverLetterId}
            onNewChat={resetConversation}
            onDeleteThread={deleteThread}
            onSelectThread={handleSelectThread}
            onOpenAuthModal={() => setIsAuthModalOpen(true)}
            onSwitchWorkspace={handleSwitchWorkspace}
          />

          {/* Center - Chat Interface */}
          <ChatPanel
            messages={messages}
            pendingMessage={pendingMessage}
            isLoading={isLoading}
            chatError={chatError}
            isSubmitDisabled={isSubmitDisabled}
            onSubmit={handleChatSubmit}
            onMessageChange={setPendingMessage}
            onFeedback={handleMessageFeedback}
            feedbackPending={feedbackPending}
          />

          {/* Right Sidebar - File Upload */}
          <FileUploadPanel
            uploadedFiles={uploadedFiles}
            isUploading={isUploading}
            uploadError={uploadError}
            deletingFiles={deletingFiles}
            latestCoverLetterId={latestCoverLetterId}
            onUpload={uploadFiles}
            onDelete={handleDeleteFile}
          />
        </div>
      </section>
    </main>
  );
};

export default HomePage;
