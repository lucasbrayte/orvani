"use client";

import { useState } from "react";

export function ShareActions({ title, url }: { title: string; url: string }) {
  const [message, setMessage] = useState("");

  async function share() {
    try {
      if (navigator.share) {
        await navigator.share({ title, url });
        setMessage("Compartilhamento aberto.");
      } else {
        await copy();
      }
    } catch (error) {
      if ((error as DOMException).name !== "AbortError") setMessage("Não foi possível compartilhar agora.");
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setMessage("Link copiado.");
    } catch {
      setMessage("Não foi possível copiar o link.");
    }
  }

  const whatsapp = `https://wa.me/?text=${encodeURIComponent(`${title} — ${url}`)}`;
  return (
    <div className="share-actions">
      <span>Compartilhar</span>
      <button type="button" onClick={share} aria-label="Compartilhar produto">↗</button>
      <a href={whatsapp} target="_blank" rel="noopener noreferrer" aria-label="Compartilhar no WhatsApp">W</a>
      <button type="button" onClick={copy}>Copiar link</button>
      {message && (
        <span className="share-actions__status" role="status" aria-live="polite">
          {message}
        </span>
      )}
    </div>
  );
}
