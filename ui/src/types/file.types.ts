/**
 * File upload related type definitions
 */

export type UploadedFileSummary = {
  id: string;
  name: string;
  size: number;
  mimeType: string;
  uploadedAt: number;
  hasText?: boolean;
};
