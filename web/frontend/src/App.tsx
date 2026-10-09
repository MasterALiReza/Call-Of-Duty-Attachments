import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { MainLayout } from './components/layout/MainLayout';
import { LoginPage } from './pages/Login/LoginPage';
import { DashboardPage } from './pages/Dashboard/DashboardPage';
import { AttachmentsPage } from './pages/Attachments/AttachmentsPage';
import { WeaponsPage } from './pages/Weapons/WeaponsPage';
import { SubmissionsPage } from './pages/Submissions/SubmissionsPage';
import { TicketsPage } from './pages/Tickets/TicketsPage';
import { BroadcastPage } from './pages/Broadcast/BroadcastPage';
import { SettingsPage } from './pages/Settings/SettingsPage';
import { ProfilePage } from './pages/Profile/ProfilePage';

const PrivateRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin shadow-glow-primary" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

export const App: React.FC = () => {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />

            <Route
              path="/"
              element={
                <PrivateRoute>
                  <MainLayout />
                </PrivateRoute>
              }
            >
              <Route index element={<DashboardPage />} />
              <Route path="attachments" element={<AttachmentsPage />} />
              <Route path="weapons" element={<WeaponsPage />} />
              <Route path="submissions" element={<SubmissionsPage />} />
              <Route path="tickets" element={<TicketsPage />} />
              <Route path="broadcast" element={<BroadcastPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="profile" element={<ProfilePage />} />
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
};
