import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, Lock, User, AlertCircle, ArrowLeft, ShieldCheck } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export const LoginPage: React.FC = () => {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('admin123');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const success = await login({ username, password });
      if (success) {
        navigate('/');
      }
    } catch (err: any) {
      setError(err.message || 'خطا در ورود به حساب کاربری');
    } finally {
      setLoading(false);
    }
  };

  const setDemoCredentials = () => {
    setUsername('admin');
    setPassword('admin123');
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4 relative overflow-hidden font-sans selection:bg-primary/20 selection:text-primary">
      {/* Background Cyber Glowing Circles */}
      <div className="absolute top-1/4 -right-20 w-96 h-96 bg-primary/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 -left-20 w-96 h-96 bg-secondary/15 rounded-full blur-3xl pointer-events-none" />

      {/* Login Card */}
      <div className="w-full max-w-md glass-panel p-8 rounded-3xl relative z-10 shadow-2xl border border-border">
        {/* Brand Icon */}
        <div className="flex flex-col items-center text-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-secondary to-primary flex items-center justify-center shadow-glow-primary mb-4 text-primary-text">
            <Sparkles className="w-7 h-7 text-primary-text" />
          </div>
          <h2 className="text-2xl font-black text-mainText tracking-tight font-mono">
            OX-LOADOUT
          </h2>
          <p className="text-xs text-mainText-muted mt-1.5 font-medium">
            ورود به پنل مدیریت هوشمند اتچمنت‌های کالاف دیوتی موبایل
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-center gap-3 text-rose-500 text-xs">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-xs font-semibold text-mainText-muted mb-2">
              نام کاربری یا آیدی عددی تلگرام
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 right-0 pr-3.5 flex items-center pointer-events-none text-mainText-subtle">
                <User className="w-4 h-4" />
              </div>
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin یا 123456789"
                className="w-full pr-10 pl-4 py-3 bg-card border border-border rounded-xl text-mainText text-sm focus:outline-none focus:border-primary transition-all font-sans"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-mainText-muted mb-2">
              رمز عبور ادمین
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 right-0 pr-3.5 flex items-center pointer-events-none text-mainText-subtle">
                <Lock className="w-4 h-4" />
              </div>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full pr-10 pl-4 py-3 bg-card border border-border rounded-xl text-mainText text-sm focus:outline-none focus:border-primary transition-all font-mono"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3.5 px-4 rounded-xl bg-primary hover:bg-primary-hover text-primary-text font-black text-sm shadow-glow-primary transition-all duration-200 flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer"
          >
            {loading ? (
              <span className="w-5 h-5 border-2 border-primary-text border-t-transparent rounded-full animate-spin" />
            ) : (
              <>
                <span>ورود به پنل مدیریت</span>
                <ArrowLeft className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        {/* Quick Demo Access Helper */}
        <div className="mt-8 pt-6 border-t border-border text-center">
          <button
            type="button"
            onClick={setDemoCredentials}
            className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline font-bold transition-colors cursor-pointer"
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>پر کردن اطلاعات ورود پیش‌فرض ادمین (admin / admin123)</span>
          </button>
        </div>
      </div>
    </div>
  );
};
