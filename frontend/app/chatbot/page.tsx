"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";

type ProcedureNotice = { kind: string; text: string };
type ProcedureSection = { title: string; steps: string[]; step_images?: string[][]; notices?: ProcedureNotice[] };
type EscalationContact = { name: string; details: string[] };
type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  followUp?: string;
  sections?: ProcedureSection[];
  sources?: string[];
  contacts?: EscalationContact[];
  error?: boolean;
};

export default function ChatbotPage() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const conversationEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    conversationEnd.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, loading]);

  async function ask(event: FormEvent) {
    event.preventDefault();
    const prompt = question.trim();
    if (!prompt || loading) return;

    const history = messages.map(({ role, content, followUp, sections, sources }) => ({
      role,
      content: [
        content,
        followUp,
        sections?.length ? `Procedures used: ${sections.map((section) => section.title).join("; ")}` : "",
        sources?.length ? `Grounded in: ${sources.join("; ")}` : "",
      ].filter(Boolean).join("\n"),
    }));
    setMessages((current) => [...current, { role: "user", content: prompt }]);
    setQuestion("");
    setLoading(true);

    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 35_000);
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/chatbot/ask`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: prompt, history }),
          signal: controller.signal,
        },
      );
      if (!response.ok) throw new Error(`Help Desk API returned ${response.status}`);
      const result = await response.json();
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: result.answer || "I could not generate a safe response.",
          followUp: result.follow_up,
          sections: Array.isArray(result.sections) ? result.sections : [],
          sources: Array.isArray(result.sources) ? result.sources : [],
          contacts: Array.isArray(result.contacts) ? result.contacts : [],
        },
      ]);
    } catch (error) {
      const timedOut = error instanceof DOMException && error.name === "AbortError";
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: timedOut
            ? "The request took too long. Please try again or add one more detail about the issue."
            : "I couldn\u2019t reach the Help Desk service. Please try again.",
          error: true,
        },
      ]);
    } finally {
      window.clearTimeout(timeout);
      setLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link className="side-logo" href="/">
          <img src="/glazed-mind-logo.png" alt="GlazedMind" />
          <span>GLAZED<br /><b>MIND</b></span>
        </Link>
        <nav>
          <Link href="/"><span>{"\u2302"}</span><span>Workspace</span></Link>
          <Link href="/onboarding"><span>{"\u25A3"}</span><span>Onboarding</span></Link>
          <Link href="/support"><span>{"\u2726"}</span><span>Customer Portal</span></Link><Link className="active" href="/chatbot"><span>{"\u25C8"}</span><span>Chatbot</span></Link>
          <Link href="/knowledge-base"><span>{"\u25A4"}</span><span>Knowledge Base</span></Link>
          <Link href="/escalations"><span>{"\u2667"}</span><span>Escalations</span></Link>
          <Link href="/impact"><span>{"\u25C9"}</span><span>Impact</span></Link>
        </nav>
        <div className="side-note"><b>AI Copilot</b><small>Grounded in Shipley guides</small></div>
      </aside>

      <main className="dashboard chatbot-dashboard">
        <header>
          <div className="top-brand"><img src="/glazed-mind-logo.png" alt="" /><div><strong>GlazedMind</strong><small>Documentation Chatbot {"\u00B7"} Help Desk workspace</small></div></div>
          <div className="connection"><span />Knowledge Base connected</div>
        </header>

        <section className="chatbot-hero">
          <p className="eyebrow">Open documentation assistant</p>
          <h1>Ask the <em>Help Desk</em></h1>
          <p className="intro-copy">Ask a question and receive a complete procedure grounded in the verified Knowledge Base.</p>
        </section>

        <section className="card chatbot-card">
          <div className="card-heading">
            <div><p className="eyebrow">Chatbot</p><h2>What can I help you with?</h2></div>
            <div className="chatbot-actions"><span className="grounded-pill">pgvector grounded</span>{messages.length > 0 && <button className="clear-chat" type="button" onClick={() => setMessages([])}>Clear chat</button>}</div>
          </div>

          <div className="chatbot-conversation" aria-live="polite">
            {messages.length === 0 && <div className="empty-chat"><b>Start a conversation</b><span>Describe the issue, request, or procedure you need.</span></div>}
            {messages.map((message, index) => (
              <article className={`chat-message ${message.role}${message.error ? " error" : ""}`} key={index}>
                <span className="chat-avatar">{message.role === "user" ? "You" : "GM"}</span>
                <div className="message-bubble">
                  <p>{message.content}</p>
                  {message.sections?.map((section) => (
                    <section className="procedure-section" key={section.title}>
                      <h3>{section.title}</h3>
                      <ol>{section.steps.map((step, stepIndex) => <li key={`${section.title}-${stepIndex}`}><div>{step}</div>{section.step_images?.[stepIndex]?.map((image, imageIndex) => <img className="step-screenshot" key={`${image}-${imageIndex}`} src={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/knowledge-images/${image}`} alt={`Documented screenshot for step ${stepIndex + 1}`} />)}</li>)}</ol>
                      {section.notices?.map((notice, noticeIndex) => <div className={`procedure-notice ${notice.kind}`} key={`${notice.kind}-${noticeIndex}`}><b>{notice.kind}</b><span>{notice.text}</span></div>)}
                    </section>
                  ))}
                  {message.contacts?.map((contact) => (
                    <section className="contact-card" key={contact.name}>
                      <h3>{contact.name}</h3>
                      <ul>{contact.details.map((detail, detailIndex) => <li key={`${contact.name}-${detailIndex}`}>{detail}</li>)}</ul>
                    </section>
                  ))}
                  {message.followUp && <p className="follow-up">{message.followUp}</p>}
                  {message.sources && message.sources.length > 0 && <small>Grounded in: {message.sources.join(" \u00B7 ")}</small>}
                </div>
              </article>
            ))}
            {loading && <div className="thinking-row"><span className="thinking-dot" /><span>GlazedMind is reviewing your request{"\u2026"}</span></div>}
            <div ref={conversationEnd} />
          </div>

          <form onSubmit={ask} className="chatbot-form">
            <textarea
              className="chatbot-input"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              placeholder="Example: How do I configure a sticky printer?"
              aria-label="Chatbot question"
            />
            <button type="submit" disabled={loading || !question.trim()}>{loading ? "Thinking\u2026" : "Send \u2192"}</button>
          </form>
          <p className="keyboard-hint">Enter to send {"\u00B7"} Shift + Enter for a new line</p>
        </section>
      </main>
    </div>
  );
}

