import React, { useMemo, useState } from "react";

/**
 * Nepxy — Mobile Registration Flow (Figma-style frames)
 *
 * This is a VISUAL canvas: it renders screens side-by-side for design.
 * Edit visuals by changing Tailwind classes, copy, or the token objects.
 */

const TOKENS = {
  brand: {
    name: "Nepxy",
    tagline: "Send money across borders — fast",
  },
  colors: {
    primary: "bg-indigo-600",
    primaryHover: "hover:bg-indigo-700",
    primaryText: "text-white",
    border: "border-slate-200",
    muted: "text-slate-500",
  },
  radius: {
    card: "rounded-3xl",
  },
  shadow: {
    card: "shadow-[0_12px_40px_rgba(2,6,23,0.10)]",
  },
} as const;

function cn(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

// ---------------------------
// Demo data (replace later)
// ---------------------------

type Country = { iso2: string; name: string; dial: string };

// For production: load full ISO-3166 + dial codes from a trusted dataset.
const COUNTRY_REGIONS: Country[] = [
  { iso2: "US", name: "United States", dial: "+1" },
  { iso2: "GH", name: "Ghana", dial: "+233" },
  { iso2: "BJ", name: "Benin", dial: "+229" },
  { iso2: "TG", name: "Togo", dial: "+228" },
  { iso2: "GB", name: "United Kingdom", dial: "+44" },
];

type Currency = { code: string; name: string; providers: string[] };

// NOTE: For production, hydrate this from provider capability endpoints.
const SUPPORTED_CURRENCIES: Currency[] = [
  { code: "USD", name: "US Dollar", providers: ["THUNES"] },
  { code: "EUR", name: "Euro", providers: ["THUNES"] },
  { code: "GBP", name: "British Pound", providers: ["THUNES"] },
  { code: "CAD", name: "Canadian Dollar", providers: ["THUNES"] },
  { code: "GHS", name: "Ghanaian Cedi", providers: ["THUNES", "MTN_MOMO"] },
  { code: "XOF", name: "West African CFA franc", providers: ["THUNES"] },
  { code: "XAF", name: "Central African CFA franc", providers: ["THUNES"] },
  { code: "NGN", name: "Nigerian Naira", providers: ["THUNES"] },
  { code: "KES", name: "Kenyan Shilling", providers: ["THUNES"] },
];

const DEMO_RATE: Record<string, number> = {
  XOF: 610,
  GHS: 13.2,
  NGN: 1450,
  XAF: 610,
  KES: 158,
  EUR: 0.92,
  GBP: 0.79,
};

function getRateSafe(to: string) {
  const has = Object.prototype.hasOwnProperty.call(DEMO_RATE, to);
  return has ? DEMO_RATE[to] : 1;
}

function flagEmoji(iso2: string) {
  if (!iso2 || iso2.length !== 2) return "🏳️";
  const codePoints = iso2
    .toUpperCase()
    .split("")
    .map((c) => 127397 + c.charCodeAt(0));

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return String.fromCodePoint.apply(String, codePoints as any);
}

// ---------------------------
// Self-tests (lightweight)
// ---------------------------

function runSelfTests() {
  // Tiny sanity checks to catch common typos/regressions.
  // Not a replacement for real unit tests.
  const isProd =
    typeof process !== "undefined" &&
    typeof process.env !== "undefined" &&
    process.env.NODE_ENV === "production";

  if (isProd) return;

  // cn()
  const joined = cn("a", false, "b", undefined, null, "c");
  if (joined !== "a b c") throw new Error(`cn() failed: got "${joined}"`);

  // flagEmoji()
  const us = flagEmoji("US");
  if (typeof us !== "string" || us.length === 0) throw new Error("flagEmoji() failed");
  if (us === "🏳️") throw new Error("flagEmoji() should not return fallback for valid iso2");

  // getRateSafe()
  const r1 = getRateSafe("XOF");
  const r2 = getRateSafe("ZZZ");
  if (typeof r1 !== "number" || typeof r2 !== "number") throw new Error("getRateSafe() failed");
  if (r2 !== 1) throw new Error("getRateSafe() default should be 1");
  if (r1 <= 0) throw new Error("getRateSafe() should return a positive number");

  // data shape expectations
  const hasUS = COUNTRY_REGIONS.some((c) => c.iso2 === "US" && c.dial === "+1");
  if (!hasUS) throw new Error("COUNTRY_REGIONS missing US (+1)");

  const hasUSD = SUPPORTED_CURRENCIES.some((c) => c.code === "USD");
  if (!hasUSD) throw new Error("SUPPORTED_CURRENCIES missing USD");

  const hasXOF = SUPPORTED_CURRENCIES.some((c) => c.code === "XOF");
  if (!hasXOF) throw new Error("SUPPORTED_CURRENCIES missing XOF");

  // Ensure unique currency codes
  const codes = SUPPORTED_CURRENCIES.map((c) => c.code);
  const unique = new Set(codes);
  if (unique.size !== codes.length) throw new Error("SUPPORTED_CURRENCIES has duplicate codes");

  // Ensure unique country iso2
  const iso2s = COUNTRY_REGIONS.map((c) => c.iso2);
  const uniqueIso = new Set(iso2s);
  if (uniqueIso.size !== iso2s.length) throw new Error("COUNTRY_REGIONS has duplicate iso2 entries");

  // Filter behavior (used by CurrencyDropdown)
  const search = (q: string) => {
    const qq = q.trim().toLowerCase();
    return SUPPORTED_CURRENCIES.filter((c) => {
      if (!qq) return true;
      return c.code.toLowerCase().includes(qq) || c.name.toLowerCase().includes(qq);
    }).map((c) => c.code);
  };

  if (!search("xof").includes("XOF")) throw new Error("Currency search should match by code");
  if (!search("ghana").includes("GHS")) throw new Error("Currency search should match by name");
}

runSelfTests();

// ---------------------------
// Shared UI atoms
// ---------------------------

type PhoneFrameProps = {
  title: string;
  subtitle?: string;
  step?: number;
  totalSteps?: number;
  children: React.ReactNode;
};

function PhoneFrame({ title, subtitle, step, totalSteps = 4, children }: PhoneFrameProps) {
  return (
    <div className="w-[360px]">
      <div
        className={cn(
          "relative mx-auto h-[740px] w-[360px] overflow-hidden border bg-white",
          TOKENS.colors.border,
          TOKENS.radius.card,
          TOKENS.shadow.card
        )}
      >
        {/* Status bar */}
        <div className="flex items-center justify-between px-5 pt-4 text-xs text-slate-500">
          <div className="font-medium">9:41</div>
          <div className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-slate-300" />
            <span className="h-2 w-2 rounded-full bg-slate-300" />
            <span className="h-2 w-2 rounded-full bg-slate-300" />
            <span className="ml-2">100%</span>
          </div>
        </div>

        {/* Header */}
        <div className="px-5 pt-4">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-sm font-semibold text-slate-900">{title}</div>
              {subtitle ? <div className="mt-1 text-xs text-slate-500">{subtitle}</div> : null}
            </div>
            <div className="text-xs text-slate-400">{TOKENS.brand.name}</div>
          </div>

          {/* Progress */}
          {typeof step === "number" ? (
            <div className="mt-4">
              <div className="flex items-center justify-between text-[11px] text-slate-500">
                <span>
                  Step {step} of {totalSteps}
                </span>
                <button
                  type="button"
                  className="rounded-full px-2 py-1 text-[11px] text-slate-500 hover:bg-slate-100"
                >
                  Need help?
                </button>
              </div>
              <div className="mt-2 h-2 w-full rounded-full bg-slate-100">
                <div
                  className="h-2 rounded-full bg-indigo-600"
                  style={{ width: `${Math.round((step / totalSteps) * 100)}%` }}
                />
              </div>
            </div>
          ) : null}
        </div>

        {/* Body */}
        <div className="px-5 pb-24 pt-5">{children}</div>

        {/* Home indicator */}
        <div className="absolute bottom-3 left-1/2 h-1.5 w-28 -translate-x-1/2 rounded-full bg-slate-200" />
      </div>
    </div>
  );
}

function PrimaryButton({
  children,
  disabled,
  className,
}: {
  children: React.ReactNode;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <button
      type="button"
      className={cn(
        "w-full rounded-2xl px-4 py-3 text-sm font-semibold transition",
        TOKENS.colors.primary,
        TOKENS.colors.primaryText,
        TOKENS.colors.primaryHover,
        disabled && "pointer-events-none opacity-50",
        className
      )}
    >
      {children}
    </button>
  );
}

function SecondaryButton({ children }: { children: React.ReactNode }) {
  return (
    <button
      type="button"
      className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-900 hover:bg-slate-50"
    >
      {children}
    </button>
  );
}

function Input({
  label,
  placeholder,
  hint,
  right,
}: {
  label: string;
  placeholder?: string;
  hint?: string;
  right?: string;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-xs font-medium text-slate-700">{label}</label>
        {right ? <div className="text-xs text-slate-500">{right}</div> : null}
      </div>
      <div className="relative">
        <input
          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-200"
          placeholder={placeholder}
        />
      </div>
      {hint ? <p className="text-[11px] text-slate-500">{hint}</p> : null}
    </div>
  );
}

function Chip({ active, children }: { active?: boolean; children: React.ReactNode }) {
  return (
    <button
      type="button"
      className={cn(
        "rounded-full border px-3 py-1 text-xs font-medium",
        active
          ? "border-indigo-200 bg-indigo-50 text-indigo-700"
          : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
      )}
    >
      {children}
    </button>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return <div className="rounded-3xl border border-slate-200 bg-white p-4">{children}</div>;
}

function FooterActions({
  primary,
  secondary,
  note,
}: {
  primary: React.ReactNode;
  secondary?: React.ReactNode;
  note?: React.ReactNode;
}) {
  return (
    <div className="absolute bottom-10 left-0 right-0 px-5">
      <div className="space-y-3">
        {primary}
        {secondary}
        {note ? <div className="text-center text-[11px] text-slate-500">{note}</div> : null}
      </div>
    </div>
  );
}

// ---------------------------
// Icons + small components
// ---------------------------

function Icon({ name }: { name: "shield" | "globe" | "bolt" | "user" | "lock" }) {
  const common = "h-5 w-5";
  switch (name) {
    case "shield":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path
            d="M12 2l8 4v6c0 5-3.5 9.7-8 10-4.5-.3-8-5-8-10V6l8-4z"
            stroke="currentColor"
            strokeWidth="1.8"
          />
          <path
            d="M9 12l2 2 4-5"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      );
    case "globe":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.8" />
          <path d="M3 12h18" stroke="currentColor" strokeWidth="1.8" />
          <path d="M12 3c3 3.2 3 14.8 0 18" stroke="currentColor" strokeWidth="1.8" />
          <path d="M12 3c-3 3.2-3 14.8 0 18" stroke="currentColor" strokeWidth="1.8" />
        </svg>
      );
    case "bolt":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path
            d="M13 2L3 14h8l-1 8 11-14h-8l0-6z"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinejoin="round"
          />
        </svg>
      );
    case "user":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path
            d="M20 21a8 8 0 10-16 0"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          />
          <path
            d="M12 13a5 5 0 100-10 5 5 0 000 10z"
            stroke="currentColor"
            strokeWidth="1.8"
          />
        </svg>
      );
    case "lock":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path
            d="M7 11V8a5 5 0 0110 0v3"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          />
          <path d="M6 11h12v10H6V11z" stroke="currentColor" strokeWidth="1.8" />
        </svg>
      );
    default:
      return <div className={common} />;
  }
}

