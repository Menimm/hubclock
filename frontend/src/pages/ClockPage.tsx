import React, { useEffect, useRef, useState } from "react";
import { api, formatApiError } from "../api/client";
import { differenceInMinutes, format } from "date-fns";
import { he } from "date-fns/locale";
import { getDeviceId } from "../utils/deviceId";
import { useSettings } from "../context/SettingsContext";

type ActiveShift = {
  employee_id: number;
  full_name: string;
  clock_in: string;
  elapsed_minutes: number;
  clock_in_device_id?: string | null;
};

type StatusKind = "success" | "error" | null;

type ClockResponse = {
  status: string;
  message: string;
  entry_id?: number;
  device_id?: string | null;
  device_match?: boolean | null;
};

const formatMinutes = (minutes: number) => {
  const hrs = Math.floor(minutes / 60)
    .toString()
    .padStart(2, "0");
  const mins = (minutes % 60).toString().padStart(2, "0");
  return `${hrs}:${mins}`;
};

const ClockPage: React.FC = () => {
  const { show_clock_device_ids: showClockDeviceIdsSetting } = useSettings();
  const showDeviceColumns = showClockDeviceIdsSetting ?? true;
  const [employeeCode, setEmployeeCode] = useState("");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [statusKind, setStatusKind] = useState<StatusKind>(null);
  const [activeShifts, setActiveShifts] = useState<ActiveShift[]>([]);
  const [isClockedIn, setIsClockedIn] = useState<boolean | null>(null);
  const [checkingStatus, setCheckingStatus] = useState(false);
  const deviceIdRef = useRef<string>(typeof window !== "undefined" ? getDeviceId() : "unknown-device");
  const [deviceId, setDeviceId] = useState<string>(deviceIdRef.current);

  useEffect(() => {
    const id = getDeviceId();
    deviceIdRef.current = id;
    setDeviceId(id);
  }, []);

  const loadActive = async (silent = false) => {
    try {
      const response = await api.get<ActiveShift[]>("/clock/active");
      setActiveShifts(response.data);
      if (!silent && employeeCode.trim()) {
        await fetchStatus(employeeCode.trim(), true);
      }
    } catch (error) {
      if (!silent) {
        console.error("טעינת המשמרות הפעילות נכשלה", error);
      }
    }
  };

  const fetchStatus = async (code: string, silent = false) => {
    if (!code) {
      setIsClockedIn(null);
      return null;
    }
    try {
      if (!silent) {
        setCheckingStatus(true);
      }
      const response = await api.post<{ is_clocked_in: boolean }>("/clock/status", {
        employee_code: code,
        device_id: deviceIdRef.current
      });
      if (code === employeeCode.trim()) {
        setIsClockedIn(response.data.is_clocked_in);
        setStatusKind(null);
        setStatusMessage(null);
      }
      return response.data.is_clocked_in;
    } catch (error) {
    if (!silent && code === employeeCode.trim()) {
      setStatusKind("error");
      setStatusMessage(formatApiError(error));
    }
    setIsClockedIn(null);
    return null;
    } finally {
      if (!silent) {
        setCheckingStatus(false);
      }
    }
  };

  useEffect(() => {
    loadActive();
    const timer = setInterval(() => loadActive(true), 10_000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!employeeCode.trim()) {
      setStatusKind(null);
      setStatusMessage(null);
      setIsClockedIn(null);
      return;
    }
    setCheckingStatus(true);
    const handler = setTimeout(() => {
      fetchStatus(employeeCode.trim());
    }, 400);
    return () => clearTimeout(handler);
  }, [employeeCode]);

  const handleToggle = async () => {
    const trimmed = employeeCode.trim();
    if (!trimmed) {
      return;
    }
    try {
      setStatusMessage(null);
      setStatusKind(null);

      let currentState = isClockedIn;
      if (currentState === null) {
        currentState = await fetchStatus(trimmed, true);
      }

      const endpoint = currentState ? "/clock/out" : "/clock/in";
      const response = await api.post<ClockResponse>(endpoint, {
        employee_code: trimmed,
        device_id: deviceIdRef.current
      });

      const stateMap: Record<string, boolean> = {
        clocked_in: true,
        already_in: true,
        clocked_out: false,
        not_in: false
      };
      if (response.data.status in stateMap) {
        setIsClockedIn(stateMap[response.data.status]);
      }

      let successMessage = response.data.message;
      if (response.data.device_match === false) {
        successMessage += " (המכשיר שונה מזה שבו התחילה המשמרת)";
      }
      setStatusKind("success");
      setStatusMessage(successMessage);
      setEmployeeCode("");
      await loadActive(true);
    } catch (error) {
      setStatusKind("error");
      setStatusMessage(formatApiError(error));
    }
  };

  return (
    <div className="card">
      <h2>שעון נוכחות</h2>
      <p>הקלידו את מספר העובד כדי לפתוח או לסגור משמרת. המספר מוסתר לשמירה על פרטיות.</p>
      {showDeviceColumns && (
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            gap: "0.5rem",
            margin: "1rem 0",
            padding: "0.6rem 0.9rem",
            borderRadius: "8px",
            backgroundColor: "#eef2ff",
            color: "#1e3a8a",
            fontWeight: 500
          }}
        >
          <span>
            מזהה המכשיר הנוכחי:&nbsp;
            <code style={{ direction: "ltr" }}>
              {deviceId && deviceId !== "unknown-device" ? deviceId : "לא זמין"}
            </code>
          </span>
          {deviceId && deviceId !== "unknown-device" ? (
            <button
              type="button"
              className="secondary"
              style={{ padding: "0.15rem 0.6rem", fontSize: "0.85rem" }}
              onClick={() => {
                void navigator.clipboard.writeText(deviceId).catch(() => {
                  window.prompt("העתקה לא הצליחה אוטומטית. העתיקו את המזהה ידנית:", deviceId);
                });
              }}
            >
              העתקה
            </button>
          ) : (
            <span style={{ fontSize: "0.85rem" }}>
              אם אינכם רואים מזהה, וודאו שהדפדפן מאפשר שימוש בעוגיות/LocalStorage.
            </span>
          )}
        </div>
      )}
      <div className="toolbar">
        <div style={{ flex: 1 }}>
          <label htmlFor="employeeCode">מספר עובד</label>
          <input
            id="employeeCode"
            type="password"
            placeholder="הקלידו מספר עובד"
            value={employeeCode}
            onChange={(event) => {
              setEmployeeCode(event.target.value);
            }}
            minLength={3}
            required
          />
        </div>
        <div className="actions">
          <button className="primary" onClick={handleToggle} disabled={!employeeCode || checkingStatus}>
            {checkingStatus ? "בודק..." : isClockedIn ? "סיום משמרת" : "תחילת משמרת"}
          </button>
        </div>
      </div>
      {statusMessage && statusKind && (
        <div className={`status ${statusKind}`} role="alert">
          {statusMessage}
        </div>
      )}

      <section style={{ marginTop: "1.75rem" }}>
        <h3>מי נמצא עכשיו במשמרת</h3>
        {activeShifts.length === 0 ? (
          <p>אין עובדים במשמרת כרגע.</p>
        ) : (
          <div className="table-wrapper" style={{ maxHeight: "420px", overflowY: "auto" }}>
            <table className="table" style={{ minWidth: showDeviceColumns ? "660px" : "520px" }}>
              <thead>
                <tr>
                  <th>שם העובד</th>
                  <th>שעת כניסה</th>
                  <th>משך משמרת</th>
                  {showDeviceColumns && <th>מכשיר</th>}
                </tr>
              </thead>
              <tbody>
                {activeShifts.map((shift) => {
                  const clockInDate = new Date(shift.clock_in);
                  const duration = differenceInMinutes(new Date(), clockInDate);
                  return (
                    <tr key={shift.employee_id}>
                      <td>{shift.full_name}</td>
                      <td>{format(clockInDate, "HH:mm", { locale: he })}</td>
                      <td>{formatMinutes(duration)}</td>
                      {showDeviceColumns && (
                        <td style={{ direction: "ltr", whiteSpace: "nowrap" }}>{shift.clock_in_device_id ?? ""}</td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
};

export default ClockPage;
