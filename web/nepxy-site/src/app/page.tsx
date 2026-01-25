"use client";

import type { ChangeEvent, FormEvent } from "react";
import { useState } from "react";
import { ArrowRight, Check } from "lucide-react";

const faqs = [
  {
    question: "Who is NepXy for?",
    answer:
      "Teams that need reliable payouts and wallet infrastructure for West Africa, with auditability and compliant flows.",
  },
  {
    question: "When will NepXy be available?",
    answer:
      "We are onboarding design partners now. Join the waitlist and we will follow up with timelines.",
  },
  {
    question: "Which rails do you support?",
    answer:
      "Initial corridors cover US/Canada/EU to Ghana, Benin, and Togo with mobile money cash-out.",
  },
  {
    question: "Do you offer webhooks and idempotency?",
    answer:
      "Yes. Events are signed and idempotency keys are supported to prevent duplicate payouts.",
  },
];

export default function Home() {
  const [formState, setFormState] = useState({
    name: "",
    email: "",
    message: "",
  });
  const [status, setStatus] = useState<
    "idle" | "loading" | "success" | "error"
  >("idle");
  const [errorMessage, setErrorMessage] = useState("");

  const handleChange = (
    event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) => {
    const { name, value } = event.target;
    setFormState((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setStatus("loading");
    setErrorMessage("");

    try {
      const response = await fetch("/api/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formState),
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        setStatus("error");
        setErrorMessage(
          payload?.error || "Something went wrong. Please try again.",
        );
        return;
      }

      setStatus("success");
      setFormState({ name: "", email: "", message: "" });
    } catch (error) {
      setStatus("error");
      setErrorMessage("Unable to send your message right now.");
    }
  };

  return (
    <div className="min-h-screen bg-white text-slate-900">
      <header className="sticky top-0 z-20 border-b border-slate-100 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="text-lg font-semibold tracking-tight">NepXy</div>
          <nav className="hidden items-center gap-6 text-sm text-slate-600 md:flex">
            <a href="#product" className="hover:text-slate-900">
              Product
            </a>
            <a href="#security" className="hover:text-slate-900">
              Security
            </a>
            <a href="#pricing" className="hover:text-slate-900">
              Pricing
            </a>
            <a href="#faqs" className="hover:text-slate-900">
              FAQs
            </a>
            <a href="#contact" className="hover:text-slate-900">
              Contact
            </a>
          </nav>
          <a
            href="#contact"
            className="rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:border-slate-300 hover:text-slate-900"
          >
            Join Waitlist
          </a>
        </div>
      </header>

      <main>
        <section className="relative overflow-hidden">
          <div className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_top,_#f8fafc,_#ffffff_60%)]" />
          <div className="mx-auto flex max-w-6xl flex-col gap-12 px-6 pb-20 pt-16 md:flex-row md:items-center">
            <div className="flex-1 space-y-6">
              <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-400">
                Cross-border wallet & payouts
              </p>
              <h1 className="text-4xl font-semibold tracking-tight text-slate-900 sm:text-5xl">
                Move money from North America and Europe to West Africa with
                clarity and control.
              </h1>
              <p className="text-lg text-slate-600">
                NepXy gives teams a fast wallet, transparent pricing, and
                compliant payout rails for mobile money destinations.
              </p>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                <a
                  href="#contact"
                  className="inline-flex items-center justify-center gap-2 rounded-full bg-slate-900 px-6 py-3 text-sm font-semibold text-white hover:bg-slate-800"
                >
                  Join Waitlist
                  <ArrowRight size={16} />
                </a>
                <a
                  href="mailto:support@nepxy.com"
                  className="inline-flex items-center justify-center gap-2 rounded-full border border-slate-200 px-6 py-3 text-sm font-semibold text-slate-700 hover:border-slate-300 hover:text-slate-900"
                >
                  Contact Sales
                </a>
              </div>
            </div>
            <div className="flex-1">
              <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
                <div className="space-y-6">
                  <div className="space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
                      Live corridors
                    </p>
                    <p className="text-2xl font-semibold text-slate-900">
                      US / Canada / EU
                    </p>
                    <p className="text-sm text-slate-500">
                      Send to West Africa with instant mobile money cash-out.
                    </p>
                  </div>
                  <div className="grid gap-3 text-sm text-slate-600">
                    <div className="flex items-center justify-between rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
                      <span>Ghana</span>
                      <span className="text-slate-500">MTN, Vodafone</span>
                    </div>
                    <div className="flex items-center justify-between rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
                      <span>Benin</span>
                      <span className="text-slate-500">Moov, MTN</span>
                    </div>
                    <div className="flex items-center justify-between rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
                      <span>Togo</span>
                      <span className="text-slate-500">TMoney</span>
                    </div>
                  </div>
                  <div className="rounded-2xl border border-slate-100 bg-white px-4 py-3 text-sm text-slate-500">
                    Built for compliance workflows and multi-step approvals.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="product" className="bg-slate-50">
          <div className="mx-auto max-w-6xl px-6 py-16">
            <div className="mb-10 flex flex-col gap-3">
              <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-400">
                Product
              </p>
              <h2 className="text-3xl font-semibold tracking-tight">
                Everything you need to move funds confidently.
              </h2>
              <p className="text-slate-600">
                A single wallet and payout layer with operational tooling and
                observability baked in.
              </p>
            </div>
            <div className="grid gap-6 md:grid-cols-3">
              {[
                {
                  title: "Fast transfers",
                  detail:
                    "Same-day settlement and rapid mobile money cash-out.",
                },
                {
                  title: "Transparent fees",
                  detail:
                    "Clear FX and payout fees with real-time corridor visibility.",
                },
                {
                  title: "Built with compliance in mind",
                  detail:
                    "Approval flows, audit logs, and traceability at every step.",
                },
              ].map((item) => (
                <div
                  key={item.title}
                  className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
                >
                  <h3 className="text-lg font-semibold">{item.title}</h3>
                  <p className="mt-3 text-sm text-slate-600">{item.detail}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="bg-white">
          <div className="mx-auto max-w-6xl px-6 py-16">
            <div className="grid gap-10 md:grid-cols-2 md:items-center">
              <div className="space-y-4">
                <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-400">
                  How it works
                </p>
                <h2 className="text-3xl font-semibold tracking-tight">
                  Three steps to reliable payouts.
                </h2>
                <p className="text-slate-600">
                  Fund, send, and track each transfer with real-time updates.
                </p>
              </div>
              <div className="grid gap-4">
                {[
                  {
                    step: "Add funds",
                    detail:
                      "Top up your wallet in USD, CAD, or EUR with instant confirmation.",
                  },
                  {
                    step: "Send",
                    detail:
                      "Trigger payouts via API or dashboard with idempotency keys.",
                  },
                  {
                    step: "Cash-out to mobile money",
                    detail:
                      "Recipients receive funds quickly with status updates.",
                  },
                ].map((item, index) => (
                  <div
                    key={item.step}
                    className="flex items-start gap-4 rounded-2xl border border-slate-200 bg-slate-50 p-5"
                  >
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white text-sm font-semibold text-slate-900 shadow-sm">
                      {index + 1}
                    </div>
                    <div>
                      <h3 className="text-base font-semibold">{item.step}</h3>
                      <p className="mt-1 text-sm text-slate-600">
                        {item.detail}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section id="pricing" className="bg-slate-50">
          <div className="mx-auto max-w-6xl px-6 py-16">
            <div className="grid gap-8 md:grid-cols-2 md:items-center">
              <div className="space-y-4">
                <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-400">
                  Initial corridors
                </p>
                <h2 className="text-3xl font-semibold tracking-tight">
                  Launching with focused coverage.
                </h2>
                <p className="text-slate-600">
                  US, Canada, and EU origin corridors to West Africa, starting
                  with Ghana, Benin, and Togo.
                </p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="space-y-4 text-sm text-slate-600">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-slate-900">
                      Origin markets
                    </span>
                    <span>US, Canada, EU</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-slate-900">
                      Destinations
                    </span>
                    <span>Ghana, Benin, Togo</span>
                  </div>
                  <div className="rounded-xl border border-slate-100 bg-slate-50 px-4 py-3">
                    Pricing is usage-based with transparent FX and payout fees.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="security" className="bg-white">
          <div className="mx-auto max-w-6xl px-6 py-16">
            <div className="grid gap-8 md:grid-cols-2 md:items-center">
              <div className="space-y-4">
                <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-400">
                  Security
                </p>
                <h2 className="text-3xl font-semibold tracking-tight">
                  Controls that match your compliance needs.
                </h2>
                <p className="text-slate-600">
                  Secure by design with operational tooling built for audit and
                  risk workflows.
                </p>
              </div>
              <div className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-6 text-sm text-slate-700">
                {[
                  "Encryption in transit and at rest",
                  "Immutable audit logs",
                  "Idempotency keys for safe retries",
                  "Webhook verification on every event",
                ].map((item) => (
                  <div key={item} className="flex items-start gap-3">
                    <Check className="mt-0.5 text-emerald-500" size={18} />
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section id="faqs" className="bg-slate-50">
          <div className="mx-auto max-w-6xl px-6 py-16">
            <div className="mb-10 space-y-3">
              <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-400">
                FAQs
              </p>
              <h2 className="text-3xl font-semibold tracking-tight">
                Answers for teams evaluating NepXy.
              </h2>
            </div>
            <div className="grid gap-6 md:grid-cols-2">
              {faqs.map((item) => (
                <div
                  key={item.question}
                  className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
                >
                  <h3 className="text-base font-semibold">{item.question}</h3>
                  <p className="mt-2 text-sm text-slate-600">{item.answer}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="contact" className="bg-white">
          <div className="mx-auto max-w-6xl px-6 py-16">
            <div className="grid gap-10 md:grid-cols-2 md:items-start">
              <div className="space-y-4">
                <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-400">
                  Contact
                </p>
                <h2 className="text-3xl font-semibold tracking-tight">
                  Talk with our team.
                </h2>
                <p className="text-slate-600">
                  Email us at{" "}
                  <a
                    href="mailto:support@nepxy.com"
                    className="font-semibold text-slate-900"
                  >
                    support@nepxy.com
                  </a>{" "}
                  or send a message below.
                </p>
              </div>
              <form
                onSubmit={handleSubmit}
                className="rounded-2xl border border-slate-200 bg-slate-50 p-6"
              >
                <div className="grid gap-4">
                  <div>
                    <label className="text-sm font-medium text-slate-700">
                      Name
                    </label>
                    <input
                      type="text"
                      name="name"
                      required
                      value={formState.name}
                      onChange={handleChange}
                      className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm text-slate-900 focus:border-slate-400 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-slate-700">
                      Email
                    </label>
                    <input
                      type="email"
                      name="email"
                      required
                      value={formState.email}
                      onChange={handleChange}
                      className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm text-slate-900 focus:border-slate-400 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-slate-700">
                      Message
                    </label>
                    <textarea
                      name="message"
                      required
                      rows={4}
                      value={formState.message}
                      onChange={handleChange}
                      className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm text-slate-900 focus:border-slate-400 focus:outline-none"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={status === "loading"}
                    className="inline-flex items-center justify-center rounded-full bg-slate-900 px-6 py-3 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-70"
                  >
                    {status === "loading" ? "Sending..." : "Send message"}
                  </button>
                  {status === "success" && (
                    <p className="text-sm text-emerald-600">
                      Thanks! We will get back to you soon.
                    </p>
                  )}
                  {status === "error" && (
                    <p className="text-sm text-rose-600">{errorMessage}</p>
                  )}
                </div>
              </form>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-100 bg-white">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-6 py-8 text-sm text-slate-500 md:flex-row">
          <span>
            © {new Date().getFullYear()} NepXy Technologies LLC
          </span>
          <div className="flex items-center gap-4">
            <a href="/privacy" className="hover:text-slate-700">
              Privacy
            </a>
            <a href="/terms" className="hover:text-slate-700">
              Terms
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
