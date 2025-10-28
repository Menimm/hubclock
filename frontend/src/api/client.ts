import axios from "axios";

export const api = axios.create({
  baseURL: "/api",
  timeout: 8000
});

export function formatApiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    return error.response?.data?.detail || error.message || "Request failed";
  }
  return "Unexpected error";
}
