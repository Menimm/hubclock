import React, { useEffect, useMemo, useState } from "react";
import { format } from "date-fns";
import { he } from "date-fns/locale";
import { api, formatApiError } from "../api/client";
import { useSettings } from "../context/SettingsContext";

interface Employee {
  id: number;
  full_name: string;
}

interface ReportRow {
  employee_id: number;
  full_name: string;
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
  shifts: DailyShift[];
}

interface DailyReportResponse {
  employees: DailyEmployeeReport[];
  range_start: string;
  range_end: string;
}

type Mode = "month" | "custom";
type ReportType = "summary" | "daily";

const DashboardPage: React.FC = () => {
  const { currency } = useSettings();
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [mode, setMode] = useState<Mode>("month");
  const [reportType, setReportType] = useState<ReportType>("summary");
  const [selectedMonth, setSelectedMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [employeeId, setEmployeeId] = useState<string>("all");
  const [summaryReport, setSummaryReport] = useState<ReportResponse | null>(null);
  const [dailyReport, setDailyReport] = useState<DailyReportResponse | null>(null);
  const [status, setStatus] = useState<{ kind: "success" | "error"; message: string } | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [includePayments, setIncludePayments] = useState(false);
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
                <th>סה"כ שעות</th>
                <th>שכר שעתי</th>
                <th>שכר משוער</th>
              </tr>
            </thead>
            <tbody>
              {summaryReport.rows.length === 0 ? (
                <tr>
                  <td colSpan={4} style={{ textAlign: "center", padding: "1rem" }}>
                    לא נמצאו שעות בתקופה שנבחרה.
                  </td>
                </tr>
              ) : (
                summaryReport.rows.map((row) => (
                  <tr key={row.employee_id}>
                    <td>{row.full_name}</td>
                    <td>{row.total_hours.toFixed(2)}</td>
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
        {dailyReport.employees.length === 0 ? (
          <p>לא נמצאו משמרות בתאריכים שנבחרו.</p>
        ) : (
          dailyReport.employees.map((employee) => (
            <div key={employee.employee_id} className="card" style={{ background: "#f8fafc" }}>
              <div className="section-title">
                <h4 style={{ margin: 0 }}>{employee.full_name}</h4>
                <span style={{ fontSize: "0.9rem", color: "#475467" }}>{employee.shifts.length} משמרות</span>
              </div>
              <div className="table-wrapper">
                <table className="table">
                  <thead>
                    <tr>
                      <th>תאריך</th>
                      <th>כניסה</th>
                      <th>יציאה</th>
                      <th>משך (דקות)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {employee.shifts.map((shift) => (
                      <tr key={shift.entry_id}>
                        <td>{format(new Date(shift.shift_date), "dd.MM.yyyy", { locale: he })}</td>
                        <td>{format(new Date(shift.clock_in), "HH:mm", { locale: he })}</td>
                        <td>{format(new Date(shift.clock_out), "HH:mm", { locale: he })}</td>
                        <td>{shift.duration_minutes}</td>
                      </tr>
                    ))}
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

      {status && <div className={`status ${status.kind}`}>{status.message}</div>}

      {reportType === "summary" ? renderSummary() : renderDaily()}
    </div>
  );
};

export default DashboardPage;
