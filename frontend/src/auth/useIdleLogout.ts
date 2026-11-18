import { useEffect, useRef } from "react";

const EVENTS = ["mousemove", "mousedown", "keydown", "touchstart", "scroll", "wheel"] as const;

/** Ejecuta `onIdle` tras `minutes` minutos sin interacción del usuario. */
export function useIdleLogout(minutes: number | undefined, onIdle: () => void) {
  const callback = useRef(onIdle);
  callback.current = onIdle;

  useEffect(() => {
    if (!minutes) return;
    const ms = minutes * 60_000;
    let timer = window.setTimeout(() => callback.current(), ms);
    let last = Date.now();
    const reset = () => {
      const now = Date.now();
      if (now - last < 1000) return; // limita el costo de mousemove
      last = now;
      window.clearTimeout(timer);
      timer = window.setTimeout(() => callback.current(), ms);
    };
    EVENTS.forEach((e) => window.addEventListener(e, reset, { passive: true }));
    return () => {
      window.clearTimeout(timer);
      EVENTS.forEach((e) => window.removeEventListener(e, reset));
    };
  }, [minutes]);
}
