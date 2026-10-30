import { createContext, ReactNode, useCallback, useContext, useState } from "react";
import { api, getToken } from "./lib/api";

interface AuthCtx {
  isAdmin: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const Ctx = createContext<AuthCtx>({
  isAdmin: false,
  login: async () => {},
  logout: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAdmin, setIsAdmin] = useState(() => !!getToken());

  const login = useCallback(async (username: string, password: string) => {
    await api.login(username, password);
    setIsAdmin(true);
  }, []);

  const logout = useCallback(() => {
    api.logout();
    setIsAdmin(false);
  }, []);

  return <Ctx.Provider value={{ isAdmin, login, logout }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  return useContext(Ctx);
}
