/**
 * Application-wide constants
 */

// Storage keys for localStorage
export const TOKEN_STORAGE_KEY = 'chatAW:sessionToken';
export const PROFILE_STORAGE_KEY = 'chatAW:profileId';
export const THREAD_STORAGE_KEY = 'chatAW:threadId';
export const THREADS_INDEX_KEY = 'chatAW:threads';

// API configuration
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:5050';

// Default messages
export const GREETING_MESSAGE =
  'Hi! Share the job description and I will craft a tailored cover letter using any files you upload.';
