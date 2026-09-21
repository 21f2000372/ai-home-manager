import { FormEvent, useState } from 'react';
import { ArrowRight, Home, LockKeyhole, Mail, UserRound } from 'lucide-react';
import { Link, useSearchParams } from 'react-router-dom';
import { ApiError, request } from '@/lib/api/request';

type JoinResponse = { message: string; user_id: string };

export function JoinHouseholdScreen() {
  const [searchParams] = useSearchParams();
  const [inviteCode, setInviteCode] = useState(searchParams.get('code') ?? '');
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [dateOfBirth, setDateOfBirth] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await request<JoinResponse>('/api/auth/join', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          invite_code: inviteCode.trim(),
          display_name: displayName.trim(),
          email: email.trim(),
          password,
          date_of_birth: dateOfBirth || undefined,
        }),
      }, { correlationId: crypto.randomUUID() });
      setSubmitted(true);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Unable to submit your request. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return <main className="min-h-screen bg-[#F3F1EB] px-4 py-6 text-[#171918] sm:px-8 sm:py-10"><section className="mx-auto w-full max-w-lg rounded-3xl border border-[#D9D8D2] bg-[#FAF9F6] p-6 shadow-xl shadow-[#171918]/10 sm:p-10"><div className="flex items-center gap-3"><span className="grid size-11 place-items-center rounded-xl bg-[#5E9278] text-white"><Home size={22} /></span><div><p className="font-bold">HomeOps</p><p className="text-xs text-[#676B68]">Join a household</p></div></div>{submitted ? <div className="mt-10"><p className="text-xs font-bold uppercase tracking-[0.16em] text-[#5E9278]">Request received</p><h1 className="mt-3 text-3xl font-bold tracking-tight">Awaiting Admin approval</h1><p className="mt-4 text-sm leading-6 text-[#676B68]">Your account is ready, but a household Admin must assign your role before you can sign in. Please return after they approve your request.</p><Link to="/" className="mt-7 inline-flex min-h-11 items-center rounded-xl bg-[#5E9278] px-4 py-2 text-sm font-bold text-white hover:bg-[#4D7A64]">Back to sign in</Link></div> : <><p className="mt-10 text-xs font-bold uppercase tracking-[0.16em] text-[#5E9278]">Household invitation</p><h1 className="mt-3 text-3xl font-bold tracking-tight">Request to join</h1><p className="mt-3 text-sm leading-6 text-[#676B68]">Create your account with the invite code shared by the household Admin. You will not get household access until approved.</p><form className="mt-7 space-y-4" onSubmit={submit}><label className="block"><span className="mb-1.5 block text-sm font-semibold">Invite code</span><input required value={inviteCode} onChange={(event) => setInviteCode(event.target.value)} className="auth-input" autoComplete="one-time-code" /></label><label className="block"><span className="mb-1.5 flex items-center gap-2 text-sm font-semibold"><UserRound size={16} />Your name</span><input required value={displayName} onChange={(event) => setDisplayName(event.target.value)} className="auth-input" autoComplete="name" /></label><label className="block"><span className="mb-1.5 flex items-center gap-2 text-sm font-semibold"><Mail size={16} />Email address</span><input required type="email" value={email} onChange={(event) => setEmail(event.target.value)} className="auth-input" autoComplete="email" /></label><label className="block"><span className="mb-1.5 flex items-center gap-2 text-sm font-semibold"><LockKeyhole size={16} />Password</span><input required type="password" minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} className="auth-input" autoComplete="new-password" /></label><label className="block"><span className="mb-1.5 block text-sm font-semibold">Date of birth <span className="font-normal text-[#676B68]">(optional)</span></span><input type="date" value={dateOfBirth} onChange={(event) => setDateOfBirth(event.target.value)} className="auth-input" /></label>{error && <p role="alert" className="rounded-xl border border-[#B96359]/30 bg-[#B96359]/10 px-3 py-2 text-sm text-[#8B3F36]">{error}</p>}<button disabled={isSubmitting} className="flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-[#5E9278] px-4 py-2 text-sm font-bold text-white hover:bg-[#4D7A64] disabled:cursor-wait disabled:opacity-60">{isSubmitting ? 'Submitting…' : 'Request to join'}<ArrowRight size={17} /></button></form><p className="mt-5 text-center text-sm text-[#676B68]">Already approved? <Link to="/" className="font-semibold text-[#3D5F4E] underline">Sign in</Link></p></>}</section></main>;
}
