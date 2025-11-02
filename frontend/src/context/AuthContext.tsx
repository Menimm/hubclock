import React, { createContext, useContext, useState, useCallback, useEffect } from "react";
import { api, formatApiError } from "../api/client";
import { useSettings } from "./SettingsContext";

type AuthContextValue = {
  isUnlocked: boolean;
  selectedAdminId: number | null;
  setSelectedAdminId: (adminId: number | null) => void;
  unlock: (adminId: number, pin: string) => Promise<{ ok: boolean; message?: string }>;
  lock: () => void;
};

const STORAGE_KEY = "hubclock:selectedAdminId";

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isUnlocked, setIsUnlocked] = useState(false);
  const { pin_set, admins } = useSettings();
  const [selectedAdminId, setSelectedAdminIdState] = useState<number | null>(() => {
    if (typeof window === "undefined") return null;
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored ? Number(stored) : null;
  });

  const setSelectedAdminId = useCallback((adminId: number | null) => {
    setSelectedAdminIdState(adminId);
    if (typeof window !== "undefined") {
      if (adminId === null) {
        window.localStorage.removeItem(STORAGE_KEY);
      } else {
        window.localStorage.setItem(STORAGE_KEY, String(adminId));
      }
    }
  }, []);

  const unlock = useCallback(async (adminId: number, pin: string) => {
    if (!adminId) {
      return { ok: false, message: "יש לבחור מנהל" };
    }
    try {
      await api.post("/auth/verify-pin", { admin_id: adminId, pin });
      setSelectedAdminId(adminId);
      setIsUnlocked(true);
      return { ok: true };
    } catch (error) {
      return { ok: false, message: formatApiError(error) };
    }
  }, [setSelectedAdminId]);

  const lock = useCallback(() => setIsUnlocked(false), []);

  useEffect(() => {
    if (!pin_set || !admins.some((admin) => admin.active)) {
      setIsUnlocked(true);
      return;
    }
    setIsUnlocked(false);
  }, [pin_set, admins]);

  useEffect(() => {
    if (!admins.length) {
      setSelectedAdminId(null);
      return;
    }
    if (selectedAdminId && admins.some((admin) => admin.id === selectedAdminId && admin.active)) {
      return;
    }
    const fallback = admins.find((admin) => admin.active) ?? admins[0];
    setSelectedAdminId(fallback ? fallback.id : null);
  }, [admins, selectedAdminId, setSelectedAdminId]);

  useEffect(() => {
    if (!pin_set) {
      setIsUnlocked(true);
    }
  }, [pin_set]);

  return (
    <AuthContext.Provider value={{ isUnlocked, unlock, lock, selectedAdminId, setSelectedAdminId }}>
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
