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
    primary: "bg-cyan-400 text-slate-950 hover:bg-cyan-300",
    secondary: "bg-white/8 text-slate-100 hover:bg-white/12 border border-white/10",
    ghost: "bg-transparent text-slate-200 hover:bg-white/8",
    danger: "bg-rose-400 text-slate-950 hover:bg-rose-300",
  }[variant];

  return (
    <button
      {...props}
      className={mergeClassNames(
        "inline-flex items-center justify-center gap-2 rounded-full px-4 py-2 text-sm font-semibold transition",
        "focus:outline-none focus:ring-2 focus:ring-cyan-300/60 focus:ring-offset-0 disabled:cursor-not-allowed disabled:opacity-60",
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
    neutral: "bg-white/8 text-slate-200 border-white/10",
    success: "bg-emerald-400/12 text-emerald-200 border-emerald-300/20",
    warning: "bg-amber-400/12 text-amber-200 border-amber-300/20",
    danger: "bg-rose-400/12 text-rose-200 border-rose-300/20",
    accent: "bg-cyan-400/12 text-cyan-100 border-cyan-300/20",
  }[tone];

  return <span className={mergeClassNames("inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold", styles, className)}>{children}</span>;
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
      <div className="flex items-center justify-between gap-3">
        <div className="space-y-1">
          {eyebrow ? <div className="label">{eyebrow}</div> : null}
          <h2 className="text-lg font-semibold text-white">{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={mergeClassNames(
        "w-full rounded-xl border border-white/10 bg-slate-950/50 px-3 py-2 text-sm text-white placeholder:text-slate-500",
        "focus:border-cyan-300 focus:outline-none focus:ring-2 focus:ring-cyan-300/30",
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
        "min-h-40 w-full rounded-2xl border border-white/10 bg-slate-950/50 px-3 py-3 font-mono text-sm text-slate-100 placeholder:text-slate-500",
        "focus:border-cyan-300 focus:outline-none focus:ring-2 focus:ring-cyan-300/30",
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
        "w-full rounded-xl border border-white/10 bg-slate-950/50 px-3 py-2 text-sm text-white",
        "focus:border-cyan-300 focus:outline-none focus:ring-2 focus:ring-cyan-300/30",
        props.className,
      )}
    />
  );
}

export function Label({ children }: { children: ReactNode }) {
  return <label className="label block">{children}</label>;
}

export function CodeBlock({ children }: { children: ReactNode }) {
  return <pre className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/80 p-4 text-xs leading-6 text-slate-200">{children}</pre>;
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
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
      <div className="label">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-white">{value}</div>
      {hint ? <div className="mt-1 text-xs text-slate-400">{hint}</div> : null}
    </div>
  );
}
