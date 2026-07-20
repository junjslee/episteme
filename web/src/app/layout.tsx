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
const SITE_TITLE = "episteme — make the AI show its work";
const SITE_DESCRIPTION =
  "episteme is 생각의 틀 — a way to think, enforced at the moment before irreversible action. Before an agent does something it cannot take back, it writes down what it knows, what it doesn't, and what would prove it wrong; a deterministic gate holds until that artifact is real. What the decision teaches is hash-chained into a protocol that resurfaces at the next matching decision.";

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
        {/* Ambient chrome, all pointer-events:none and behind content. The
            hero's WebGL scene supplies its own depth, so these layers stay
            deliberately faint — they carry the sections below the fold. */}
        <div className="atmosphere" aria-hidden />
        <div className="grid-overlay" aria-hidden />
        <div className="noise-layer" aria-hidden />
        {children}
      </body>
    </html>
  );
}
