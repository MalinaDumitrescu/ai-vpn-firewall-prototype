import React from 'react';
import '../styles/goose.css';

/**
 * GooseMascot — subtle animated SVG goose guardian mascot.
 *
 * Props:
 *   size     "tiny" | "small" | "medium"
 *   variant  "idle" | "watching" | "alert" | "blocking"
 *   style    optional inline overrides
 *   className optional extra CSS classes
 *
 * The goose is a pure SVG drawn inline — no image dependency.
 * It respects overflow: visible so the beak / shield badge can
 * extend slightly past the declared width/height without clipping.
 *
 * Goose is white/pale-blue, orange beak & feet, dark eye.
 * Colours are chosen to look polished on the dark dashboard theme.
 */

const SIZES = {
  tiny:   { w: 26, h: 30 },   // navbar companion
  small:  { w: 44, h: 52 },   // dashboard header decoration
  medium: { w: 76, h: 90 },   // empty / loading state
};

export default function GooseMascot({
  size      = 'small',
  variant   = 'idle',
  style,
  className = '',
}) {
  const dim = SIZES[size] || SIZES.small;

  return (
    <svg
      width={dim.w}
      height={dim.h}
      viewBox="0 0 52 64"
      xmlns="http://www.w3.org/2000/svg"
      className={`goose-mascot goose-${variant} goose-sz-${size} ${className}`.trim()}
      style={style}
      aria-hidden="true"
      focusable="false"
    >
      {/* ── Shield badge (blocking variant only) ──────────────────────── */}
      {variant === 'blocking' && (
        <g className="goose-shield">
          {/* Shield outline */}
          <path
            d="M 41 42 Q 34 46 34 52 Q 34 60 41 63 Q 48 60 48 52 Q 48 46 41 42 Z"
            fill="rgba(79,157,255,0.12)"
            stroke="rgba(79,157,255,0.52)"
            strokeWidth="1.3"
            strokeLinejoin="round"
          />
          {/* Check-mark inside shield */}
          <path
            d="M 38 52 L 40 55 L 44 49"
            stroke="rgba(79,157,255,0.78)"
            strokeWidth="1.3"
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />
        </g>
      )}

      {/* ── Tail feathers ─────────────────────────────────────────────── */}
      <path
        d="M 10 39 Q 4 33 6 26 Q 7 23 10 24 Q 8 29 11 35 Z"
        fill="#a8c8dc"
        stroke="#7aa8c4"
        strokeWidth="0.8"
        strokeLinejoin="round"
      />

      {/* ── Body ──────────────────────────────────────────────────────── */}
      <ellipse
        cx="26" cy="42" rx="17" ry="12"
        fill="#d0e8f4"
        stroke="#8ab8d2"
        strokeWidth="1"
      />

      {/* ── Wing (folded against body) ─────────────────────────────────── */}
      <ellipse
        cx="34" cy="41" rx="11" ry="7"
        transform="rotate(-8 34 41)"
        fill="#aeccde"
        stroke="#8ab8d2"
        strokeWidth="0.8"
      />
      {/* Wing primary feather lines */}
      <path
        d="M 28 43 L 33 48 M 32 42 L 37 47 M 36 40 L 41 44"
        stroke="#88b2cc"
        strokeWidth="0.9"
        strokeLinecap="round"
      />

      {/* ── Feet ──────────────────────────────────────────────────────── */}
      <g stroke="#f97316" strokeLinecap="round">
        {/* Left leg */}
        <line x1="20" y1="53" x2="18" y2="59" strokeWidth="1.8" />
        <line x1="18" y1="59" x2="13" y2="59" strokeWidth="1.4" />
        <line x1="18" y1="59" x2="17" y2="61.5" strokeWidth="1.4" />
        <line x1="18" y1="59" x2="21" y2="60" strokeWidth="1.4" />
        {/* Right leg */}
        <line x1="28" y1="53" x2="30" y2="59" strokeWidth="1.8" />
        <line x1="30" y1="59" x2="35" y2="59" strokeWidth="1.4" />
        <line x1="30" y1="59" x2="31" y2="61.5" strokeWidth="1.4" />
        <line x1="30" y1="59" x2="27" y2="60" strokeWidth="1.4" />
      </g>

      {/* ── Head + neck group (tilts as a unit for variant animations) ── */}
      <g className="goose-head-g">
        {/* Neck: filled ellipse, same colour as body — blends seamlessly */}
        <ellipse
          cx="19" cy="27" rx="6" ry="10"
          transform="rotate(-12 19 27)"
          fill="#d0e8f4"
        />

        {/* Head */}
        <circle
          cx="20" cy="11" r="10"
          fill="#d0e8f4"
          stroke="#8ab8d2"
          strokeWidth="1"
        />

        {/* Beak */}
        <path
          d="M 29 9.5 L 39 11 L 29 13 Z"
          fill="#f97316"
          stroke="#df6a10"
          strokeWidth="0.6"
          strokeLinejoin="round"
        />
        {/* Nostril hint */}
        <ellipse cx="33" cy="11" rx="0.8" ry="0.6" fill="#c85008" opacity="0.45" />

        {/* Eye — wrapped in its own group for CSS blink transform */}
        <g className="goose-eye-g">
          <circle cx="25" cy="8" r="2.6" fill="#1a2d3d" />
          {/* Eye shine */}
          <circle cx="26" cy="7" r="1" fill="#d8eeff" opacity="0.9" />
        </g>

        {/* Subtle cheek blush */}
        <ellipse cx="22" cy="11.5" rx="3" ry="1.8" fill="rgba(250,140,90,0.14)" />
      </g>
    </svg>
  );
}

