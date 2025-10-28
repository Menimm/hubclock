import React from "react";
import { NavigateFunction, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { PinPrompt } from "./PinPrompt";

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isUnlocked } = useAuth();
  const location = useLocation();
  const navigate: NavigateFunction = useNavigate();

  if (isUnlocked) {
    return <>{children}</>;
  }

  return <PinPrompt onSuccess={() => navigate(location.pathname)} />;
};
