const TABLE_ROWS = [180, 208, 236, 264, 292];
const STAT_TILES = [130, 214, 298, 382];

export function TenderSchematic() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 520 360"
      fill="none"
      className="text-border w-full max-w-lg"
    >
      <g stroke="currentColor" strokeWidth="1">
        {/* Top bar */}
        <line x1="40" y1="36" x2="480" y2="36" opacity="0.8" />
        <line x1="40" y1="30" x2="40" y2="42" opacity="0.8" />
        <line x1="480" y1="30" x2="480" y2="42" opacity="0.8" />

        {/* Main content area */}
        <rect x="40" y="56" width="440" height="272" strokeDasharray="4 4" />

        {/* Sidebar */}
        <line x1="130" y1="56" x2="130" y2="328" strokeDasharray="4 4" />

        {/* Header area */}
        <rect x="146" y="70" width="140" height="14" rx="7" opacity="0.9" />
        <circle cx="460" cy="77" r="7" opacity="0.9" />

        {/* Stat tiles */}
        {STAT_TILES.map((x) => (
          <rect key={x} y="100" x={x} width="68" height="44" rx="2" />
        ))}

        {/* Table area */}
        <rect
          x="146"
          y="164"
          width="320"
          height="148"
          rx="2"
          strokeDasharray="4 4"
        />
        {TABLE_ROWS.map((y) => (
          <line key={y} x1="162" y1={y} x2="450" y2={y} opacity="0.65" />
        ))}

        {/* Sidebar nav bars */}
        {[128, 148, 168, 188].map((y, i) => (
          <rect
            key={y}
            x="52"
            y={y}
            width="64"
            height="8"
            rx="2"
            className={i === 0 ? "fill-primary" : "fill-current"}
            opacity={i === 0 ? 0.5 : 0.35}
          />
        ))}

        {/* Sidebar icon placeholder */}
        <rect
          x="52"
          y="80"
          width="18"
          height="18"
          rx="5"
          className="fill-primary"
          opacity="0.7"
        />
      </g>

      {/* Labels */}
      <g className="fill-muted-foreground font-mono" fontSize="9">
        <text x="260" y="26" textAnchor="middle" letterSpacing="1.5">
          EXTRACTO AI DASHBOARD
        </text>
        <text x="85" y="350" textAnchor="middle" letterSpacing="1.5">
          NAV
        </text>
        <text x="300" y="350" textAnchor="middle" letterSpacing="1.5">
          DOCUMENTS
        </text>
      </g>
    </svg>
  );
}
