import React, { useEffect, useState } from "react";
import { api, formatApiError } from "../api/client";
import { useSettings } from "../context/SettingsContext";

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
  const [currentPin, setCurrentPin] = useState("");
  const [newPin, setNewPin] = useState("");
  const [generalStatus, setGeneralStatus] = useState<StatusMessage>(null);
  const [dbStatus, setDbStatus] = useState<StatusMessage>(null);
  const [pinStatus, setPinStatus] = useState<StatusMessage>(null);
  const [importStatus, setImportStatus] = useState<StatusMessage>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [showPrimaryPassword, setShowPrimaryPassword] = useState(false);
  const [showSecondaryPassword, setShowSecondaryPassword] = useState(false);
  const [schemaTarget, setSchemaTarget] = useState<SchemaTarget>("active");
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

  const updateAppearance = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      setGeneralStatus(null);
      await api.put("/settings", {
        currency: currencyValue,
        theme_color: themeColor,
        brand_name: brandName,
        show_clock_device_ids: showClockDevices
      });
      setGeneralStatus({ kind: "success", message: "ההגדרות נשמרו" });
      setLocal({
        currency: currencyValue,
        theme_color: themeColor,
        brand_name: brandName,
        show_clock_device_ids: showClockDevices
      });
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
      const response = await api.put("/settings", payload);
      setDbStatus({ kind: "success", message: "הגדרות מסדי הנתונים נשמרו" });
      setLocal({
        db_host: payload.db_host ?? "",
        db_port: payload.db_port,
        db_user: payload.db_user ?? "",
        db_password: payload.db_password as string,
        secondary_db_host: payload.secondary_db_host ?? "",
        secondary_db_port: payload.secondary_db_port,
        secondary_db_user: payload.secondary_db_user ?? "",
        secondary_db_password: payload.secondary_db_password as string,
        primary_db_active: primaryActive,
        secondary_db_active: secondaryActive,
        primary_database: primaryChoice,
        schema_ok: response.data.schema_ok ?? schema_ok,
        schema_version: response.data.schema_version ?? schema_version,
        show_clock_device_ids: response.data.show_clock_device_ids ?? show_clock_device_ids
      });
    } catch (error) {
      setDbStatus({ kind: "error", message: formatApiError(error) });
    }
  };

  const updatePin = async (event: React.FormEvent) => {
    event.preventDefault();
  try {
    setPinStatus(null);
    await api.put("/settings", {
      current_pin: pin_set ? currentPin : undefined,
      new_pin: newPin
    });
    setPinStatus({ kind: "success", message: "קוד ה-PIN עודכן" });
    setCurrentPin("");
    setNewPin("");
    refresh();
  } catch (error) {
    setPinStatus({ kind: "error", message: formatApiError(error) });
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
      await api.post("/settings/import", payload);
      setImportStatus({ kind: "success", message: "ההגדרות נטענו בהצלחה" });
    setCurrentPin("");
    setNewPin("");
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
        <h3>קוד מנהל (PIN)</h3>
        <p>{pin_set ? "עדכנו את קוד ה-PIN הקיים." : "צרו קוד PIN חדש כדי לנעול את אזור הניהול."}</p>
        <form onSubmit={updatePin} className="input-row">
          {pin_set && (
            <div>
              <label htmlFor="currentPin">PIN נוכחי</label>
              <input
                id="currentPin"
                type="password"
                value={currentPin}
                onChange={(event) => setCurrentPin(event.target.value)}
                minLength={4}
                maxLength={12}
                required={pin_set}
              />
            </div>
          )}
          <div>
            <label htmlFor="newPin">PIN חדש</label>
            <input
              id="newPin"
              type="password"
              value={newPin}
              onChange={(event) => setNewPin(event.target.value)}
              minLength={4}
              maxLength={12}
              required
            />
          </div>
        <div style={{ display: "flex", alignItems: "flex-end" }}>
          <button className="secondary" type="submit">
            שמירת PIN
          </button>
        </div>
      </form>
        {pinStatus && <div className={`status ${pinStatus.kind}`} style={{ marginTop: "0.75rem" }}>{pinStatus.message}</div>}
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
