import React, { useEffect, useState } from "react";
import { api, formatApiError } from "../api/client";

interface Employee {
  id: number;
  full_name: string;
  employee_code: string;
  id_number?: string | null;
  hourly_rate: number;
  active: boolean;
}

interface ManualEntryPayload {
  employee_id: number;
  clock_in: string;
  clock_out: string;
}

const initialEmployee: Omit<Employee, "id"> = {
  full_name: "",
  employee_code: "",
  id_number: "",
  hourly_rate: 0,
  active: true
};

const EmployeesPage: React.FC = () => {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [form, setForm] = useState(initialEmployee);
  const [status, setStatus] = useState<{ kind: "success" | "error"; message: string } | null>(null);
  const [manualEntry, setManualEntry] = useState<ManualEntryPayload>({ employee_id: 0, clock_in: "", clock_out: "" });
  const [isImporting, setIsImporting] = useState(false);
  const [replaceExisting, setReplaceExisting] = useState(false);

  const loadEmployees = async () => {
    try {
      const response = await api.get<Employee[]>("/employees");
      setEmployees(response.data);
    } catch (error) {
      setStatus({ kind: "error", message: formatApiError(error) });
    }
  };

  useEffect(() => {
    loadEmployees();
  }, []);

  const submitNewEmployee = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      await api.post<Employee>("/employees", form);
      setForm(initialEmployee);
      setStatus({ kind: "success", message: "העובד נוסף בהצלחה" });
      loadEmployees();
    } catch (error) {
      setStatus({ kind: "error", message: formatApiError(error) });
    }
  };

  const updateEmployee = async (employeeId: number, updates: Partial<Employee>) => {
    try {
      const payload: Record<string, unknown> = {};
      if (updates.full_name !== undefined) payload.full_name = updates.full_name;
      if (updates.employee_code !== undefined) payload.employee_code = updates.employee_code;
      if (updates.id_number !== undefined) {
        if (updates.id_number === "" || updates.id_number === null) {
          payload.id_number = null;
        } else {
          payload.id_number = updates.id_number;
        }
      }
      if (updates.hourly_rate !== undefined) payload.hourly_rate = updates.hourly_rate;
      if (updates.active !== undefined) payload.active = updates.active;
      const response = await api.put<Employee>(`/employees/${employeeId}`, payload);
      setEmployees((prev) => prev.map((item) => (item.id === employeeId ? response.data : item)));
      setStatus({ kind: "success", message: "פרטי העובד עודכנו" });
    } catch (error) {
      setStatus({ kind: "error", message: formatApiError(error) });
    }
  };

  const submitManualEntry = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!manualEntry.employee_id) {
      setStatus({ kind: "error", message: "בחרו עובד לפני שמירת משמרת" });
      return;
    }
    try {
      await api.post(`/employees/${manualEntry.employee_id}/entries`, {
        employee_id: manualEntry.employee_id,
        clock_in: new Date(manualEntry.clock_in).toISOString(),
        clock_out: new Date(manualEntry.clock_out).toISOString(),
        manual: true
      });
      setManualEntry((prev) => ({ ...prev, clock_in: "", clock_out: "" }));
      setStatus({ kind: "success", message: "המשמרת הידנית נשמרה" });
    } catch (error) {
      setStatus({ kind: "error", message: formatApiError(error) });
    }
  };

  const exportEmployees = async () => {
    try {
      const response = await api.get("/employees/export");
      const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: "application/json" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `employees-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      setStatus({ kind: "success", message: "נתוני העובדים יוצאו לקובץ" });
    } catch (error) {
      setStatus({ kind: "error", message: formatApiError(error) });
    }
  };

  const importEmployees = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setIsImporting(true);
    try {
      const text = await file.text();
      const payload = JSON.parse(text);
      await api.post("/employees/import", {
        replace_existing: replaceExisting,
        ...payload
      });
      setStatus({ kind: "success", message: "הנתונים נטענו בהצלחה" });
      await loadEmployees();
    } catch (error) {
      setStatus({ kind: "error", message: formatApiError(error) });
    } finally {
      setIsImporting(false);
      event.target.value = "";
    }
  };

  return (
    <div className="card">
      <h2>ניהול עובדים</h2>
      <p>הוסיפו עובדים חדשים, עדכנו שכר שעתי והשלימו משמרות שנשכחו.</p>

      {status && <div className={`status ${status.kind}`}>{status.message}</div>}

      <section className="card">
        <h3>הוספת עובד חדש</h3>
        <form onSubmit={submitNewEmployee} className="input-row">
          <div>
            <label htmlFor="fullName">שם מלא</label>
            <input
              id="fullName"
              value={form.full_name}
              onChange={(event) => setForm((prev) => ({ ...prev, full_name: event.target.value }))}
              required
            />
          </div>
          <div>
            <label htmlFor="employeeCode">מספר עובד</label>
            <input
              id="employeeCode"
              value={form.employee_code}
              onChange={(event) => setForm((prev) => ({ ...prev, employee_code: event.target.value }))}
              required
            />
          </div>
          <div>
            <label htmlFor="idNumber">מספר ת"ז</label>
            <input
              id="idNumber"
              value={form.id_number ?? ""}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, id_number: event.target.value.replace(/[^0-9]/g, "") }))
              }
              maxLength={32}
              inputMode="numeric"
              placeholder="ספרות בלבד"
              required
            />
          </div>
          <div>
            <label htmlFor="hourlyRate">שכר שעתי</label>
            <input
              id="hourlyRate"
              type="number"
              min="0"
              step="0.25"
              value={form.hourly_rate}
              onChange={(event) => setForm((prev) => ({ ...prev, hourly_rate: Number(event.target.value) }))}
              required
            />
          </div>
          <div style={{ display: "flex", alignItems: "flex-end" }}>
            <button className="primary" type="submit">שמירת עובד</button>
          </div>
        </form>
      </section>

      <section className="card">
        <h3>רשימת עובדים</h3>
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>שם</th>
                <th>מספר עובד</th>
                <th>מספר ת"ז</th>
                <th>שכר שעתי</th>
                <th>סטטוס</th>
                <th>פעולות</th>
              </tr>
            </thead>
            <tbody>
              {employees.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", padding: "1rem" }}>
                    התחילו בהוספת העובדים.
                  </td>
                </tr>
              ) : (
                employees.map((employee) => (
                  <tr key={employee.id}>
                    <td>
                      <input
                        value={employee.full_name}
                        onChange={(event) =>
                          setEmployees((prev) =>
                            prev.map((item) =>
                              item.id === employee.id
                                ? { ...item, full_name: event.target.value }
                                : item
                            )
                          )
                        }
                      />
                    </td>
                    <td>
                      <input
                        value={employee.employee_code}
                        maxLength={32}
                        onChange={(event) =>
                          setEmployees((prev) =>
                            prev.map((item) =>
                              item.id === employee.id
                                ? { ...item, employee_code: event.target.value }
                                : item
                            )
                          )
                        }
                      />
                    </td>
                    <td>
                      <input
                        value={employee.id_number ?? ""}
                        maxLength={32}
                        inputMode="numeric"
                        onChange={(event) =>
                          setEmployees((prev) =>
                            prev.map((item) =>
                              item.id === employee.id
                                ? { ...item, id_number: event.target.value.replace(/[^0-9]/g, "") }
                                : item
                            )
                          )
                        }
                      />
                    </td>
                    <td>
                      <input
                        type="number"
                        min="0"
                        step="0.25"
                        value={employee.hourly_rate}
                        onChange={(event) =>
                          setEmployees((prev) =>
                            prev.map((item) =>
                              item.id === employee.id
                                ? { ...item, hourly_rate: Number(event.target.value) }
                                : item
                            )
                          )
                        }
                        style={{ width: "6rem" }}
                      />
                    </td>
                    <td>
                      <select
                        value={employee.active ? "active" : "inactive"}
                        onChange={(event) =>
                          setEmployees((prev) =>
                            prev.map((item) =>
                              item.id === employee.id
                                ? { ...item, active: event.target.value === "active" }
                                : item
                            )
                          )
                        }
                      >
                        <option value="active">פעיל</option>
                        <option value="inactive">לא פעיל</option>
                      </select>
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: "0.5rem" }}>
                        <button
                          className="primary"
                          type="button"
                          onClick={() =>
                            updateEmployee(employee.id, {
                              full_name: employee.full_name,
                              employee_code: employee.employee_code,
                              id_number: employee.id_number ?? null,
                              hourly_rate: employee.hourly_rate,
                              active: employee.active
                            })
                          }
                        >
                          שמירה
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card">
        <h3>הוספת משמרת ידנית</h3>
        <form onSubmit={submitManualEntry} className="input-row">
          <div>
            <label>עובד</label>
            <select
              value={manualEntry.employee_id || ""}
              onChange={(event) =>
                setManualEntry((prev) => ({ ...prev, employee_id: Number(event.target.value) }))
              }
              required
            >
              <option value="" disabled>
                בחרו עובד
              </option>
              {employees.map((employee) => (
                <option key={employee.id} value={employee.id}>
                  {employee.full_name}
                  {employee.id_number ? ` (${employee.id_number})` : ""}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>שעת התחלה</label>
            <input
              type="datetime-local"
              value={manualEntry.clock_in}
              onChange={(event) => {
                const value = event.target.value;
                setManualEntry((prev) => ({
                  ...prev,
                  clock_in: value,
                  clock_out: prev.clock_out || value
                }));
              }}
              required
            />
          </div>
          <div>
            <label>שעת סיום</label>
            <input
              type="datetime-local"
              value={manualEntry.clock_out}
              onChange={(event) => setManualEntry((prev) => ({ ...prev, clock_out: event.target.value }))}
              required
            />
          </div>
          <div style={{ display: "flex", alignItems: "flex-end" }}>
            <button className="secondary" type="submit">
              שמירת משמרת
            </button>
          </div>
        </form>
      </section>

      <section className="card" style={{ background: "#f9fbff" }}>
        <h3>ייבוא וייצוא נתוני עובדים</h3>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "center" }}>
          <button className="secondary" type="button" onClick={exportEmployees}>
            ייצוא לקובץ JSON
          </button>
          <label className="secondary" style={{ padding: "0.55rem 1.2rem", cursor: "pointer" }}>
            ייבוא מקובץ JSON
            <input type="file" accept="application/json" onChange={importEmployees} hidden disabled={isImporting} />
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <input
              type="checkbox"
              checked={replaceExisting}
              onChange={(event) => setReplaceExisting(event.target.checked)}
            />
            להחליף נתונים קיימים
          </label>
        </div>
      </section>
    </div>
  );
};

export default EmployeesPage;
