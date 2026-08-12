"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

const menuLinks = [
  ["Catálogo", "/catalogo"],
  ["Como funciona", "/como-funciona"],
  ["Transparência", "/transparencia"],
  ["Sobre", "/sobre"],
] as const;

export function MobileMenu() {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  function close() {
    setOpen(false);
    requestAnimationFrame(() => triggerRef.current?.focus());
  }

  useEffect(() => {
    if (!open) return;
    panelRef.current?.querySelector<HTMLElement>("a")?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);

  function keepFocus(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "Tab") return;
    const focusable = panelRef.current?.querySelectorAll<HTMLElement>("a, button") ?? [];
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first?.focus();
    }
  }

  return (
    <div className="mobile-menu">
      <button
        ref={triggerRef}
        className="icon-button mobile-menu__trigger"
        type="button"
        aria-expanded={open}
        aria-controls="mobile-navigation"
        aria-label={open ? "Fechar menu" : "Abrir menu"}
        onClick={() => (open ? close() : setOpen(true))}
      >
        <span />
        <span />
      </button>
      {open && (
        <div className="mobile-menu__backdrop" role="presentation" onMouseDown={close}>
          <div
            ref={panelRef}
            className="mobile-menu__panel"
            onKeyDown={keepFocus}
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="mobile-menu__topline">
              <span>Explore a Orvani</span>
              <button className="icon-button" type="button" aria-label="Fechar menu" onClick={close}>
                ×
              </button>
            </div>
            <nav id="mobile-navigation" aria-label="Menu móvel">
              {menuLinks.map(([label, href]) => (
                <Link key={href} href={href} onClick={close}>
                  {label}
                  <span aria-hidden="true">↗</span>
                </Link>
              ))}
            </nav>
          </div>
        </div>
      )}
    </div>
  );
}
