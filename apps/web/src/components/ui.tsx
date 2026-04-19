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
      "border border-[color:var(--color-accent-strong)] bg-[color:var(--color-accent-strong)] text-white hover:border-[#1f6feb] hover:bg-[#1f6feb]",
    secondary:
      "border border-[color:var(--color-line)] bg-[color:var(--color-card)] text-slate-100 hover:border-[color:var(--color-line-strong)] hover:bg-white/8",
    ghost:
      "border border-transparent bg-transparent text-slate-200 hover:border-white/8 hover:bg-white/6",
    danger: "border border-transparent bg-[color:var(--color-danger)] text-white hover:bg-[#ff6a69]",
  }[variant];

  return (
    <button
      {...props}
      className={mergeClassNames(
        "inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-center text-[15px] font-semibold leading-tight whitespace-normal shadow-sm transition duration-150 sm:min-h-10 sm:py-2 sm:text-sm",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--color-accent)]/45 disabled:cursor-not-allowed disabled:opacity-60",
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
    neutral: "border-[color:var(--color-line)] bg-[color:var(--color-card-inset)] text-slate-200",
    success: "border-emerald-400/28 bg-emerald-400/12 text-emerald-100",
    warning: "border-amber-400/28 bg-amber-400/12 text-amber-100",
    danger: "border-rose-400/30 bg-rose-400/12 text-rose-100",
    accent: "border-[color:var(--color-line-strong)] bg-[color:var(--color-card-accent)] text-blue-100",
  }[tone];

  return (
    <span
      className={mergeClassNames(
        "inline-flex max-w-full rounded-md border px-2.5 py-1 text-xs font-medium whitespace-normal",
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
  return <div className={mergeClassNames("panel p-5", className)}>{children}</div>;
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
          <h2 className="text-xl font-semibold tracking-tight text-white">{title}</h2>
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
    <div className="panel space-y-4 p-5 sm:p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <div className="label">{eyebrow}</div>
            {status}
          </div>
          <div className="space-y-2">
            <h2 className="text-2xl font-semibold tracking-tight text-white sm:text-[1.75rem]">{title}</h2>
            {description ? <div className="max-w-3xl text-sm leading-6 text-slate-300">{description}</div> : null}
          </div>
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
      {meta ? <div className="flex flex-wrap items-center gap-2">{meta}</div> : null}
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
    <div className="panel-muted space-y-3 p-5">
      {eyebrow ? <div className="label">{eyebrow}</div> : null}
      <div className="text-lg font-semibold text-white">{title}</div>
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
        "w-full rounded-lg border border-[color:var(--color-line)] bg-[color:var(--color-card-inset)] px-3 py-2.5 text-base text-white placeholder:text-slate-500 shadow-inner sm:py-2 sm:text-sm",
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
        "min-h-40 w-full resize-y rounded-xl border border-[color:var(--color-line)] bg-[color:var(--color-card-inset)] px-3 py-3 font-[family:var(--font-mono)] text-base leading-6 text-slate-100 placeholder:text-slate-500 shadow-inner sm:text-sm",
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
        "w-full rounded-lg border border-[color:var(--color-line)] bg-[color:var(--color-card-inset)] px-3 py-2.5 text-base text-white shadow-inner sm:py-2 sm:text-sm",
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
    <pre className="overflow-auto rounded-2xl border border-[color:var(--color-line-subtle)] bg-[color:var(--color-card-inset)] p-4 text-xs leading-6 text-slate-200">
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
    <div className="min-w-0 rounded-2xl border border-[color:var(--color-line)] bg-[color:var(--color-card)] p-4 shadow-[var(--shadow-raised)]">
      <div className="label">{label}</div>
      <div className="mt-2 break-words text-xl font-semibold text-white sm:text-2xl">{value}</div>
      {hint ? <div className="mt-1 text-xs text-slate-400">{hint}</div> : null}
    </div>
  );
}
