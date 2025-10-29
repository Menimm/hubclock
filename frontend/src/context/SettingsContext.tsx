import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "../api/client";

type DatabaseKey = "primary" | "secondary";

interface SettingsResponse {
  currency: string;
  pin_set: boolean;
  db_host: string | null;
  db_port: number | null;
  db_user: string | null;
  db_password: string | null;
  secondary_db_host: string | null;
  secondary_db_port: number | null;
  secondary_db_user: string | null;
  secondary_db_password: string | null;
  primary_db_active: boolean | null;
  secondary_db_active: boolean | null;
  primary_database: DatabaseKey | null;
  brand_name: string | null;
  theme_color: string | null;
}

interface Settings {
  currency: string;
  pin_set: boolean;
  db_host: string;
  db_port: number | null;
  db_user: string;
  db_password: string;
  secondary_db_host: string;
  secondary_db_port: number | null;
  secondary_db_user: string;
  secondary_db_password: string;
  primary_db_active: boolean;
  secondary_db_active: boolean;
  primary_database: DatabaseKey;
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
    secondary_db_host: "",
    secondary_db_port: null,
    secondary_db_user: "",
    secondary_db_password: "",
    primary_db_active: true,
    secondary_db_active: false,
    primary_database: "primary",
    brand_name: "דלי",
    theme_color: "#1b3aa6"
  });

  const load = useCallback(async () => {
    const response = await api.get<SettingsResponse>("/settings");
    setSettings((prev) => ({
      ...prev,
      currency: response.data.currency ?? prev.currency,
      pin_set: response.data.pin_set,
      db_host: response.data.db_host ?? "",
      db_port: response.data.db_port ?? null,
      db_user: response.data.db_user ?? "",
      db_password: response.data.db_password ?? "",
      secondary_db_host: response.data.secondary_db_host ?? "",
      secondary_db_port: response.data.secondary_db_port ?? null,
      secondary_db_user: response.data.secondary_db_user ?? "",
      secondary_db_password: response.data.secondary_db_password ?? "",
      primary_db_active: response.data.primary_db_active ?? true,
      secondary_db_active: response.data.secondary_db_active ?? false,
      primary_database: (response.data.primary_database as DatabaseKey) ?? "primary",
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
