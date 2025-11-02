import React, { useEffect, useMemo, useState } from "react";
import { api, formatApiError } from "../api/client";
import { useSettings } from "../context/SettingsContext";
import type { AdminSummary } from "../context/SettingsContext";
import { useAuth } from "../context/AuthContext";

type StatusMessage = { kind: "success" | "error"; message: string } | null;
type SchemaTarget = "active" | "primary" | "secondary" | "both";

const currencyOptions = [
  { value: "ILS", label: "שקל חדש (ILS)" },
  { value: "USD", label: "דולר אמריקאי (USD)" },
  { value: "EUR", label: "אירו (EUR)" },
  { value: "GBP", label: "ליש\"ט (GBP)" }
];

const SettingsPage: React.FC = () => {
  const {
    currency,
    pin_set,
    admins,
    db_host,
    db_port,
    db_user,
    db_password,
    secondary_db_host,
    secondary_db_port,
    secondary_db_user,
    secondary_db_password,
    primary_db_active,
    secondary_db_active,
    primary_database,
    schema_ok,
    schema_version,
    brand_name,
    theme_color: themeColorSetting,
    show_clock_device_ids,
    refresh,
    setLocal
  } = useSettings();
  const { selectedAdminId, setSelectedAdminId } = useAuth();

  const [currencyValue, setCurrencyValue] = useState(currency);
  const [primaryHost, setPrimaryHost] = useState(db_host ?? "");
  const [primaryPort, setPrimaryPort] = useState(db_port ? String(db_port) : "");
  const [primaryUser, setPrimaryUser] = useState(db_user ?? "");
  const [primaryPassword, setPrimaryPassword] = useState(db_password ?? "");
  const [primaryActive, setPrimaryActive] = useState<boolean>(primary_db_active ?? true);
  const [secondaryHost, setSecondaryHost] = useState(secondary_db_host ?? "");
  const [secondaryPort, setSecondaryPort] = useState(secondary_db_port ? String(secondary_db_port) : "");
  const [secondaryUser, setSecondaryUser] = useState(secondary_db_user ?? "");
  const [secondaryPassword, setSecondaryPassword] = useState(secondary_db_password ?? "");
  const [secondaryActive, setSecondaryActive] = useState<boolean>(secondary_db_active ?? false);
  const [primaryChoice, setPrimaryChoice] = useState<"primary" | "secondary">(primary_database ?? "primary");
  const [brandName, setBrandName] = useState(brand_name ?? "העסק שלי");
  const [themeColor, setThemeColor] = useState(themeColorSetting ?? "#1b3aa6");
  const [showClockDevices, setShowClockDevices] = useState<boolean>(show_clock_device_ids ?? true);
  const activeAdmins = useMemo(() => admins.filter((admin) => admin.active), [admins]);
  const effectiveAdmins = useMemo(() => (activeAdmins.length > 0 ? activeAdmins : admins), [activeAdmins, admins]);
  const [actingAdminId, setActingAdminId] = useState<number | "">(() => {
    if (selectedAdminId && effectiveAdmins.some((admin) => admin.id === selectedAdminId)) {
      return selectedAdminId;
    }
    const fallback = effectiveAdmins[0]?.id;
    return fallback ?? "";
  });
  const [adminPinEntry, setAdminPinEntry] = useState("");
  const [generalStatus, setGeneralStatus] = useState<StatusMessage>(null);
  const [dbStatus, setDbStatus] = useState<StatusMessage>(null);
  const [adminStatus, setAdminStatus] = useState<StatusMessage>(null);
  const [importStatus, setImportStatus] = useState<StatusMessage>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [isSavingAdmin, setIsSavingAdmin] = useState(false);
  const [adminEdits, setAdminEdits] = useState<Record<number, { name?: string; active?: boolean; newPin?: string }>>({});
  const [newAdminName, setNewAdminName] = useState("");
  const [newAdminPin, setNewAdminPin] = useState("");
  const [newAdminPinConfirm, setNewAdminPinConfirm] = useState("");
  const [showPrimaryPassword, setShowPrimaryPassword] = useState(false);
  const [showSecondaryPassword, setShowSecondaryPassword] = useState(false);
  const [schemaTarget, setSchemaTarget] = useState<SchemaTarget>("active");

  useEffect(() => {
    setAdminEdits((prev) => {
      const next: Record<number, { name?: string; active?: boolean; newPin?: string }> = {};
      admins.forEach((admin) => {
        if (prev[admin.id]) {
          next[admin.id] = prev[admin.id];
        }
      });
      return next;
    });
  }, [admins]);
  useEffect(() => {
    setCurrencyValue(currency);
  }, [currency]);

  useEffect(() => {
    setPrimaryHost(db_host ?? "");
    setPrimaryPort(db_port ? String(db_port) : "");
    setPrimaryUser(db_user ?? "");
    setPrimaryPassword(db_password ?? "");
    setPrimaryActive(primary_db_active ?? true);
    setSecondaryHost(secondary_db_host ?? "");
    setSecondaryPort(secondary_db_port ? String(secondary_db_port) : "");
    setSecondaryUser(secondary_db_user ?? "");
    setSecondaryPassword(secondary_db_password ?? "");
    setSecondaryActive(secondary_db_active ?? false);
    setPrimaryChoice(primary_database ?? "primary");
    setBrandName(brand_name ?? "העסק שלי");
    setThemeColor(themeColorSetting ?? "#1b3aa6");
    setShowClockDevices(show_clock_device_ids ?? true);
  }, [
    db_host,
    db_port,
    db_user,
    db_password,
    secondary_db_host,
    secondary_db_port,
    secondary_db_user,
    secondary_db_password,
    primary_db_active,
    secondary_db_active,
    primary_database,
    brand_name,
    themeColorSetting,
    show_clock_device_ids
  ]);

  useEffect(() => {
    if (!effectiveAdmins.length) {
      setActingAdminId("");
      return;
    }
    if (selectedAdminId && effectiveAdmins.some((admin) => admin.id === selectedAdminId)) {
      setActingAdminId(selectedAdminId);
      return;
    }
    setActingAdminId((prev) => {
      if (typeof prev === "number" && effectiveAdmins.some((admin) => admin.id === prev)) {
        return prev;
      }
      return effectiveAdmins[0].id;
    });
  }, [effectiveAdmins, selectedAdminId]);

  useEffect(() => {
    if (typeof actingAdminId === "number") {
      setSelectedAdminId(actingAdminId);
    }
  }, [actingAdminId, setSelectedAdminId]);

  const updateAdminEdit = (id: number, updates: Partial<{ name: string; active: boolean; newPin: string }>) => {
    setAdminEdits((prev) => ({ ...prev, [id]: { ...prev[id], ...updates } }));
  };

  const clearAdminEdit = (id: number) => {
    setAdminEdits((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  };

  const resolveCredentials = (
    setStatus: React.Dispatch<React.SetStateAction<StatusMessage>>
  ): { adminId: number; pin: string } | null => {
    if (!effectiveAdmins.length) {
      setStatus({ kind: "error", message: "אין מנהלי מערכת פעילים. צרו או הפעילו מנהל לפני ביצוע פעולה זו." });
      return null;
    }
    if (actingAdminId === "" || actingAdminId === null) {
      setStatus({ kind: "error", message: "בחרו מנהל מבצע מהרשימה." });
      return null;
    }
    if (!adminPinEntry.trim()) {
      setStatus({ kind: "error", message: "הזינו את קוד ה-PIN של המנהל המבצע." });
      return null;
    }
    return { adminId: Number(actingAdminId), pin: adminPinEntry.trim() };
  };

  const handleAdminSave = async (admin: AdminSummary) => {
    setAdminStatus(null);
    const credentials = resolveCredentials(setAdminStatus);
    if (!credentials) {
      return;
    }
    const edits = adminEdits[admin.id] ?? {};
    const nameCandidate = edits.name !== undefined ? edits.name.trim() : undefined;
    if (nameCandidate !== undefined && nameCandidate.length === 0) {
      setAdminStatus({ kind: "error", message: "שם המנהל לא יכול להיות ריק" });
      return;
    }
    if (edits.newPin && (edits.newPin.trim().length < 4 || edits.newPin.trim().length > 12)) {
      setAdminStatus({ kind: "error", message: "PIN חדש חייב להיות באורך שבין 4 ל-12 תווים" });
      return;
    }
    const payload: Record<string, unknown> = {
      requestor_admin_id: credentials.adminId,
      requestor_pin: credentials.pin
    };
    let hasChanges = false;
    if (nameCandidate !== undefined && nameCandidate !== admin.name) {
      payload.name = nameCandidate;
      hasChanges = true;
    }
    if (edits.active !== undefined && edits.active !== admin.active) {
      payload.active = edits.active;
      hasChanges = true;
    }
    if (edits.newPin && edits.newPin.trim().length > 0) {
      payload.new_pin = edits.newPin.trim();
      hasChanges = true;
    }
    if (!hasChanges) {
      setAdminStatus({ kind: "error", message: `לא בוצעו שינויים עבור \"${admin.name}\"` });
      return;
    }
    setIsSavingAdmin(true);
    try {
      await api.put(`/admins/${admin.id}`, payload);
      const updatedName = (payload.name as string | undefined) ?? admin.name;
      setAdminStatus({ kind: "success", message: `פרטי המנהל \"${updatedName}\" עודכנו` });
      clearAdminEdit(admin.id);
      setAdminPinEntry("");
      await refresh();
    } catch (error) {
      setAdminStatus({ kind: "error", message: formatApiError(error) });
    } finally {
      setIsSavingAdmin(false);
    }
  };

  const handleCreateAdmin = async (event: React.FormEvent) => {
    event.preventDefault();
    setAdminStatus(null);
    const trimmedName = newAdminName.trim();
    const trimmedPin = newAdminPin.trim();
    if (!trimmedName) {
      setAdminStatus({ kind: "error", message: "שם המנהל נדרש" });
      return;
    }
    if (trimmedPin.length < 4 || trimmedPin.length > 12) {
      setAdminStatus({ kind: "error", message: "קוד ה-PIN חייב להכיל בין 4 ל-12 תווים" });
      return;
    }
    if (trimmedPin !== newAdminPinConfirm.trim()) {
      setAdminStatus({ kind: "error", message: "אימות ה-PIN אינו תואם" });
      return;
    }
    const credentials = resolveCredentials(setAdminStatus);
    if (!credentials) {
      return;
    }
    setIsSavingAdmin(true);
    try {
      await api.post("/admins", {
        requestor_admin_id: credentials.adminId,
        requestor_pin: credentials.pin,
        name: trimmedName,
        pin: trimmedPin
      });
      setAdminStatus({ kind: "success", message: `המנהל \"${trimmedName}\" נוצר בהצלחה` });
      setNewAdminName("");
      setNewAdminPin("");
      setNewAdminPinConfirm("");
      setAdminPinEntry("");
      await refresh();
    } catch (error) {
      setAdminStatus({ kind: "error", message: formatApiError(error) });
    } finally {
      setIsSavingAdmin(false);
    }
  };

  const updateAppearance = async (event: React.FormEvent) => {
    event.preventDefault();
    setGeneralStatus(null);
    const credentials = resolveCredentials(setGeneralStatus);
    if (!credentials) {
      return;
    }
    try {
      const response = await api.put("/settings", {
        admin_id: credentials.adminId,
        current_pin: credentials.pin,
        currency: currencyValue,
        theme_color: themeColor,
        brand_name: brandName,
        show_clock_device_ids: showClockDevices
      });
      setGeneralStatus({ kind: "success", message: "ההגדרות נשמרו" });
      const nextAdmins = response.data.admins ?? admins;
      setLocal({
        currency: response.data.currency ?? currencyValue,
        theme_color: response.data.theme_color ?? themeColor,
        brand_name: response.data.brand_name ?? brandName,
        show_clock_device_ids: response.data.show_clock_device_ids ?? showClockDevices,
        admins: nextAdmins,
        pin_set: response.data.pin_set ?? nextAdmins.some((admin) => admin.active)
      });
      setAdminPinEntry("");
    } catch (error) {
      setGeneralStatus({ kind: "error", message: formatApiError(error) });
    }
  };

  const handlePrimaryActiveChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const next = event.target.checked;
    if (!next && !secondaryActive) {
      setDbStatus({ kind: "error", message: "לפחות מסד נתונים אחד חייב להיות פעיל" });
      return;
    }
    setPrimaryActive(next);
    if (!next && primaryChoice === "primary") {
      setPrimaryChoice("secondary");
    }
  };

  const handleSecondaryActiveChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const next = event.target.checked;
    if (!next && !primaryActive) {
      setDbStatus({ kind: "error", message: "לפחות מסד נתונים אחד חייב להיות פעיל" });
      return;
    }
    setSecondaryActive(next);
    if (!next && primaryChoice === "secondary") {
      setPrimaryChoice("primary");
    }
  };

  const updateDatabase = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      setDbStatus(null);
      if (primaryChoice === "primary" && !primaryActive) {
        setDbStatus({ kind: "error", message: "בחרתם במסד הנתונים הראשי כלא פעיל" });
        return;
      }
      if (primaryChoice === "secondary" && !secondaryActive) {
        setDbStatus({ kind: "error", message: "לא ניתן לקבוע את המסד המשני כראשי כשהוא אינו פעיל" });
        return;
      }
      const payload = {
        db_host: primaryHost,
        db_port: primaryPort ? Number(primaryPort) : null,
        db_user: primaryUser,
        db_password: primaryPassword ?? "",
        primary_db_active: primaryActive,
        primary_database: primaryChoice,
        secondary_db_host: secondaryHost,
        secondary_db_port: secondaryPort ? Number(secondaryPort) : null,
        secondary_db_user: secondaryUser,
        secondary_db_password: secondaryPassword ?? "",
        secondary_db_active: secondaryActive
      };
      const credentials = resolveCredentials(setDbStatus);
      if (!credentials) {
        return;
      }
      const response = await api.put("/settings", {
        admin_id: credentials.adminId,
        current_pin: credentials.pin,
        ...payload
      });
      setDbStatus({ kind: "success", message: "הגדרות מסדי הנתונים נשמרו" });
      const nextAdmins = response.data.admins ?? admins;
      setLocal({
        db_host: response.data.db_host ?? payload.db_host ?? "",
        db_port: response.data.db_port ?? payload.db_port,
        db_user: response.data.db_user ?? payload.db_user ?? "",
        db_password: response.data.db_password ?? (payload.db_password as string),
        secondary_db_host: response.data.secondary_db_host ?? payload.secondary_db_host ?? "",
        secondary_db_port: response.data.secondary_db_port ?? payload.secondary_db_port,
        secondary_db_user: response.data.secondary_db_user ?? payload.secondary_db_user ?? "",
        secondary_db_password:
          response.data.secondary_db_password ?? (payload.secondary_db_password as string),
        primary_db_active: response.data.primary_db_active ?? primaryActive,
        secondary_db_active: response.data.secondary_db_active ?? secondaryActive,
        primary_database: (response.data.primary_database as typeof primaryChoice) ?? primaryChoice,
        schema_ok: response.data.schema_ok ?? schema_ok,
        schema_version: response.data.schema_version ?? schema_version,
        show_clock_device_ids: response.data.show_clock_device_ids ?? show_clock_device_ids,
        admins: nextAdmins,
        pin_set: response.data.pin_set ?? nextAdmins.some((admin) => admin.active)
      });
      setAdminPinEntry("");
    } catch (error) {
      setDbStatus({ kind: "error", message: formatApiError(error) });
    }
  };

  const testDbConnection = async (target: "primary" | "secondary") => {
    try {
      setDbStatus(null);
      const isSecondary = target === "secondary";
      const targetHost = (isSecondary ? secondaryHost : primaryHost) ?? "";
      const targetUser = (isSecondary ? secondaryUser : primaryUser) ?? "";
      const targetPassword = isSecondary ? secondaryPassword : primaryPassword;
      const targetPort = isSecondary ? secondaryPort : primaryPort;

      if (!targetHost.trim() || !targetUser.trim()) {
        setDbStatus({ kind: "error", message: "יש להזין כתובת שרת ומשתמש לפני בדיקת חיבור" });
        return;
      }

      const payload: Record<string, unknown> = {
        db_host: targetHost,
        db_user: targetUser,
        db_password: targetPassword ?? "",
        target
      };
      if (targetPort) {
        payload.db_port = Number(targetPort);
      }

      const response = await api.post<{ ok: boolean; message: string; schema_version?: number | null; schema_ok?: boolean | null }>("/db/test", payload);
      const { message, schema_version, schema_ok: schemaOkFlag } = response.data;
      let finalMessage = message;
      if (schema_version !== undefined && schema_version !== null) {
        finalMessage = `${message} — גרסת סכימה ${schema_version}${schemaOkFlag ? " (עדכנית)" : " (נדרש עדכון)"}`;
      }
      setDbStatus({ kind: response.data.ok ? "success" : "error", message: finalMessage });
    } catch (error) {
      setDbStatus({ kind: "error", message: formatApiError(error) });
    }
  };

  const ensureSchema = async () => {
  try {
    setDbStatus(null);
    const response = await api.post<{ ok: boolean; message: string }>("/db/init", null, {
      params: { target: schemaTarget }
    });
    setDbStatus({ kind: response.data.ok ? "success" : "error", message: response.data.message });
    if (response.data.ok) {
      await refresh();
    }
  } catch (error) {
    setDbStatus({ kind: "error", message: formatApiError(error) });
  }
};

  const exportSettings = async () => {
  try {
    setImportStatus(null);
    const response = await api.get("/settings/export");
    const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
      a.href = url;
      a.download = `hubclock-settings-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setImportStatus({ kind: "success", message: "ההגדרות יוצאו לקובץ" });
  } catch (error) {
    setImportStatus({ kind: "error", message: formatApiError(error) });
  }
};

  const importSettings = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setIsImporting(true);
  try {
    setImportStatus(null);
    const text = await file.text();
    const payload = JSON.parse(text);
    const requestBody = { ...payload };
    if (admins.length > 0) {
      const credentials = resolveCredentials(setImportStatus);
      if (!credentials) {
        return;
      }
      requestBody.requestor_admin_id = credentials.adminId;
      requestBody.requestor_pin = credentials.pin;
    }
      await api.post("/settings/import", requestBody);
      setImportStatus({ kind: "success", message: "ההגדרות נטענו בהצלחה" });
    setAdminPinEntry("");
    await refresh();
  } catch (error) {
    setImportStatus({ kind: "error", message: formatApiError(error) });
    } finally {
      setIsImporting(false);
      event.target.value = "";
    }
  };

  return (
    <div className="card">
      <h2>הגדרות המערכת</h2>
      <p>נהל את ההגדרות המרכזיות ואת חיבור מסד הנתונים של עמדת הנוכחות.</p>

      {!schema_ok && (
        <div className="status error">
          גרסת סכימת בסיס הנתונים ({schema_version}) אינה מעודכנת. הריצו "יצירת/עדכון סכימה" כדי לאפשר את כל היכולות החדשות.
        </div>
      )}

      {generalStatus && <div className={`status ${generalStatus.kind}`}>{generalStatus.message}</div>}

      <section className="card">
        <h3>אימות מנהל</h3>
        <p>בחרו את המנהל המבצע והזינו את קוד ה-PIN שלו. נשתמש בפרטים אלו לביצוע שינויים מוגנים בהמשך העמוד.</p>
        <div className="input-row">
          <div>
            <label htmlFor="actingAdmin">מנהל מבצע</label>
            <select
              id="actingAdmin"
              value={actingAdminId === "" ? "" : Number(actingAdminId)}
              onChange={(event) => {
                const value = event.target.value ? Number(event.target.value) : "";
                setActingAdminId(value);
              }}
              disabled={effectiveAdmins.length === 0 || isSavingAdmin}
            >
              <option value="" disabled>
                {effectiveAdmins.length === 0 ? "אין מנהלים זמינים" : "בחרו מנהל"}
              </option>
              {effectiveAdmins.map((admin) => (
                <option key={admin.id} value={admin.id}>
                  {admin.name}
                  {!admin.active ? " (מושבת)" : ""}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="actingAdminPin">קוד PIN של המנהל</label>
            <input
              id="actingAdminPin"
              type="password"
              value={adminPinEntry}
              onChange={(event) => setAdminPinEntry(event.target.value)}
              minLength={4}
              maxLength={12}
              placeholder="הזינו PIN לפני שמירה"
              disabled={effectiveAdmins.length === 0}
            />
          </div>
        </div>
        {!pin_set && (
          <div className="status error" style={{ marginTop: "0.75rem" }}>
            טרם הוגדר PIN פעיל. צרו או הפעילו מנהל כדי לאפשר פעולות מוגנות.
          </div>
        )}
      </section>

      <section className="card">
        <h3>ניהול מנהלים וקודי PIN</h3>
        <p>הוסיפו מנהל חדש או עדכנו מנהלים קיימים. מומלץ להחזיק לפחות שני מנהלים פעילים למקרי גיבוי.</p>
        <form onSubmit={handleCreateAdmin} className="input-row">
          <div>
            <label htmlFor="newAdminName">שם מנהל חדש</label>
            <input
              id="newAdminName"
              value={newAdminName}
              onChange={(event) => setNewAdminName(event.target.value)}
              placeholder="לדוגמה: מנהל תורן"
              disabled={isSavingAdmin}
            />
          </div>
          <div>
            <label htmlFor="newAdminPin">PIN חדש</label>
            <input
              id="newAdminPin"
              type="password"
              value={newAdminPin}
              onChange={(event) => setNewAdminPin(event.target.value)}
              minLength={4}
              maxLength={12}
              disabled={isSavingAdmin}
            />
          </div>
          <div>
            <label htmlFor="newAdminPinConfirm">אימות PIN</label>
            <input
              id="newAdminPinConfirm"
              type="password"
              value={newAdminPinConfirm}
              onChange={(event) => setNewAdminPinConfirm(event.target.value)}
              minLength={4}
              maxLength={12}
              disabled={isSavingAdmin}
            />
          </div>
          <div style={{ display: "flex", alignItems: "flex-end" }}>
            <button className="secondary" type="submit" disabled={isSavingAdmin}>
              הוספת מנהל
            </button>
          </div>
        </form>
        {adminStatus && (
          <div className={`status ${adminStatus.kind}`} style={{ marginTop: "0.75rem" }}>
            {adminStatus.message}
          </div>
        )}
        {admins.length === 0 ? (
          <div className="status warning" style={{ marginTop: "0.75rem" }}>
            אין מנהלים קיימים. השתמשו בכלי השחזור הייעודי כדי ליצור מנהל ראשי במקרה הצורך.
          </div>
        ) : (
          <div style={{ display: "grid", gap: "1rem", marginTop: "1rem" }}>
            {admins.map((admin) => {
              const edits = adminEdits[admin.id] ?? {};
              const nameValue = edits.name ?? admin.name;
              const activeValue = edits.active ?? admin.active;
              const newPinValue = edits.newPin ?? "";
              return (
                <form
                  key={admin.id}
                  onSubmit={(event) => {
                    event.preventDefault();
                    handleAdminSave(admin);
                  }}
                  className="input-row"
                  style={{ border: "1px solid #d0d5dd", borderRadius: "0.75rem", padding: "1rem" }}
                >
                  <div>
                    <label>שם המנהל</label>
                    <input
                      value={nameValue}
                      onChange={(event) => updateAdminEdit(admin.id, { name: event.target.value })}
                      disabled={isSavingAdmin}
                    />
                  </div>
                  <div>
                    <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "1.5rem" }}>
                      <input
                        type="checkbox"
                        checked={activeValue}
                        onChange={(event) => updateAdminEdit(admin.id, { active: event.target.checked })}
                        disabled={isSavingAdmin}
                      />
                      פעיל
                    </label>
                  </div>
                  <div>
                    <label>PIN חדש (אופציונלי)</label>
                    <input
                      type="password"
                      value={newPinValue}
                      onChange={(event) => updateAdminEdit(admin.id, { newPin: event.target.value })}
                      minLength={0}
                      maxLength={12}
                      placeholder="השאירו ריק כדי לא לשנות"
                      disabled={isSavingAdmin}
                    />
                  </div>
                  <div style={{ display: "flex", alignItems: "flex-end", gap: "0.75rem" }}>
                    <button className="primary" type="submit" disabled={isSavingAdmin}>
                      שמירת שינויים
                    </button>
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => clearAdminEdit(admin.id)}
                      disabled={isSavingAdmin}
                    >
                      איפוס
                    </button>
                  </div>
                </form>
              );
            })}
          </div>
        )}
        {admins.filter((admin) => admin.active).length < 2 && admins.length > 0 && (
          <div className="status warning" style={{ marginTop: "0.75rem" }}>
            מומלץ להחזיק לפחות שני מנהלים פעילים לצורך שחזור בעת הצורך.
          </div>
        )}
      </section>

      <section className="card">
        <h3>מטבע, מותג וצבע</h3>
        <form onSubmit={updateAppearance} className="input-row">
          <div>
            <label htmlFor="currency">קוד מטבע</label>
            <select id="currency" value={currencyValue} onChange={(event) => setCurrencyValue(event.target.value)}>
              {currencyOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="brandName">שם העסק</label>
            <input
              id="brandName"
              value={brandName}
              onChange={(event) => setBrandName(event.target.value)}
              placeholder="לדוגמה: בית הקפה שלנו"
            />
          </div>
          <div>
            <label htmlFor="themeColor">צבע נושא</label>
            <input
              id="themeColor"
              type="color"
              value={themeColor}
              onChange={(event) => setThemeColor(event.target.value)}
              title="בחרו צבע עבור הכותרת והכפתורים"
            />
          </div>
          <div style={{ display: "flex", alignItems: "flex-end" }}>
            <button className="primary" type="submit">
              שמירת ההגדרות
            </button>
          </div>
          <div
            style={{
              flexBasis: "100%",
              display: "inline-flex",
              alignItems: "center",
              gap: "0.5rem",
              marginTop: "0.75rem",
              whiteSpace: "nowrap"
            }}
          >
            <input
              id="showClockDevices"
              type="checkbox"
              checked={showClockDevices}
              onChange={(event) => setShowClockDevices(event.target.checked)}
            />
            <label htmlFor="showClockDevices" style={{ fontWeight: 500, cursor: "pointer" }}>
              להציג מזהי מכשיר במסכי השעון והרשימות החיות
            </label>
          </div>
        </form>
      </section>

      <section className="card">
        <h3>חיבור למסדי נתונים</h3>
        <form onSubmit={updateDatabase}>
          <fieldset style={{ border: "1px solid #d0d5dd", borderRadius: "0.75rem", padding: "1rem", marginBottom: "1rem" }}>
            <legend style={{ fontWeight: 600 }}>מסד נתונים א'</legend>
            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
              <input type="checkbox" checked={primaryActive} onChange={handlePrimaryActiveChange} /> פעיל
            </label>
            <label htmlFor="primaryHost">כתובת שרת</label>
              <input
                id="primaryHost"
                value={primaryHost}
                onChange={(event) => setPrimaryHost(event.target.value)}
                required={primaryActive}
              />
              <label htmlFor="primaryPort">פורט</label>
              <input
                id="primaryPort"
                type="number"
                value={primaryPort}
                onChange={(event) => setPrimaryPort(event.target.value)}
                min={0}
              />
              <label htmlFor="primaryUser">שם משתמש</label>
              <input
                id="primaryUser"
                value={primaryUser}
                onChange={(event) => setPrimaryUser(event.target.value)}
                required={primaryActive}
              />
              <label htmlFor="primaryPassword">סיסמה</label>
              <div style={{ position: "relative" }}>
                <input
                  id="primaryPassword"
                  type={showPrimaryPassword ? "text" : "password"}
                  value={primaryPassword}
                  onChange={(event) => setPrimaryPassword(event.target.value)}
                  style={{ paddingLeft: "3.2rem" }}
                />
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setShowPrimaryPassword((prev) => !prev)}
                  style={{
                    position: "absolute",
                    top: "50%",
                    left: "0.4rem",
                    transform: "translateY(-50%)",
                    padding: "0.25rem 0.6rem",
                    fontSize: "0.8rem"
                  }}
                >
                  {showPrimaryPassword ? "הסתר" : "הצג"}
                </button>
              </div>
            </fieldset>
          <fieldset style={{ border: "1px solid #d0d5dd", borderRadius: "0.75rem", padding: "1rem" }}>
            <legend style={{ fontWeight: 600 }}>מסד נתונים ב'</legend>
            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
              <input type="checkbox" checked={secondaryActive} onChange={handleSecondaryActiveChange} /> פעיל
            </label>
            <label htmlFor="secondaryHost">כתובת שרת</label>
            <input
              id="secondaryHost"
              value={secondaryHost}
              onChange={(event) => setSecondaryHost(event.target.value)}
            />
            <label htmlFor="secondaryPort">פורט</label>
            <input
              id="secondaryPort"
              type="number"
              value={secondaryPort}
              onChange={(event) => setSecondaryPort(event.target.value)}
              min={0}
            />
            <label htmlFor="secondaryUser">שם משתמש</label>
            <input
              id="secondaryUser"
              value={secondaryUser}
              onChange={(event) => setSecondaryUser(event.target.value)}
            />
            <label htmlFor="secondaryPassword">סיסמה</label>
            <div style={{ position: "relative" }}>
              <input
                id="secondaryPassword"
                type={showSecondaryPassword ? "text" : "password"}
                value={secondaryPassword}
                onChange={(event) => setSecondaryPassword(event.target.value)}
                style={{ paddingLeft: "3.2rem" }}
              />
              <button
                type="button"
                className="secondary"
                onClick={() => setShowSecondaryPassword((prev) => !prev)}
                style={{
                  position: "absolute",
                  top: "50%",
                  left: "0.4rem",
                  transform: "translateY(-50%)",
                  padding: "0.25rem 0.6rem",
                  fontSize: "0.8rem"
                }}
              >
                {showSecondaryPassword ? "הסתר" : "הצג"}
              </button>
            </div>
          </fieldset>

          <div style={{ marginTop: "1.25rem" }}>
            <label style={{ fontWeight: 600, display: "block", marginBottom: "0.5rem" }}>בחירת מסד נתונים ראשי</label>
            <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
              <label style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem" }}>
                <input
                  type="radio"
                  name="primaryChoice"
                  value="primary"
                  checked={primaryChoice === "primary"}
                  onChange={(event) => setPrimaryChoice(event.target.value as "primary" | "secondary")}
                  disabled={!primaryActive}
                />
                <span>מסד נתונים א' (קריאה וכתיבה)</span>
              </label>
              <label style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem" }}>
                <input
                  type="radio"
                  name="primaryChoice"
                  value="secondary"
                  checked={primaryChoice === "secondary"}
                  onChange={(event) => setPrimaryChoice(event.target.value as "primary" | "secondary")}
                  disabled={!secondaryActive}
                />
                <span>מסד נתונים ב' (קריאה וכתיבה)</span>
              </label>
            </div>
          </div>

          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", marginTop: "1.5rem", alignItems: "flex-end" }}>
            <button className="secondary" type="button" onClick={() => testDbConnection("primary")}>בדיקת חיבור ראשי</button>
            <button
              className="secondary"
              type="button"
              onClick={() => testDbConnection("secondary")}
              disabled={!secondaryHost.trim() || !secondaryUser.trim()}
            >
              בדיקת חיבור משני
            </button>
            <div>
              <label htmlFor="schemaTarget">יעד יצירת סכימה</label>
              <select
                id="schemaTarget"
                value={schemaTarget}
                onChange={(event) => setSchemaTarget(event.target.value as SchemaTarget)}
                style={{ minWidth: "10rem" }}
              >
                <option value="active">מסדי נתונים פעילים</option>
                <option value="primary">מסד נתונים ראשי</option>
                <option value="secondary">מסד נתונים משני</option>
                <option value="both">שני המסדים</option>
              </select>
            </div>
            <button className="secondary" type="button" onClick={ensureSchema}>
              יצירת/עדכון סכימה
            </button>
            <div style={{ flexGrow: 1 }} />
            <button className="primary" type="submit">
              שמירת פרטי חיבור
            </button>
          </div>
        </form>
        {dbStatus && <div className={`status ${dbStatus.kind}`} style={{ marginTop: "0.75rem" }}>{dbStatus.message}</div>}
      </section>

      <section className="card">
        <h3>ייצוא וייבוא הגדרות</h3>
        <p>שמרו את ההגדרות לקובץ JSON או טענו קובץ מוכן מראש, כולל קוד ה-PIN.</p>
        <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", alignItems: "center" }}>
          <button className="secondary" type="button" onClick={exportSettings}>
            ייצוא הגדרות
          </button>
          <label className="secondary" style={{ padding: "0.55rem 1.2rem", cursor: "pointer" }}>
            ייבוא מקובץ
            <input type="file" accept="application/json" onChange={importSettings} hidden disabled={isImporting} />
          </label>
        </div>
        {importStatus && <div className={`status ${importStatus.kind}`} style={{ marginTop: "0.75rem" }}>{importStatus.message}</div>}
      </section>
    </div>
  );
};

export default SettingsPage;
