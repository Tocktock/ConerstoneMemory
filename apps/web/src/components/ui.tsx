"use client";

import type { ReactNode } from "react";
import { cx as mergeClassNames } from "@/lib/classnames";

export { mergeClassNames as cx };

export function Button({
  children,
  className,
  variant = "primary",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
}) {
  const styles = {
    primary:
      "border border-[color:var(--color-accent)] bg-[color:var(--color-accent)] text-slate-950 shadow-[0_12px_28px_rgba(34,211,238,0.16)] hover:border-cyan-200 hover:bg-cyan-200",
    secondary:
      "border border-[color:var(--color-line)] bg-[color:var(--color-card-inset)] text-slate-100 hover:border-[color:var(--color-line-strong)] hover:bg-white/7",
    ghost:
      "border border-transparent bg-transparent text-slate-300 shadow-none hover:border-white/8 hover:bg-white/6 hover:text-white",
    danger: "border border-rose-300/30 bg-rose-400/15 text-rose-100 hover:bg-rose-400/22 hover:text-white",
  }[variant];

  return (
    <button
      {...props}
      className={mergeClassNames(
        "inline-flex min-h-[44px] items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-center text-[15px] font-semibold leading-tight whitespace-normal transition duration-200 ease-out active:translate-y-px active:scale-[0.99] sm:min-h-10 sm:py-2 sm:text-sm",
        "focus-ring disabled:cursor-not-allowed disabled:opacity-50",
        styles,
        className,
      )}
    >
      {children}
    </button>
  );
}

export function Badge({
  children,
  className,
  tone = "neutral",
}: {
  children: ReactNode;
  className?: string;
  tone?: "neutral" | "success" | "warning" | "danger" | "accent";
}) {
  const styles = {
    neutral: "border-[color:var(--color-line-subtle)] bg-white/[0.035] text-slate-300",
    success: "border-emerald-300/24 bg-emerald-400/10 text-emerald-200",
    warning: "border-amber-300/28 bg-amber-400/10 text-amber-200",
    danger: "border-rose-300/30 bg-rose-400/12 text-rose-200",
    accent: "border-cyan-300/26 bg-cyan-400/10 text-cyan-200",
  }[tone];

  return (
    <span
      className={mergeClassNames(
        "inline-flex max-w-full items-center rounded-md border px-2.5 py-1 text-xs font-semibold leading-tight whitespace-normal",
        styles,
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Card({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={mergeClassNames("surface-workspace rounded-2xl p-4 sm:p-5", className)}>{children}</div>;
}

export function Section({
  title,
  eyebrow,
  children,
  action,
}: {
  title: string;
  eyebrow?: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section className="space-y-3">
      <div className="flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
        <div className="space-y-1">
          {eyebrow ? <div className="label">{eyebrow}</div> : null}
          <h2 className="text-xl font-semibold tracking-tight text-white text-balance">{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

export function ConsolePageHeader({
  eyebrow,
  title,
  description,
  status,
  meta,
  actions,
}: {
  eyebrow: string;
  title: string;
  description?: ReactNode;
  status?: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="border-b border-[color:var(--color-line-subtle)] pb-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <div className="label">{eyebrow}</div>
            {status}
          </div>
          <div className="space-y-2">
            <h2 className="text-2xl font-semibold tracking-tight text-white text-balance sm:text-[1.75rem]">{title}</h2>
            {description ? <div className="max-w-3xl text-sm leading-6 text-slate-300">{description}</div> : null}
          </div>
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
      {meta ? <div className="mt-3 flex flex-wrap items-center gap-2">{meta}</div> : null}
    </div>
  );
}

export function EmptyState({
  eyebrow,
  title,
  body,
  action,
}: {
  eyebrow?: string;
  title: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <div className="surface-rail rounded-2xl p-5">
      {eyebrow ? <div className="label">{eyebrow}</div> : null}
      <div className="mt-3 text-lg font-semibold text-white text-balance">{title}</div>
      <p className="text-sm leading-6 text-slate-300">{body}</p>
      {action ? <div>{action}</div> : null}
    </div>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={mergeClassNames(
        "w-full rounded-xl border border-[color:var(--color-line-subtle)] bg-[color:var(--color-card-inset)] px-3 py-2.5 text-base text-white placeholder:text-slate-500 shadow-inner transition sm:py-2 sm:text-sm",
        "focus:border-[color:var(--color-line-strong)] focus:outline-none focus:ring-2 focus:ring-[color:var(--color-accent)]/22",
        props.className,
      )}
    />
  );
}

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={mergeClassNames(
        "min-h-40 w-full resize-y rounded-xl border border-[color:var(--color-line-subtle)] bg-[color:var(--color-card-inset)] px-3 py-3 font-[family:var(--font-mono)] text-base leading-6 text-slate-100 placeholder:text-slate-500 shadow-inner transition sm:text-sm",
        "focus:border-[color:var(--color-line-strong)] focus:outline-none focus:ring-2 focus:ring-[color:var(--color-accent)]/22",
        props.className,
      )}
    />
  );
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={mergeClassNames(
        "w-full rounded-xl border border-[color:var(--color-line-subtle)] bg-[color:var(--color-card-inset)] px-3 py-2.5 text-base text-white shadow-inner transition sm:py-2 sm:text-sm",
        "focus:border-[color:var(--color-line-strong)] focus:outline-none focus:ring-2 focus:ring-[color:var(--color-accent)]/22",
        props.className,
      )}
    />
  );
}

export function Label({ children }: { children: ReactNode }) {
  return <label className="label block text-slate-400">{children}</label>;
}

export function CodeBlock({ children }: { children: ReactNode }) {
  return (
    <pre className="overflow-auto rounded-xl border border-[color:var(--color-line-subtle)] bg-[color:var(--color-card-inset)] p-4 text-xs leading-6 text-slate-200 shadow-inner">
      {children}
    </pre>
  );
}

export function Metric({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="panel-inset min-w-0 p-4">
      <div className="label">{label}</div>
      <div className="numeric mt-2 break-words text-xl font-semibold text-white sm:text-2xl">{value}</div>
      {hint ? <div className="mt-1 text-xs text-slate-400">{hint}</div> : null}
    </div>
  );
}