function FeatureRow({
  icon,
  title,
  desc,
  onClick,
}: {
  icon: "shield" | "globe" | "bolt" | "user" | "lock";
  title: string;
  desc: string;
  onClick?: () => void;
}) {
  const Wrapper = (onClick ? "button" : "div") as unknown as React.ElementType;
  return (
    <Wrapper
      type={onClick ? "button" : undefined}
      onClick={onClick}
      className={cn(
        "flex w-full gap-3 text-left",
        onClick && "-m-2 rounded-3xl p-2 hover:bg-slate-50"
      )}
    >
      <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-100 text-slate-700">
        <Icon name={icon} />
      </div>
      <div>
        <div className="text-sm font-semibold text-slate-900">{title}</div>
        <div className="mt-1 text-xs text-slate-500">{desc}</div>
      </div>
    </Wrapper>
  );
}

function OTPBoxes({ length = 6 }: { length?: number }) {
  const boxes = Array.from({ length });
  return (
    <div className="flex justify-between gap-2">
      {boxes.map((_, i) => (
        <div
          key={i}
          className="flex h-12 w-12 items-center justify-center rounded-2xl border border-slate-200 bg-white text-lg font-semibold text-slate-900"
        >
          {i === 1 ? "•" : ""}
        </div>
      ))}
    </div>
  );
}

