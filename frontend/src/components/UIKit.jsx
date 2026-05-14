/**
 * UIKit.jsx — Alpha-Omega shared design system
 * Clean, consistent components used across all tabs.
 * Import what you need: import { StatCard, SectionCard, PageHeader, BarRow, Badge } from './UIKit';
 */

// ── Design tokens ─────────────────────────────────────────────────────────────
export const C = {
  bg:       '#050810',
  card:     '#080c14',
  inner:    '#0d1420',
  border:   '#1a2535',
  borderFaint: '#111825',
  text:     '#c9d8e8',
  textDim:  '#8899aa',
  textFaint:'#4a6a8a',
  green:    '#00ff88',
  red:      '#ff4466',
  blue:     '#00d4ff',
  purple:   '#c084fc',
  yellow:   '#fbbf24',
  orange:   '#f7931a',
};

// ── StatCard ──────────────────────────────────────────────────────────────────
export const StatCard = ({ label, value, sub, color, accent, minWidth = 130, compact = false }) => (
  <div style={{
    background: C.card,
    border: `1px solid ${accent ? accent + '30' : C.border}`,
    borderTop: accent ? `2px solid ${accent}` : `1px solid ${C.border}`,
    borderRadius: compact ? 6 : 10,
    padding: compact ? '7px 10px' : '16px 18px',
    flex: 1,
    minWidth: compact ? 72 : minWidth,
  }}>
    <div style={{ color: C.textFaint, fontSize: compact ? 7 : 9, letterSpacing: compact ? 1 : 2,
      fontFamily: 'sans-serif', textTransform: 'uppercase', marginBottom: compact ? 3 : 8 }}>
      {label}
    </div>
    <div style={{ color: color || C.text, fontSize: compact ? 15 : 24,
      fontWeight: 'bold', fontFamily: 'monospace', lineHeight: 1.1 }}>
      {value}
    </div>
    {sub && !compact && (
      <div style={{ color: C.textFaint, fontSize: 9, fontFamily: 'sans-serif', marginTop: 5 }}>{sub}</div>
    )}
  </div>
);

// ── SectionCard ───────────────────────────────────────────────────────────────
export const SectionCard = ({ title, subtitle, children, accent, action }) => (
  <div style={{
    background: C.card,
    border: `1px solid ${C.border}`,
    borderRadius: 12,
    overflow: 'hidden',
  }}>
    <div style={{
      padding: '14px 22px',
      borderBottom: `1px solid ${C.borderFaint}`,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        {accent && <div style={{ width: 3, height: 16, background: accent, borderRadius: 2 }} />}
        <div>
          <div style={{ color: C.text, fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace', letterSpacing: 1.5 }}>
            {title}
          </div>
          {subtitle && (
            <div style={{ color: C.textFaint, fontSize: 9, fontFamily: 'sans-serif', marginTop: 2, letterSpacing: 0.5 }}>
              {subtitle}
            </div>
          )}
        </div>
      </div>
      {action}
    </div>
    <div style={{ padding: '18px 22px' }}>{children}</div>
  </div>
);

// ── PageHeader ────────────────────────────────────────────────────────────────
export const PageHeader = ({ icon, title, subtitle, right }) => (
  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      {icon && <div style={{ color: C.blue, display: 'flex' }}>{icon}</div>}
      <div>
        <div style={{ color: C.text, fontSize: 15, fontWeight: 'bold', fontFamily: 'monospace', letterSpacing: 2 }}>
          {title}
        </div>
        {subtitle && (
          <div style={{ color: C.textFaint, fontSize: 9, fontFamily: 'sans-serif', marginTop: 3, letterSpacing: 1 }}>
            {subtitle}
          </div>
        )}
      </div>
    </div>
    {right}
  </div>
);

// ── BarRow ────────────────────────────────────────────────────────────────────
export const BarRow = ({ label, pct, count, color }) => (
  <div style={{ marginBottom: 14 }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, alignItems: 'center' }}>
      <span style={{ color: C.textDim, fontSize: 10, fontFamily: 'sans-serif' }}>{label}</span>
      <span style={{ color: color || C.text, fontSize: 11, fontFamily: 'monospace', fontWeight: 'bold' }}>
        {pct}%
        {count !== undefined && (
          <span style={{ color: C.textFaint, fontWeight: 'normal', fontSize: 9 }}> ({count} trades)</span>
        )}
      </span>
    </div>
    <div style={{ background: C.inner, borderRadius: 4, height: 6, overflow: 'hidden' }}>
      <div style={{
        background: color || C.blue,
        width: `${Math.min(pct, 100)}%`,
        height: '100%',
        borderRadius: 4,
        transition: 'width 0.6s cubic-bezier(0.4,0,0.2,1)',
      }} />
    </div>
  </div>
);

// ── Badge ─────────────────────────────────────────────────────────────────────
export const Badge = ({ label, color = C.blue, size = 'sm' }) => {
  const pad = size === 'lg' ? '4px 12px' : '2px 8px';
  const fs  = size === 'lg' ? 10 : 9;
  return (
    <div style={{
      background: color + '18',
      border: `1px solid ${color}44`,
      borderRadius: 4,
      padding: pad,
      color,
      fontSize: fs,
      fontWeight: 'bold',
      fontFamily: 'sans-serif',
      letterSpacing: 1,
      display: 'inline-flex',
      alignItems: 'center',
    }}>
      {label}
    </div>
  );
};

// ── Divider ───────────────────────────────────────────────────────────────────
export const Divider = () => (
  <div style={{ height: 1, background: C.borderFaint, margin: '4px 0' }} />
);

// ── EmptyState ────────────────────────────────────────────────────────────────
export const EmptyState = ({ icon, title, subtitle }) => (
  <div style={{ textAlign: 'center', padding: '40px 20px' }}>
    {icon && <div style={{ color: C.border, marginBottom: 14, display: 'flex', justifyContent: 'center' }}>{icon}</div>}
    <div style={{ color: C.textDim, fontSize: 13, fontFamily: 'sans-serif', marginBottom: 6 }}>{title}</div>
    {subtitle && <div style={{ color: C.textFaint, fontSize: 10, fontFamily: 'sans-serif' }}>{subtitle}</div>}
  </div>
);

// ── LoadingSpinner ────────────────────────────────────────────────────────────
export const LoadingSpinner = ({ text = 'Loading...' }) => (
  <div style={{ color: C.textDim, textAlign: 'center', padding: '48px 20px', fontFamily: 'sans-serif', fontSize: 12 }}>
    {text}
  </div>
);
