import { AlertTriangle, CheckCircle2, Loader2, X } from "lucide-react";
import { ReactNode, useEffect, useState } from "react";

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-slate-300">
      <Loader2 className="w-4 h-4 animate-spin text-gold-400" />
      {label}
    </span>
  );
}

export function ProgressBar({ value, message }: { value: number; message?: string }) {
  return (
    <div className="w-full">
      <div className="h-2.5 rounded-full bg-ink-700 overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-gold-500 to-ember-400 transition-all duration-300"
          style={{ width: `${Math.round(value * 100)}%` }}
        />
      </div>
      {message && <p className="text-xs text-slate-400 mt-1.5 truncate">{message}</p>}
    </div>
  );
}

export function Badge({ tone = "neutral", children }: { tone?: "neutral" | "green" | "amber" | "red" | "blue"; children: ReactNode }) {
  const tones: Record<string, string> = {
    neutral: "bg-ink-700 text-slate-300",
    green: "bg-emerald-900/60 text-emerald-300",
    amber: "bg-amber-900/50 text-amber-300",
    red: "bg-red-900/50 text-red-300",
    blue: "bg-blue-900/50 text-blue-300",
  };
  return <span className={`chip ${tones[tone]}`}>{children}</span>;
}

export function Notice({ tone = "info", children }: { tone?: "info" | "warn" | "ok"; children: ReactNode }) {
  const styles = {
    info: "border-blue-800 bg-blue-950/40 text-blue-200",
    warn: "border-amber-800 bg-amber-950/40 text-amber-200",
    ok: "border-emerald-800 bg-emerald-950/40 text-emerald-200",
  } as const;
  const Icon = tone === "warn" ? AlertTriangle : tone === "ok" ? CheckCircle2 : AlertTriangle;
  return (
    <div className={`flex gap-2.5 items-start border rounded-xl px-3.5 py-3 text-sm ${styles[tone]}`}>
      <Icon className="w-4 h-4 mt-0.5 shrink-0" />
      <div className="space-y-1">{children}</div>
    </div>
  );
}

export function Modal({ title, onClose, children, wide }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70" onClick={onClose}>
      <div
        className={`card w-full ${wide ? "max-w-4xl" : "max-w-lg"} max-h-[88vh] overflow-y-auto p-6`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-display text-xl text-gold-300">{title}</h3>
          <button className="btn-ghost p-1.5" onClick={onClose} aria-label="Close">
            <X className="w-5 h-5" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function useToast() {
  const [toast, setToast] = useState<{ text: string; tone: "ok" | "err" } | null>(null);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4200);
    return () => clearTimeout(t);
  }, [toast]);
  return {
    toast,
    show: (text: string, tone: "ok" | "err" = "ok") => setToast({ text, tone }),
  };
}

export function Toast({ toast }: { toast: { text: string; tone: "ok" | "err" } | null }) {
  if (!toast) return null;
  return (
    <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-[60] max-w-md w-[92vw]">
      <Notice tone={toast.tone === "ok" ? "ok" : "warn"}>{toast.text}</Notice>
    </div>
  );
}

export function EmptyState({ icon, title, hint }: { icon: ReactNode; title: string; hint?: string }) {
  return (
    <div className="text-center py-12 px-4 border border-dashed border-ink-600 rounded-2xl">
      <div className="mx-auto w-12 h-12 rounded-full bg-ink-800 flex items-center justify-center text-gold-400 mb-3">
        {icon}
      </div>
      <p className="font-semibold text-slate-200">{title}</p>
      {hint && <p className="text-sm text-slate-400 mt-1">{hint}</p>}
    </div>
  );
}

export function formatTime(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}
