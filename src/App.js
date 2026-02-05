import React, { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, useLocation, useNavigate, Navigate } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import { AdminDataProvider } from "./contexts/AdminDataContext";
import { ThemeProvider } from "./contexts/ThemeContext";
import FeedbackButton from "./components/FeedbackButton";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Exam from "./pages/Exam";
import Results from "./pages/Results";
import History from "./pages/History";
import Subjects from "./pages/Subjects";
import SubjectPractice from "./pages/SubjectPractice";
import Plans from "./pages/Plans";
import Subscription from "./pages/Subscription";
import PaymentSuccess from "./pages/PaymentSuccess";
import PaymentCancel from "./pages/PaymentCancel";
import AdminDashboard from "./pages/admin/AdminDashboard";
import AdminQuestions from "./pages/admin/AdminQuestions";
import AdminSimulators from "./pages/admin/AdminSimulators";
import AdminUsers from "./pages/admin/AdminUsers";
import AdminReports from "./pages/admin/AdminReports";
import AdminReadingTexts from "./pages/admin/AdminReadingTexts";
import AdminFeedback from "./pages/admin/AdminFeedback";
import "./App.css";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "http://localhost:8000";
const API = `${BACKEND_URL}/api`;

// Auth Context
export const AuthContext = React.createContext(null);

// Protected Route Component
const ProtectedRoute = ({ children, adminOnly = false }) => {
  const [authState, setAuthState] = useState({ loading: true, authenticated: false, user: null });
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    const checkAuth = async () => {
      const storedUser = localStorage.getItem("user");
      const isAuth = localStorage.getItem("isAuthenticated");

      if (storedUser && isAuth === "true") {
        try {
          // Verify with backend
          const response = await fetch(`${API}/auth/me`, {
            credentials: "include",
            headers: {
              "Authorization": `Bearer ${localStorage.getItem("token") || ""}`
            }
          });

          if (response.ok) {
            const user = await response.json();
            setAuthState({ loading: false, authenticated: true, user });
            return;
          }
        } catch (error) {
          // Auth check failed silently
        }
      }

      // Try token from localStorage
      const token = localStorage.getItem("token");
      if (token) {
        try {
          const response = await fetch(`${API}/auth/me`, {
            headers: { "Authorization": `Bearer ${token}` }
          });

          if (response.ok) {
            const user = await response.json();
            setAuthState({ loading: false, authenticated: true, user });
            return;
          }
        } catch (error) {
          // Token auth failed silently
        }
      }

      setAuthState({ loading: false, authenticated: false, user: null });
    };

    checkAuth();
  }, [location]);

  if (authState.loading) {
    return (
      <div className="min-h-screen bg-[#F5F7FA] flex items-center justify-center">
        <div className="w-12 h-12 border-4 border-[#0A2540] border-t-[#F2B705] rounded-full animate-spin"></div>
      </div>
    );
  }

  if (!authState.authenticated) {
    return <Navigate to="/login" replace />;
  }

  if (adminOnly && authState.user?.role !== "admin") {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <AuthContext.Provider value={{ user: authState.user, setUser: (u) => setAuthState(s => ({ ...s, user: u })) }}>
      {children}
      <FeedbackButton />
    </AuthContext.Provider>
  );
};

// Admin Routes Wrapper with Data Provider
const AdminRoutes = ({ children }) => (
  <ProtectedRoute adminOnly>
    <AdminDataProvider>
      {children}
    </AdminDataProvider>
  </ProtectedRoute>
);

// App Router
const AppRouter = () => {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
      <Route path="/simulators" element={<Navigate to="/dashboard" replace />} />
      <Route path="/exam/:simulatorId" element={<ProtectedRoute><Exam /></ProtectedRoute>} />
      <Route path="/results/:attemptId" element={<ProtectedRoute><Results /></ProtectedRoute>} />
      <Route path="/history" element={<ProtectedRoute><History /></ProtectedRoute>} />
      <Route path="/subjects" element={<ProtectedRoute><Subjects /></ProtectedRoute>} />
      <Route path="/subjects/:subjectId" element={<ProtectedRoute><SubjectPractice /></ProtectedRoute>} />
      <Route path="/plans" element={<ProtectedRoute><Plans /></ProtectedRoute>} />
      <Route path="/subscription" element={<ProtectedRoute><Subscription /></ProtectedRoute>} />
      <Route path="/payment/success" element={<ProtectedRoute><PaymentSuccess /></ProtectedRoute>} />
      <Route path="/payment/cancel" element={<ProtectedRoute><PaymentCancel /></ProtectedRoute>} />
      <Route path="/admin" element={<AdminRoutes><AdminDashboard /></AdminRoutes>} />
      <Route path="/admin/questions" element={<AdminRoutes><AdminQuestions /></AdminRoutes>} />
      <Route path="/admin/simulators" element={<AdminRoutes><AdminSimulators /></AdminRoutes>} />
      <Route path="/admin/users" element={<AdminRoutes><AdminUsers /></AdminRoutes>} />
      <Route path="/admin/reports" element={<AdminRoutes><AdminReports /></AdminRoutes>} />
      <Route path="/admin/reading-texts" element={<AdminRoutes><AdminReadingTexts /></AdminRoutes>} />
      <Route path="/admin/feedback" element={<AdminRoutes><AdminFeedback /></AdminRoutes>} />
    </Routes>
  );
};

function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Toaster position="top-right" richColors />
        <AppRouter />
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
export { API, BACKEND_URL };
