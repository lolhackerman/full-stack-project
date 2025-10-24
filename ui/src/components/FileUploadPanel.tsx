/**
 * FileUploadPanel Component
 * Handles file uploads, displays uploaded files, and manages file deletion
 */

import { ChangeEvent, DragEvent, useRef, useState } from 'react';
import { UploadedFileSummary } from '../types/file.types';

type FileUploadPanelProps = {
  uploadedFiles: UploadedFileSummary[];
  isUploading: boolean;
  uploadError: string | null;
  deletingFiles: Record<string, boolean>;
  latestCoverLetterId: string | null;
  onUpload: (files: FileList | File[]) => Promise<void>;
  onDelete: (fileId: string) => Promise<void>;
};

export const FileUploadPanel = ({
  uploadedFiles,
  isUploading,
  uploadError,
  deletingFiles,
  latestCoverLetterId,
  onUpload,
  onDelete,
}: FileUploadPanelProps) => {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const handleFileInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files && files.length > 0) {
      void onUpload(files);
    }
    // Reset value so the same file can be selected again
    event.target.value = '';
  };

  const handleDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragOver(false);
    void onUpload(event.dataTransfer.files);
  };

  const handleDragOver = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  return (
    <aside className="lg:sticky lg:top-16 lg:h-[calc(100vh-4rem)] lg:self-start flex flex-col gap-4 rounded-2xl border border-slate-800/60 bg-slate-900/60 p-6 shadow-lg shadow-emerald-500/10">
      <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-400">
        Upload resume or relevant files
      </h2>

      {/* Drag & Drop Upload Area */}
      <label
        htmlFor="file-upload"
        className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border border-dashed px-6 py-10 text-center text-sm transition focus:outline-none focus:ring-2 focus:ring-emerald-300/70 md:text-base ${
          isDragOver
            ? 'border-emerald-400/80 bg-emerald-500/10 text-emerald-200'
            : 'border-slate-700/70 text-slate-300'
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
        <span className="text-xs font-semibold uppercase tracking-[0.3em] text-emerald-400/80">Drop files here</span>
        <p className="max-w-[220px] text-xs text-slate-400">
          Drag and drop your resume, job description PDFs, or click to browse. Files upload securely to this session
          and will feed future cover letter drafts.
        </p>
        <button
          type="button"
          className="rounded-full bg-emerald-400/90 px-4 py-2 text-xs font-semibold text-emerald-950 shadow transition hover:bg-emerald-300"
          onClick={() => fileInputRef.current?.click()}
        >
          Browse files
        </button>
      </label>

      {/* Uploaded Files List */}
      {!!uploadedFiles.length && (
        <ul className="max-h-64 space-y-2 overflow-y-auto text-sm text-slate-300 scrollbar-hover-only">
          {uploadedFiles.map((file) => {
            const isDeleting = Boolean(deletingFiles[file.id]);
            return (
              <li
                key={file.id}
                className="flex items-center gap-3 rounded-xl border border-slate-800/80 bg-slate-900/70 px-4 py-2"
              >
                <div className="min-w-0 flex-1">
                  <p className="line-clamp-2 font-medium text-slate-100" title={file.name}>
                    {file.name}
                  </p>
                  <p className="text-xs text-slate-500">
                    {(file.size / 1024).toFixed(1)} KB · {new Date(file.uploadedAt).toLocaleTimeString()}
                  </p>
                </div>
                <div className="flex flex-shrink-0 items-center gap-2">
                  {/* Upload Status Icon */}
                  <span
                    className={`flex h-5 w-5 items-center justify-center ${
                      isDeleting ? 'text-rose-300' : 'text-emerald-400'
                    }`}
                    aria-live="polite"
                  >
                    {isDeleting ? (
                      'Removing…'
                    ) : (
                      <svg
                        className="h-3.5 w-3.5"
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

                  {/* Delete Button */}
                  <button
                    type="button"
                    className="flex h-6 w-6 items-center justify-center rounded-full border border-slate-700 text-slate-400 transition hover:border-rose-400 hover:text-rose-300 disabled:opacity-50"
                    onClick={() => void onDelete(file.id)}
                    disabled={isDeleting}
                    aria-label={`Remove ${file.name}`}
                  >
                    <svg
                      className="h-3.5 w-3.5"
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

      {/* Upload Status Messages */}
      {isUploading && (
        <p className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-xs text-emerald-200">
          Uploading files… they will be available to the assistant in a moment.
        </p>
      )}

      {uploadError && (
        <p className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-xs text-rose-200">
          {uploadError}
        </p>
      )}

      {/* PDF Export Tip / Cover Letter Ready Indicator */}
      {latestCoverLetterId ? (
        <div className="mt-2 rounded-2xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-4 text-xs text-emerald-100">
          Latest cover letter draft ready. Ask for edits or generate a PDF of your cover letter when you&apos;re happy.
        </div>
      ) : (
        <div className="mt-2 rounded-2xl border border-slate-800/70 bg-slate-900/70 px-4 py-4 text-xs text-slate-400">
          Ask the assistant for a cover letter PDF to receive a styled download link right in the conversation.
        </div>
      )}
    </aside>
  );
};
