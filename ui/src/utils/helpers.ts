/**
 * Utility helper functions
 */

/**
 * Generates a unique ID for messages and other entities
 */
export const createId = () => `${Date.now().toString(36)}-${Math.random().toString(16).slice(2, 10)}`;

/**
 * Generates a unique thread ID
 */
export const createThreadId = () => `thread_${Date.now().toString(36)}${Math.random().toString(16).slice(2, 8)}`;

/**
 * Safely reads a value from localStorage
 * @param key - The storage key to read
 * @returns The stored value or null if not available
 */
export const readFromStorage = (key: string): string | null => {
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

/**
 * Safely writes a value to localStorage
 * @param key - The storage key
 * @param value - The value to store
 */
export const writeToStorage = (key: string, value: string): void => {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    window.localStorage.setItem(key, value);
  } catch (err) {
    console.warn('Unable to write to localStorage', err);
  }
};

/**
 * Safely removes a value from localStorage
 * @param key - The storage key to remove
 */
export const removeFromStorage = (key: string): void => {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    window.localStorage.removeItem(key);
  } catch (err) {
    console.warn('Unable to remove from localStorage', err);
  }
};
