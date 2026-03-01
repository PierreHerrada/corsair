import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { login as apiLogin } from "../api/auth";
import { clearToken, getToken, setToken } from "../api/client";

interface AuthContextValue {
  isAuthenticated: boolean;
  token: string | null;
  login: (password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setTokenState] = useState<string | null>(getToken);

  const login = useCallback(async (password: string) => {
    const resp = await apiLogin(password);
    setToken(resp.access_token);
    setTokenState(resp.access_token);
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setTokenState(null);
  }, []);

  const value = useMemo(
    () => ({
      isAuthenticated: token !== null,
      token,
      login,
      logout,
    }),
    [token, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