function PinPad() {
  const keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", " ", "0", "⌫"];
  return (
    <div className="grid grid-cols-3 gap-3">
      {keys.map((k, idx) => (
        <button
          key={idx}
          type="button"
          className={cn(
            "h-12 rounded-2xl border border-slate-200 bg-white text-sm font-semibold text-slate-900 hover:bg-slate-50",
            k === " " && "pointer-events-none opacity-0"
          )}
        >
          {k}
        </button>
      ))}
    </div>
  );
}

// ---------------------------
// Dropdowns (FX)
// ---------------------------

function FXBadge({
  from = "USD",
  to = "XOF",
  onClick,
}: {
  from?: string;
  to?: string;
  onClick?: () => void;
}) {
  const rate = getRateSafe(to);
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex w-full items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-left text-[11px] text-slate-600 hover:bg-slate-50"
    >
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full bg-emerald-500" />
        <span>Live rate</span>
        <span className="font-semibold text-slate-900">
          1 {from} → {rate} {to}
        </span>
      </div>
      <svg
        className="h-4 w-4 text-slate-400"
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M6 9l6 6 6-6"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </button>
  );
}

function CurrencyDropdown({
  open,
  onClose,
  query,
  setQuery,
  selected,
  onSelect,
}: {
  open: boolean;
  onClose: () => void;
  query: string;
  setQuery: (v: string) => void;
  selected: string;
  onSelect: (code: string) => void;
}) {
  if (!open) return null;

  const q = query.trim().toLowerCase();
  const filtered = SUPPORTED_CURRENCIES.filter((c) => {
    if (!q) return true;
    return c.code.toLowerCase().includes(q) || c.name.toLowerCase().includes(q);
  });

  const popularCodes = ["XOF", "GHS", "NGN", "EUR", "GBP", "USD"];
  const popular = filtered.filter((c) => popularCodes.includes(c.code));
  const rest = filtered.filter((c) => !popularCodes.includes(c.code));

  return (
    <div className="mt-3 rounded-3xl border border-slate-200 bg-white p-3">
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold text-slate-700">Choose payout currency</div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-full px-2 py-1 text-[11px] font-semibold text-slate-600 hover:bg-slate-100"
        >
          Close
        </button>
      </div>

      <div className="mt-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search (e.g., XOF, Ghana)"
          className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-200"
        />
      </div>

      <div className="mt-3 space-y-3">
        <div>
          <div className="px-1 text-[11px] font-semibold text-slate-500">Popular</div>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {popular.map((c) => (
              <button
                type="button"
                key={c.code}
                onClick={() => onSelect(c.code)}
                className={cn(
                  "rounded-2xl border px-3 py-2 text-left",
                  selected === c.code
                    ? "border-indigo-200 bg-indigo-50"
                    : "border-slate-200 bg-white hover:bg-slate-50"
                )}
              >
                <div className="flex items-center justify-between">
                  <div className="text-xs font-semibold text-slate-900">{c.code}</div>
                  <div
                    className={cn(
                      "h-2 w-2 rounded-full",
                      selected === c.code ? "bg-indigo-500" : "bg-slate-200"
                    )}
                  />
                </div>
                <div className="mt-0.5 text-[11px] text-slate-500">{c.name}</div>
              </button>
            ))}
          </div>
        </div>

        <div>
          <div className="px-1 text-[11px] font-semibold text-slate-500">All supported</div>
          <div className="mt-2 max-h-44 overflow-auto rounded-2xl border border-slate-200">
            {rest.map((c) => (
              <button
                type="button"
                key={c.code}
                onClick={() => onSelect(c.code)}
                className={cn(
                  "flex w-full items-start justify-between gap-3 px-3 py-2 text-left hover:bg-slate-50",
                  selected === c.code && "bg-indigo-50"
                )}
              >
                <div>
                  <div className="text-xs font-semibold text-slate-900">{c.code}</div>
                  <div className="text-[11px] text-slate-500">{c.name}</div>
                </div>
                <div
                  className={cn(
                    "mt-1 h-2 w-2 rounded-full",
                    selected === c.code ? "bg-indigo-500" : "bg-slate-200"
                  )}
                />
              </button>
            ))}
            {rest.length === 0 ? <div className="px-3 py-3 text-xs text-slate-500">No matches.</div> : null}
          </div>
        </div>

        <div className="rounded-2xl bg-slate-50 p-3 text-[11px] text-slate-500">
          Tip: In production, show only currencies available for the selected corridor + provider.
        </div>
      </div>
    </div>
  );
}

