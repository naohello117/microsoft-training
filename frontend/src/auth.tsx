import { createContext, useContext, useEffect, useState, ReactNode } from "react";

// Azure Static Web Apps が /.auth/me で返す形式
interface ClientPrincipal {
  userId: string;
  userDetails: string;
  identityProvider: string;
  userRoles: string[];
}

interface AuthState {
  loading: boolean;
  principal: ClientPrincipal | null;
  isAdmin: boolean;
}

const AuthContext = createContext<AuthState>({
  loading: true,
  principal: null,
  isAdmin: false,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    loading: true,
    principal: null,
    isAdmin: false,
  });

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch("/.auth/me", { credentials: "include" });
        if (!res.ok) throw new Error(String(res.status));
        const data = await res.json();
        const principal: ClientPrincipal | null = data?.clientPrincipal ?? null;
        const isAdmin = !!principal?.userRoles?.includes("admin");
        setState({ loading: false, principal, isAdmin });
      } catch {
        // ローカル開発では /.auth/me が存在しない。環境変数で管理者バイパスを許可。
        const bypass = import.meta.env.VITE_LOCAL_ADMIN_BYPASS === "true";
        setState({
          loading: false,
          principal: bypass
            ? {
                userId: "local-dev",
                userDetails: "local-dev",
                identityProvider: "local",
                userRoles: ["admin"],
              }
            : null,
          isAdmin: bypass,
        });
      }
    })();
  }, []);

  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}

export const AUTH_URLS = {
  login: "/.auth/login/aad?post_login_redirect_uri=/",
  logout: "/.auth/logout?post_logout_redirect_uri=/",
};
