/**
 * useAuth Hook
 * Manages authentication state and session validation
 */

import { useEffect, useState } from 'react';
import { readFromStorage, writeToStorage, removeFromStorage } from '../utils/helpers';
import { TOKEN_STORAGE_KEY, PROFILE_STORAGE_KEY } from '../utils/constants';

type UseAuthReturn = {
  sessionToken: string | null;
  profileId: string | null;
  isAuthModalOpen: boolean;
  authError: string | null;
  setSessionToken: (token: string | null) => void;
  setProfileId: (id: string | null) => void;
  setIsAuthModalOpen: (isOpen: boolean) => void;
  setAuthError: (error: string | null) => void;
};

/**
 * Custom hook for managing authentication state
 * Handles session token persistence and validation
 */
export const useAuth = (apiBaseUrl: string): UseAuthReturn => {
  const [sessionToken, setSessionToken] = useState<string | null>(() => readFromStorage(TOKEN_STORAGE_KEY));
  const [profileId, setProfileId] = useState<string | null>(() => readFromStorage(PROFILE_STORAGE_KEY));
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(() => !readFromStorage(TOKEN_STORAGE_KEY));
  const [authError, setAuthError] = useState<string | null>(null);

  // Persist session token to localStorage
  useEffect(() => {
    if (sessionToken) {
      writeToStorage(TOKEN_STORAGE_KEY, sessionToken);
    } else {
      removeFromStorage(TOKEN_STORAGE_KEY);
    }
  }, [sessionToken]);

  // Persist profile ID to localStorage
  useEffect(() => {
    if (profileId) {
      writeToStorage(PROFILE_STORAGE_KEY, profileId);
    } else {
      removeFromStorage(PROFILE_STORAGE_KEY);
    }
  }, [profileId]);

  // Show auth modal when no token exists
  useEffect(() => {
    if (!sessionToken) {
      setIsAuthModalOpen(true);
    }
  }, [sessionToken]);

  // Validate session on mount and when token changes
  useEffect(() => {
    if (!sessionToken) return;

    const controller = new AbortController();

    const validateSession = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/api/auth/session`, {
          method: 'GET',
          headers: { Authorization: `Bearer ${sessionToken}` },
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error('Session invalid');
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        
        setSessionToken(null);
        setProfileId(null);
        setIsAuthModalOpen(true);
        setAuthError('Session expired. Please enter a new access code.');
      }
    };

    void validateSession();

    return () => controller.abort();
  }, [sessionToken, apiBaseUrl]);

  return {
    sessionToken,
    profileId,
    isAuthModalOpen,
    authError,
    setSessionToken,
    setProfileId,
    setIsAuthModalOpen,
    setAuthError,
  };
};
