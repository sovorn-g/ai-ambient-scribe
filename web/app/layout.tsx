import type { Metadata } from "next";
import { Space_Grotesk, Lora } from "next/font/google";
import "./globals.css";

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-grotesk",
  display: "swap",
});

const lora = Lora({
  subsets: ["latin"],
  variable: "--font-lora",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Ambient Scribe",
  description: "Fully-local AI ambient scribe — audio to FHIR R5 clinical note",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${spaceGrotesk.variable} ${lora.variable} font-grotesk bg-vellum text-nuit min-h-screen`}>
        {children}
      </body>
    </html>
  );
}
