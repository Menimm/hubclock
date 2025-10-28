import React, { useEffect, useState } from "react";
import { api, formatApiError } from "../api/client";
import { useSettings } from "../context/SettingsContext";

type StatusMessage = { kind: "success" | "error"; message: string } | null;

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
    brand_name,
    theme_color: themeColorSetting,
    refresh,
    setLocal
  } = useSettings();
  const [currencyValue, setCurrencyValue] = useState(currency);
  const [host, setHost] = useState(db_host);
  const [port, setPort] = useState(db_port ? String(db_port) : "");
  const [user, setUser] = useState(db_user);
  const [password, setPassword] = useState(db_password);
  const [brandName, setBrandName] = useState(brand_name ?? "דלי");
  const [themeColor, setThemeColor] = useState(themeColorSetting ?? "#1b3aa6");
  const [currentPin, setCurrentPin] = useState("");
  const [newPin, setNewPin] = useState("");
  const [generalStatus, setGeneralStatus] = useState<StatusMessage>(null);
  const [dbStatus, setDbStatus] = useState<StatusMessage>(null);
  const [pinStatus, setPinStatus] = useState<StatusMessage>(null);
  const [importStatus, setImportStatus] = useState<StatusMessage>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [showDbPassword, setShowDbPassword] = useState(false);

  useEffect(() => {
    setCurrencyValue(currency);
  }, [currency]);

useEffect(() => {
  setHost(db_host ?? "");
  setPort(db_port ? String(db_port) : "");
  setUser(db_user ?? "");
  setPassword(db_password ?? "");
  setBrandName(brand_name ?? "דלי");
  setThemeColor(themeColorSetting ?? "#1b3aa6");
}, [db_host, db_port, db_user, db_password, brand_name, themeColorSetting]);

  const updateAppearance = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      setGeneralStatus(null);
      await api.put("/settings", {
        currency: currencyValue,
        theme_color: themeColor,
        brand_name: brandName
      });
      setGeneralStatus({ kind: "success", message: "ההגדרות נשמרו" });
      setLocal({ currency: currencyValue, theme_color: themeColor, brand_name: brandName });
    } catch (error) {
      setGeneralStatus({ kind: "error", message: formatApiError(error) });
    }
  };

const updateDatabase = async (event: React.FormEvent) => {
  event.preventDefault();
  try {
    setDbStatus(null);
      await api.put("/settings", {
        db_host: host,
        db_port: port ? Number(port) : null,
        db_user: user,
        db_password: password
      });
    setDbStatus({ kind: "success", message: "פרטי החיבור למסד הנתונים נשמרו" });
    setLocal({
      db_host: host,
      db_port: port ? Number(port) : null,
      db_user: user,
      db_password: password
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

  const ensureSchema = async () => {
  try {
    setDbStatus(null);
    const response = await api.post<{ ok: boolean; message: string }>("/db/init");
    setDbStatus({ kind: response.data.ok ? "success" : "error", message: response.data.message });
  } catch (error) {
    setDbStatus({ kind: "error", message: formatApiError(error) });
  }
};

  const testConnection = async () => {
  try {
    setDbStatus(null);
    const payload: Record<string, unknown> = {
      db_host: host,
      db_user: user,
      db_password: password ?? ""
    };
    if (port) {
      payload.db_port = Number(port);
    }
    const response = await api.post<{ ok: boolean; message: string }>("/db/test", payload);
    setDbStatus({ kind: response.data.ok ? "success" : "error", message: response.data.message });
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
              placeholder="לדוגמה: דלי משפחתי"
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
        </form>
      </section>

      <section className="card">
        <h3>חיבור למסד הנתונים</h3>
        <form onSubmit={updateDatabase} className="input-row">
          <div>
            <label htmlFor="dbHost">כתובת שרת</label>
            <input id="dbHost" value={host} onChange={(event) => setHost(event.target.value)} required />
          </div>
          <div>
            <label htmlFor="dbPort">פורט</label>
            <input id="dbPort" type="number" value={port} onChange={(event) => setPort(event.target.value)} />
          </div>
          <div>
            <label htmlFor="dbUser">שם משתמש</label>
            <input id="dbUser" value={user} onChange={(event) => setUser(event.target.value)} required />
          </div>
          <div>
            <label htmlFor="dbPassword">סיסמה</label>
            <div style={{ position: "relative" }}>
              <input
                id="dbPassword"
                type={showDbPassword ? "text" : "password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                style={{ paddingLeft: "3.2rem" }}
              />
              <button
                type="button"
                className="secondary"
                onClick={() => setShowDbPassword((prev) => !prev)}
                style={{
                  position: "absolute",
                  top: "50%",
                  left: "0.4rem",
                  transform: "translateY(-50%)",
                  padding: "0.25rem 0.6rem",
                  fontSize: "0.8rem"
                }}
              >
                {showDbPassword ? "הסתר" : "הצג"}
              </button>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "flex-end" }}>
            <button className="secondary" type="submit">
              שמירת פרטי חיבור
            </button>
          </div>
        </form>
        <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", marginTop: "1rem" }}>
          <button className="secondary" onClick={testConnection} type="button">
            בדיקת חיבור
          </button>
          <button className="primary" onClick={ensureSchema} type="button">
            יצירת/עדכון סכימה
          </button>
        </div>
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
