/**
 * Lexi's mark: a rounded speech bubble that doubles as an open book, with a
 * single spark for curiosity. Original artwork for Dyscover; colours come from
 * design tokens so it follows light/dark themes.
 */
export function LexiLogo({ size = 40, title }: { size?: number; title?: string }) {
  const labelled = Boolean(title);
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      role={labelled ? 'img' : undefined}
      aria-hidden={labelled ? undefined : true}
      aria-label={title}
      focusable="false"
      className="lexi-logo"
    >
      {labelled && <title>{title}</title>}
      <path
        d="M24 5c10.5 0 19 7.2 19 16.2 0 9-8.5 16.2-19 16.2-2 0-3.9-.3-5.7-.8L10.4 41c-1 .5-2.1-.4-1.8-1.5l1.6-5.8C6.9 30.8 5 26.2 5 21.2 5 12.2 13.5 5 24 5z"
        fill="var(--lexi-bubble, #5b4bdb)"
      />
      <path
        d="M14 16.5c3.4-.9 6.6-.4 9.2 1.5v12.3c-2.6-1.8-5.8-2.3-9.2-1.4V16.5zM34 16.5c-3.4-.9-6.6-.4-9.2 1.5v12.3c2.6-1.8 5.8-2.3 9.2-1.4V16.5z"
        fill="var(--lexi-page, #ffffff)"
      />
      <path
        d="M24 18v12.3"
        stroke="var(--lexi-bubble, #5b4bdb)"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
      <path
        d="M37.5 6.5l1.1 2.6 2.6 1.1-2.6 1.1-1.1 2.6-1.1-2.6-2.6-1.1 2.6-1.1z"
        fill="var(--lexi-spark, #ffc94d)"
      />
    </svg>
  );
}
