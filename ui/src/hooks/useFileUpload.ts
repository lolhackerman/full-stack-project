/**
 * useFileUpload Hook
 * Manages file uploads, deletion, and loading of uploaded files
 */

import { useEffect, useState } from 'react';
import { UploadedFileSummary } from '../types/file.types';

type UseFileUploadProps = {
  sessionToken: string | null;
  apiBaseUrl: string;
  onAuthError: () => void;
};

type UseFileUploadReturn = {
  uploadedFiles: UploadedFileSummary[];
  uploadError: string | null;
  isUploading: boolean;
  deletingFiles: Record<string, boolean>;
  uploadFiles: (files: FileList | File[]) => Promise<void>;
  handleDeleteFile: (fileId: string) => Promise<void>;
};

/**
 * Custom hook for managing file upload operations
 * Handles uploading, deleting, and loading files from the server
 */
export const useFileUpload = ({ sessionToken, apiBaseUrl, onAuthError }: UseFileUploadProps): UseFileUploadReturn => {
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFileSummary[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [deletingFiles, setDeletingFiles] = useState<Record<string, boolean>>({});

  // Load uploaded files when authenticated
  useEffect(() => {
    if (!sessionToken) return;

    const loadUploadedFiles = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/api/uploads`, {
          method: 'GET',
          headers: { Authorization: `Bearer ${sessionToken}` },
        });

        if (!response.ok) {
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

    void loadUploadedFiles();
  }, [sessionToken, apiBaseUrl]);

  /**
   * Uploads files to the server
   */
  const uploadFiles = async (files: FileList | File[]) => {
    if (!sessionToken) {
      onAuthError();
      return;
    }

    const fileArray = Array.isArray(files) ? files : Array.from(files);
    if (!fileArray.length) return;

    const formData = new FormData();
    fileArray.forEach((file) => formData.append('files', file));

    setIsUploading(true);
    setUploadError(null);

    try {
      const response = await fetch(`${apiBaseUrl}/api/uploads`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${sessionToken}` },
        body: formData,
      });

      if (!response.ok) {
        if (response.status === 401) {
          onAuthError();
        }
        const problem = await response.json().catch(() => ({}));
        throw new Error(problem.error ?? 'Upload failed');
      }

      const payload: { files: UploadedFileSummary[] } = await response.json();
      setUploadedFiles((prev) => {
        const merged = new Map(prev.map((file) => [file.id, file]));
        payload.files.forEach((file) => merged.set(file.id, file));
        return Array.from(merged.values()).sort((a, b) => b.uploadedAt - a.uploadedAt);
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown upload error';
      setUploadError(message);
    } finally {
      setIsUploading(false);
    }
  };

  /**
   * Deletes a file from the server
   */
  const handleDeleteFile = async (fileId: string) => {
    if (!sessionToken) {
      onAuthError();
      return;
    }

    setDeletingFiles((prev) => ({ ...prev, [fileId]: true }));
    setUploadError(null);

    try {
      const response = await fetch(`${apiBaseUrl}/api/uploads/${fileId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${sessionToken}` },
      });

      if (!response.ok) {
        if (response.status === 401) {
          onAuthError();
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

  return {
    uploadedFiles,
    uploadError,
    isUploading,
    deletingFiles,
    uploadFiles,
    handleDeleteFile,
  };
};
