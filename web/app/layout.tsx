import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ambient Scribe",
  description: "Fully-local AI ambient scribe for clinical consultations",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-50 min-h-screen font-sans">{children}</body>
    </html>
  );
}
