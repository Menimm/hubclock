import React, { useState } from "react";
import { useAuth } from "../context/AuthContext";

interface PinPromptProps {
  onSuccess?: () => void;
}

export const PinPrompt: React.FC<PinPromptProps> = ({ onSuccess }) => {
  const { unlock } = useAuth();
  const [pin, setPin] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [isSubmitting, setSubmitting] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    const result = await unlock(pin.trim());
    if (result.ok) {
      setStatus(null);
      setPin("");
      onSuccess?.();
    } else {
      setStatus(result.message ?? "קוד ה-PIN שגוי");
    }
    setSubmitting(false);
  };

  return (
    <div className="card" style={{ maxWidth: 360, margin: "2rem auto" }}>
      <h2>כניסת מנהל</h2>
      <form onSubmit={submit}>
        <label htmlFor="pin">קוד PIN</label>
        <input
          id="pin"
          autoFocus
          type="password"
          minLength={4}
          maxLength={12}
          value={pin}
          onChange={(event) => setPin(event.target.value)}
          placeholder="הזינו את קוד ה-PIN"
          required
        />
        <button className="primary" type="submit" disabled={isSubmitting} style={{ marginTop: "1rem", width: "100%" }}>
          {isSubmitting ? "בודק..." : "כניסה"}
        </button>
        {status && (
          <div className="status error" role="alert">
            {status}
          </div>
        )}
      </form>
    </div>
  );
};
