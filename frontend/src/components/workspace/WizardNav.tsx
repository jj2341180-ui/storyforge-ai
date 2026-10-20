import { ArrowLeft, ArrowRight, Home } from "lucide-react";

export interface WizardStep {
  id: string;
  label: string;
}

/**
 * Big, thumb-friendly Back / Next bar shown under every workspace page so the flow is
 * obvious on a phone (the horizontal tab strip alone is easy to miss on small screens).
 */
export default function WizardNav({
  steps,
  currentId,
  onGo,
  onHome,
  nextDisabled = false,
  nextHint = "",
}: {
  steps: WizardStep[];
  currentId: string;
  onGo: (tab: string) => void;
  onHome: () => void;
  nextDisabled?: boolean;
  nextHint?: string;
}) {
  const index = Math.max(0, steps.findIndex((s) => s.id === currentId));
  const step = steps[index];
  const prev = index > 0 ? steps[index - 1] : null;
  const next = index < steps.length - 1 ? steps[index + 1] : null;

  return (
    <div className="max-w-7xl w-full mx-auto px-4 pb-10 pt-2">
      <div className="card p-4 space-y-3">
        <div className="flex items-center justify-between text-xs text-slate-400">
          <span className="font-semibold text-gold-300">
            Step {index + 1} of {steps.length} · {step.label}
          </span>
          <span className="hidden sm:block">Tip: your work saves automatically as you move</span>
        </div>

        {/* Step dots */}
        <div className="flex gap-1.5">
          {steps.map((s, i) => (
            <button
              key={s.id}
              onClick={() => onGo(s.id)}
              title={s.label}
              className={`h-1.5 rounded-full transition-all ${
                i === index ? "w-8 bg-gold-400" : i < index ? "w-4 bg-gold-700" : "w-4 bg-ink-700"
              }`}
            />
          ))}
        </div>

        <div className="flex gap-3">
          {prev ? (
            <button className="btn-secondary flex-1 sm:flex-none" onClick={() => onGo(prev.id)}>
              <ArrowLeft className="w-4 h-4" /> Back: {prev.label}
            </button>
          ) : (
            <button className="btn-secondary flex-1 sm:flex-none" onClick={onHome}>
              <Home className="w-4 h-4" /> Back to Home
            </button>
          )}

          {next && (
            <div className="flex-1 flex flex-col items-end gap-1">
              <button
                className="btn-primary w-full sm:w-auto"
                disabled={nextDisabled}
                onClick={() => !nextDisabled && onGo(next.id)}
              >
                Next: {next.label} <ArrowRight className="w-4 h-4" />
              </button>
              {nextDisabled && nextHint && <p className="text-xs text-amber-300">{nextHint}</p>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/** Simple footer for the single-page Video Clip mode. */
export function ClipNav({ onHome }: { onHome: () => void }) {
  return (
    <div className="max-w-7xl w-full mx-auto px-4 pb-10 pt-2">
      <div className="card p-4 flex items-center justify-between gap-3">
        <button className="btn-secondary" onClick={onHome}>
          <ArrowLeft className="w-4 h-4" /> Back to Home
        </button>
        <span className="text-xs text-slate-400">Video Clip mode · one screen, no further steps</span>
      </div>
    </div>
  );
}
