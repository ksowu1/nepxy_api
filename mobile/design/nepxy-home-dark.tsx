import React, { useMemo, useState } from "react";

/**
 * Nepxy — High‑Fidelity Mobile Home Page (Dark Theme)
 *
 * Edit visuals directly: Tailwind classes, copy, tokens.
 * This is a single “Figma-style” phone frame for the home screen.
 */

const TOKENS = {
  brand: {
    name: "Nepxy",
    accent: "cyan",
  },
  colors: {
    bg: "bg-[#0B0F1A]", // deep navy
    surface: "bg-[#10182B]", // card surface
    surface2: "bg-[#0F1526]", // alt surface
    border: "border-white/10",
    text: "text-white",
    muted: "text-white/60",
    muted2: "text-white/40",

    // Nepxy accent (Option A: Electric Cyan)
    accentBg: "bg-cyan-500",
    accentBgHover: "hover:bg-cyan-400",
    accentText: "text-white",

    good: "text-emerald-400",
    warn: "text-amber-300",
  },
  radius: {
    frame: "rounded-[34px]",
    card: "rounded-3xl",
    pill: "rounded-full",
    btn: "rounded-2xl",
  },
  shadow: {
    frame: "shadow-[0_18px_60px_rgba(0,0,0,0.55)]",
    glow: "shadow-[0_0_0_1px_rgba(255,255,255,0.06),_0_10px_40px_rgba(34,211,238,0.18)]",
  },
};

function cn(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

// ---------------------------
// Self-tests (lightweight)
// ---------------------------

function runSelfTests() {
  // These are lightweight sanity checks to catch syntax/regression issues
  // in this visual canvas. They should be safe in dev.
  const isProd =
    typeof process !== "undefined" &&
    typeof process.env !== "undefined" &&
    process.env.NODE_ENV === "production";

  if (isProd) return;

  // cn()
  const joined = cn("a", false, "b", undefined, null, "c");
  if (joined !== "a b c") throw new Error(`cn() failed: got "${joined}"`);

  // Token presence
  if (!TOKENS.colors.accentBg || !TOKENS.colors.accentBgHover) {
    throw new Error("TOKENS.colors accent values missing");
  }
  if (!TOKENS.brand.name) throw new Error("TOKENS.brand.name missing");
}

runSelfTests();

// ---------------------------
// Icons (inline, editable)
// ---------------------------

type IconName =
  | "qr"
  | "gear"
  | "money"
  | "send"
  | "activity"
  | "gift"
  | "arrowUpRight"
  | "arrowDownLeft"
  | "bolt";

function Icon({ name }: { name: IconName }) {
  const common = "h-6 w-6";
  switch (name) {
    case "qr":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M4 4h6v6H4V4z" stroke="currentColor" strokeWidth="1.8" />
          <path d="M14 4h6v6h-6V4z" stroke="currentColor" strokeWidth="1.8" />
          <path d="M4 14h6v6H4v-6z" stroke="currentColor" strokeWidth="1.8" />
          <path d="M14 14h3v3h-3v-3z" stroke="currentColor" strokeWidth="1.8" />
          <path d="M20 14v6h-6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          <path d="M14 20h2.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          <path d="M18 18h2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      );

    case "gear":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path
            d="M12 15.5a3.5 3.5 0 100-7 3.5 3.5 0 000 7z"
            stroke="currentColor"
            strokeWidth="1.8"
          />
          <path
            d="M19.4 15a8 8 0 00.1-1l2-1.2-2-3.6-2.3.6a7.7 7.7 0 00-1.7-1L15 6h-6l-.5 2.8a7.7 7.7 0 00-1.7 1L4.5 9.2l-2 3.6 2 1.2a8 8 0 00.1 1 8 8 0 00-.1 1l-2 1.2 2 3.6 2.3-.6a7.7 7.7 0 001.7 1L9 22h6l.5-2.8a7.7 7.7 0 001.7-1l2.3.6 2-3.6-2-1.2a8 8 0 00-.1-1z"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinejoin="round"
          />
        </svg>
      );

    case "money":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M4 7h16v10H4V7z" stroke="currentColor" strokeWidth="1.8" />
          <path d="M8 12h.01" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
          <path d="M16 12h.01" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
          <path d="M12 10a2 2 0 100 4 2 2 0 000-4z" stroke="currentColor" strokeWidth="1.8" />
        </svg>
      );

    case "send":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path
            d="M21 3L10 14"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M21 3l-7 18-4-7-7-4 18-7z"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinejoin="round"
          />
        </svg>
      );

    case "activity":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path
            d="M3 12h4l2-6 4 12 2-6h6"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      );

    case "gift":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M20 12v10H4V12" stroke="currentColor" strokeWidth="1.8" />
          <path d="M2 7h20v5H2V7z" stroke="currentColor" strokeWidth="1.8" />
          <path d="M12 22V7" stroke="currentColor" strokeWidth="1.8" />
          <path
            d="M12 7c-1.8 0-3-1-3-2.2C9 3.6 10 3 11 3c1.6 0 2.4 1.6 2 4z"
            stroke="currentColor"
            strokeWidth="1.8"
          />
          <path
            d="M12 7c1.8 0 3-1 3-2.2C15 3.6 14 3 13 3c-1.6 0-2.4 1.6-2 4z"
            stroke="currentColor"
            strokeWidth="1.8"
          />
        </svg>
      );

    case "arrowUpRight":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M7 17L17 7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          <path d="M10 7h7v7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      );

    case "arrowDownLeft":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M17 7L7 17" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          <path d="M7 10v7h7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      );

    case "bolt":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path
            d="M13 2L3 14h8l-1 8 11-14h-8V2z"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinejoin="round"
          />
        </svg>
      );

    default:
      return <div className={common} />;
  }
}

