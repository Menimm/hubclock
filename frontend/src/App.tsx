import React from "react";
import { Route, Routes } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { Navigation } from "./components/Navigation";
import { ProtectedRoute } from "./components/ProtectedRoute";
import ClockPage from "./pages/ClockPage";
import DashboardPage from "./pages/DashboardPage";
import EmployeesPage from "./pages/EmployeesPage";
import SettingsPage from "./pages/SettingsPage";
import { SettingsProvider } from "./context/SettingsContext";

const App: React.FC = () => {
  return (
    <AuthProvider>
      <SettingsProvider>
        <Navigation />
        <main className="container">
          <Routes>
            <Route path="/" element={<ClockPage />} />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <DashboardPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/employees"
              element={
                <ProtectedRoute>
                  <EmployeesPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/settings"
              element={
                <ProtectedRoute>
                  <SettingsPage />
                </ProtectedRoute>
              }
            />
            <Route path="*" element={<ClockPage />} />
          </Routes>
        </main>
      </SettingsProvider>
    </AuthProvider>
  );
};

export default App;
