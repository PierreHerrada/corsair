import { Route, Routes, useLocation } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { useTheme } from "./hooks/useTheme";
import Board from "./pages/Board";
import Chat from "./pages/Chat";
import Dashboard from "./pages/Dashboard";
import Datadog from "./pages/Datadog";
import Login from "./pages/Login";
import Logs from "./pages/Logs";
import Settings from "./pages/Settings";
import Status from "./pages/Status";
import TaskDetail from "./pages/TaskDetail";

function AppContent() {
  const { theme, toggleTheme } = useTheme();
  const { isAuthenticated, logout } = useAuth();
  const location = useLocation();
  const isLoginPage = location.pathname === "/login";

  return (
    <div className="min-h-screen bg-deep text-white">
      {!isLoginPage && isAuthenticated && (
        <nav className="bg-navy border-b border-foam/8 px-6 py-3 flex items-center gap-6">
          <img src="/logo.svg" alt="Corsair" className="h-8 w-8" />
          <span className="text-foam font-semibold text-lg">corsair</span>
          <a href="/" className="text-mist hover:text-white text-sm">
            Board
          </a>
          <a href="/dashboard" className="text-mist hover:text-white text-sm">
            Dashboard
          </a>
          <a href="/status" className="text-mist hover:text-white text-sm">
            Status
          </a>
          <a href="/chat" className="text-mist hover:text-white text-sm">
            Chat
          </a>
          <a href="/datadog" className="text-mist hover:text-white text-sm">
            Datadog
          </a>
          <a href="/logs" className="text-mist hover:text-white text-sm">
            Logs
          </a>
          <a href="/settings" className="text-mist hover:text-white text-sm">
            Settings
          </a>
          <button
            onClick={toggleTheme}
            className="ml-auto text-mist hover:text-white text-xl cursor-pointer"
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          >
            {theme === "dark" ? "\u2600\uFE0F" : "\uD83C\uDF19"}
          </button>
          <button
            onClick={logout}
            className="text-mist hover:text-white text-sm cursor-pointer"
          >
            Logout
          </button>
        </nav>
      )}
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Board />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/status"
          element={
            <ProtectedRoute>
              <Status />
            </ProtectedRoute>
          }
        />
        <Route
          path="/chat"
          element={
            <ProtectedRoute>
              <Chat />
            </ProtectedRoute>
          }
        />
        <Route
          path="/datadog"
          element={
            <ProtectedRoute>
              <Datadog />
            </ProtectedRoute>
          }
        />
        <Route
          path="/tasks/:taskId"
          element={
            <ProtectedRoute>
              <TaskDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/logs"
          element={
            <ProtectedRoute>
              <Logs />
            </ProtectedRoute>
          }
        />
        <Route
          path="/settings"
          element={
            <ProtectedRoute>
              <Settings />
            </ProtectedRoute>
          }
        />
      </Routes>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