// ---------------------------
// Screens
// ---------------------------

function Screen01_Welcome() {
  const [fxOpen, setFxOpen] = useState(false);
  const [fxQuery, setFxQuery] = useState("");
  const [toCcy, setToCcy] = useState("XOF");
  const [highlightSignup, setHighlightSignup] = useState(false);

  return (
    <PhoneFrame title="Welcome" subtitle="Sign in or create an account">
      <div className="space-y-5">
        <div className="rounded-3xl bg-gradient-to-b from-indigo-50 to-white p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-slate-900">Welcome to {TOKENS.brand.name}</div>
              <div className="mt-1 text-sm text-slate-600">{TOKENS.brand.tagline}</div>
            </div>
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-600 text-white">
              <Icon name="globe" />
            </div>
          </div>

          <div className="mt-4">
            <FXBadge onClick={() => setFxOpen((v) => !v)} from="USD" to={toCcy} />
            <CurrencyDropdown
              open={fxOpen}
              onClose={() => setFxOpen(false)}
              query={fxQuery}
              setQuery={setFxQuery}
              selected={toCcy}
              onSelect={(code) => {
                setToCcy(code);
                setFxOpen(false);
                setFxQuery("");
              }}
            />
          </div>
        </div>

        <Card>
          <div className="space-y-4">
            <FeatureRow
              icon="bolt"
              title="Fast transfers"
              desc="Tap to sign up and send in minutes."
              onClick={() => {
                setHighlightSignup(true);
                if (typeof window !== "undefined") {
                  window.setTimeout(() => setHighlightSignup(false), 1200);
                }
              }}
            />
            <FeatureRow icon="shield" title="Secure by design" desc="PIN + device checks + fraud monitoring." />
            <FeatureRow icon="globe" title="Transparent FX" desc="See live rates before you confirm." />
          </div>
        </Card>
      </div>

      <div className="absolute bottom-10 left-0 right-0 px-5">
        <div className="space-y-3">
          <button
            type="button"
            className="flex w-full items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-900 hover:bg-slate-50"
          >
            <svg className="h-5 w-5" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
              <path
                d="M44.5 20H24v8.5h11.8C34.2 33.6 30 37 24 37c-7.2 0-13-5.8-13-13s5.8-13 13-13c3.5 0 6.7 1.4 9.1 3.6l6.1-6.1C35.4 4.9 30 2.8 24 2.8 12.4 2.8 3 12.2 3 23.8S12.4 44.8 24 44.8c11 0 20.3-8 20.3-21 0-1.4-.1-2.5-.3-3.8z"
                fill="#FFC107"
              />
              <path
                d="M6.3 14.7l7.1 5.2C15.2 16 19.3 13 24 13c3.5 0 6.7 1.4 9.1 3.6l6.1-6.1C35.4 4.9 30 2.8 24 2.8c-8 0-14.9 4.5-18.7 11.9z"
                fill="#FF3D00"
              />
              <path
                d="M24 44.8c5.8 0 11.1-2 15.1-5.5l-7.1-5.8C29.7 35.6 27 37 24 37c-5.9 0-10.9-4-12.6-9.5l-7.3 5.6C7.8 40.6 15.4 44.8 24 44.8z"
                fill="#4CAF50"
              />
              <path
                d="M44.5 20H24v8.5h11.8c-1 2.7-3 5-5.8 6.5l7.1 5.8c-.5.5 7.2-5.2 7.2-17 0-1.4-.1-2.5-.3-3.8z"
                fill="#1976D2"
              />
            </svg>
            Continue with Google
          </button>

          <div className="relative py-1">
            <div className="h-px bg-slate-200" />
            <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white px-2 text-[11px] text-slate-500">
              or
            </div>
          </div>

          <PrimaryButton className={highlightSignup ? "animate-pulse ring-2 ring-indigo-300 ring-offset-2" : ""}>
            Sign up
          </PrimaryButton>
          <SecondaryButton>Sign in</SecondaryButton>

          <div className="text-center text-[11px] text-slate-500">
            By continuing, you agree to our <span className="text-slate-700 underline">Terms</span> and{" "}
            <span className="text-slate-700 underline">Privacy Policy</span>.
          </div>
        </div>
      </div>
    </PhoneFrame>
  );
}

