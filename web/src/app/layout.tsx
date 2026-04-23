import type { Metadata } from "next";
import { Fraunces, JetBrains_Mono } from "next/font/google";
import localFont from "next/font/local";
import "./globals.css";

const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
  style: ["normal", "italic"],
  axes: ["opsz", "SOFT"],
  display: "swap",
});

const jetbrains = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

const satoshi = localFont({
  variable: "--font-satoshi",
  src: [
    {
      path: "../../public/fonts/satoshi/Satoshi-Variable.woff2",
      weight: "300 900",
      style: "normal",
    },
    {
      path: "../../public/fonts/satoshi/Satoshi-VariableItalic.woff2",
      weight: "300 900",
      style: "italic",
    },
  ],
  display: "swap",
});

const SITE_URL = "https://www.epistemekernel.com";
const SITE_TITLE = "episteme — a thinking framework for AI agents";
const SITE_DESCRIPTION =
  "Before any high-impact move, your AI coding agent has to state its reasoning on disk — core question, knowns, unknowns, what would prove the plan wrong. Posture over prompt.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: SITE_TITLE,
  description: SITE_DESCRIPTION,
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    url: SITE_URL,
    siteName: "episteme",
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
  },
  twitter: {
    card: "summary_large_image",
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${fraunces.variable} ${satoshi.variable} ${jetbrains.variable}`}
    >
      <body className="min-h-screen antialiased">
        <div className="atmosphere" aria-hidden />
        <div className="column-grid" aria-hidden>
          <div className="column-grid-inner">
            <div>
              <span className="data-stream" style={{ animationDuration: "6s", animationDelay: "0s" }} />
            </div>
            <div>
              <span className="data-stream" style={{ animationDuration: "8s", animationDelay: "1.4s" }} />
            </div>
            <div>
              <span className="data-stream" style={{ animationDuration: "5.5s", animationDelay: "0.7s" }} />
            </div>
            <div>
              <span className="data-stream" style={{ animationDuration: "7.2s", animationDelay: "2.1s" }} />
            </div>
          </div>
        </div>
        <div className="grid-overlay" aria-hidden />
        <div className="noise-layer" aria-hidden />
        <div className="gradient-blur" aria-hidden>
          <div />
          <div />
          <div />
          <div />
        </div>
        {children}
      </body>
    </html>
  );
}
