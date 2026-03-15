import { Navigate } from "react-router-dom";

export interface AuthUser {
  sub: string;
  email: string;
  name: string;
  picture: string;
  exp: number;
}

/** Decode JWT payload without verifying the signature (trust is on the backend). */
export function getStoredUser(): AuthUser | null {
  const token = localStorage.getItem("auth_token");
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split(".")[1])) as AuthUser;
    // Check expiry
    if (payload.exp && payload.exp < Date.now() / 1000) {
      localStorage.removeItem("auth_token");
      return null;
    }
    return payload;
  } catch {
    localStorage.removeItem("auth_token");
    return null;
  }
}

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const user = getStoredUser();
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