function Screen02_Phone() {
  // Screen2: simple, original row with a "Change" action.
  const country: Country = { iso2: "US", name: "United States", dial: "+1" };

  return (
    <PhoneFrame title="Verify your phone" subtitle="We’ll send a one-time code" step={1} totalSteps={4}>
      <div className="space-y-5">
        <div className="rounded-3xl border border-slate-200 bg-white p-4">
          <div className="text-sm font-semibold text-slate-900">Country / Region</div>
          <div className="mt-3 flex items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-3">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-slate-100 text-lg">
                {flagEmoji(country.iso2)}
              </div>
              <div>
                <div className="text-sm font-semibold text-slate-900">{country.name}</div>
                <div className="text-xs text-slate-500">{country.dial}</div>
              </div>
            </div>
            <button type="button" className="text-xs font-semibold text-indigo-600 hover:text-indigo-700">
              Change
            </button>
          </div>
        </div>

        <Input label="Phone number" placeholder="(555) 123-4567" hint="Standard SMS rates may apply." right="Required" />
      </div>

      <FooterActions
        primary={<PrimaryButton>Send code</PrimaryButton>}
        secondary={<SecondaryButton>Use email instead</SecondaryButton>}
      />
    </PhoneFrame>
  );
}

function Screen03_OTP() {
  return (
    <PhoneFrame title="Enter the code" subtitle="Sent to +1 (555) •••-4567" step={2} totalSteps={4}>
      <div className="space-y-6">
        <div className="rounded-3xl border border-slate-200 bg-white p-4">
          <div className="text-sm font-semibold text-slate-900">6-digit verification code</div>
          <div className="mt-4">
            <OTPBoxes length={6} />
          </div>
          <div className="mt-4 flex items-center justify-between text-xs">
            <button type="button" className="text-slate-600 hover:text-slate-900">
              Edit phone
            </button>
            <button type="button" className="font-semibold text-indigo-600 hover:text-indigo-700">
              Resend (0:32)
            </button>
          </div>
        </div>

        <div className="rounded-3xl bg-slate-50 p-4">
          <div className="text-xs font-semibold text-slate-700">Trouble getting a code?</div>
          <div className="mt-2 text-xs text-slate-500">Try resending or switch to email verification.</div>
          <div className="mt-3">
            <SecondaryButton>Verify by email</SecondaryButton>
          </div>
        </div>
      </div>

      <FooterActions primary={<PrimaryButton>Continue</PrimaryButton>} secondary={<SecondaryButton>Back</SecondaryButton>} />
    </PhoneFrame>
  );
}

