import { FormEvent, type ReactNode, useState } from 'react';
import { ArrowRight, Home, LockKeyhole, Mail, UserRound } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { ApiError, request } from '@/lib/api/request';
import { setAccessToken } from '@/lib/auth/auth-adapter';
import { useSessionStore, type SessionUser } from '@/stores/session-store';

type AuthMode = 'login' | 'register';
type AuthResponse = { token: string; user: { id: string; email: string; name?: string; role: SessionUser['role'] } };

function requestId() {
  return crypto.randomUUID();
}

export function AuthScreen() {
  const [mode, setMode] = useState<AuthMode>('login');
  const [email, setEmail] = useState('admin@home.test');
  const [password, setPassword] = useState('password123');
  const [displayName, setDisplayName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const navigate = useNavigate();
  const setAuthenticated = useSessionStore((state) => state.setAuthenticated);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const response = mode === 'login'
        ? await request<AuthResponse>('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
          }, { correlationId: requestId() })
        : await request<AuthResponse>('/api/auth/register-household', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password, display_name: displayName }),
          }, { correlationId: requestId() });

      setAccessToken(response.token);
      setAuthenticated({ ...response.user, name: response.user.name ?? (displayName || 'Household admin') });
      navigate('/t/home-lakeview/overview', { replace: true });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Unable to connect to HomeOps. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return <main className="min-h-screen bg-[#F3F1EB] px-4 py-6 text-[#171918] sm:px-8 sm:py-10"><div className="mx-auto grid min-h-[calc(100vh-3rem)] max-w-6xl overflow-hidden rounded-3xl border border-[#D9D8D2] bg-[#FAF9F6] shadow-2xl shadow-[#171918]/10 lg:grid-cols-[1.1fr_0.9fr]"><section className="relative hidden overflow-hidden bg-[#284837] p-10 text-white lg:flex lg:flex-col"><div className="absolute -right-16 -top-20 size-72 rounded-full bg-[#D19A4C]/20" /><div className="absolute -bottom-28 -left-20 size-80 rounded-full border-[40px] border-[#9BCDB4]/10" /><div className="relative"><div className="flex items-center gap-3"><span className="grid size-11 place-items-center rounded-xl bg-[#5E9278] shadow-lg shadow-black/20"><Home size={22} /></span><div><p className="text-lg font-bold tracking-tight">HomeOps</p><p className="text-xs text-[#D2E6D8]">Your household, in sync</p></div></div><p className="mt-20 max-w-md text-sm font-semibold uppercase tracking-[0.18em] text-[#D19A4C]">One calm place for home life</p><h1 className="mt-4 max-w-lg text-4xl font-bold leading-tight tracking-tight">Turn everyday changes into a household plan.</h1><p className="mt-5 max-w-md text-sm leading-6 text-[#D2E6D8]">Coordinate tasks, schedules, pantry alerts, documents, and household decisions with the right privacy boundaries.</p></div><div className="relative mt-auto rounded-2xl border border-white/10 bg-white/10 p-5 backdrop-blur"><p className="text-sm font-semibold">Built for the weekend ahead</p><p className="mt-2 text-sm leading-6 text-[#D2E6D8]">Your assistant can surface conflicts, propose actions, and wait for approval before changing household data.</p></div></section><section className="flex items-center justify-center p-6 sm:p-10"><div className="w-full max-w-md"><div className="lg:hidden"><div className="flex items-center gap-2"><span className="grid size-9 place-items-center rounded-lg bg-[#5E9278] text-white"><Home size={18} /></span><span className="font-bold tracking-tight">HomeOps</span></div></div><p className="mt-12 text-xs font-bold uppercase tracking-[0.16em] text-[#5E9278]">Welcome</p><h2 className="mt-3 text-3xl font-bold tracking-tight">{mode === 'login' ? 'Sign in to your household' : 'Create your household'}</h2><p className="mt-3 text-sm leading-6 text-[#676B68]">{mode === 'login' ? 'Use your household account to view the home dashboard.' : 'The first member becomes the household administrator.'}</p><div className="mt-7 grid grid-cols-2 rounded-xl bg-[#ECEAE4] p-1"><button type="button" onClick={() => setMode('login')} className={`rounded-lg px-3 py-2 text-sm font-semibold transition ${mode === 'login' ? 'bg-white text-[#171918] shadow-sm' : 'text-[#676B68]'}`}>Sign in</button><button type="button" onClick={() => setMode('register')} className={`rounded-lg px-3 py-2 text-sm font-semibold transition ${mode === 'register' ? 'bg-white text-[#171918] shadow-sm' : 'text-[#676B68]'}`}>Create household</button></div><form className="mt-6 space-y-4" onSubmit={handleSubmit}>{mode === 'register' && <Field label="Your name" icon={<UserRound size={17} />}><input required value={displayName} onChange={(event) => setDisplayName(event.target.value)} className="auth-input" placeholder="e.g. Priya Sharma" /></Field>}<Field label="Email address" icon={<Mail size={17} />}><input required type="email" value={email} onChange={(event) => setEmail(event.target.value)} className="auth-input" placeholder="you@example.com" /></Field><Field label="Password" icon={<LockKeyhole size={17} />}><input required type="password" minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} className="auth-input" placeholder="At least 8 characters" /></Field>{error && <p role="alert" className="rounded-xl border border-[#B96359]/30 bg-[#B96359]/10 px-3 py-2 text-sm text-[#8B3F36]">{error}</p>}<button disabled={isSubmitting} className="mt-2 flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-[#5E9278] px-4 py-2 text-sm font-bold text-white transition hover:bg-[#4D7A64] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#5E9278] disabled:cursor-wait disabled:opacity-60">{isSubmitting ? 'Connecting…' : mode === 'login' ? 'Sign in' : 'Create household'}<ArrowRight size={17} /></button></form>{mode === 'login' && <p className="mt-5 rounded-xl bg-[#E4F0E8] px-3 py-3 text-xs leading-5 text-[#3D5F4E]"><strong>Demo account:</strong> admin@home.test / password123</p>}</div></section></div></main>;
}

function Field({ label, icon, children }: { label: string; icon: ReactNode; children: ReactNode }) {
  return <label className="block"><span className="mb-1.5 block text-sm font-semibold">{label}</span><span className="relative block"><span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#676B68]">{icon}</span>{children}</span></label>;
}
