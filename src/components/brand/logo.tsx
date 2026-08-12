type LogoProps = {
  compact?: boolean;
  className?: string;
};

export function Logo({ compact = false, className }: LogoProps) {
  return (
    <span className={["logo", className].filter(Boolean).join(" ")}>
      <svg viewBox="0 0 48 48" aria-hidden="true" className="logo__symbol">
        <path
          d="M35.7 37.3A17 17 0 1 1 38 13.2"
          fill="none"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="6"
        />
        <path d="m32.5 16.5 8-8" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="4" />
        <circle cx="31.5" cy="17.5" r="4.5" fill="#ff6b4a" />
        <circle cx="41.5" cy="7.5" r="3.5" fill="currentColor" />
      </svg>
      {!compact && <span className="logo__word">Orvani</span>}
    </span>
  );
}
