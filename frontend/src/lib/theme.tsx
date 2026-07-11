import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

const KEY = "io_theme";

interface ThemeState {
  dark: boolean;
  toggle: () => void;
}

const ThemeContext = createContext<ThemeState | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [dark, setDark] = useState(() => localStorage.getItem(KEY) === "dark");

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem(KEY, dark ? "dark" : "light");
  }, [dark]);

  const toggle = useCallback(() => setDark((d) => !d), []);
  const value = useMemo(() => ({ dark, toggle }), [dark, toggle]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeState {
  const ctx = useContext(ThemeContext);
  return ctx ?? { dark: false, toggle: () => {} };
}
