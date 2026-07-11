import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, TOKEN_KEY, type User } from "./api";

const USER_KEY = "io_user";

interface AuthState {
  user: User | null;
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
  }, []);

  const value = useMemo(() => ({ user, login, logout }), [user, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
