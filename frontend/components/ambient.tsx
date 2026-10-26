"use client";

import { useEffect, useRef } from "react";
import { gsap } from "gsap";

/**
 * Site-wide pointer effects: a soft glow that trails the cursor, a spotlight
 * position for `[data-spotlight]` surfaces, and a gentle pull on
 * `[data-magnetic]` controls. Only runs for fine pointers without
 * reduced-motion, and never changes layout or intercepts input.
 */
export default function Ambient() {
  const glow = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = glow.current;
    const media = gsap.matchMedia();
    media.add(
      "(pointer: fine) and (prefers-reduced-motion: no-preference)",
      () => {
        if (!el) return;
        gsap.set(el, { xPercent: -50, yPercent: -50, opacity: 0 });
        const toX = gsap.quickTo(el, "x", { duration: 0.8, ease: "power3.out" });
        const toY = gsap.quickTo(el, "y", { duration: 0.8, ease: "power3.out" });
        const pulls = new WeakMap<Element, { x: gsap.QuickToFunc; y: gsap.QuickToFunc }>();
        const pull = (target: Element) => {
          let entry = pulls.get(target);
          if (!entry) {
            entry = {
              x: gsap.quickTo(target, "x", { duration: 0.5, ease: "power3.out" }),
              y: gsap.quickTo(target, "y", { duration: 0.5, ease: "power3.out" }),
            };
            pulls.set(target, entry);
          }
          return entry;
        };
        let magnet: HTMLElement | null = null;

        const onMove = (event: PointerEvent) => {
          gsap.to(el, { opacity: 1, duration: 0.6, overwrite: "auto" });
          toX(event.clientX);
          toY(event.clientY);
          const target = event.target as Element | null;

          const surface = target?.closest<HTMLElement>("[data-spotlight]");
          if (surface) {
            const box = surface.getBoundingClientRect();
            surface.style.setProperty("--mx", `${event.clientX - box.left}px`);
            surface.style.setProperty("--my", `${event.clientY - box.top}px`);
          }

          const next = target?.closest<HTMLElement>("[data-magnetic]") ?? null;
          if (magnet && magnet !== next) {
            pull(magnet).x(0);
            pull(magnet).y(0);
          }
          magnet = next;
          if (magnet) {
            const box = magnet.getBoundingClientRect();
            const strength = 0.22;
            pull(magnet).x((event.clientX - box.left - box.width / 2) * strength);
            pull(magnet).y((event.clientY - box.top - box.height / 2) * strength);
          }
        };
        const onLeave = () => {
          gsap.to(el, { opacity: 0, duration: 0.6, overwrite: "auto" });
          if (magnet) {
            pull(magnet).x(0);
            pull(magnet).y(0);
            magnet = null;
          }
        };

        window.addEventListener("pointermove", onMove, { passive: true });
        document.documentElement.addEventListener("pointerleave", onLeave);
        return () => {
          window.removeEventListener("pointermove", onMove);
          document.documentElement.removeEventListener("pointerleave", onLeave);
        };
      },
    );
    return () => media.revert();
  }, []);

  return <div ref={glow} className="cursor-glow" aria-hidden="true" />;
}
