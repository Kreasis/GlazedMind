"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const SESSION_KEY = "glazedmind-support-case";

type SupportMessage = { id: string; role: "customer" | "agent"; content: string; created_at: string };
type SupportCase = {
  id: string;
  monday_item_id: string;
  store_code: string;
  subject: string;
  status: string;
  priority: string;
  request_type: string;
  automation_status: string;
  messages: SupportMessage[];
};
type Session = { caseId: string; accessToken: string };

const initialForm = {
  store_code: "",
  customer_name: "",
  customer_email: "",
  subject: "",
  description: "",
  request_type: "Question",
  priority: "Medium Priority",
};

export default function SupportPage() {
  const [form, setForm] = useState(initialForm);
  const [supportCase, setSupportCase] = useState<SupportCase | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const conversationEnd = useRef<HTMLDivElement | null>(null);

  async function loadCase(current: Session, showError = false) {
    try {
      const response = await fetch(`${API}/api/v1/support/cases/${current.caseId}?access_token=${encodeURIComponent(current.accessToken)}`, { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Your support case could not be loaded.");
      setSupportCase(data);
      if (showError) setError("");
    } catch (reason) {
      if (showError) setError(reason instanceof Error ? reason.message : "Your support case could not be loaded.");
    }
  }

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(SESSION_KEY);
      if (stored) {
        const current = JSON.parse(stored) as Session;
        setSession(current);
        void loadCase(current, true);
      }
    } catch {
      window.localStorage.removeItem(SESSION_KEY);
    }
  }, []);

  useEffect(() => {
    if (!session) return;
    const interval = window.setInterval(() => void loadCase(session), 5000);
    return () => window.clearInterval(interval);
  }, [session]);

  useEffect(() => {
    conversationEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [supportCase?.messages.length]);

  async function createRequest(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API}/api/v1/support/cases`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Your support request could not be created.");
      const current = { caseId: String(data.id), accessToken: String(data.access_token) };
      window.localStorage.setItem(SESSION_KEY, JSON.stringify(current));
      setSession(current);
      setSupportCase(data);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Your support request could not be created.");
    } finally {
      setLoading(false);
    }
  }

  async function sendMessage(event: FormEvent) {
    event.preventDefault();
    if (!session || !message.trim()) return;
    setSending(true);
    setError("");
    try {
      const response = await fetch(`${API}/api/v1/support/cases/${session.caseId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ access_token: session.accessToken, message }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Your message could not be delivered.");
      setSupportCase(data);
      setMessage("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Your message could not be delivered.");
    } finally {
      setSending(false);
    }
  }

  function startAnotherRequest() {
    window.localStorage.removeItem(SESSION_KEY);
    setSession(null);
    setSupportCase(null);
    setForm(initialForm);
    setError("");
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <Link className="side-logo" href="/"><img src="/glazed-mind-logo.png" alt="GlazedMind"/><span>GLAZED<br/><b>MIND</b></span></Link>
      <nav>
        <Link href="/"><span>{"\u2302"}</span><span>Workspace</span></Link>
        <Link href="/onboarding"><span>{"\u25A3"}</span><span>Onboarding</span></Link>
        <Link className="active" href="/support"><span>{"\u2726"}</span><span>Customer Portal</span></Link>
        <Link href="/chatbot"><span>{"\u25C8"}</span><span>Chatbot</span></Link>
        <Link href="/knowledge-base"><span>{"\u25A4"}</span><span>Knowledge Base</span></Link>
        <Link href="/escalations"><span>{"\u2667"}</span><span>Escalations</span></Link>
        <Link href="/impact"><span>{"\u25C9"}</span><span>Impact</span></Link>
      </nav>
      <div className="side-note"><b>Customer Channel</b><small>Connected to Monday</small></div>
    </aside>
    <main className="support-page">
    <header className="support-header">
      <Link href="/support" className="support-brand"><img src="/glazed-mind-logo.png" alt="GlazedMind"/><span><b>GlazedMind</b><small>Store Support</small></span></Link>
      <div className="support-header-actions"><span><i/> Help Desk online</span><Link href="/">Agent workspace</Link></div>
    </header>

    {!supportCase ? <div className="support-intake-layout">
      <section className="support-welcome">
        <p className="eyebrow">Connected store support</p>
        <h1>Tell us what is happening.<br/><em>We will take it from here.</em></h1>
        <p>Send your request directly to the Glazed Mind Help Desk. Your case will be created in Monday, acknowledged immediately, and kept in sync while our team works on it.</p>
        <div className="support-promises"><article><span>01</span><b>One case</b><small>Your FC number keeps every update connected.</small></article><article><span>02</span><b>Live status</b><small>Follow the same case without calling again.</small></article><article><span>03</span><b>Human support</b><small>The Help Desk remains in control of every resolution.</small></article></div>
      </section>
      <form className="support-intake-card" onSubmit={createRequest}>
        <div><p className="eyebrow">New support request</p><h2>How can we help?</h2><small>All fields are required.</small></div>
        <div className="support-form-grid">
          <label>Store number<input required pattern="FC[0-9]{3,}" placeholder="FC1234" value={form.store_code} onChange={event => setForm({...form, store_code: event.target.value.toUpperCase()})}/></label>
          <label>Your name<input required placeholder="Jane Smith" value={form.customer_name} onChange={event => setForm({...form, customer_name: event.target.value})}/></label>
          <label className="wide">Email address<input required type="email" placeholder="jane@shipley.com" value={form.customer_email} onChange={event => setForm({...form, customer_email: event.target.value})}/></label>
          <label>Request type<select value={form.request_type} onChange={event => setForm({...form, request_type: event.target.value})}><option>Issue</option><option>Question</option><option>Request</option></select></label>
          <label>Business impact<select value={form.priority} onChange={event => setForm({...form, priority: event.target.value})}><option>Low Priority</option><option>Medium Priority</option><option>High Priority</option></select></label>
          <label className="wide">Short subject<input required minLength={4} placeholder="Cash drawer is not opening" value={form.subject} onChange={event => setForm({...form, subject: event.target.value})}/></label>
          <label className="wide">What happened?<textarea required minLength={8} placeholder="Describe what you were doing, what you expected, and what you see now." value={form.description} onChange={event => setForm({...form, description: event.target.value})}/></label>
        </div>
        {error && <p className="support-error">{error}</p>}
        <button type="submit" disabled={loading}>{loading ? "Creating your case…" : "Contact the Help Desk →"}</button>
        <p className="support-privacy">Your request is sent securely to the Glazed Mind Help Desk and recorded in Monday.</p>
      </form>
    </div> : <div className="support-case-layout">
      <aside className="support-case-summary">
        <p className="eyebrow">Active support case</p>
        <h1>{supportCase.subject}</h1>
        <div className="support-case-number"><span>Case</span><b>GM-{supportCase.monday_item_id}</b></div>
        <dl><div><dt>Store</dt><dd>{supportCase.store_code}</dd></div><div><dt>Status</dt><dd className="status-value"><i/>{supportCase.status}</dd></div><div><dt>Type</dt><dd>{supportCase.request_type}</dd></div><div><dt>Priority</dt><dd>{supportCase.priority}</dd></div></dl>
        <p className="support-sync"><span>✓</span> Conversation synced with Monday</p>
        <button type="button" onClick={startAnotherRequest}>Start another request</button>
      </aside>
      <section className="support-conversation-card">
        <div className="support-conversation-heading"><div><p className="eyebrow">Help Desk conversation</p><h2>We are working with you</h2></div><span className={supportCase.automation_status === "complete" || supportCase.automation_status === "linked" ? "complete" : "pending"}>{supportCase.automation_status === "linked" ? "Existing case linked" : supportCase.automation_status === "complete" ? "First touch complete" : "Processing"}</span></div>
        <div className="support-messages">{supportCase.messages.map(item => <article className={item.role} key={item.id}><div className="support-avatar">{item.role === "agent" ? "GM" : "You"}</div><div><small>{item.role === "agent" ? "Glazed Mind Help Desk" : supportCase.store_code}</small><p>{item.content}</p><time>{new Date(item.created_at).toLocaleString([], {month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"})}</time></div></article>)}<div ref={conversationEnd}/></div>
        <form className="support-composer" onSubmit={sendMessage}><textarea aria-label="Message the Help Desk" placeholder="Add an update or answer a question from the Help Desk…" value={message} onChange={event => setMessage(event.target.value)} onKeyDown={event => {if (event.key === "Enter" && !event.shiftKey) {event.preventDefault(); event.currentTarget.form?.requestSubmit();}}}/><button disabled={sending || !message.trim()}>{sending ? "Sending…" : "Send →"}</button></form>
        {error && <p className="support-error">{error}</p>}
        <small className="support-refresh-note">Updates from Monday appear here automatically.</small>
      </section>
    </div>}
    </main>
  </div>;
}
