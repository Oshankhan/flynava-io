import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, SESSION_EXPIRED_EVENT, TOKEN_KEY, type User } from "./api";

const USER_KEY = "io_user";
export const SESSION_EXPIRED_KEY = "io_session_expired";

interface AuthState {
  user: User | null;
  modules: Record<string, string>;
  login: (email: string, password: string) => Promise<User>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

function readUser(): User | null {
  const raw = localStorage.getItem(USER_KEY);
  return raw ? (JSON.parse(raw) as User) : null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(readUser);
  const [modules, setModules] = useState<Record<string, string>>({});

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.login(email, password);
    localStorage.setItem(TOKEN_KEY, res.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(res.user));
    setUser(res.user);
    return res.user;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setUser(null);
    setModules({});
  }, []);

  useEffect(() => {
    const onExpired = () => {
      localStorage.setItem(SESSION_EXPIRED_KEY, "1");
      logout();
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired);
  }, [logout]);

  // /auth/login doesn't return the modules map — it's fetched separately
  // here (the one canonical /auth/me call site) so it's available
  // app-wide, not just to Layout.tsx's nav-building.
  useEffect(() => {
    if (!user) return;
    api.me().then((r) => setModules(r.modules)).catch(() => setModules({}));
  }, [user]);

  const value = useMemo(
    () => ({ user, modules, login, logout }),
    [user, modules, login, logout]
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