function Screen04_Profile() {
  return (
    <PhoneFrame title="Set up your profile" subtitle="This helps recipients identify you" step={3} totalSteps={4}>
      <div className="space-y-5">
        <div className="flex items-center gap-4">
          <div className="relative h-16 w-16 rounded-3xl bg-slate-100">
            <div className="absolute -bottom-2 -right-2 rounded-2xl bg-indigo-600 px-2 py-1 text-[11px] font-semibold text-white">
              +
            </div>
          </div>
          <div>
            <div className="text-sm font-semibold text-slate-900">Add a photo</div>
            <div className="mt-1 text-xs text-slate-500">Optional, you can add later.</div>
          </div>
        </div>

        <div className="grid gap-4">
          <Input label="First name" placeholder="Komi" />
          <Input label="Last name" placeholder="Sowu" />
          <Input label="Email" placeholder="name@example.com" hint="We’ll send receipts and security alerts." />
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-4">
          <div className="text-sm font-semibold text-slate-900">Your default send corridor</div>
          <div className="mt-2 text-xs text-slate-500">You can still send to other countries later.</div>
          <div className="mt-4 flex items-center gap-2">
            <Chip active>US → Ghana</Chip>
            <Chip>US → Benin</Chip>
            <Chip>US → Togo</Chip>
          </div>
        </div>
      </div>

      <FooterActions primary={<PrimaryButton>Continue</PrimaryButton>} secondary={<SecondaryButton>Back</SecondaryButton>} />
    </PhoneFrame>
  );
}

