"use client";

import { useState } from "react";

/**
 * Tiny ⓘ icon next to a metric label that reveals a tooltip on hover or click.
 * No external library — pure CSS positioning.
 */
export function InfoTip({ children, position = "right" }: { children: React.ReactNode; position?: "right" | "left" }) {
  const [open, setOpen] = useState(false);
  return (
    <span
      style={{ position: "relative", marginLeft: 4, fontSize: 11, cursor: "help" }}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onClick={(e) => {
        e.stopPropagation();
        setOpen((o) => !o);
      }}
    >
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: 13,
          height: 13,
          borderRadius: "50%",
          border: "1px solid var(--muted)",
          color: "var(--muted)",
          fontSize: 9,
          lineHeight: 1,
          fontFamily: "Georgia, serif",
          fontStyle: "italic",
        }}
      >
        i
      </span>
      {open ? (
        <span
          role="tooltip"
          style={{
            position: "absolute",
            zIndex: 10,
            top: "calc(100% + 6px)",
            [position]: 0,
            background: "var(--bg)",
            border: "1px solid var(--border)",
            padding: "8px 10px",
            width: 280,
            color: "var(--fg)",
            fontSize: 11,
            lineHeight: 1.5,
            boxShadow: "0 6px 16px rgba(0,0,0,0.35)",
          }}
        >
          {children}
        </span>
      ) : null}
    </span>
  );
}
