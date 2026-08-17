"use client";

import { useEffect, useRef, useState } from "react";

type Ticket = { id: string; ticket: string; store_code?: string; ticket_number?: string; description: string; priority: string; status: string; request_type?: string; requestor_name?: string };
type ProcedureNotice = { kind: string; text: string };
type ProcedureSection = { title: string; steps: string[]; step_images?: string[][]; notices?: ProcedureNotice[] };
type Answer = { mode?: string; sections: ProcedureSection[]; sources: string[] };
type ActivityEvent = { id: string; event_type: string; title: string; detail: string; created_at?: string; metadata?: Record<string, unknown> };

const analysisSteps = [
  "Evaluating the Knowledge Base",
  "Reviewing how similar tickets were resolved",
  "Preparing the recommended response",
];

function normalizeAnswer(payload: any): Answer {
  return { mode: String(payload?.mode || "no_match"), sections: Array.isArray(payload?.sections) ? payload.sections : [], sources: Array.isArray(payload?.sources) ? payload.sources.map(String) : [] };
}

export default function Home() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [selected, setSelected] = useState<Ticket | null>(null);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [analysisStage, setAnalysisStage] = useState(0);
  const [unreadTicketIds, setUnreadTicketIds] = useState<Set<string>>(new Set());
  const [soundEnabled, setSoundEnabled] = useState(false);
  const [ticketsRefreshing, setTicketsRefreshing] = useState(false);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [activityLoading, setActivityLoading] = useState(false);
  const requestSequence = useRef(0);
  const ticketRefreshSequence = useRef(0);
  const knownTicketIds = useRef<Set<string>>(new Set());
  const ticketsInitialized = useRef(false);
  const soundEnabledRef = useRef(false);

  function playNewTicketSound() {
    if (!soundEnabledRef.current) return;
    try {
      const AudioContextClass = window.AudioContext || (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!AudioContextClass) return;
      const context = new AudioContextClass();
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.frequency.setValueAtTime(720, context.currentTime);
      gain.gain.setValueAtTime(0.0001, context.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.12, context.currentTime + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + 0.28);
      oscillator.connect(gain); gain.connect(context.destination);
      oscillator.start(); oscillator.stop(context.currentTime + 0.3);
      oscillator.addEventListener("ended", () => void context.close());
    } catch { /* Visual notification remains available if audio is blocked. */ }
  }

  async function refreshTickets(showLoading = false) {
    const sequence = ++ticketRefreshSequence.current;
    if (showLoading) setTicketsRefreshing(true);
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const response = await fetch(`${baseUrl}/api/v1/tickets?refresh=${Date.now()}`, { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Monday connection failed");
      if (sequence !== ticketRefreshSequence.current) return;
        const incoming: Ticket[] = data.tickets ?? [];
        const incomingIds = new Set(incoming.map((ticket) => ticket.id));
        if (!ticketsInitialized.current) {
          knownTicketIds.current = incomingIds;
          ticketsInitialized.current = true;
        } else {
          const arrivals = incoming.filter((ticket) => !knownTicketIds.current.has(ticket.id));
          if (arrivals.length) {
            setUnreadTicketIds((current) => new Set([...current, ...arrivals.map((ticket) => ticket.id)]));
            playNewTicketSound();
          }
          knownTicketIds.current = new Set([...knownTicketIds.current, ...incomingIds]);
        }
        // The most recent Monday response is authoritative. The sequence guard
        // prevents an older overlapping poll from replacing a newer ticket list.
        setTickets(incoming);
        setSelected((current) => current ? incoming.find((ticket) => ticket.id === current.id) ?? null : null);
        setError("");
    } catch (reason) {
      if (sequence === ticketRefreshSequence.current) setError(reason instanceof Error ? reason.message : "Monday connection failed");
    } finally {
      if (showLoading && sequence === ticketRefreshSequence.current) setTicketsRefreshing(false);
    }
  }

  useEffect(() => {
    void refreshTickets();
    const timer = window.setInterval(() => void refreshTickets(), 10000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!selected?.id) { setActivity([]); return; }
    let active = true;
    async function loadActivity() {
      setActivityLoading(true);
      try {
        const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
        const response = await fetch(`${baseUrl}/api/v1/operations/activity?ticket_id=${encodeURIComponent(selected!.id)}&refresh=${Date.now()}`, { cache: "no-store" });
        const payload = await response.json();
        if (active && response.ok) setActivity(Array.isArray(payload.events) ? payload.events : []);
      } finally { if (active) setActivityLoading(false); }
    }
    void loadActivity();
    const timer = window.setInterval(() => void loadActivity(), 5000);
    return () => { active = false; window.clearInterval(timer); };
  }, [selected?.id]);

  function chooseTicket(itemId: string) {
    const item = tickets.find((ticket) => ticket.id === itemId) ?? null;
    const ticketContext = item ? `${item.ticket}\n${item.description}`.trim() : "";
    setSelected(item); setQuestion(ticketContext); setAnswer(null);
    if (item) setUnreadTicketIds((current) => { const next = new Set(current); next.delete(item.id); return next; });
    if (item) void askAssistant(ticketContext, item.id);
  }

  function toggleSound() {
    const next = !soundEnabled;
    soundEnabledRef.current = next;
    setSoundEnabled(next);
  }

  function ticketLabel(item: Ticket) {
    const storeCode = item.store_code || item.ticket_number || "Store unavailable";
    const title = item.ticket.trim();
    const titleIsOnlyStoreCode = title.toUpperCase().replace(/[\s-]/g, "") === storeCode.toUpperCase().replace(/[\s-]/g, "");
    const request = titleIsOnlyStoreCode ? item.description.trim() : title;
    const conciseRequest = request.length > 72 ? `${request.slice(0, 69).trimEnd()}\u2026` : request;
    return `${storeCode} \u00B7 ${conciseRequest || "Request details unavailable"}`;
  }

  async function askAssistant(input?: string, ticketId?: string) {
    const request = (input ?? question).trim();
    if (!request) return;
    const sequence = ++requestSequence.current;
    const startedAt = Date.now();
    setLoading(true); setAnalysisStage(0); setError("");
    window.setTimeout(() => { if (sequence === requestSequence.current) setAnalysisStage(1); }, 1800);
    window.setTimeout(() => { if (sequence === requestSequence.current) setAnalysisStage(2); }, 3700);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/workspace/troubleshoot`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: request, history: [], ticket_id: ticketId ?? selected?.id ?? null }) });
      if (!response.ok) throw new Error("The assistant could not process this ticket.");
      const result = normalizeAnswer(await response.json());
      const remainingThinkingTime = Math.max(0, 5600 - (Date.now() - startedAt));
      if (remainingThinkingTime) await new Promise((resolve) => window.setTimeout(resolve, remainingThinkingTime));
      if (sequence === requestSequence.current) setAnswer(result);
    } catch (reason) { if (sequence === requestSequence.current) setError(reason instanceof Error ? reason.message : "Unexpected error"); }
    finally { if (sequence === requestSequence.current) setLoading(false); }
  }

  const orderedTickets = [...tickets].sort((left, right) => Number(unreadTicketIds.has(right.id)) - Number(unreadTicketIds.has(left.id)));
  const newestTicket = orderedTickets.find((ticket) => unreadTicketIds.has(ticket.id));

  return <div className="app-shell">
    <aside className="sidebar"><div className="side-logo"><img src="/glazed-mind-logo.png" alt="Glazed Mind"/><span>GLAZED<br/><b>MIND</b></span></div><nav><a className="active" href="#workspace">{"\u2302"} <span>Workspace</span></a><a href="/onboarding">{"\u25A3"} <span>Onboarding</span></a><a href="/support">{"\u2726"} <span>Customer Portal</span></a><a href="/chatbot">{"\u25C8"} <span>Chatbot</span></a><a href="/knowledge-base">{"\u25A4"} <span>Knowledge Base</span></a><a href="/escalations">{"\u2667"} <span>Escalations</span></a><a href="/impact">{"\u25C9"} <span>Impact</span></a></nav><div className="side-note"><b>AI Copilot</b><small>Grounded in Shipley guides</small></div></aside>
    <main className="dashboard" id="workspace"><header><div className="top-brand"><img src="/glazed-mind-logo.png" alt=""/><div><strong>Glazed Mind</strong><small>Shipley Do-Nuts {"\u00B7"} Help Desk workspace</small></div></div><div className="header-actions"><button className={`sound-toggle${soundEnabled ? " enabled" : ""}`} onClick={toggleSound} aria-pressed={soundEnabled}>{soundEnabled ? "Sound on" : "Sound off"}</button><div className="connection"><span/> {tickets.length ? "Monday connected" : error ? "Monday unavailable" : "Connecting to Monday\u2026"}</div></div></header>
      {newestTicket && <section className="new-ticket-alert" role="status"><div><span className="alert-pulse"/><div><b>{unreadTicketIds.size === 1 ? "New Monday ticket received" : `${unreadTicketIds.size} new Monday tickets received`}</b><p>{ticketLabel(newestTicket)}</p></div></div><div className="alert-actions"><button onClick={() => chooseTicket(newestTicket.id)}>Open ticket</button><button className="dismiss-alert" onClick={() => setUnreadTicketIds(new Set())}>Mark all viewed</button></div></section>}
      <section className="intro"><div><p className="eyebrow">Support workspace</p><h1>Resolve the next ticket<br/><em>with evidence.</em></h1><p className="intro-copy">Select an open Monday ticket, ask the Knowledge Assistant, and receive the documented procedure with its source material.</p></div><img className="intro-logo" src="/glazed-mind-logo.png" alt="Glazed Mind"/></section>
      <section className="content-grid"><div className="card ticket-card" id="tickets"><div className="card-heading"><div><p className="eyebrow">01 {"\u00B7"} Ticket Reader</p><h2>Open ticket</h2></div><div className="ticket-card-actions"><button className="refresh-tickets" type="button" onClick={() => void refreshTickets(true)} disabled={ticketsRefreshing}>{ticketsRefreshing ? "Refreshing\u2026" : "Refresh tickets"}</button><span className="live-pill">Monday</span></div></div>{tickets.length ? <select key={orderedTickets.map((ticket) => ticket.id).join("-")} aria-label="Select an open ticket" value={selected?.id ?? ""} onChange={(event) => chooseTicket(event.target.value)}><option value="">Choose an open ticket</option>{orderedTickets.map((item) => <option key={item.id} value={item.id}>{unreadTicketIds.has(item.id) ? "\u25CF NEW \u00B7 " : ""}{ticketLabel(item)}</option>)}</select> : <div className="connect-error">{error || "Loading Open Tickets\u2026"}</div>}{selected && <div className="ticket-meta"><span>{selected.store_code || selected.ticket_number || "Store unavailable"}</span><span>{selected.status || "Status unavailable"}</span><span>{selected.priority || "Priority unavailable"}</span><span>{selected.request_type || "Request"}</span></div>}<textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Describe the issue or select a ticket above\u2026" aria-label="Ticket description"/><button onClick={() => void askAssistant()} disabled={loading || !question.trim()}>{loading ? "Reading ticket & guides\u2026" : "Run troubleshooting again"} <b>{"\u2192"}</b></button>{selected && <p className="automation-note"><span>{"\u2713"}</span> Acknowledgment and status updates are handled automatically in Monday.</p>}{error && tickets.length > 0 && <p className="error-text">{error}</p>}</div>
        <div className="card answer-card" id="knowledge"><div className="card-heading"><div><p className="eyebrow">02 {"\u00B7"} Knowledge Assistant</p><h2>Ticket troubleshooting</h2></div>{answer?.sections.length && !loading ? <span className="grounded-pill">Documentation grounded</span> : null}</div>{loading ? <div className="workspace-thinking"><div className="thinking-orbit"><span>{"\u2726"}</span></div><p className="eyebrow">Agent analysis</p><h3>{analysisSteps[analysisStage]}{"\u2026"}</h3><div className="thinking-progress">{analysisSteps.map((step, index) => <div className={index < analysisStage ? "complete" : index === analysisStage ? "active" : "pending"} key={step}><i>{index < analysisStage ? "\u2713" : index + 1}</i><span>{step}</span></div>)}</div><small>GlazedMind is grounding the complete procedure before presenting it.</small></div> : answer ? answer.sections.length ? <div className="answer-scroll">{answer.sections.map((section) => <section className="answer-section" key={section.title}><p className="eyebrow">{section.title}</p><ol>{section.steps.map((step, index) => <li key={`${section.title}-${index}`}><div>{step}</div>{section.step_images?.[index]?.map((image, imageIndex) => <img className="workspace-step-image" key={`${image}-${imageIndex}`} src={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/knowledge-images/${image}`} alt={`Documented screenshot for step ${index + 1}`} />)}</li>)}</ol>{section.notices?.map((notice,index)=><div className={`procedure-notice ${notice.kind}`} key={`${notice.kind}-${index}`}><b>{notice.kind}</b><span>{notice.text}</span></div>)}</section>)}{answer.sources.length > 0 && <div className="sources"><p className="eyebrow">Sources</p><div>{answer.sources.map((source) => <span key={source}>{source}</span>)}</div></div>}</div> : <div className="empty-answer"><div>!</div><p>No documented procedure matched this ticket.</p><small>Review the ticket details or consult the Escalations directory.</small></div> : <div className="empty-answer"><div>{"\u2726"}</div><p>Select a Monday ticket to begin.</p><small>GlazedMind will read it and retrieve the complete documented troubleshooting.</small></div>}</div></section>
      <section className="activity-card"><div className="activity-heading"><div><p className="eyebrow">Agent activity</p><h2>Ticket action timeline</h2></div>{selected && <span className="live-pill">Live workflow</span>}</div>{!selected ? <div className="activity-empty"><b>Select a ticket to see every action GlazedMind performs.</b><small>Monday updates, knowledge retrieval and follow-ups will appear here.</small></div> : activityLoading && !activity.length ? <div className="activity-empty"><b>Loading operational history...</b></div> : activity.length ? <div className="activity-timeline">{activity.map((event, index) => <article key={event.id}><div className={`activity-node event-${event.event_type}`}>{index + 1}</div><div><div className="activity-event-top"><b>{event.title}{Number(event.metadata?.run_count || 1) > 1 && <span className="activity-rerun">Run {"\u00D7"}{Number(event.metadata?.run_count)}</span>}</b><time>{event.created_at ? new Date(event.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "Recorded workflow"}</time></div><p>{event.detail}</p></div></article>)}</div> : <div className="activity-empty"><b>No automated actions recorded for this ticket yet.</b><small>The timeline updates automatically every five seconds.</small></div>}</section>
      <section className="module-row" id="escalation"><div><span>01</span><b>Ticket Reader</b><small>Open tickets from Monday</small></div><div><span>02</span><b>Knowledge Assistant</b><small>Procedures from verified guides</small></div><div><span>03</span><b>Escalation</b><small>Contacts matched to the issue</small></div></section>
      <footer>THINK SWEET. &nbsp; SOLVE SMART.</footer>
    </main>
  </div>;
}

