import React, { useMemo, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useSettings } from "../context/SettingsContext";

interface PinPromptProps {
  onSuccess?: () => void;
}

export const PinPrompt: React.FC<PinPromptProps> = ({ onSuccess }) => {
  const { unlock, selectedAdminId, setSelectedAdminId } = useAuth();
  const { admins } = useSettings();
  const [pin, setPin] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [isSubmitting, setSubmitting] = useState(false);

  const activeAdmins = useMemo(() => admins.filter((admin) => admin.active), [admins]);
  const effectiveAdmins = activeAdmins.length > 0 ? activeAdmins : admins;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selectedAdminId) {
      setStatus("יש לבחור מנהל");
      return;
    }
    if (!pin.trim()) {
      setStatus("יש להזין קוד PIN");
      return;
    }
    setSubmitting(true);
    const result = await unlock(selectedAdminId, pin.trim());
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
        {effectiveAdmins.length === 0 ? (
          <div className="status error" role="alert">
            אין משתמשי מנהל פעילים. צרו מנהל חדש במסך ההגדרות.
          </div>
        ) : (
          <>
            <label htmlFor="adminSelect">בחרו מנהל</label>
            <select
              id="adminSelect"
              value={selectedAdminId ?? ""}
              onChange={(event) => {
                const value = event.target.value;
                setSelectedAdminId(value ? Number(value) : null);
              }}
            >
              <option value="" disabled>
                בחרו מנהל
              </option>
              {effectiveAdmins.map((admin) => (
                <option key={admin.id} value={admin.id}>
                  {admin.name}
                  {!admin.active ? " (מושבת)" : ""}
                </option>
              ))}
            </select>
          </>
        )}
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
        <button
          className="primary"
          type="submit"
          disabled={isSubmitting || effectiveAdmins.length === 0}
          style={{ marginTop: "1rem", width: "100%" }}
        >
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