function Screen05_CreatePIN() {
  return (
    <PhoneFrame title="Create your PIN" subtitle="Used for sending money and login" step={4} totalSteps={4}>
      <div className="space-y-5">
        <div className="rounded-3xl border border-slate-200 bg-white p-4">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 text-slate-700">
              <Icon name="lock" />
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-900">4-digit PIN</div>
              <div className="mt-1 text-xs text-slate-500">Don’t share it. You’ll use Face/Touch ID later.</div>
            </div>
          </div>

          <div className="mt-5 flex justify-center gap-3">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className={cn("h-3 w-3 rounded-full", i < 2 ? "bg-slate-900" : "bg-slate-200")} />
            ))}
          </div>

          <div className="mt-6">
            <PinPad />
          </div>

          <div className="mt-4 text-center text-[11px] text-slate-500">Forgot your PIN? You can reset with phone verification.</div>
        </div>

        <div className="rounded-3xl bg-slate-50 p-4">
          <div className="text-xs font-semibold text-slate-700">Optional next: Enable biometrics</div>
          <div className="mt-2 text-xs text-slate-500">Use Face ID / Touch ID to confirm transfers faster.</div>
          <div className="mt-3 grid grid-cols-2 gap-3">
            <button
              type="button"
              className="rounded-2xl border border-slate-200 bg-white px-3 py-3 text-xs font-semibold text-slate-900 hover:bg-slate-50"
            >
              Not now
            </button>
            <button type="button" className="rounded-2xl bg-slate-900 px-3 py-3 text-xs font-semibold text-white hover:bg-black">
              Enable
            </button>
          </div>
        </div>
      </div>

      <FooterActions primary={<PrimaryButton>Finish</PrimaryButton>} secondary={<SecondaryButton>Back</SecondaryButton>} />
    </PhoneFrame>
  );
}