// ---------------------------
// Phone Frame
// ---------------------------

type PhoneFrameProps = {
  title?: string;
  children: React.ReactNode;
};

function PhoneFrame({ title, children }: PhoneFrameProps) {
  return (
    <div className="w-[390px]">
      <div
        className={cn(
          "relative mx-auto h-[780px] w-[390px] overflow-hidden border",
          TOKENS.colors.border,
          TOKENS.radius.frame,
          TOKENS.shadow.frame,
          TOKENS.colors.bg
        )}
      >
        {/* subtle background glow */}
        <div className="pointer-events-none absolute -top-24 left-1/2 h-72 w-72 -translate-x-1/2 rounded-full bg-cyan-500/15 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-32 left-10 h-72 w-72 rounded-full bg-fuchsia-500/10 blur-3xl" />

        {/* status bar */}
        <div className="flex items-center justify-between px-6 pt-4 text-xs text-white/70">
          <div className="font-medium">9:41</div>
          <div className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-white/35" />
            <span className="h-2 w-2 rounded-full bg-white/35" />
            <span className="h-2 w-2 rounded-full bg-white/35" />
            <span className="ml-2">100%</span>
          </div>
        </div>

        {/* optional title (hidden by default for home) */}
        {title ? <div className="px-6 pt-3 text-sm font-semibold text-white/90">{title}</div> : null}

        <div className="relative px-6 pb-28 pt-4">{children}</div>

        {/* home indicator */}
        <div className="absolute bottom-3 left-1/2 h-1.5 w-28 -translate-x-1/2 rounded-full bg-white/20" />
      </div>
    </div>
  );
}

// ---------------------------
// Components
// ---------------------------

function IconButton({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-label={label}
      className={cn(
        "inline-flex h-11 w-11 items-center justify-center",
        TOKENS.radius.pill,
        "border border-white/10 bg-white/5 text-white hover:bg-white/10"
      )}
    >
      {children}
    </button>
  );
}

type PrimaryActionIcon = "arrowDownLeft" | "arrowUpRight";

function PrimaryAction({ label, icon }: { label: string; icon: PrimaryActionIcon }) {
  return (
    <button
      type="button"
      className={cn(
        "flex w-full items-center justify-between gap-3 px-4 py-4",
        TOKENS.radius.btn,
        "bg-white/8 text-white hover:bg-white/12",
        "border border-white/10"
      )}
    >
      <div>
        <div className="text-xs text-white/60">Action</div>
        <div className="mt-0.5 text-sm font-semibold">{label}</div>
      </div>
      <div className={cn("flex h-10 w-10 items-center justify-center rounded-2xl", "bg-cyan-500/20 text-cyan-200")}>
        <Icon name={icon} />
      </div>
    </button>
  );
}

