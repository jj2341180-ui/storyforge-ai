import { useEffect, useMemo, useRef, useState } from "react";

/**
 * True desktop layout on a portrait phone — without rotating the device.
 *
 * A CSS transform alone does not change media-query evaluation (Tailwind's md:/lg:
 * breakpoints would still see the 414px phone viewport), so the full app is rendered
 * inside a same-origin iframe whose own viewport is 1280px wide. Media queries inside
 * the iframe therefore resolve exactly as on a desktop monitor; the iframe element is
 * then scaled down to fit the phone's width and its wrapper is sized for native page
 * scrolling.
 */
export const DESKTOP_WIDTH = 1280;

export function desktopIframeSrc(): string {
  const u = new URL(window.location.href);
  u.searchParams.set("desktop", "1");
  return u.toString();
}

export function isInsideDesktopFrame(): boolean {
  try {
    return new URLSearchParams(window.location.search).get("desktop") === "1";
  } catch {
    return false;
  }
}

export default function DesktopStage({ children }: { children?: React.ReactNode }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef<HTMLIFrameElement>(null);
  const [ready, setReady] = useState(false);
  const scale = typeof window !== "undefined" ? Math.min(1, window.innerWidth / DESKTOP_WIDTH) : 1;
  const src = useMemo(desktopIframeSrc, []);

  useEffect(() => {
    const frame = frameRef.current;
    if (!frame) return;

    const sync = () => {
      const doc = frame.contentDocument;
      if (!doc || !wrapRef.current) return;
      const h = Math.max(doc.documentElement.scrollHeight, doc.body?.scrollHeight || 0);
      frame.style.height = `${h}px`;
      wrapRef.current.style.height = `${h * scale}px`;
      setReady(true);
    };

    let ro: ResizeObserver | null = null;
    let poll: ReturnType<typeof setInterval> | null = null;

    const onLoad = () => {
      const doc = frame.contentDocument;
      if (!doc) return;
      // Dark background while/inside the frame, and no inner scrollbar (outer page scrolls).
      const style = doc.createElement("style");
      style.textContent = "html,body{background:#070910!important;overflow-x:hidden!important;}";
      doc.head.appendChild(style);
      sync();
      ro = new ResizeObserver(sync);
      ro.observe(doc.documentElement);
      if (doc.body) ro.observe(doc.body);
      // Content grows as projects/data load; poll briefly so the wrapper never lags.
      let ticks = 0;
      poll = setInterval(() => {
        sync();
        if (++ticks > 12 && poll) clearInterval(poll);
      }, 250);
    };

    frame.addEventListener("load", onLoad);
    window.addEventListener("resize", sync);
    return () => {
      frame.removeEventListener("load", onLoad);
      window.removeEventListener("resize", sync);
      ro?.disconnect();
      if (poll) clearInterval(poll);
    };
  }, [scale]);

  return (
    <div ref={wrapRef} className="sf-desktop-wrap" style={{ opacity: ready ? 1 : 0, transition: "opacity .25s" }}>
      <iframe
        ref={frameRef}
        src={src}
        title="StoryForge desktop workspace"
        className="sf-desktop-frame"
        style={{
          width: `${DESKTOP_WIDTH}px`,
          transform: `scale(${scale})`,
          transformOrigin: "top left",
          border: "none",
        }}
      />
      {children}
    </div>
  );
}
