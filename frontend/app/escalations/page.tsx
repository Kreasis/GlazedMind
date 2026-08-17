"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

type Contact = {
  name: string;
  scope: string;
  category: string;
  details: string[];
  note?: string;
};

const contacts: Contact[] = [
  { name: "NCR Aloha Cloud Support", scope: "NCR POS", category: "NCR & Payments", details: ["Phone: (877) 270-3475", "Email: customercare@ncrvoyix.com", "Support representative: Ana.Majstorovic@ncrvoyix.com", "Account manager: Viviana.Lujan@ncrvoyix.com", "PTO backup: Stefan.Bubanja@ncrvoyix.com"] },
  { name: "Payments Assist", scope: "Credit card processor", category: "NCR & Payments", details: ["Phone: (800) 834-4405", "Email: assist.payments@ncrvoyix.com"] },
  { name: "Connected Payments", scope: "Connected payments support", category: "NCR & Payments", details: ["Phone: (800) 433-0355"] },
  { name: "Credit Card Reader Registration", scope: "Reader registration", category: "NCR & Payments", details: ["Email: VoyixConnect.Support@ncrvoyix.com"] },
  { name: "PCI Compliance Contact", scope: "NCR PCI compliance", category: "NCR & Payments", details: ["Phone: (855) 826-2132", "Select option 1 or 2"] },
  { name: "Double Charges NCR", scope: "Duplicate or double charges", category: "NCR & Payments", details: ["Email: voyixpay.support@ncrvoyix.com"] },
  { name: "NCR Escalation", scope: "NCR escalation path", category: "NCR & Payments", details: ["Email: silverescalate@ncrvoyix.com"] },
  { name: "OLO Help", scope: "OLO and menu-related issues", category: "Ordering & Menus", details: ["Hours: 9:00 AM\u20136:00 PM EST", "Phone: (844) 656-2414", "Account representative: emily.hone@olo.com"], note: "Create a ticket in OLO Help first and save the ticket number. The account representative can help escalate an existing ticket when necessary." },
  { name: "Scale Computing Support", scope: "Network, firewall, and internet", category: "Network & Store Systems", details: ["Phone: (512) 617-0923", "Queue: Partner Queue \u2014 Level 2", "Email: team@scalecomputing.com"], note: "The source document also references the Scale Computing NOC & Technical Support Escalation Process \u2014 General 2026." },
  { name: "SageNet Support", scope: "Digital menu boards, front-screen monitors, and content management", category: "Network & Store Systems", details: ["Phone: (470) 632-1128", "Support: digitalsignageCTS@sagenet.com", "Menu updates: digitalsignagemedia@sagenet.com"] },
  { name: "DTiQ Drive Thru Support", scope: "Headsets, timers, cameras, and surveillance", category: "Drive Thru & Security", details: ["PAR headsets: (800) 328-0033", "Cameras / 360: (866) 388-7877", "Surveillance 24/7: (800) 933-8388", "Drive-thru support: drivethrusupport@dtiq.com", "Timer reporting: panoramasupport@dtiq.com", "General support: Support@dtiq.com"] },
  { name: "Uber Help", scope: "Uber merchant support", category: "Third-Party Delivery", details: ["Phone: (833) 275-3287", "Email: merchants@uber.com"] },
  { name: "3PT Refunds", scope: "Uber third-party refunds", category: "Third-Party Delivery", details: ["Email: restaurants@uber.com"] },
  { name: "DoorDash", scope: "Orders and customer refunds", category: "Third-Party Delivery", details: ["Phone: (855) 222-8111", "Availability: 24/7", "Merchant support: mxpsupport@doordash.com"], note: "For a cancelled-order refund, use Help \u2192 Merchant Experience Partner \u2192 Send Message \u2192 Marketplace \u2192 Payments \u2192 Cancelled Order Refund. Include escalations@shipleydonuts.com in the email. Customer refund requests are normally submitted by the customer through DoorDash website, app, or Customer Support." },
  { name: "SynergySuite Support", scope: "SynergySuite", category: "Business Applications", details: ["Phone: (888) 531-2090", "Email: support@synergysuite.com", "Availability: Monday\u2013Friday"] },
  { name: "Supply Chain / Bakemark", scope: "Incomplete orders and order deletion requests", category: "Business Applications", details: ["Email: supplychain@shipleydonuts.com"], note: "For franchisee requests to delete an order, obtain approval through this email first. Also use it for customer complaints involving incomplete orders." },
  { name: "Saivory", scope: "Shipley website", category: "Websites & Apps", details: ["Email: diego@saivory.com"], note: "The document states that Saivory will take responsibility for the app in the future, but no date is currently documented." },
  { name: "Clutch", scope: "Shipley website", category: "Websites & Apps", details: ["Email: sophie@clutch.io"] },
  { name: "Paytronix", scope: "App issues, discounts, and reward redemption", category: "Websites & Apps", details: ["Email: support@paytronix.com", "CC: marketing@shipleydonuts.com"] },
];

