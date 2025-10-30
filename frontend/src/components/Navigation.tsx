import React from "react";
import { format } from "date-fns";
import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useSettings } from "../context/SettingsContext";

export const Navigation: React.FC = () => {
  const { isUnlocked, lock } = useAuth();
  const { brand_name, theme_color } = useSettings();
  const title = brand_name || "העסק שלי";
  const accent = theme_color || "#1b3aa6";
  const todayLabel = format(new Date(), "dd/MM/yy");

  const linkStyle = ({ isActive }: { isActive: boolean }): React.CSSProperties => ({
    padding: "0.5rem 0.8rem",
    borderRadius: 8,
    fontWeight: 600,
    backgroundColor: isActive ? "rgba(255,255,255,0.22)" : "transparent",
    color: "#fff"
  });

  return (
    <header style={{ background: accent, color: "#fff" }}>
      <div className="container" style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
        <span style={{ fontWeight: 600, fontSize: "0.95rem" }}>{todayLabel}</span>
        <h1 style={{ margin: 0, fontSize: "1.5rem", fontWeight: 700 }}>{title}</h1>
        <nav>
          <NavLink to="/" end style={({ isActive }) => linkStyle({ isActive })}>
            שעון נוכחות
          </NavLink>
          <NavLink to="/dashboard" style={({ isActive }) => linkStyle({ isActive })}>
            דוחות
          </NavLink>
          <NavLink to="/employees" style={({ isActive }) => linkStyle({ isActive })}>
            עובדים
          </NavLink>
          <NavLink to="/settings" style={({ isActive }) => linkStyle({ isActive })}>
            הגדרות
          </NavLink>
        </nav>
        <div style={{ marginLeft: "auto" }}>
          {isUnlocked ? (
            <button className="secondary" onClick={lock} title="נעילת אזור הניהול">
              נעילת מנהל
            </button>
          ) : (
            <span className="badge">נעול</span>
          )}
        </div>
      </div>
    </header>
  );
};
