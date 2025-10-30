import React, { useEffect, useMemo, useState } from "react";
import { format } from "date-fns";
import { he } from "date-fns/locale";
import { api, formatApiError } from "../api/client";
import { useSettings } from "../context/SettingsContext";

interface Employee {
  id: number;
  full_name: string;
  id_number?: string | null;
}

interface ReportRow {
  employee_id: number;
  full_name: string;
  id_number?: string | null;
  total_seconds: number;
  total_hours: number;
  hourly_rate: number;
  total_pay: number;
}

interface ReportResponse {
  rows: ReportRow[];
  range_start: string;
  range_end: string;
}

interface DailyShift {
  entry_id: number;
  shift_date: string;
  clock_in: string;
  clock_out: string;
  duration_minutes: number;
  hourly_rate: number;
  estimated_pay: number;
}

interface DailyEmployeeReport {
  employee_id: number;
  full_name: string;
  id_number?: string | null;
  shifts: DailyShift[];
}

interface DailyReportResponse {
  employees: DailyEmployeeReport[];
  range_start: string;
  range_end: string;
}

type Mode = "month" | "custom";
type ReportType = "summary" | "daily";
type StatusMessage = { kind: "success" | "error"; message: string } | null;

interface PinModalConfig {
  title: string;
  confirmLabel: string;
  message?: string;
  onConfirm: (pin: string) => Promise<void>;
}

const formatMinutesToHHMM = (minutes: number): string => {
  const safeMinutes = Math.max(0, Math.round(minutes));
  const hoursPart = Math.floor(safeMinutes / 60);
  const minutesPart = safeMinutes % 60;
  return `${hoursPart.toString().padStart(2, "0")}:${minutesPart.toString().padStart(2, "0")}`;
};

const formatSecondsToHHMM = (seconds: number): string => {
  return formatMinutesToHHMM(Math.round(seconds / 60));
};

