// Authentication state for the Dyscover frontend.
//
// The access token is held in memory by the API client. On load the session is
// restored from the HttpOnly refresh cookie, so refreshing the page keeps the
// adult signed in without exposing any token to page scripts' storage.
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import {
  api,
  onSessionExpired,
  refreshSession,
  setAccessToken,
  type CurrentUser,
  type UserRegister,
} from '../services/apiClient';
import { clearAccountScopedStorage } from '../app/activeChild';

interface AuthContextValue {
  user: CurrentUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<CurrentUser>;
  register: (payload: UserRegister) => Promise<CurrentUser>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  /** Clear local state after the server has already ended the session (e.g. account deletion). */
  clearSession: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const clearSession = useCallback(() => {
    setAccessToken(null);
    clearAccountScopedStorage();
    setUser(null);
  }, []);

  const refreshUser = useCallback(async (): Promise<void> => {
    try {
      setUser(await api.getCurrentUser());
    } catch {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    let active = true;
    onSessionExpired(() => {
      if (active) setUser(null);
    });
    refreshSession()
      .then(async restored => {
        if (!restored || !active) return;
        const current = await api.getCurrentUser().catch(() => null);
        if (active) setUser(current);
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
      onSessionExpired(null);
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await api.login({ email, password });
    // A different account may have used this browser before.
    clearAccountScopedStorage();
    setAccessToken(tokens.access_token);
    const current = await api.getCurrentUser();
    setUser(current);
    return current;
  }, []);

  const register = useCallback(
    async (payload: UserRegister) => {
      await api.register(payload);
      return login(payload.email, payload.password);
    },
    [login]
  );

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      clearSession();
    }
  }, [clearSession]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: !!user,
      isLoading,
      login,
      register,
      logout,
      refreshUser,
      clearSession,
    }),
    [user, isLoading, login, register, logout, refreshUser, clearSession]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
