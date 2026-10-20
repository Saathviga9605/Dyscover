// Safe wrapper around window.localStorage: storage can be unavailable (private
// mode, disabled cookies, quota exceeded) and must never crash the app.
export const safeStorage = {
  getItem(key: string): string | null {
    try {
      return typeof window !== 'undefined' ? window.localStorage.getItem(key) : null;
    } catch {
      return null;
    }
  },
  setItem(key: string, value: string): void {
    try {
      if (typeof window !== 'undefined') window.localStorage.setItem(key, value);
    } catch {
      // Unavailable storage only loses a per-device convenience.
    }
  },
  removeItem(key: string): void {
    try {
      if (typeof window !== 'undefined') window.localStorage.removeItem(key);
    } catch {
      // As above.
    }
  },
};
