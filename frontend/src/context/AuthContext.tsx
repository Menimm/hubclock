import React, { createContext, useContext, useState, useCallback, useEffect } from "react";
import { api, formatApiError } from "../api/client";
import { useSettings } from "./SettingsContext";

type AuthContextValue = {
  isUnlocked: boolean;
  unlock: (pin: string) => Promise<{ ok: boolean; message?: string }>;
  lock: () => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isUnlocked, setIsUnlocked] = useState(false);
  const { pin_set } = useSettings();

  const unlock = useCallback(async (pin: string) => {
    try {
      await api.post("/auth/verify-pin", { pin });
      setIsUnlocked(true);
      return { ok: true };
    } catch (error) {
      return { ok: false, message: formatApiError(error) };
    }
  }, []);

  const lock = useCallback(() => setIsUnlocked(false), []);

  useEffect(() => {
    if (!pin_set) {
      setIsUnlocked(true);
    } else {
      setIsUnlocked(false);
    }
  }, [pin_set]);

  return <AuthContext.Provider value={{ isUnlocked, unlock, lock }}>{children}</AuthContext.Provider>;
};

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
