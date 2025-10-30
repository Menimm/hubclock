const STORAGE_KEY = "hubclock_device_id";

const generateId = (): string => {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
};

export const getDeviceId = (): string => {
  if (typeof window === "undefined" || typeof localStorage === "undefined") {
    return "unknown-device";
  }

  let existing = localStorage.getItem(STORAGE_KEY);
  if (!existing) {
    existing = generateId();
    try {
      localStorage.setItem(STORAGE_KEY, existing);
    } catch (error) {
      // Ignore storage errors (private mode, etc.)
    }
  }
  return existing;
};