const categories = [...new Set(contacts.map((contact) => contact.category))];

export default function EscalationsPage() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All");
  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    return contacts.filter((contact) =>
      (category === "All" || contact.category === category) &&
      (!term || [contact.name, contact.scope, contact.category, ...contact.details, contact.note || ""].join(" ").toLowerCase().includes(term)),
    );
  }, [query, category]);

  return <div className="app-shell">
    <aside className="sidebar">
      <Link className="side-logo" href="/"><img src="/glazed-mind-logo.png" alt="GlazedMind"/><span>GLAZED<br/><b>MIND</b></span></Link>
      <nav>
        <Link href="/"><span>{"\u2302"}</span><span>Workspace</span></Link>
        <Link href="/onboarding"><span>{"\u25A3"}</span><span>Onboarding</span></Link>
        <Link href="/support"><span>{"\u2726"}</span><span>Customer Portal</span></Link><Link href="/chatbot"><span>{"\u25C8"}</span><span>Chatbot</span></Link>
        <Link href="/knowledge-base"><span>{"\u25A4"}</span><span>Knowledge Base</span></Link>
        <Link className="active" href="/escalations"><span>{"\u2667"}</span><span>Escalations</span></Link>
        <Link href="/impact"><span>{"\u25C9"}</span><span>Impact</span></Link>
      </nav>
      <div className="side-note"><b>Reference directory</b><small>Verified contact guide</small></div>
    </aside>

    <main className="dashboard escalation-dashboard">
      <header><div className="top-brand"><img src="/glazed-mind-logo.png" alt=""/><div><strong>GlazedMind</strong><small>Escalation directory {"\u00B7"} Help Desk workspace</small></div></div><div className="connection"><span/>Point of Contacts connected</div></header>

      <section className="escalation-hero">
        <div><p className="eyebrow">Verified support directory</p><h1>Escalation <em>Points of Contact</em></h1><p>Find the correct vendor or internal team after documented troubleshooting has been exhausted.</p></div>
        <div className="directory-stat"><b>{contacts.length}</b><span>documented contacts</span><small>{categories.length} support categories</small></div>
      </section>

      <section className="directory-controls" aria-label="Filter escalation contacts">
        <label><span>Search contacts</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search NCR, printer, refund, network\u2026"/></label>
        <div className="category-filters">
          {["All", ...categories].map((item) => <button className={category === item ? "active" : ""} key={item} onClick={() => setCategory(item)}>{item}</button>)}
        </div>
      </section>

      <section className="directory-results">
        <div className="directory-heading"><div><p className="eyebrow">Contact directory</p><h2>{category === "All" ? "All escalation paths" : category}</h2></div><span>{filtered.length} {filtered.length === 1 ? "contact" : "contacts"}</span></div>
        {filtered.length ? <div className="contact-grid">{filtered.map((contact) => <article className="directory-card" key={contact.name}>
          <div className="contact-card-top"><span>{contact.category}</span><i>Verified</i></div>
          <h3>{contact.name}</h3><p className="contact-scope">{contact.scope}</p>
          <ul>{contact.details.map((detail) => <li key={detail}>{detail}</li>)}</ul>
          {contact.note && <div className="contact-note"><b>Before escalating</b><p>{contact.note}</p></div>}
        </article>)}</div> : <div className="directory-empty"><b>No matching contacts</b><span>Try another platform, issue, or category.</span></div>}
      </section>
      <footer>THINK SWEET. &nbsp; SOLVE SMART.</footer>
    </main>
  </div>;
}

