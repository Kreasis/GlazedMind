"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type Quiz = { question: string; choices: string[]; answer: number; explanation: string };
type Lesson = { id: string; number: string; title: string; duration: string; summary: string; outcomes: string[]; body: React.ReactNode; quiz: Quiz };
type TrainingMetrics = { startedAt: string; quizAttempts: Record<string, number>; quizMistakes: Record<string, number>; scenarioDecisions: number; scenarioMistakes: number; scenarioCompleted: boolean; assessmentAttempts: number; finalScore: number | null; completedAt?: string };
const newTrainingMetrics = (): TrainingMetrics => ({ startedAt: new Date().toISOString(), quizAttempts: {}, quizMistakes: {}, scenarioDecisions: 0, scenarioMistakes: 0, scenarioCompleted: false, assessmentAttempts: 0, finalScore: null });

const systems = [
  { id: "isp", label: "ISP Modem", role: "Provides the store internet connection.", symptoms: "Most or all connected systems lose internet access.", first: "Confirm modem power and whether the connection is available." },
  { id: "network", label: "Acumera / Scale", role: "Protects the network and controls device access.", symptoms: "A new or unregistered device cannot reach NCR services.", first: "Search for the FC number and verify that the device is registered and online." },
  { id: "switch", label: "Store Switch", role: "Distributes network connectivity to store equipment.", symptoms: "One physical area or a group of wired devices may be offline.", first: "Check power, ports and cable connections without changing the configuration." },
  { id: "systems", label: "Store Systems", role: "NCR, Sagenet, DTiQ and Olo perform store operations.", symptoms: "A single service or device fails while the network remains available.", first: "Identify the exact platform and retrieve its verified runbook." },
];

const lessons: Lesson[] = [
  { id: "architecture", number: "01", title: "Store Architecture", duration: "8 min", summary: "Understand how store systems connect before troubleshooting them.", outcomes: ["Read the connectivity flow", "Locate the affected layer", "Avoid troubleshooting the wrong system"], body: <><h3>Follow the dependency chain</h3><p>The ISP modem supplies connectivity. Acumera or Scale protects the network. The switch distributes access, and the store platforms use that connection.</p><p>When multiple systems fail together, investigate their shared dependency before treating every symptom separately.</p></>, quiz: { question: "The POS and online ordering fail at the same time. What should you verify first?", choices: ["Replace the POS", "The shared network path", "Reset the customer password"], answer: 1, explanation: "Two unrelated services failing together usually points to a shared dependency such as connectivity." } },
  { id: "network", number: "02", title: "Network & Scale", duration: "10 min", summary: "Understand firewall access, device registration and network availability.", outcomes: ["Recognize an offline device", "Understand whitelisting", "Separate network and app failures"], body: <><h3>Recognized devices receive access</h3><p>Acumera, Acuvigil or Scale may block a new device that has not been registered. A POS, BOH terminal, KDS or printer can have power and still be unable to reach NCR services.</p><ol><li>Confirm power and cable connections.</li><li>Check whether other store devices are online.</li><li>Locate the store with its FC number.</li><li>Verify that the device is registered and online.</li></ol></>, quiz: { question: "A new POS has power but cannot reach NCR services. What is the best next check?", choices: ["Its registration in Acumera or Scale", "The digital menu content", "The cash drawer name"], answer: 0, explanation: "A new device may be blocked until it is registered or whitelisted in the network platform." } },
  { id: "ncr", number: "03", title: "NCR POS Ecosystem", duration: "12 min", summary: "Map the POS, printers, cash drawer and Back Office dependencies.", outcomes: ["Identify NCR components", "Understand peripheral dependencies", "Choose the correct runbook"], body: <><h3>NCR is an ecosystem</h3><p>The NCR environment includes the POS, Back Office, payment processing, receipt and kitchen printers, cash drawers and store configuration.</p><div className="system-chips"><span>POS</span><span>Back Office</span><span>Printers</span><span>Cash Drawer</span><span>Payments</span></div><p>Identify the exact component before retrieving a procedure. Never invent credentials, configuration values or network settings.</p></>, quiz: { question: "Only the receipt printer is failing. Which approach is most appropriate?", choices: ["Assume the entire NCR platform is down", "Use the verified receipt printer runbook", "Reconfigure the firewall immediately"], answer: 1, explanation: "A single-component symptom should be handled with the specific verified procedure for that component." } },
  { id: "platforms", number: "04", title: "Store Platforms", duration: "10 min", summary: "Recognize the responsibilities of Sagenet, DTiQ and Olo.", outcomes: ["Classify display incidents", "Recognize surveillance issues", "Identify online-order dependencies"], body: <><h3>Know who owns the symptom</h3><div className="platform-grid"><article><b>Sagenet</b><p>Digital menu boards and content display.</p></article><article><b>DTiQ</b><p>Camera and surveillance services.</p></article><article><b>Olo</b><p>Online ordering and order flow.</p></article></div><p>Correct classification determines both the troubleshooting guide and the escalation path.</p></>, quiz: { question: "A store is not receiving online orders. Which platform is directly relevant?", choices: ["DTiQ", "Olo", "Sagenet"], answer: 1, explanation: "Olo handles online ordering and the order flow into the store ecosystem." } },
  { id: "triage", number: "05", title: "First-Line Triage", duration: "10 min", summary: "Apply a repeatable process whenever a store contacts the Help Desk.", outcomes: ["Collect useful context", "Run safe basic checks", "Escalate with evidence"], body: <><h3>A consistent first response</h3><ol><li>Confirm the FC number and affected system.</li><li>Clarify the symptom, start time and impact.</li><li>Verify power, cables and restart safely when appropriate.</li><li>Retrieve the verified procedure from GlazedMind.</li><li>If unresolved, record completed steps and escalate.</li></ol><div className="onboarding-callout"><b>Golden rule</b><span>Troubleshoot from infrastructure toward the application and document what you verified.</span></div></>, quiz: { question: "What information should always be captured before troubleshooting?", choices: ["Only the requester name", "FC number, affected system and exact symptom", "The escalation email first"], answer: 1, explanation: "The FC number, affected system and symptom establish the context required for a useful diagnosis." } },
];

