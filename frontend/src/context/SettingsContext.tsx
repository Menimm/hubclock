import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "../api/client";

interface Settings {
  currency: string;
  pin_set: boolean;
  db_host: string;
  db_port: number | null;
  db_user: string;
  db_password: string;
  brand_name: string;
  theme_color: string;
}

interface SettingsContextValue extends Settings {
  refresh: () => Promise<void>;
  setLocal: (settings: Partial<Settings>) => void;
}

const SettingsContext = createContext<SettingsContextValue | undefined>(undefined);

export const SettingsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [settings, setSettings] = useState<Settings>({
    currency: "ILS",
    pin_set: false,
    db_host: "127.0.0.1",
    db_port: 3306,
    db_user: "hubclock",
    db_password: "hubclock",
    brand_name: "דלי",
    theme_color: "#1b3aa6"
  });

  const load = useCallback(async () => {
    const response = await api.get<Settings>("/settings");
    setSettings((prev) => ({
      ...prev,
      ...response.data,
      brand_name: response.data.brand_name ?? "דלי",
      theme_color: response.data.theme_color ?? "#1b3aa6"
    }));
  }, []);

  useEffect(() => {
    load().catch((error) => console.error("Failed to load settings", error));
  }, [load]);

  useEffect(() => {
    document.documentElement.style.setProperty("--accent-color", settings.theme_color);
  }, [settings.theme_color]);

  useEffect(() => {
    const trimmed = settings.brand_name?.trim();
    document.title = trimmed && trimmed.length > 0 ? trimmed : "HubClock";
  }, [settings.brand_name]);

  const setLocal = (partial: Partial<Settings>) => {
    setSettings((prev) => ({ ...prev, ...partial }));
  };

  return <SettingsContext.Provider value={{ ...settings, refresh: load, setLocal }}>{children}</SettingsContext.Provider>;
};

export function useSettings(): SettingsContextValue {
  const ctx = useContext(SettingsContext);
  if (!ctx) {
    throw new Error("useSettings must be used within SettingsProvider");
  }
  return ctx;
}
