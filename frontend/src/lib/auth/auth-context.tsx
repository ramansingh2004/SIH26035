"use client";

import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useQueryClient } from "@tanstack/react-query";

import {
  apiRequest,
  refreshAccessToken,
  setAccessToken,
} from "@/lib/api/client";
import { hasPermission as checkPermission } from "@/lib/auth/permissions";
import type { AuthStatus, AuthUser } from "@/lib/auth/types";

type TokenView = {
  access_token: string;
  token_type: string;
  expires_in: number;
};

type LoginInput = {
  email: string;
  password: string;
};

type AuthContextValue = {
  status: AuthStatus;
  user: AuthUser | null;
  selectedLaboratoryId: string | null;
  setSelectedLaboratoryId: (laboratoryId: string) => void;
  hasPermission: (permission: string) => boolean;
  login: (input: LoginInput) => Promise<void>;
  logout: () => Promise<void>;
  logoutAll: () => Promise<void>;
  clearAuthentication: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);
const LAB_STORAGE_KEY = "sih26035.selected-laboratory";

function preferredLaboratory(user: AuthUser): string | null {
  const available = new Set(
    user.laboratories.map((item) => item.laboratory_id),
  );

  if (typeof window !== "undefined") {
    const stored = window.sessionStorage.getItem(LAB_STORAGE_KEY);
    if (stored && available.has(stored)) {
      return stored;
    }
  }

  return user.laboratories[0]?.laboratory_id ?? null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [selectedLaboratoryId, setSelectedLaboratoryIdState] = useState<
    string | null
  >(null);

  const clearAuthentication = useCallback(() => {
    setAccessToken(null);
    setUser(null);
    setSelectedLaboratoryIdState(null);
    setStatus("unauthenticated");
    queryClient.clear();

    if (typeof window !== "undefined") {
      window.sessionStorage.removeItem(LAB_STORAGE_KEY);
    }
  }, [queryClient]);

  const establishUser = useCallback(async () => {
    const response = await apiRequest<AuthUser>("/api/v1/auth/me", {
      retryAuth: false,
    });
    setUser(response.data);
    const laboratoryId = preferredLaboratory(response.data);
    setSelectedLaboratoryIdState(laboratoryId);
    setStatus("authenticated");
  }, []);

  useEffect(() => {
    let active = true;

    async function restoreSession() {
      const token = await refreshAccessToken();
      if (!active) {
        return;
      }

      if (!token) {
        setUser(null);
        setSelectedLaboratoryIdState(null);
        setStatus("unauthenticated");
        return;
      }

      try {
        await establishUser();
      } catch {
        setAccessToken(null);
        if (active) {
          setUser(null);
          setSelectedLaboratoryIdState(null);
          setStatus("unauthenticated");
        }
      }
    }

    void restoreSession();

    return () => {
      active = false;
    };
  }, [establishUser]);

  const login = useCallback(
    async (input: LoginInput) => {
      const response = await apiRequest<TokenView>("/api/v1/auth/login", {
        method: "POST",
        body: input,
        auth: false,
        retryAuth: false,
      });
      setAccessToken(response.data.access_token);
      await establishUser();
    },
    [establishUser],
  );

  const logout = useCallback(async () => {
    try {
      await apiRequest<void>("/api/v1/auth/logout", {
        method: "POST",
        retryAuth: false,
      });
    } finally {
      clearAuthentication();
    }
  }, [clearAuthentication]);

  const logoutAll = useCallback(async () => {
    await apiRequest<void>("/api/v1/auth/logout-all", {
      method: "POST",
    });
    clearAuthentication();
  }, [clearAuthentication]);

  const setSelectedLaboratoryId = useCallback(
    (laboratoryId: string) => {
      if (
        !user?.laboratories.some((item) => item.laboratory_id === laboratoryId)
      ) {
        return;
      }

      setSelectedLaboratoryIdState(laboratoryId);
      queryClient.clear();
      if (typeof window !== "undefined") {
        window.sessionStorage.setItem(LAB_STORAGE_KEY, laboratoryId);
      }
    },
    [queryClient, user],
  );

  const hasPermission = useCallback(
    (permission: string) =>
      checkPermission(user, permission, selectedLaboratoryId),
    [selectedLaboratoryId, user],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      selectedLaboratoryId,
      setSelectedLaboratoryId,
      hasPermission,
      login,
      logout,
      logoutAll,
      clearAuthentication,
    }),
    [
      clearAuthentication,
      hasPermission,
      login,
      logout,
      logoutAll,
      selectedLaboratoryId,
      setSelectedLaboratoryId,
      status,
      user,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
