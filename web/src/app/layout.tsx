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
const SITE_TITLE = "episteme — a way to think when the model can finish your sentences";
const SITE_DESCRIPTION =
  "episteme is a way to think — 생각의 틀. A five-stage practice (frame, decompose, execute, verify, handoff) made mechanical at the file system level. Before any irreversible move, you write down what you know, what you don't, and what would prove you wrong; a hook refuses to proceed if that reasoning is thin. The practice is the product — the signed, hash-chained trail is what it leaves behind.";

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
