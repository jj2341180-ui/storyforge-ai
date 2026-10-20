import { Monitor, Smartphone } from "lucide-react";

/**
 * Phone-portrait / desktop-layout switch.
 *
 * "Desktop layout" renders the full wide (1280px) workspace scaled down to fit a
 * portrait phone — the device itself never rotates. Only shown on narrow screens.
 */
export default function LayoutToggle({
  desktop,
  onToggle,
}: {
  desktop: boolean;
  onToggle: (v: boolean) => void;
}) {
  return (
    <button
      className="btn-ghost text-xs px-2.5 py-2 gap-1.5"
      onClick={() => onToggle(!desktop)}
      aria-pressed={desktop}
      aria-label={desktop ? "Switch to phone layout" : "Switch to desktop layout"}
      title={desktop ? "Switch to phone layout" : "Switch to desktop layout"}
    >
      {desktop ? <Monitor className="w-4 h-4" /> : <Smartphone className="w-4 h-4" />}
      <span className="hidden sm:inline">{desktop ? "Desktop layout" : "Phone layout"}</span>
    </button>
  );
}
