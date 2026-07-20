"use client";

import { useCallback, useState } from "react";
import { motion } from "motion/react";

/**
 * Install — the closing beat.
 *
 * The two commands are the real Claude Code plugin-marketplace quick start; the
 * plugin is complete by itself. The shell CLI belongs to the source-checkout
 * path, which the secondary link owns — conflating the two is what dead-ended
 * the project's first external adopter, so the distinction stays explicit.
 */

const COMMANDS = [
  "/plugin marketplace add junjslee/episteme",
  "/plugin install episteme@episteme",
];

const COPY_PAYLOAD = COMMANDS.join("\n");

export function Install() {
  const [copied, setCopied] = useState(false);

  const copy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(COPY_PAYLOAD);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard permission denied — the commands are visible and selectable,
      // so the visitor can still copy them by hand. Nothing to recover.
    }
  }, []);

  return (
    <section id="install" className="border-b border-hairline">
      <div className="mx-auto max-w-7xl px-6 py-24 md:px-12 md:py-32">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.7, ease: [0, 0, 0.2, 1] }}
          className="relative overflow-hidden border border-hairline bg-surface/60 p-8 md:p-14"
        >
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0"
            style={{
              background:
                "radial-gradient(ellipse 50% 60% at 85% 15%, rgba(87,199,255,0.08), transparent 65%)",
            }}
          />

          <div className="relative flex flex-col gap-10 lg:flex-row lg:items-start lg:justify-between">
            <div className="flex max-w-xl flex-col gap-5">
              <span className="font-mono text-[0.6875rem] uppercase tracking-[0.2em] text-muted">
                04 / install
              </span>
              <h2 className="font-display text-[2.25rem] leading-[1.08] text-bone md:text-[3rem]">
                Two commands, inside Claude Code.
              </h2>
              <p className="font-sans text-[1rem] leading-relaxed text-ash">
                Hooks, agents, and skills go live immediately — the gate starts
                holding your irreversible operations from the next session on.
                The <code className="font-mono text-bone">episteme</code> shell
                CLI ships with the source checkout rather than the plugin.
              </p>
            </div>

            <div className="flex w-full max-w-xl flex-col gap-4">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[0.6875rem] uppercase tracking-[0.16em] text-muted">
                  the commands
                </span>
                <button
                  type="button"
                  onClick={copy}
                  className={`inline-flex items-center gap-2 border px-3 py-1.5 font-mono text-[0.6875rem] uppercase tracking-[0.12em] transition-colors ${
                    copied
                      ? "border-verified/50 bg-verified/10 text-verified"
                      : "border-line text-ash hover:border-chain/60 hover:text-chain"
                  }`}
                  aria-live="polite"
                >
                  {copied ? "copied" : "copy"}
                </button>
              </div>

              <div className="border border-hairline bg-void p-5 font-mono text-[0.8125rem] leading-[1.9]">
                <div className="text-muted"># inside claude code</div>
                {COMMANDS.map((c) => (
                  <div key={c} className="text-bone">
                    {c}
                  </div>
                ))}
                <div className="text-muted">
                  # done — hooks, agents, and skills are live
                </div>
              </div>

              <a
                href="https://github.com/junjslee/episteme#quick-start"
                target="_blank"
                rel="noopener"
                className="font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-muted transition-colors hover:text-chain"
              >
                prefer a clone? full quick start →
              </a>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
