import axios from "axios";

declare global {
  interface Window {
    __HUBCLOCK_API_BASE__?: string;
  }
}

const resolveBaseUrl = (): string => {
  const envBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim();
  let base = envBase && envBase.length > 0 ? envBase : "/api";

  if (typeof window !== "undefined") {
    const override = window.__HUBCLOCK_API_BASE__;
    if (override && override.trim().length > 0) {
      base = override.trim();
    }
  }

  return base;
};

export const api = axios.create({
  baseURL: resolveBaseUrl(),
  timeout: 8000
});

export function formatApiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    return error.response?.data?.detail || error.message || "Request failed";
  }
  return "Unexpected error";
}
