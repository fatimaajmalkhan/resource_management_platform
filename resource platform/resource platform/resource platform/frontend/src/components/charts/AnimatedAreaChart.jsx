import React, { useState } from 'react';
import { createPortal } from 'react-dom';

// Premium Theme Colors (Red, White, Yellow)
export const C = {
    white: '#ffffff',
    red: '#ef4444',
    yellow: '#fbbf24',
    gray: '#6b7280',
    billable: '#ffffff',  // White for active/billing
    bench: '#ef4444',     // Red for bench
    other: '#fbbf24',     // Yellow for other
};

// ---------------------------------------------------------------------------
// Shared floating tooltip
// ---------------------------------------------------------------------------
export function useTooltip() {
    const [tip, setTip] = useState(null);
    const show = (x, y, node) => setTip({ x, y, node });
    const hide = () => setTip(null);
    const portal = tip
        ? createPortal(
              <div className="ov-tooltip glass-card" style={{
                  position: 'fixed', left: tip.x + 10, top: tip.y + 10, zIndex: 9999,
                  padding: '12px', border: '1px solid rgba(255,255,255,0.1)',
                  pointerEvents: 'none', background: 'rgba(11, 12, 16, 0.85)'
              }} role="status">
                  {tip.node}
              </div>,
              document.body
          )
        : null;
    return { show, hide, portal };
}

