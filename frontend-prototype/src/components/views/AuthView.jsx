import React, { useState } from 'react';
import { useHousehold } from '../../context/HouseholdContext';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { 
  Home, 
  Lock, 
  Mail, 
  User, 
  ArrowRight, 
  Sun, 
  Moon, 
  Eye, 
  EyeOff, 
  ArrowLeft 
} from 'lucide-react';

export const AuthView = () => {
  const { 
    loginAs, 
    navigateTo, 
    authMode, 
    setAuthMode, 
    theme, 
    toggleTheme, 
    addToast, 
    addMember 
  } = useHousehold();

  // Sign In Form State — only 2 fields: Email and Password
  const [signInEmail, setSignInEmail] = useState('');
  const [signInPassword, setSignInPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // Register Form State — strictly 4 clean fields: Full Name, Household Name, Email, Password
  const [regName, setRegName] = useState('');
  const [regHouseholdName, setRegHouseholdName] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [showRegPassword, setShowRegPassword] = useState(false);

  const handleStandardSignIn = (e) => {
    e.preventDefault();
    // Log in to household dashboard
    loginAs('rajesh');
  };

  const handleRegisterHousehold = (e) => {
    e.preventDefault();
    if (!regName.trim() || !regHouseholdName.trim()) return;

    // Creator automatically defaults to Household Admin
    addMember({
      name: regName.trim(),
      relation: 'Parent / Head of House',
      role: 'Household Admin',
      avatar: '👤',
      availability: 'Available',
      statusText: `Admin of ${regHouseholdName.trim()}`,
      responsibilities: ['Household Administration & Coordination'],
    });

    addToast('Household Created', `${regHouseholdName} created with admin ${regName}`, 'success');
    navigateTo('app', 'today');
  };

  return (
    <div className="min-h-screen bg-[#F3F1EB] dark:bg-[#101210] text-[#171918] dark:text-[#EFF1EC] flex flex-col transition-colors">
      {/* Top Navigation Bar */}
      <header className="px-4 sm:px-8 py-3.5 flex items-center justify-between border-b border-[#D9D8D2] dark:border-[#2D322E] bg-[#FAF9F6] dark:bg-[#181B18]/90 backdrop-blur-md sticky top-0 z-30">
        <button
          onClick={() => navigateTo('landing')}
          className="flex items-center gap-1.5 text-xs font-semibold text-[#676B68] dark:text-[#969D96] hover:text-[#171918] dark:hover:text-[#EFF1EC] transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Home</span>
        </button>

        <div 
          onClick={() => navigateTo('landing')} 
          className="flex items-center gap-2 cursor-pointer select-none"
        >
          <div className="w-7 h-7 rounded-lg bg-[#5E9278] text-white flex items-center justify-center shadow-xs">
            <Home className="w-4 h-4" />
          </div>
          <span className="text-base font-bold tracking-tight text-[#171918] dark:text-[#EFF1EC]">
            HomeOps
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={toggleTheme}
            className="w-8 h-8 flex items-center justify-center rounded-lg border border-[#D9D8D2] dark:border-[#2D322E] bg-[#FAF9F6] dark:bg-[#181B18] text-[#676B68] dark:text-[#969D96] hover:text-[#171918] dark:hover:text-[#EFF1EC] transition-colors"
            title={theme === 'light' ? 'Switch to Dark mode' : 'Switch to Light mode'}
          >
            {theme === 'light' ? (
              <Moon className="w-3.5 h-3.5" />
            ) : (
              <Sun className="w-3.5 h-3.5 text-[#D19A4C]" />
            )}
          </button>
        </div>
      </header>

      {/* Main Authentication Container */}
      <main className="flex-1 flex items-center justify-center px-4 py-8 sm:py-12 animate-fade-in">
        <div className="w-full max-w-md space-y-5">
          {/* Clean Header Title */}
          <div className="text-center space-y-1">
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#171918] dark:text-[#EFF1EC]">
              {authMode === 'login' ? 'Welcome back' : 'Create your household'}
            </h1>
            <p className="text-xs sm:text-sm text-[#676B68] dark:text-[#969D96]">
              {authMode === 'login' 
                ? 'Sign in to access your family dashboard and schedule.'
                : 'Get started with a unified system for your home.'}
            </p>
          </div>

          {/* Simple Tab Switcher */}
          <div className="flex p-1 rounded-xl bg-black/5 dark:bg-white/5 border border-[#D9D8D2] dark:border-[#2D322E]">
            <button
              type="button"
              onClick={() => setAuthMode('login')}
              className={`flex-1 py-2 rounded-lg text-xs font-semibold transition-all ${
                authMode === 'login'
                  ? 'bg-white dark:bg-[#1E231F] text-[#171918] dark:text-[#EFF1EC] shadow-xs'
                  : 'text-[#676B68] dark:text-[#969D96] hover:text-[#171918]'
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => setAuthMode('register')}
              className={`flex-1 py-2 rounded-lg text-xs font-semibold transition-all ${
                authMode === 'register'
                  ? 'bg-white dark:bg-[#1E231F] text-[#171918] dark:text-[#EFF1EC] shadow-xs'
                  : 'text-[#676B68] dark:text-[#969D96] hover:text-[#171918]'
              }`}
            >
              Create Household
            </button>
          </div>

          {/* Standard Authentication Card */}
          <Card className="p-6 sm:p-7 bg-white dark:bg-[#181B18] shadow-elevated dark:shadow-elevated-dark border border-[#D9D8D2] dark:border-[#2D322E]">
            {authMode === 'login' ? (
              /* Standard Clean Sign In: Exactly 2 fields (Email, Password) */
              <form onSubmit={handleStandardSignIn} className="space-y-4 text-xs">
                <div>
                  <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1.5">
                    Email Address
                  </label>
                  <div className="relative">
                    <Mail className="w-4 h-4 text-[#676B68] dark:text-[#969D96] absolute left-3 top-1/2 -translate-y-1/2" />
                    <Input
                      type="email"
                      value={signInEmail}
                      onChange={(e) => setSignInEmail(e.target.value)}
                      placeholder="you@example.com"
                      className="pl-9"
                      required
                    />
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="font-medium text-[#171918] dark:text-[#EFF1EC]">
                      Password
                    </label>
                    <button
                      type="button"
                      onClick={() => addToast('Password Reset', 'Password reset instructions sent to your email.', 'info')}
                      className="text-[11px] text-[#5E9278] hover:underline"
                    >
                      Forgot password?
                    </button>
                  </div>
                  <div className="relative">
                    <Lock className="w-4 h-4 text-[#676B68] dark:text-[#969D96] absolute left-3 top-1/2 -translate-y-1/2" />
                    <Input
                      type={showPassword ? 'text' : 'password'}
                      value={signInPassword}
                      onChange={(e) => setSignInPassword(e.target.value)}
                      placeholder="••••••••••••"
                      className="pl-9 pr-9"
                      required
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-[#676B68] dark:text-[#969D96] hover:text-[#171918]"
                    >
                      {showPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>

                <Button
                  type="submit"
                  variant="primary"
                  size="md"
                  className="w-full font-bold h-11 text-sm mt-3"
                >
                  <span>Sign In</span>
                  <ArrowRight className="w-4 h-4" />
                </Button>

                <div className="text-center pt-2">
                  <p className="text-xs text-[#676B68] dark:text-[#969D96]">
                    Don't have a household yet?{' '}
                    <button
                      type="button"
                      onClick={() => setAuthMode('register')}
                      className="text-[#5E9278] font-semibold hover:underline"
                    >
                      Create Household
                    </button>
                  </p>
                </div>
              </form>
            ) : (
              /* Simplified Household Registration: Exactly 4 clean fields */
              <form onSubmit={handleRegisterHousehold} className="space-y-3.5 text-xs animate-fade-in">
                <div>
                  <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1.5">
                    Full Name
                  </label>
                  <div className="relative">
                    <User className="w-4 h-4 text-[#676B68] dark:text-[#969D96] absolute left-3 top-1/2 -translate-y-1/2" />
                    <Input
                      type="text"
                      value={regName}
                      onChange={(e) => setRegName(e.target.value)}
                      placeholder="e.g. Vikram Malhotra"
                      className="pl-9"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1.5">
                    Household Name
                  </label>
                  <div className="relative">
                    <Home className="w-4 h-4 text-[#676B68] dark:text-[#969D96] absolute left-3 top-1/2 -translate-y-1/2" />
                    <Input
                      type="text"
                      value={regHouseholdName}
                      onChange={(e) => setRegHouseholdName(e.target.value)}
                      placeholder="e.g. Malhotra Family"
                      className="pl-9"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1.5">
                    Email Address
                  </label>
                  <div className="relative">
                    <Mail className="w-4 h-4 text-[#676B68] dark:text-[#969D96] absolute left-3 top-1/2 -translate-y-1/2" />
                    <Input
                      type="email"
                      value={regEmail}
                      onChange={(e) => setRegEmail(e.target.value)}
                      placeholder="vikram@example.com"
                      className="pl-9"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1.5">
                    Password
                  </label>
                  <div className="relative">
                    <Lock className="w-4 h-4 text-[#676B68] dark:text-[#969D96] absolute left-3 top-1/2 -translate-y-1/2" />
                    <Input
                      type={showRegPassword ? 'text' : 'password'}
                      value={regPassword}
                      onChange={(e) => setRegPassword(e.target.value)}
                      placeholder="••••••••••••"
                      className="pl-9 pr-9"
                      required
                    />
                    <button
                      type="button"
                      onClick={() => setShowRegPassword(!showRegPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-[#676B68] dark:text-[#969D96] hover:text-[#171918]"
                    >
                      {showRegPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>

                <Button
                  type="submit"
                  variant="primary"
                  size="md"
                  className="w-full font-bold h-11 text-sm mt-3"
                >
                  <span>Create Household</span>
                  <ArrowRight className="w-4 h-4" />
                </Button>

                <div className="text-center pt-2">
                  <p className="text-xs text-[#676B68] dark:text-[#969D96]">
                    Already have a household?{' '}
                    <button
                      type="button"
                      onClick={() => setAuthMode('login')}
                      className="text-[#5E9278] font-semibold hover:underline"
                    >
                      Sign In
                    </button>
                  </p>
                </div>
              </form>
            )}
          </Card>
        </div>
      </main>
    </div>
  );
};
