"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type ImpactMetrics = { tickets_acknowledged: number; status_updates: number; followups_sent: number; tickets_auto_resolved: number; automated_actions: number; estimated_minutes_saved: number; knowledge_documents: number; activity_events: number; calculation_note: string; runtime?: { mode: string; demo_mode: boolean; followup_time_unit: string } };
type TrainingMetrics = { quizAttempts?: Record<string, number>; quizMistakes?: Record<string, number>; scenarioDecisions?: number; scenarioMistakes?: number; scenarioCompleted?: boolean; assessmentAttempts?: number; finalScore?: number | null };

const emptyImpact: ImpactMetrics = { tickets_acknowledged: 0, status_updates: 0, followups_sent: 0, tickets_auto_resolved: 0, automated_actions: 0, estimated_minutes_saved: 0, knowledge_documents: 0, activity_events: 0, calculation_note: "" };
const skillLabels: Record<string, string> = { architecture: "Store Architecture", network: "Network & Scale", ncr: "NCR POS Ecosystem", platforms: "Store Platforms", triage: "First-Line Triage" };

export default function ImpactPage() {
  const [impact, setImpact] = useState<ImpactMetrics>(emptyImpact);
  const [training, setTraining] = useState<TrainingMetrics>({});
  const [completed, setCompleted] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    try { setTraining(JSON.parse(localStorage.getItem("glazedmind-onboarding-metrics") || "{}")); setCompleted(JSON.parse(localStorage.getItem("glazedmind-onboarding-v2") || "[]")); } catch { /* Empty learning profile is valid. */ }
    let active = true;
    async function load() {
      try {
        const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
        const response = await fetch(`${baseUrl}/api/v1/operations/metrics?refresh=${Date.now()}`, { cache: "no-store" });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || "Impact metrics are unavailable");
        if (active) { setImpact(payload); setError(""); }
      } catch (reason) { if (active) setError(reason instanceof Error ? reason.message : "Impact metrics are unavailable"); }
      finally { if (active) setLoading(false); }
    }
    void load(); const timer = window.setInterval(() => void load(), 10000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  const trainingAttempts = Object.values(training.quizAttempts || {}).reduce((sum, value) => sum + value, 0) + (training.scenarioDecisions || 0) + (training.assessmentAttempts || 0);
  const trainingMistakes = Object.values(training.quizMistakes || {}).reduce((sum, value) => sum + value, 0) + (training.scenarioMistakes || 0);
  const readinessCheckpoints = completed.length + (training.scenarioCompleted ? 1 : 0) + (training.finalScore === 3 ? 1 : 0);
  const readiness = Math.round((readinessCheckpoints / 7) * 100);
  const skillProfile = useMemo(() => Object.entries(skillLabels).map(([id, label]) => { const mistakes = training.quizMistakes?.[id] || 0; const passed = completed.includes(id); return { id, label, mistakes, status: passed && mistakes <= 1 ? "Strong" : mistakes >= 2 ? "Needs reinforcement" : passed ? "Developing" : "Not assessed" }; }), [training, completed]);

  const cards = [
    { label: "Automated actions", value: impact.automated_actions, detail: "Actions completed without manual processing", tone: "pink" },
    { label: "Tickets acknowledged", value: impact.tickets_acknowledged, detail: "Personalized first-touch communications", tone: "cyan" },
    { label: "Status updates", value: impact.status_updates, detail: "Monday workflow transitions", tone: "purple" },
    { label: "Follow-ups sent", value: impact.followups_sent, detail: "Priority-based customer reminders", tone: "yellow" },
    { label: "Auto-resolved", value: impact.tickets_auto_resolved, detail: "Closed after three unanswered follow-ups", tone: "green" },
    { label: "Estimated time saved", value: `${impact.estimated_minutes_saved}m`, detail: "Transparent operational estimate", tone: "blue" },
  ];

  return <div className="app-shell">
    <aside className="sidebar"><Link className="side-logo" href="/"><img src="/glazed-mind-logo.png" alt="GlazedMind"/><span>GLAZED<br/><b>MIND</b></span></Link><nav><Link href="/"><span>{"\u2302"}</span><span>Workspace</span></Link><Link href="/onboarding"><span>{"\u25A3"}</span><span>Onboarding</span></Link><Link href="/support"><span>{"\u2726"}</span><span>Customer Portal</span></Link><Link href="/chatbot"><span>{"\u25C8"}</span><span>Chatbot</span></Link><Link href="/knowledge-base"><span>{"\u25A4"}</span><span>Knowledge Base</span></Link><Link href="/escalations"><span>{"\u2667"}</span><span>Escalations</span></Link><Link className="active" href="/impact"><span>{"\u25C9"}</span><span>Impact</span></Link></nav><div className="side-note"><b>Know. Act. Learn.</b><small>Live operational evidence</small></div></aside>
    <main className="dashboard impact-dashboard"><header><div className="top-brand"><img src="/glazed-mind-logo.png" alt="GlazedMind"/><div><strong>GlazedMind</strong><small>Executive impact dashboard</small></div></div><div className="connection"><span/>{loading ? "Calculating impact..." : error ? "Metrics unavailable" : "Live metrics"}</div></header>
      <section className="impact-hero"><div><p className="eyebrow">Operational intelligence</p><h1>From answers<br/><em>to measurable action.</em></h1><p>Real activity from Monday automation, follow-up workflows, verified knowledge and agent onboarding.</p></div><div className="impact-loop"><div><span>KNOW</span><b>{impact.knowledge_documents}</b><small>verified guides</small></div><i>{"\u2192"}</i><div><span>ACT</span><b>{impact.automated_actions}</b><small>automated actions</small></div><i>{"\u2192"}</i><div><span>LEARN</span><b>{readiness}%</b><small>agent readiness</small></div></div></section>
      {error && <div className="impact-error">{error}</div>}
      {impact.runtime?.demo_mode && <div className="demo-runtime-note"><b>Hackathon demo mode</b><span>Priority follow-up intervals are represented in minutes instead of production days so the full workflow can be demonstrated live.</span></div>}
      <section className="impact-cards">{cards.map((card) => <article className={`impact-card ${card.tone}`} key={card.label}><span>{card.label}</span><strong>{card.value}</strong><p>{card.detail}</p></article>)}</section>
      <section className="impact-details"><article className="automation-summary"><div className="section-heading"><p className="eyebrow">Operational automation</p><h2>Work completed by GlazedMind</h2><p>Each count comes from the persisted acknowledgment and follow-up workflow state.</p></div><div className="automation-flow"><div><span>01</span><b>Understand</b><strong>{impact.tickets_acknowledged}</strong><small>requests processed</small></div><i>{"\u2192"}</i><div><span>02</span><b>Communicate</b><strong>{impact.tickets_acknowledged + impact.followups_sent}</strong><small>customer messages</small></div><i>{"\u2192"}</i><div><span>03</span><b>Update</b><strong>{impact.status_updates}</strong><small>Monday transitions</small></div><i>{"\u2192"}</i><div><span>04</span><b>Resolve</b><strong>{impact.tickets_auto_resolved}</strong><small>automatic closures</small></div></div><p className="metric-note">{impact.calculation_note}</p></article>
        <article className="ramp-summary"><div className="section-heading"><p className="eyebrow">Ramp-up metrics</p><h2>Agent skill profile</h2></div><div className="ramp-stats"><div><strong>{readiness}%</strong><span>Readiness</span></div><div><strong>{trainingAttempts}</strong><span>Attempts</span></div><div><strong>{trainingMistakes}</strong><span>Mistakes</span></div><div><strong>{training.finalScore ?? "-"}/3</strong><span>Assessment</span></div></div><div className="impact-skills">{skillProfile.map((skill) => <div key={skill.id}><span>{skill.label}</span><b className={skill.status.toLowerCase().replaceAll(" ", "-")}>{skill.status}</b></div>)}</div><Link href="/onboarding">Open onboarding intelligence {"\u2192"}</Link></article>
      </section><footer>THINK SWEET. &nbsp;&nbsp; SOLVE SMART.</footer>
    </main>
  </div>;
}
