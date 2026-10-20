// Authentication context for Dyscover frontend
import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { api, type CurrentUser } from '../services/apiClient';
import { safeStorage } from '../utils/storage';

interface AuthContextValue {
  user: CurrentUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string, role?: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshUser = useCallback(async (): Promise<void> => {
    try {
      const currentUser = await api.getCurrentUser();
      setUser(currentUser);
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const login = async (email: string, password: string) => {
    const tokens = await api.login({ email, password });
    safeStorage.setItem('dyscover-access-token', tokens.access_token);
    await refreshUser();
  };

  const register = async (email: string, password: string, displayName: string, role = 'parent') => {
    await api.register({ email, password, display_name: displayName, role });
    await login(email, password);
  };

  const logout = async () => {
    await api.logout();
    safeStorage.removeItem('dyscover-access-token');
    setUser(null);
    // Redirect to login page safely
    if (typeof window !== 'undefined') {
      window.location.href = '/login';
    }
  };

  return (
    <AuthContext.Provider value={{ user, isAuthenticated: !!user, isLoading, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