function Card({
  title,
  subtitle,
  right,
  icon,
  children,
}: {
  title: string;
  subtitle?: string;
  right?: React.ReactNode;
  icon?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "border",
        TOKENS.colors.border,
        TOKENS.radius.card,
        "p-4",
        TOKENS.colors.surface,
        TOKENS.shadow.glow
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          {icon ? (
            <div className="mt-0.5 flex h-10 w-10 items-center justify-center rounded-2xl bg-white/6 text-white/80">
              {icon}
            </div>
          ) : null}
          <div>
            <div className="text-sm font-semibold text-white">{title}</div>
            {subtitle ? <div className="mt-1 text-xs text-white/60">{subtitle}</div> : null}
          </div>
        </div>
        {right ? <div className="pt-1">{right}</div> : null}
      </div>

      {children ? <div className="mt-4">{children}</div> : null}
    </div>
  );
}

function Pill({ children }: { children: React.ReactNode }) {
  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] text-white/70">
      {children}
    </div>
  );
}

function BottomTab({
  active,
  label,
  icon,
}: {
  active?: boolean;
  label: string;
  icon: "money" | "send" | "activity";
}) {
  return (
    <button type="button" className="flex flex-1 flex-col items-center justify-center gap-1 py-3">
      <div
        className={cn(
          "flex h-10 w-14 items-center justify-center rounded-2xl border",
          active
            ? "border-cyan-300/40 bg-cyan-500/15 text-cyan-200"
            : "border-white/10 bg-white/5 text-white/60"
        )}
      >
        <Icon name={icon} />
      </div>
      <div className={cn("text-[11px]", active ? "text-white" : "text-white/55")}>{label}</div>
    </button>
  );
}

// ---------------------------
// Home Screen
// ---------------------------

type LastTxn = {
  from: "USD" | "EUR";
  to: "GHS" | "NGN";
  rate: number;
  ts: string;
};