const scenarioSteps = [
  { prompt: "FC2045 reports that the POS and online ordering are offline. What should you ask first?", choices: ["Are other store devices online?", "Can you replace the POS?", "What is the menu price?"], answer: 0, feedback: "Correct. This establishes whether the incident affects a shared network dependency." },
  { prompt: "The customer confirms that several store systems are offline. Where should you investigate next?", choices: ["The cash drawer configuration", "The network path and Acumera or Scale", "The DTiQ camera password"], answer: 1, feedback: "Correct. Multiple affected systems point to the shared connectivity layer." },
  { prompt: "Power and cables are secure, but the connection is still unavailable. What is the best action?", choices: ["Document the checks and use the verified network escalation", "Invent new firewall settings", "Close the ticket"], answer: 0, feedback: "Correct. Preserve the evidence and escalate through the documented contact path." },
];

const finalQuestions = [
  { question: "Which value identifies the store?", choices: ["FC number", "POS password", "Camera serial"], answer: 0 },
  { question: "Which platform handles online ordering?", choices: ["Sagenet", "Olo", "DTiQ"], answer: 1 },
  { question: "What comes before application-specific troubleshooting when several systems are offline?", choices: ["Network verification", "Price change", "Printer replacement"], answer: 0 },
];

export default function OnboardingPage() {
  const [activeId, setActiveId] = useState(lessons[0].id);
  const [selectedSystem, setSelectedSystem] = useState(systems[0].id);
  const [completed, setCompleted] = useState<string[]>([]);
  const [quizChoice, setQuizChoice] = useState<number | null>(null);
  const [quizChecked, setQuizChecked] = useState(false);
  const [scenarioStep, setScenarioStep] = useState(0);
  const [scenarioChoice, setScenarioChoice] = useState<number | null>(null);
  const [scenarioComplete, setScenarioComplete] = useState(false);
  const [finalAnswers, setFinalAnswers] = useState<Array<number | null>>([null, null, null]);
  const [finalScore, setFinalScore] = useState<number | null>(null);
  const [metrics, setMetrics] = useState<TrainingMetrics>(() => newTrainingMetrics());

  useEffect(() => {
    try {
      setCompleted(JSON.parse(localStorage.getItem("glazedmind-onboarding-v2") || "[]"));
      const saved = localStorage.getItem("glazedmind-onboarding-metrics");
      if (saved) { const parsed = JSON.parse(saved) as TrainingMetrics; setMetrics(parsed); setScenarioComplete(Boolean(parsed.scenarioCompleted)); setFinalScore(parsed.finalScore); }
      else localStorage.setItem("glazedmind-onboarding-metrics", JSON.stringify(metrics));
    } catch { setCompleted([]); }
  }, []);
  const active = lessons.find((lesson) => lesson.id === activeId) || lessons[0];
  const system = systems.find((item) => item.id === selectedSystem) || systems[0];
  const checkpoints = completed.length + (scenarioComplete ? 1 : 0) + (finalScore === 3 ? 1 : 0);
  const progress = useMemo(() => Math.round((checkpoints / 7) * 100), [checkpoints]);
  const totalMistakes = Object.values(metrics.quizMistakes).reduce((sum, value) => sum + value, 0) + metrics.scenarioMistakes;
  const totalAttempts = Object.values(metrics.quizAttempts).reduce((sum, value) => sum + value, 0) + metrics.scenarioDecisions + metrics.assessmentAttempts;
  const elapsedMinutes = Math.max(1, Math.round((Date.now() - new Date(metrics.startedAt).getTime()) / 60000));

  function saveMetrics(next: TrainingMetrics) { setMetrics(next); localStorage.setItem("glazedmind-onboarding-metrics", JSON.stringify(next)); }

  function selectLesson(id: string) { setActiveId(id); setQuizChoice(null); setQuizChecked(false); }
  function checkQuiz() {
    if (quizChoice === null) return;
    setQuizChecked(true);
    saveMetrics({ ...metrics,
      quizAttempts: { ...metrics.quizAttempts, [active.id]: (metrics.quizAttempts[active.id] || 0) + 1 },
      quizMistakes: { ...metrics.quizMistakes, [active.id]: (metrics.quizMistakes[active.id] || 0) + (quizChoice === active.quiz.answer ? 0 : 1) },
    });
    if (quizChoice === active.quiz.answer && !completed.includes(active.id)) {
      const next = [...completed, active.id]; setCompleted(next); localStorage.setItem("glazedmind-onboarding-v2", JSON.stringify(next));
    }
  }
  function chooseScenario(index: number) {
    setScenarioChoice(index);
    const correct = index === scenarioSteps[scenarioStep].answer;
    const completedNow = correct && scenarioStep === scenarioSteps.length - 1;
    saveMetrics({ ...metrics, scenarioDecisions: metrics.scenarioDecisions + 1, scenarioMistakes: metrics.scenarioMistakes + (correct ? 0 : 1), scenarioCompleted: metrics.scenarioCompleted || completedNow });
    if (completedNow) setScenarioComplete(true);
  }
  function nextScenario() { if (scenarioChoice !== scenarioSteps[scenarioStep].answer) return; setScenarioStep((step) => Math.min(step + 1, scenarioSteps.length - 1)); setScenarioChoice(null); }
  function resetScenario() { setScenarioStep(0); setScenarioChoice(null); setScenarioComplete(false); }
  function gradeAssessment() { if (finalAnswers.some((answer) => answer === null)) return; const score = finalQuestions.reduce((value, question, index) => value + (finalAnswers[index] === question.answer ? 1 : 0), 0); setFinalScore(score); saveMetrics({ ...metrics, assessmentAttempts: metrics.assessmentAttempts + 1, finalScore: score, completedAt: score === 3 ? new Date().toISOString() : metrics.completedAt }); }
  function resetTraining() {
    setActiveId(lessons[0].id); setSelectedSystem(systems[0].id); setCompleted([]); setQuizChoice(null); setQuizChecked(false);
    setScenarioStep(0); setScenarioChoice(null); setScenarioComplete(false); setFinalAnswers([null, null, null]); setFinalScore(null);
    localStorage.removeItem("glazedmind-onboarding-v2");
    const fresh = newTrainingMetrics(); saveMetrics(fresh);
  }

  return <div className="app-shell">
    <aside className="sidebar"><Link className="side-logo" href="/"><img src="/glazed-mind-logo.png" alt="GlazedMind"/><span>GLAZED<br/><b>MIND</b></span></Link><nav><Link href="/"><span>{"\u2302"}</span><span>Workspace</span></Link><Link className="active" href="/onboarding"><span>{"\u25A3"}</span><span>Onboarding</span></Link><Link href="/support"><span>{"\u2726"}</span><span>Customer Portal</span></Link><Link href="/chatbot"><span>{"\u25C8"}</span><span>Chatbot</span></Link><Link href="/knowledge-base"><span>{"\u25A4"}</span><span>Knowledge Base</span></Link><Link href="/escalations"><span>{"\u2667"}</span><span>Escalations</span></Link><Link href="/impact"><span>{"\u25C9"}</span><span>Impact</span></Link></nav><div className="side-note"><b>Learning Path</b><small>{progress}% complete</small></div></aside>
    <main className="dashboard onboarding-dashboard">
      <header><div className="top-brand"><img src="/glazed-mind-logo.png" alt="GlazedMind"/><div><strong>GlazedMind</strong><small>Help Desk onboarding</small></div></div><div className="connection"><span/>Interactive training ready</div></header>
      <section className="onboarding-hero"><div><p className="eyebrow">New team member journey</p><h1>Learn by doing.<br/><em>Support with confidence.</em></h1><p>Explore the store ecosystem, solve a realistic ticket and prove that you are ready for the Help Desk.</p></div><div className="progress-card"><strong>{progress}%</strong><span>Onboarding progress</span><div><i style={{width: `${progress}%`}}/></div><small>{checkpoints} of 7 checkpoints completed</small><button onClick={resetTraining}>Reset training</button></div></section>

      <section className="system-lab"><div className="section-heading"><p className="eyebrow">Interactive map</p><h2>Follow the store connection</h2><p>Select a layer to understand its role, symptoms and first check.</p></div><div className="system-map">{systems.map((item, index) => <div className="system-map-part" key={item.id}><button className={selectedSystem === item.id ? "active" : ""} onClick={() => setSelectedSystem(item.id)}><span>{String(index + 1).padStart(2, "0")}</span><b>{item.label}</b></button>{index < systems.length - 1 && <i>{"\u2192"}</i>}</div>)}</div><div className="system-detail"><div><small>ROLE</small><p>{system.role}</p></div><div><small>COMMON SIGNAL</small><p>{system.symptoms}</p></div><div><small>FIRST CHECK</small><p>{system.first}</p></div></div></section>

      <section className="onboarding-grid"><div className="lesson-list"><div className="section-heading"><p className="eyebrow">Learn</p><h2>Core modules</h2><small>Pass each knowledge check to complete a module.</small></div>{lessons.map((lesson) => <button key={lesson.id} className={`${active.id === lesson.id ? "active" : ""} ${completed.includes(lesson.id) ? "complete" : ""}`} onClick={() => selectLesson(lesson.id)}><span>{completed.includes(lesson.id) ? "\u2713" : lesson.number}</span><div><b>{lesson.title}</b><small>{lesson.summary}</small></div><i>{lesson.duration}</i></button>)}</div>
        <article className="learning-panel"><div className="lesson-meta"><span>MODULE {active.number}</span><i>{active.duration}</i></div><h2>{active.title}</h2><p className="lesson-summary">{active.summary}</p><div className="lesson-content">{active.body}</div><div className="learning-outcomes"><b>After this module, you can:</b><ul>{active.outcomes.map((outcome) => <li key={outcome}>{outcome}</li>)}</ul></div><div className="module-quiz"><p className="eyebrow">Knowledge check</p><h3>{active.quiz.question}</h3><div className="quiz-options">{active.quiz.choices.map((choice, index) => <button key={choice} className={`${quizChoice === index ? "selected" : ""} ${quizChecked && index === active.quiz.answer ? "correct" : ""} ${quizChecked && quizChoice === index && index !== active.quiz.answer ? "incorrect" : ""}`} onClick={() => { setQuizChoice(index); setQuizChecked(false); }}>{choice}</button>)}</div><div className="quiz-footer"><button onClick={checkQuiz} disabled={quizChoice === null}>{completed.includes(active.id) ? "Module completed" : "Check answer"}</button>{quizChecked && <p className={quizChoice === active.quiz.answer ? "success" : "error"}>{quizChoice === active.quiz.answer ? "Correct. " : "Not quite. "}{active.quiz.explanation}</p>}</div></div></article>
      </section>

      <section className="practice-section"><div className="section-heading"><p className="eyebrow">Practice</p><h2>Ticket simulation</h2><p>Make the same decisions you would make during a real support interaction.</p></div><div className="scenario-card"><div className="scenario-ticket"><span>MONDAY TICKET</span><b>FC2045 - Store systems offline</b><p>The customer reports that the POS and online ordering stopped working.</p><div><small>Medium Priority</small><small>Issue</small><small>New Reply</small></div></div><div className="scenario-work"><div className="scenario-progress">{scenarioSteps.map((_, index) => <i key={index} className={`${index < scenarioStep || scenarioComplete ? "done" : ""} ${index === scenarioStep && !scenarioComplete ? "active" : ""}`}/>)}</div>{scenarioComplete ? <div className="scenario-result"><span>{"\u2713"}</span><h3>Scenario completed</h3><p>You identified the shared dependency, verified the network layer and escalated with evidence.</p><button onClick={resetScenario}>Run again</button></div> : <><small>DECISION {scenarioStep + 1} OF {scenarioSteps.length}</small><h3>{scenarioSteps[scenarioStep].prompt}</h3><div className="scenario-options">{scenarioSteps[scenarioStep].choices.map((choice, index) => <button key={choice} className={`${scenarioChoice === index ? "selected" : ""} ${scenarioChoice !== null && index === scenarioSteps[scenarioStep].answer ? "correct" : ""} ${scenarioChoice === index && index !== scenarioSteps[scenarioStep].answer ? "incorrect" : ""}`} onClick={() => chooseScenario(index)}>{choice}</button>)}</div>{scenarioChoice !== null && <p className={scenarioChoice === scenarioSteps[scenarioStep].answer ? "decision-feedback success" : "decision-feedback error"}>{scenarioChoice === scenarioSteps[scenarioStep].answer ? scenarioSteps[scenarioStep].feedback : "That action does not follow the safest documented troubleshooting path. Try again."}</p>}<button className="next-decision" disabled={scenarioChoice !== scenarioSteps[scenarioStep].answer} onClick={nextScenario}>{scenarioStep === scenarioSteps.length - 1 ? "Complete scenario" : "Next decision"} {"\u2192"}</button></>}</div></div></section>

      <section className="assessment-section"><div className="assessment-copy"><p className="eyebrow">Final assessment</p><h2>Are you Help Desk ready?</h2><p>Answer all three questions. A perfect score completes the onboarding journey.</p>{finalScore !== null && <div className={`assessment-result ${finalScore === 3 ? "passed" : "retry"}`}><strong>{finalScore}/3</strong><span>{finalScore === 3 ? "Ready for Help Desk" : "Review the modules and try again"}</span></div>}</div><div className="assessment-questions">{finalQuestions.map((question, questionIndex) => <div className="assessment-question" key={question.question}><b>{questionIndex + 1}. {question.question}</b><div>{question.choices.map((choice, choiceIndex) => <button key={choice} className={finalAnswers[questionIndex] === choiceIndex ? "selected" : ""} onClick={() => { const next = [...finalAnswers]; next[questionIndex] = choiceIndex; setFinalAnswers(next); setFinalScore(null); }}>{choice}</button>)}</div></div>)}<button className="grade-button" disabled={finalAnswers.some((answer) => answer === null)} onClick={gradeAssessment}>Submit assessment</button></div></section>
      <section className="skill-dashboard"><div className="section-heading"><p className="eyebrow">Ramp-up intelligence</p><h2>Agent readiness & skill gaps</h2><p>Results are calculated from real attempts, mistakes and completed exercises.</p></div><div className="readiness-stats"><article><strong>{progress}%</strong><span>Agent readiness</span></article><article><strong>{totalAttempts}</strong><span>Total attempts</span></article><article><strong>{totalMistakes}</strong><span>Learning mistakes</span></article><article><strong>{elapsedMinutes}m</strong><span>Training time</span></article></div><div className="skill-grid">{lessons.map((lesson) => { const mistakes = metrics.quizMistakes[lesson.id] || 0; const passed = completed.includes(lesson.id); const status = passed && mistakes <= 1 ? "Strong" : mistakes >= 2 ? "Needs reinforcement" : passed ? "Developing" : "Not assessed"; return <article key={lesson.id}><div><b>{lesson.title}</b><span className={`skill-status ${status.toLowerCase().replaceAll(" ", "-")}`}>{status}</span></div><div className="skill-bar"><i style={{width: passed ? mistakes === 0 ? "100%" : mistakes === 1 ? "82%" : "65%" : "12%"}}/></div><small>{metrics.quizAttempts[lesson.id] || 0} attempts {mistakes ? `\u00B7 ${mistakes} mistakes` : passed ? "\u00B7 passed first try" : ""}</small></article>; })}</div></section>
      <footer>THINK SWEET. &nbsp;&nbsp; SOLVE SMART.</footer>
    </main>
  </div>;
}
