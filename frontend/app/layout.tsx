import type { Metadata } from "next";
import "./globals.css";
import "./answer-fix.css";
import "./chatbot/chatbot.css";
import "./chatbot/escalation.css";
import "./support/support.css";
import "./demo.css";

export const metadata: Metadata = {
  title: "Glazed Mind | Help Desk Copilot",
  description: "AI help desk copilot for Shipley Do-Nuts",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