export function TipBody({ swatch, value, label, extra }) {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '16px', fontWeight: 600, color: '#fff', display: 'flex', alignItems: 'center', gap: '6px' }}>
                {swatch && <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: swatch }} />}
                {value}
            </span>
            <span style={{ fontSize: '13px', color: '#9ca3af' }}>{label}</span>
            {extra && <span style={{ fontSize: '12px', color: '#6b7280' }}>{extra}</span>}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Animated Area Chart — actuals (solid) vs. linear-trend forecast (dashed +
// confidence band). Plots Billable/Benched (which together represent
// headcount) and Revenue (billing) together.
// ---------------------------------------------------------------------------
// Helper to format currency compactly (e.g. $500k, $1.2M)
const fmtUsdCompact = (n) => {
    const absN = Math.abs(n ?? 0);
    if (absN >= 1000000) {
        return '$' + (absN / 1000000).toFixed(1) + 'M';
    }
    if (absN >= 1000) {
        return '$' + (absN / 1000).toFixed(0) + 'k';
    }
    return '$' + absN;
};

export default function AnimatedAreaChart({ data, forecast, forecastMeta, tooltip }) {
    if (!data || data.length === 0) return null;

    const width = 800;
    const height = 270;
    const padX = 65;
    const padYTop = 30;
    const padYBot = 50;
    const plotW = width - padX * 2;
    const plotH = height - padYTop - padYBot;

    const hasForecast = Array.isArray(forecast) && forecast.length > 0;
    const historyLen = data.length;

    // Prefix the forecast series with the last actual point (band width 0 there)
    // so the dashed/banded segment visually continues from the solid one instead
    // of leaving a gap.
    const lastActual = data[historyLen - 1];
    const boundaryPoint = hasForecast ? {
        ...lastActual,
        billable_low: lastActual.billable, billable_high: lastActual.billable,
        benched_low: lastActual.benched, benched_high: lastActual.benched,
        revenue_low: lastActual.revenue, revenue_high: lastActual.revenue,
    } : null;
    const forecastSeries = hasForecast ? [boundaryPoint, ...forecast] : [];
    const combined = hasForecast ? [...data, ...forecast] : data;

    // We'll plot Billable (White), Bench (Red), and Revenue (Yellow, secondary axis)
    const maxVal = Math.max(...combined.map(d => (d.billable_high ?? d.billable) + (d.benched_high ?? d.benched))) * 1.2;
    const maxRev = Math.max(...combined.map(d => d.revenue_high ?? d.revenue), 1) * 1.2;

    const getX = (i) => padX + (i / (combined.length - 1)) * plotW;
    const getY = (val) => height - padYBot - (val / maxVal) * plotH;
    const getYRev = (val) => height - padYBot - (val / maxRev) * plotH;
    const forecastIndex = (j) => historyLen - 1 + j; // j=0 -> shared boundary point

    const buildHistoryPath = (key, yFn = getY) =>
        data.map((d, i) => `${i === 0 ? 'M' : 'L'} ${getX(i)} ${yFn(d[key])}`).join(' ');
    const buildHistoryArea = (key) => {
        const path = buildHistoryPath(key);
        return `${path} L ${getX(historyLen - 1)} ${height - padYBot} L ${getX(0)} ${height - padYBot} Z`;
    };
    const buildForecastPath = (key, yFn = getY) =>
        forecastSeries.map((d, j) => `${j === 0 ? 'M' : 'L'} ${getX(forecastIndex(j))} ${yFn(d[key])}`).join(' ');
    const buildForecastBand = (lowKey, highKey, yFn = getY) => {
        const top = forecastSeries.map((d, j) => [getX(forecastIndex(j)), yFn(d[highKey])]);
        const bot = [...forecastSeries].reverse().map((d, j) =>
            [getX(forecastIndex(forecastSeries.length - 1 - j)), yFn(d[lowKey])]);
        return [...top, ...bot].map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0]} ${p[1]}`).join(' ') + ' Z';
    };

    const pathBillable = buildHistoryPath('billable');
    const areaBillable = buildHistoryArea('billable');
    const pathBenched = buildHistoryPath('benched');
    const areaBenched = buildHistoryArea('benched');
    const pathRev = buildHistoryPath('revenue', getYRev);

    const fcPathBillable = hasForecast ? buildForecastPath('billable') : null;
    const fcPathBenched = hasForecast ? buildForecastPath('benched') : null;
    const fcPathRev = hasForecast ? buildForecastPath('revenue', getYRev) : null;
    const fcBandBillable = hasForecast ? buildForecastBand('billable_low', 'billable_high') : null;
    const fcBandBenched = hasForecast ? buildForecastBand('benched_low', 'benched_high') : null;
    const fcBandRev = hasForecast ? buildForecastBand('revenue_low', 'revenue_high', getYRev) : null;

    const dividerX = hasForecast ? (getX(historyLen - 1) + getX(historyLen)) / 2 : null;

    const meta = forecastMeta || {};
    const badge = (key) => {
        const m = meta[key];
        if (!m) return null;
        if (m.all_zero || m.low_confidence) return 'low confidence';
        if (m.flat_trend) return 'stable';
        return null;
    };

    return (
        <div style={{ width: '100%', overflowX: 'auto' }}>
            {/* Legend */}
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '18px', marginBottom: '10px', fontSize: '12px', color: '#9ca3af' }}>
                {[
                    { key: 'billable', label: 'Billable', color: C.white },
                    { key: 'benched', label: 'Benched', color: C.red },
                    { key: 'revenue', label: 'Revenue', color: C.yellow },
                ].map(s => (
                    <span key={s.key} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ width: 8, height: 8, borderRadius: '50%', background: s.color }} />
                        {s.label}
                        {badge(s.key) && (
                            <span style={{ fontSize: '10px', color: C.yellow, border: `1px solid ${C.yellow}`, borderRadius: '4px', padding: '0 4px' }}>
                                {badge(s.key)}
                            </span>
                        )}
                    </span>
                ))}
                {hasForecast && (
                    <>
                        <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <svg width="18" height="8"><line x1="0" y1="4" x2="18" y2="4" stroke="#9ca3af" strokeWidth="2" /></svg>
                            Actual
                        </span>
                        <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <svg width="18" height="8"><line x1="0" y1="4" x2="18" y2="4" stroke="#9ca3af" strokeWidth="2" strokeDasharray="4 4" /></svg>
                            Projected
                        </span>
                    </>
                )}
            </div>

            <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', minWidth: '600px', height: 'auto', overflow: 'visible' }}>
                <defs>
                    <linearGradient id="area-white" x1="0%" y1="0%" x2="0%" y2="100%">
                        <stop offset="0%" stopColor={C.white} stopOpacity="0.3" />
                        <stop offset="100%" stopColor={C.white} stopOpacity="0.0" />
                    </linearGradient>
                    <linearGradient id="area-red" x1="0%" y1="0%" x2="0%" y2="100%">
                        <stop offset="0%" stopColor={C.red} stopOpacity="0.3" />
                        <stop offset="100%" stopColor={C.red} stopOpacity="0.0" />
                    </linearGradient>
                </defs>

                {/* Grid Lines & Y-Axis Scales */}
                {[0, 0.25, 0.5, 0.75, 1].map(pct => {
                    const y = padYTop + plotH * pct;
                    const hcVal = Math.round((1 - pct) * maxVal);
                    const revVal = (1 - pct) * maxRev;
                    return (
                        <g key={pct}>
                            <line x1={padX} y1={y} x2={width - padX} y2={y} stroke="rgba(255,255,255,0.06)" strokeWidth="1" />
                            {/* Left Y Axis Label (Headcount) */}
                            <text x={padX - 10} y={y + 4} fill="#9ca3af" fontSize="10" textAnchor="end">{hcVal}</text>
                            {/* Right Y Axis Label (Revenue) */}
                            <text x={width - padX + 10} y={y + 4} fill="#fbbf24" fontSize="10" textAnchor="start">{fmtUsdCompact(revVal)}</text>
                        </g>
                    );
                })}

                {/* Actual-region areas */}
                <path d={areaBillable} fill="url(#area-white)" />
                <path d={areaBenched} fill="url(#area-red)" />

                {/* Forecast confidence bands (forecast region only) */}
                {hasForecast && <path d={fcBandBillable} fill={C.white} fillOpacity="0.12" />}
                {hasForecast && <path d={fcBandBenched} fill={C.red} fillOpacity="0.12" />}
                {hasForecast && <path d={fcBandRev} fill={C.yellow} fillOpacity="0.08" />}

                {/* Actual lines (solid) */}
                <path d={pathBillable} fill="none" stroke={C.white} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
                <path d={pathBenched} fill="none" stroke={C.red} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
                <path d={pathRev} fill="none" stroke={C.yellow} strokeWidth="3" strokeDasharray="6 6" strokeLinecap="round" strokeLinejoin="round" />

                {/* Forecast lines (dashed; revenue keeps its dash but fades) */}
                {hasForecast && <path d={fcPathBillable} fill="none" stroke={C.white} strokeWidth="3" strokeDasharray="6 6" strokeLinecap="round" strokeLinejoin="round" />}
                {hasForecast && <path d={fcPathBenched} fill="none" stroke={C.red} strokeWidth="3" strokeDasharray="6 6" strokeLinecap="round" strokeLinejoin="round" />}
                {hasForecast && <path d={fcPathRev} fill="none" stroke={C.yellow} strokeWidth="3" strokeDasharray="6 6" strokeOpacity="0.5" strokeLinecap="round" strokeLinejoin="round" />}

                {/* Actual/forecast divider */}
                {hasForecast && (
                    <g>
                        <line x1={dividerX} y1={padYTop} x2={dividerX} y2={height - padYBot} stroke="rgba(255,255,255,0.15)" strokeWidth="1" />
                        <text x={dividerX} y={padYTop - 8} fill="#9ca3af" fontSize="11" textAnchor="middle">Projected →</text>
                    </g>
                )}

                {/* Data Points */}
                {combined.map((d, i) => {
                    const isForecast = i >= historyLen;
                    const x = getX(i);
                    const yBill = getY(d.billable);
                    const yBench = getY(d.benched);
                    const yRev = getYRev(d.revenue);
                    const zoneW = plotW / (combined.length - 1);
                    return (
                        <g key={`${d.month}-${i}`}>
                            {/* X Axis Label (Rotated to prevent overlaps) */}
                            <text 
                                transform={`translate(${x}, ${height - 25}) rotate(-35)`} 
                                fill="#9ca3af" 
                                fontSize="11" 
                                textAnchor="end"
                            >
                                {d.month}
                            </text>

                            {/* Interactive Zone */}
                            <rect
                                x={x - zoneW / 2}
                                y={padYTop}
                                width={zoneW}
                                height={plotH}
                                fill="transparent"
                                style={{ cursor: 'crosshair' }}
                                onMouseMove={(e) => tooltip.show(e.clientX, e.clientY, (
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                        <span style={{ color: '#fff', fontWeight: 'bold' }}>
                                            {d.month}{isForecast && <span style={{ color: '#9ca3af', fontWeight: 400 }}> (projected)</span>}
                                        </span>
                                        <TipBody swatch={C.white} label="Billable"
                                            value={isForecast ? `${d.billable} (range ${d.billable_low}–${d.billable_high})` : d.billable} />
                                        <TipBody swatch={C.red} label="Benched"
                                            value={isForecast ? `${d.benched} (range ${d.benched_low}–${d.benched_high})` : d.benched} />
                                        <TipBody swatch={C.yellow} label="Revenue"
                                            value={isForecast
                                                ? `$${(d.revenue / 1e6).toFixed(2)}M (range $${(d.revenue_low / 1e6).toFixed(2)}–$${(d.revenue_high / 1e6).toFixed(2)}M)`
                                                : `$${(d.revenue / 1000000).toFixed(2)}M`} />
                                    </div>
                                ))}
                                onMouseLeave={tooltip.hide}
                            />
                            {/* Dots: filled = actual, hollow = forecast */}
                            <circle cx={x} cy={yBill} r="4" fill={isForecast ? 'none' : C.white} stroke={isForecast ? C.white : '#111'} strokeWidth="2" style={{ pointerEvents: 'none' }} />
                            <circle cx={x} cy={yBench} r="4" fill={isForecast ? 'none' : C.red} stroke={isForecast ? C.red : '#111'} strokeWidth="2" style={{ pointerEvents: 'none' }} />
                            <circle cx={x} cy={yRev} r="4" fill={isForecast ? 'none' : C.yellow} stroke={isForecast ? C.yellow : '#111'} strokeWidth="2" style={{ pointerEvents: 'none' }} />
                        </g>
                    );
                })}
            </svg>
        </div>
    );
}
