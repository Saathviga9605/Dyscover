import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { useAuth } from '../auth/AuthContext';
import { api, type ChildProfile } from '../services/apiClient';
import { getActiveChildId, onActiveChildChange, setActiveChildId } from './activeChild';

interface ChildContextValue {
  children: ChildProfile[];
  activeChild: ChildProfile | null;
  loading: boolean;
  /** True once the list has loaded at least once (avoids flashing a spinner on refresh). */
  loaded: boolean;
  error: string | null;
  selectChild: (childId: string | null) => void;
  reload: () => Promise<void>;
}

const ChildContext = createContext<ChildContextValue | null>(null);

/** Child profiles of the signed-in parent, and which one is currently selected. */
export function ChildProvider({ children: content }: { children: ReactNode }) {
  const { user } = useAuth();
  const [profiles, setProfiles] = useState<ChildProfile[]>([]);
  const [activeId, setActiveId] = useState<string | null>(getActiveChildId);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!user || user.role !== 'parent') {
      setProfiles([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const list = await api.listChildren();
      setProfiles(list);
      setLoaded(true);
      const stored = getActiveChildId();
      // Discard a remembered id that is not one of this account's children.
      if (stored && !list.some(child => child.id === stored))
        setActiveChildId(list.length === 1 ? list[0].id : null);
      else if (!stored && list.length === 1) setActiveChildId(list[0].id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'error');
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    // A different account may now be signed in: never show the previous list.
    setProfiles([]);
    setLoaded(false);
    void reload();
  }, [reload]);

  useEffect(() => onActiveChildChange(() => setActiveId(getActiveChildId())), []);

  const selectChild = useCallback((childId: string | null) => setActiveChildId(childId), []);

  const value = useMemo<ChildContextValue>(
    () => ({
      children: profiles,
      activeChild: profiles.find(child => child.id === activeId) ?? null,
      loading,
      loaded,
      error,
      selectChild,
      reload,
    }),
    [profiles, activeId, loading, loaded, error, selectChild, reload]
  );
  return <ChildContext.Provider value={value}>{content}</ChildContext.Provider>;
}

export function useChildren(): ChildContextValue {
  const context = useContext(ChildContext);
  if (!context) throw new Error('useChildren must be used within a ChildProvider');
  return context;
}
