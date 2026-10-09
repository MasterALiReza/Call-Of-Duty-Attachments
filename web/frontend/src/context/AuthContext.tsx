import React, { createContext, useContext, useState, useEffect } from 'react';
import { AdminUser, AuthResponse } from '../types';
import { api } from '../services/api';

interface AuthContextType {
  user: AdminUser | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: { username: string; password: string }) => Promise<boolean>;
  logout: () => void;
  hasPermission: (perm: string) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AdminUser | null>(() => {
    const saved = localStorage.getItem('ox_admin_user');
    return saved ? JSON.parse(saved) : null;
  });
  const [token, setToken] = useState<string | null>(() => {
    return localStorage.getItem('ox_admin_token');
  });
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const verifyAuth = async () => {
      if (token) {
        try {
          const res = await api.get('/auth/me');
          if (res.data && res.data.data) {
            setUser(res.data.data);
            localStorage.setItem('ox_admin_user', JSON.stringify(res.data.data));
          }
        } catch {
          logout();
        }
      }
      setIsLoading(false);
    };
    verifyAuth();
  }, [token]);

  const login = async (credentials: { username: string; password: string }): Promise<boolean> => {
    try {
      const res = await api.post<{ success: boolean; data: AuthResponse; message?: string }>('/auth/login', credentials);
      if (res.data && res.data.success && res.data.data) {
        const { access_token, user: userData } = res.data.data;
        setToken(access_token);
        setUser(userData);
        localStorage.setItem('ox_admin_token', access_token);
        localStorage.setItem('ox_admin_user', JSON.stringify(userData));
        return true;
      }
      return false;
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.response?.data?.message || 'خطا در ورود به پنل';
      throw new Error(msg);
    }
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('ox_admin_token');
    localStorage.removeItem('ox_admin_user');
  };

  const hasPermission = (perm: string): boolean => {
    if (!user) return false;
    if (user.is_super_admin || user.permissions.includes('all')) return true;
    return user.permissions.includes(perm);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token && !!user,
        isLoading,
        login,
        logout,
        hasPermission,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