const DashboardPage: React.FC = () => {
  const { currency, schema_ok } = useSettings();
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [mode, setMode] = useState<Mode>("month");
  const [reportType, setReportType] = useState<ReportType>("summary");
  const [selectedMonth, setSelectedMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [employeeId, setEmployeeId] = useState<string>("all");
  const [summaryReport, setSummaryReport] = useState<ReportResponse | null>(null);
  const [dailyReport, setDailyReport] = useState<DailyReportResponse | null>(null);
  const [status, setStatus] = useState<StatusMessage>(null);
  const [dailyStatus, setDailyStatus] = useState<StatusMessage>(null);
  const [editingEntryId, setEditingEntryId] = useState<number | null>(null);
  const [editClockIn, setEditClockIn] = useState<string>("");
  const [editClockOut, setEditClockOut] = useState<string>("");
  const [isSavingEntry, setIsSavingEntry] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [includePayments, setIncludePayments] = useState(false);
  const [pinModal, setPinModal] = useState<PinModalConfig | null>(null);
  const [pinValue, setPinValue] = useState("");
  const [pinError, setPinError] = useState<string | null>(null);
  const [isConfirmingPin, setIsConfirmingPin] = useState(false);
  const currencyFormatter = useMemo(
    () =>
      new Intl.NumberFormat("he-IL", {
        style: "currency",
        currency
      }),
    [currency]
  );

  useEffect(() => {
    const loadEmployees = async () => {
      try {
        const response = await api.get<Employee[]>("/employees");
        setEmployees(response.data);
      } catch (error) {
        console.error("טעינת רשימת העובדים נכשלה", error);
      }
    };
    loadEmployees();
  }, []);

  const filters = useMemo(() => {
    const params = new URLSearchParams();
    if (employeeId !== "all") {
      params.set("employee_id", employeeId);
    }
    if (mode === "month") {
      params.set("month", selectedMonth);
    } else {
      if (startDate) params.set("start", startDate);
      if (endDate) params.set("end", endDate);
    }
    return params;
  }, [mode, selectedMonth, startDate, endDate, employeeId]);

  const runReport = async () => {
    try {
      setDailyStatus(null);
      if (reportType === "summary") {
        const response = await api.get<ReportResponse>(`/reports?${filters.toString()}`);
        setSummaryReport(response.data);
        setDailyReport(null);
      } else {
        const response = await api.get<DailyReportResponse>(`/reports/daily?${filters.toString()}`);
        setDailyReport(response.data);
        setSummaryReport(null);
      }
      setStatus({ kind: "success", message: "הדוח עודכן" });
    } catch (error) {
      setStatus({ kind: "error", message: formatApiError(error) });
    }
  };

  const downloadDailyReport = async () => {
    setStatus(null);
    setIsExporting(true);
    try {
      const qs = filters.toString();
      const requestUrl = `/reports/daily/export?${qs ? `${qs}&` : ""}include_payments=${includePayments}`;
      const response = await api.get(requestUrl, {
        responseType: "blob"
      });
      const blob = new Blob([response.data], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `daily-report-${new Date().toISOString().slice(0, 10)}.xlsx`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      setStatus({ kind: "success", message: "הקובץ הוכן להורדה" });
    } catch (error) {
      setStatus({ kind: "error", message: formatApiError(error) });
    } finally {
      setIsExporting(false);
    }
  };

  const downloadSummaryReport = async () => {
    setStatus(null);
    setIsExporting(true);
    try {
      const qs = filters.toString();
      const requestUrl = `/reports/export?${qs ? `${qs}&` : ""}include_payments=${includePayments}`;
      const response = await api.get(requestUrl, { responseType: "blob" });
      const blob = new Blob([response.data], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      });
      const urlObject = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = urlObject;
      link.download = `summary-report-${new Date().toISOString().slice(0, 10)}.xlsx`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(urlObject);
      setStatus({ kind: "success", message: "הקובץ הוכן להורדה" });
    } catch (error) {
      setStatus({ kind: "error", message: formatApiError(error) });
    } finally {
      setIsExporting(false);
    }
  };

  const toInputValue = (iso: string) => {
    const date = new Date(iso);
    const tzOffset = date.getTimezoneOffset();
    const local = new Date(date.getTime() - tzOffset * 60000);
    return local.toISOString().slice(0, 16);
  };

  const toNaiveIsoString = (value: string) => {
    if (!value) return value;
    if (value.length === 16) return `${value}:00`;
    if (value.length === 19) return value;
    return value;
  };

  const resetEditingState = () => {
    setEditingEntryId(null);
    setEditClockIn("");
    setEditClockOut("");
  };

  useEffect(() => {
    if (!schema_ok) {
      resetEditingState();
    }
  }, [schema_ok]);

  const startEditingShift = (shift: DailyShift) => {
    if (!schema_ok) {
      setDailyStatus({ kind: "error", message: "יש לעדכן את סכימת בסיס הנתונים לפני עריכת משמרות" });
      return;
    }
    setDailyStatus(null);
    setEditingEntryId(shift.entry_id);
    setEditClockIn(toInputValue(shift.clock_in));
    setEditClockOut(toInputValue(shift.clock_out));
  };

  const openPinModal = (config: PinModalConfig) => {
    setPinValue("");
    setPinError(null);
    setPinModal(config);
  };

  const performSaveShift = async (pin: string) => {
    if (!editingEntryId) return;
    setIsSavingEntry(true);
    setDailyStatus(null);
    try {
      await api.put(`/time-entries/${editingEntryId}`, {
        pin: pin.trim(),
        clock_in: toNaiveIsoString(editClockIn),
        clock_out: toNaiveIsoString(editClockOut)
      });
      await runReport();
      setDailyStatus({ kind: "success", message: "המשמרת עודכנה בהצלחה" });
      resetEditingState();
    } catch (error) {
      setDailyStatus({ kind: "error", message: formatApiError(error) });
      throw error;
    } finally {
      setIsSavingEntry(false);
    }
  };

  const saveShiftChanges = () => {
    if (!editingEntryId) {
      return;
    }
    if (!schema_ok) {
      setDailyStatus({ kind: "error", message: "יש לעדכן את סכימת בסיס הנתונים לפני עריכת משמרות" });
      return;
    }
    if (!editClockIn || !editClockOut) {
      setDailyStatus({ kind: "error", message: "יש להזין זמני כניסה ויציאה תקינים" });
      return;
    }
    openPinModal({
      title: "אימות עדכון משמרת",
      confirmLabel: "עדכון",
      onConfirm: async (pin) => performSaveShift(pin)
    });
  };

  const cancelShiftEditing = () => {
    resetEditingState();
    setDailyStatus(null);
  };

  const performDeleteShift = async (shift: DailyShift, pin: string) => {
    setIsSavingEntry(true);
    setDailyStatus(null);
    try {
      await api.delete(`/time-entries/${shift.entry_id}`, {
        data: { pin: pin.trim() }
      });
      if (editingEntryId === shift.entry_id) {
        resetEditingState();
      }
      await runReport();
      setDailyStatus({ kind: "success", message: "המשמרת נמחקה" });
    } catch (error) {
      setDailyStatus({ kind: "error", message: formatApiError(error) });
      throw error;
    } finally {
      setIsSavingEntry(false);
    }
  };

  const closePinModal = () => {
    setPinModal(null);
    setPinValue("");
    setPinError(null);
  };

  const requestDeleteShift = (shift: DailyShift) => {
    if (!schema_ok) {
      setDailyStatus({ kind: "error", message: "יש לעדכן את סכימת בסיס הנתונים לפני מחיקת משמרות" });
      return;
    }
    openPinModal({
      title: "אימות מחיקת משמרת",
      confirmLabel: "מחיקה",
      message: "המחיקה בלתי הפיכה. האם להמשיך?",
      onConfirm: async (pin) => performDeleteShift(shift, pin)
    });
  };

  const handlePinSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!pinModal) return;
    if (!pinValue.trim()) {
      setPinError("נא להזין קוד PIN");
      return;
    }
    setIsConfirmingPin(true);
    setPinError(null);
    try {
      await pinModal.onConfirm(pinValue.trim());
      closePinModal();
    } catch (error) {
      setPinError(formatApiError(error));
    } finally {
      setIsConfirmingPin(false);
    }
  };

  const renderSummary = () => {
    if (!summaryReport) {
      return <p style={{ marginTop: "1rem" }}>הפעילו דוח כדי לצפות בנתונים.</p>;
    }

    return (
      <div style={{ marginTop: "1.5rem" }}>
        <h3>
          תקופה: {summaryReport.range_start} – {summaryReport.range_end}
        </h3>
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>שם העובד</th>
                <th>מספר ת"ז</th>
                <th>סה"כ שעות</th>
                <th>שכר שעתי</th>
                <th>שכר משוער</th>
              </tr>
            </thead>
            <tbody>
              {summaryReport.rows.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ textAlign: "center", padding: "1rem" }}>
                    לא נמצאו שעות בתקופה שנבחרה.
                  </td>
                </tr>
              ) : (
                summaryReport.rows.map((row) => (
                  <tr key={row.employee_id}>
                    <td>{row.full_name}</td>
                    <td>{row.id_number ?? ""}</td>
                    <td>{formatSecondsToHHMM(row.total_seconds)}</td>
                    <td>{currencyFormatter.format(Number(row.hourly_rate ?? 0))}</td>
                    <td>{currencyFormatter.format(row.total_pay)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  const renderDaily = () => {
    if (!dailyReport) {
      return <p style={{ marginTop: "1rem" }}>הפעילו דוח כדי לצפות בנתונים.</p>;
    }

    return (
      <div style={{ marginTop: "1.5rem" }}>
        <h3>
          יומן משמרות: {dailyReport.range_start} – {dailyReport.range_end}
        </h3>
        {!schema_ok && (
          <div className="status error" style={{ marginBottom: "1rem" }}>
            גרסת סכימת בסיס הנתונים אינה מעודכנת. הפעלו "יצירת/עדכון סכימה" במסך ההגדרות כדי לאפשר עריכת משמרות.
          </div>
        )}
        {dailyStatus && (
          <div className={`status ${dailyStatus.kind}`} style={{ marginBottom: "1rem" }}>
            {dailyStatus.message}
          </div>
        )}
        {dailyReport.employees.length === 0 ? (
          <p>לא נמצאו משמרות בתאריכים שנבחרו.</p>
        ) : (
          dailyReport.employees.map((employee) => (
            <div key={employee.employee_id} className="card" style={{ background: "#f8fafc" }}>
              <div className="section-title">
                <div>
                  <h4 style={{ margin: 0 }}>{employee.full_name}</h4>
                  {employee.id_number && (
                    <div style={{ fontSize: "0.85rem", color: "#475467" }}>מספר ת"ז: {employee.id_number}</div>
                  )}
                </div>
                <span style={{ fontSize: "0.9rem", color: "#475467" }}>{employee.shifts.length} משמרות</span>
              </div>
              <div className="table-wrapper">
                <table className="table">
                  <thead>
                    <tr>
                      <th>תאריך</th>
                      <th>כניסה</th>
                      <th>יציאה</th>
                      <th>משך (HH:MM)</th>
                      <th style={{ minWidth: "160px" }}>פעולות</th>
                    </tr>
                  </thead>
                  <tbody>
                    {employee.shifts.map((shift) => {
                      const isEditing = schema_ok && editingEntryId === shift.entry_id;
                      let durationPreview: number | string = formatMinutesToHHMM(shift.duration_minutes);
                      if (isEditing) {
                        if (!editClockIn || !editClockOut) {
                          durationPreview = "-";
                        } else {
                          const startMs = new Date(editClockIn).getTime();
                          const endMs = new Date(editClockOut).getTime();
                          durationPreview = Number.isNaN(startMs) || Number.isNaN(endMs)
                            ? "-"
                            : formatMinutesToHHMM(Math.max(0, Math.round((endMs - startMs) / 60000)));
                        }
                      }

                      return (
                        <tr key={shift.entry_id} style={isEditing ? { background: "#eef2ff" } : undefined}>
                          <td>{format(new Date(shift.shift_date), "dd.MM.yyyy", { locale: he })}</td>
                          <td>
                            {isEditing ? (
                              <input
                                type="datetime-local"
                                value={editClockIn}
                                onChange={(event) => setEditClockIn(event.target.value)}
                                style={{ minWidth: "200px" }}
                              />
                            ) : (
                              format(new Date(shift.clock_in), "HH:mm", { locale: he })
                            )}
                          </td>
                          <td>
                            {isEditing ? (
                              <input
                                type="datetime-local"
                                value={editClockOut}
                                onChange={(event) => setEditClockOut(event.target.value)}
                                style={{ minWidth: "200px" }}
                              />
                            ) : (
                              format(new Date(shift.clock_out), "HH:mm", { locale: he })
                            )}
                          </td>
                          <td>{durationPreview}</td>
                          <td>
                            {isEditing ? (
                              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                                <button
                                  className="primary"
                                  type="button"
                                  disabled={isSavingEntry}
                                  onClick={saveShiftChanges}
                                >
                                  שמירה
                                </button>
                                <button
                                  className="secondary"
                                  type="button"
                                  onClick={cancelShiftEditing}
                                  disabled={isSavingEntry}
                                >
                                  ביטול
                                </button>
                              </div>
                            ) : (
                              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                                <button
                                  className="secondary"
                                  type="button"
                                  onClick={() => startEditingShift(shift)}
                                  disabled={!schema_ok || isSavingEntry}
                                >
                                  עריכה
                                </button>
                                <button
                                  className="secondary"
                                  type="button"
                                  onClick={() => requestDeleteShift(shift)}
                                  disabled={!schema_ok || isSavingEntry}
                                >
                                  מחיקה
                                </button>
                              </div>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ))
        )}
      </div>
    );
  };

  return (
    <div className="card">
      <h2>דוחות</h2>
      <p>הריצו סיכום חודשי או צפייה יומית מפורטת עבור העובדים.</p>

      <div className="card" style={{ background: "#f9fbff" }}>
        <div className="input-row">
          <div>
            <label>סוג דוח</label>
            <select value={reportType} onChange={(event) => setReportType(event.target.value as ReportType)}>
              <option value="summary">סיכום שעות</option>
              <option value="daily">יומן יומי</option>
            </select>
          </div>
          <div>
            <label>טווח</label>
            <select value={mode} onChange={(event) => setMode(event.target.value as Mode)}>
              <option value="month">חודש קלנדרי</option>
              <option value="custom">טווח מותאם אישית</option>
            </select>
          </div>
          {mode === "month" ? (
            <div>
              <label>חודש</label>
              <input type="month" value={selectedMonth} onChange={(event) => setSelectedMonth(event.target.value)} />
            </div>
          ) : (
            <>
              <div>
                <label>תאריך התחלה</label>
                <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
              </div>
              <div>
                <label>תאריך סיום</label>
                <input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
              </div>
            </>
          )}
          <div>
            <label>עובד</label>
            <select value={employeeId} onChange={(event) => setEmployeeId(event.target.value)}>
              <option value="all">כל העובדים</option>
              {employees.map((employee) => (
                <option key={employee.id} value={employee.id}>
                  {employee.full_name}
                  {employee.id_number ? ` (${employee.id_number})` : ""}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "center" }}>
          <button className="primary" style={{ marginTop: "1rem" }} onClick={runReport}>
            הפעלת דוח
          </button>
          <button
            className="secondary"
            style={{ marginTop: "1rem" }}
            onClick={reportType === "daily" ? downloadDailyReport : downloadSummaryReport}
            disabled={isExporting}
          >
            {isExporting ? "מכין קובץ..." : "ייצוא לאקסל"}
          </button>
          <label style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginTop: "1rem" }}>
            <input
              type="checkbox"
              checked={includePayments}
              onChange={(event) => setIncludePayments(event.target.checked)}
            />
            לכלול חישובי שכר בקובץ
          </label>
        </div>
      </div>

      {pinModal && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <form className="modal" onSubmit={handlePinSubmit}>
            <h3>{pinModal.title}</h3>
            {pinModal.message && <p style={{ marginTop: 0 }}>{pinModal.message}</p>}
            <label htmlFor="adminPin">קוד PIN</label>
            <input
              id="adminPin"
              type="password"
              value={pinValue}
              onChange={(event) => setPinValue(event.target.value)}
              autoFocus
              disabled={isConfirmingPin || isSavingEntry}
              placeholder="הזינו את קוד ה-PIN"
              minLength={4}
              maxLength={12}
              required
            />
            {pinError && (
              <div className="status error" style={{ marginTop: "0.75rem" }}>
                {pinError}
              </div>
            )}
            <div className="modal-actions">
              <button
                type="button"
                className="secondary"
                onClick={closePinModal}
                disabled={isConfirmingPin}
              >
                ביטול
              </button>
              <button
                type="submit"
                className="primary"
                disabled={isConfirmingPin || isSavingEntry}
              >
                {isConfirmingPin ? "מאמת..." : pinModal.confirmLabel}
              </button>
            </div>
          </form>
        </div>
      )}

      {status && <div className={`status ${status.kind}`}>{status.message}</div>}

      {reportType === "summary" ? renderSummary() : renderDaily()}
    </div>
  );
};

export default DashboardPage;
