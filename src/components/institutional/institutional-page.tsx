import type { ReactNode } from "react";

type Section = { title: string; content: ReactNode };

export function InstitutionalPage({
  eyebrow,
  title,
  lead,
  sections,
  note,
}: {
  eyebrow: string;
  title: string;
  lead: string;
  sections: Section[];
  note?: ReactNode;
}) {
  return (
    <article className="institutional-page">
      <header className="institutional-hero">
        <span className="section-kicker">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{lead}</p>
      </header>
      <div className="institutional-layout">
        <div className="institutional-copy">
          {sections.map((section) => (
            <section key={section.title}>
              <h2>{section.title}</h2>
              <div>{section.content}</div>
            </section>
          ))}
        </div>
        {note && <aside className="institutional-note">{note}</aside>}
      </div>
    </article>
  );
}