export default function NepxyHomePageCanvas() {
  const [cashBalance, setCashBalance] = useState(1240.55);

  // “Based on the last transaction” (editable demo state)
  const lastTxn: LastTxn = useMemo(() => ({ from: "USD", to: "GHS", rate: 13.2, ts: "Just now" }), []);

  return (
    <div className={cn("min-h-screen", TOKENS.colors.bg)}>
      <div className="mx-auto max-w-6xl px-4 py-8">
        <div className="mb-4">
          <div className="text-sm font-semibold text-white">Nepxy — Home (Hi‑Fi Dark)</div>
          <div className="mt-1 text-xs text-white/60">
            Edit the UI by tweaking Tailwind classes + copy inside this canvas.
          </div>
        </div>

        <div className="overflow-x-auto">
          <div className="flex w-max items-start gap-8 pb-8">
            <div className="space-y-2">
              <div className="px-2 text-xs font-semibold text-white/60">Home</div>

              <PhoneFrame>
                {/* Header: QR left, gear right */}
                <div className="flex items-center justify-between">
                  <IconButton label="Scan QR">
                    <Icon name="qr" />
                  </IconButton>

                  <div className="flex items-center gap-2">
                    <Pill>
                      <span className="h-2 w-2 rounded-full bg-emerald-400" />
                      <span>Online</span>
                    </Pill>
                    <IconButton label="Settings">
                      <Icon name="gear" />
                    </IconButton>
                  </div>
                </div>

                {/* Main Hero: Cash Balance + actions */}
                <div className="mt-6">
                  <div className="text-xs text-white/60">Cash Balance</div>
                  <div className="mt-2 flex items-end justify-between gap-3">
                    <div>
                      <div className="text-4xl font-extrabold tracking-tight text-white">
                        ${cashBalance.toLocaleString(undefined, {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}
                      </div>
                      <div className="mt-2 text-xs text-white/60">Available to send or withdraw</div>
                    </div>
                    <button
                      type="button"
                      className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-white/70 hover:bg-white/10"
                      onClick={() => setCashBalance((v) => v + 25)}
                      title="Demo: adds $25"
                    >
                      +$25
                    </button>
                  </div>

                  <div className="mt-5 grid grid-cols-2 gap-3">
                    <PrimaryAction label="Add Money" icon="arrowDownLeft" />
                    <PrimaryAction label="Withdraw" icon="arrowUpRight" />
                  </div>
                </div>

                {/* Mid section: Live FX + Referral */}
                <div className="mt-6 grid gap-4">
                  <Card
                    title="Live Exchange Rate"
                    subtitle={`Based on your last transfer • ${lastTxn.ts}`}
                    icon={<Icon name="bolt" />}
                    right={<span className="text-[11px] font-semibold text-emerald-300">Live</span>}
                  >
                    <div className="rounded-3xl border border-white/10 bg-white/5 p-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-xs text-white/60">Rate</div>
                          <div className="mt-1 text-lg font-extrabold text-white">
                            1 {lastTxn.from} → {lastTxn.rate} {lastTxn.to}
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-xs text-white/60">Trend</div>
                          <div className="mt-1 text-sm font-semibold text-emerald-300">+0.4%</div>
                        </div>
                      </div>
                      <div className="mt-3 flex items-center justify-between text-[11px] text-white/60">
                        <span>Updated moments ago</span>
                        <button type="button" className="font-semibold text-cyan-200 hover:text-cyan-100">
                          View rates
                        </button>
                      </div>
                    </div>
                  </Card>

                  <Card
                    title="Referral Program"
                    subtitle="Invite friends. Earn rewards when they send."
                    icon={<Icon name="gift" />}
                    right={
                      <button
                        type="button"
                        className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-semibold text-white/70 hover:bg-white/10"
                      >
                        Share
                      </button>
                    }
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="text-xs text-white/60">Your code</div>
                        <div className="mt-1 inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-black/20 px-3 py-2 text-sm font-semibold text-white">
                          NEPXY-7K2P
                          <span className="text-[11px] font-medium text-white/50">Copy</span>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-xs text-white/60">Bonus</div>
                        <div className="mt-1 text-sm font-semibold text-emerald-300">$5 each</div>
                      </div>
                    </div>
                  </Card>
                </div>

                {/* Bottom Navigation (fixed) */}
                <div className="pointer-events-none absolute inset-x-0 bottom-0 px-4 pb-6">
                  <div className="pointer-events-auto rounded-3xl border border-white/10 bg-[#0A0E18]/80 p-2 backdrop-blur">
                    <div className="flex items-center">
                      <BottomTab active label="Money" icon="money" />
                      <BottomTab label="Send" icon="send" />
                      <BottomTab label="Activity" icon="activity" />
                    </div>
                  </div>
                </div>
              </PhoneFrame>

              {/* Notes */}
              <div className="max-w-[390px] rounded-2xl border border-white/10 bg-white/5 p-4 text-xs text-white/60">
                <div className="font-semibold text-white/80">Canvas notes</div>
                <ul className="mt-2 list-disc space-y-1 pl-5">
                  <li>Header icons: QR (left), Settings (right).</li>
                  <li>Hero balance is large + bold, actions are side-by-side.</li>
                  <li>Cards: Live FX first, then Referral.</li>
                  <li>Bottom nav is fixed, 3 tabs: Money / Send / Activity.</li>
                </ul>
              </div>
            </div>

            {/* Optional: Theme swatches panel (editable tokens) */}
            <div className="w-[360px]">
              <div className="rounded-3xl border border-white/10 bg-white/5 p-5 text-white/80">
                <div className="text-sm font-semibold">Theme controls (edit tokens)</div>
                <div className="mt-3 grid gap-3 text-xs text-white/60">
                  <div className="flex items-center justify-between">
                    <span>Background</span>
                    <span className="font-mono">{TOKENS.colors.bg}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Surface</span>
                    <span className="font-mono">{TOKENS.colors.surface}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Accent</span>
                    <span className="font-mono">{TOKENS.colors.accentBg}</span>
                  </div>
                </div>
                <div className="mt-4 text-[11px] text-white/50">
                  Note: This canvas can’t generate a native “Open in Figma” link automatically. When you approve the layout, I’ll give you an exact plugin workflow (HTML-to-Figma) to import these layers.
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