function Screen06_Success() {
  return (
    <PhoneFrame title="You’re in!" subtitle="Account created successfully">
      <div className="space-y-6">
        <div className="rounded-3xl bg-gradient-to-b from-emerald-50 to-white p-5">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-3xl font-extrabold text-slate-900">Welcome 🎉</div>
              <div className="mt-2 text-sm text-slate-600">You can now send money to mobile money wallets.</div>
            </div>
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-600 text-white">
              <Icon name="shield" />
            </div>
          </div>
          <div className="mt-4">
            <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-[11px] text-slate-600">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              <span>Live rate</span>
              <span className="font-semibold text-slate-900">1 USD → 610 XOF</span>
            </div>
          </div>
        </div>

        <Card>
          <div className="space-y-3">
            <div className="text-sm font-semibold text-slate-900">Next steps</div>
            <div className="grid gap-2 text-xs text-slate-600">
              <div className="flex items-center justify-between">
                <span>Add a funding method</span>
                <span className="font-semibold text-slate-900">Recommended</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Invite a recipient</span>
                <span className="font-semibold text-slate-900">Optional</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Complete verification for higher limits</span>
                <span className="font-semibold text-slate-900">Later</span>
              </div>
            </div>
          </div>
        </Card>

        <div className="rounded-3xl border border-slate-200 bg-white p-4">
          <div className="text-sm font-semibold text-slate-900">Quick action</div>
          <div className="mt-2 text-xs text-slate-500">View the exchange rate page before you send.</div>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <button
              type="button"
              className="rounded-2xl border border-slate-200 bg-white px-3 py-3 text-xs font-semibold text-slate-900 hover:bg-slate-50"
            >
              Explore
            </button>
            <button type="button" className="rounded-2xl bg-indigo-600 px-3 py-3 text-xs font-semibold text-white hover:bg-indigo-700">
              Send money
            </button>
          </div>
        </div>
      </div>

      <FooterActions primary={<PrimaryButton>Go to home</PrimaryButton>} secondary={<SecondaryButton>See exchange rates</SecondaryButton>} />
    </PhoneFrame>
  );
}

// ---------------------------
// Main canvas
// ---------------------------

export default function NepxyRegistrationFlowCanvas() {
  const [density, setDensity] = useState<"comfortable" | "compact">("comfortable");

  // Keep frames as a stable list of elements for easy mapping.
  const frames = useMemo(
    () => [
      <Screen01_Welcome key="s1" />,
      <Screen02_Phone key="s2" />,
      <Screen03_OTP key="s3" />,
      <Screen04_Profile key="s4" />,
      <Screen05_CreatePIN key="s5" />,
      <Screen06_Success key="s6" />,
    ],
    []
  );

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Top bar */}
      <div className="sticky top-0 z-10 border-b border-slate-200 bg-white/80 backdrop-blur">
        <div className="mx-auto max-w-6xl px-4 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-lg font-extrabold text-slate-900">Nepxy — Registration Flow</div>
              <div className="mt-1 text-sm text-slate-500">Edit visuals directly in this file (Tailwind classes + copy).</div>
            </div>

            <div className="flex items-center gap-2">
              <div className="text-xs font-semibold text-slate-600">Density</div>
              <button
                type="button"
                onClick={() => setDensity((d) => (d === "comfortable" ? "compact" : "comfortable"))}
                className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-900 hover:bg-slate-50"
              >
                {density === "comfortable" ? "Comfortable" : "Compact"}
              </button>
            </div>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-600">
            <span className="rounded-full bg-slate-100 px-3 py-1">Screens: 6</span>
            <span className="rounded-full bg-slate-100 px-3 py-1">Flow: Welcome → Phone → OTP → Profile → PIN → Success</span>
            <span className="rounded-full bg-slate-100 px-3 py-1">Targets: US/EU → West Africa</span>
          </div>
        </div>
      </div>

      {/* Canvas */}
      <div className={cn("mx-auto max-w-6xl px-4", density === "compact" ? "py-5" : "py-8")}>
        <div className="mb-4 flex items-center justify-between">
          <div className="text-sm font-semibold text-slate-900">Frames</div>
          <div className="text-xs text-slate-500">Tip: scroll horizontally • tweak spacing • export via plugin later</div>
        </div>

        <div className="overflow-x-auto pb-6">
          <div className={cn("flex w-max items-start", density === "compact" ? "gap-4" : "gap-6")}>
            {frames.map((frame, idx) => (
              <div key={idx} className="space-y-2">
                <div className="px-1 text-xs font-semibold text-slate-600">Screen {idx + 1}</div>
                {frame}
              </div>
            ))}
          </div>
        </div>

        {/* Notes */}
        <div className="mt-8 rounded-3xl border border-slate-200 bg-white p-5">
          <div className="text-sm font-semibold text-slate-900">Design notes (editable)</div>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-600">
            <li>Primary CTA stays fixed at bottom for thumb reach.</li>
            <li>Registration steps are minimal; higher limits can require deeper KYC later.</li>
            <li>Include exchange-rate awareness early (Live rate) to reinforce price advantage.</li>
            <li>Optional alternate path: email verification instead of SMS.</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
