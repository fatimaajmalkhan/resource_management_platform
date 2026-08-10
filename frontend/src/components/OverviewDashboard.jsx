import React, { useState, useEffect, useRef } from 'react';
import { IconAlert } from './icons';
import AnimatedAreaChart, { useTooltip, TipBody, C } from './charts/AnimatedAreaChart';
import '../overview.css';

const fmtUsd = (n) => {
    const formatted = Math.abs(n ?? 0).toLocaleString();
    return (n < 0 ? '-' : '') + '$' + formatted;
};
const fmtUsdCompact = (n) => {
    const absN = Math.abs(n ?? 0);
    const formatted = absN >= 1000 ? '$' + (absN / 1000).toFixed(0) + 'k' : '$' + absN;
    return n < 0 ? '-' + formatted : formatted;
};
const FLAG_LABELS = {
    missing_hr_fields: 'Missing HR fields',
    zero_billing_active: 'Active but zero billing',
};

// ---------------------------------------------------------------------------
// Animated Donut
// ---------------------------------------------------------------------------
function AnimatedDonut({ segments, centerValue, centerLabel, tooltip }) {
    const total = segments.reduce((s, d) => s + d.value, 0) || 1;
    const size = 220;
    const r = 85;
    const cx = size / 2;
    const cy = size / 2;
    const circ = 2 * Math.PI * r;
    const gap = 4;
    let offset = 0;

    return (
        <div className="chart-container" style={{ position: 'relative', width: size, height: size, margin: '0 auto' }}>
            <svg viewBox={`0 0 ${size} ${size}`} className="svg-donut" role="img" aria-label={centerLabel}>
                <defs>
                    <linearGradient id="white-grad" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stopColor="#f3f4f6" />
                        <stop offset="100%" stopColor="#ffffff" />
                    </linearGradient>
                    <linearGradient id="red-grad" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stopColor="#f87171" />
                        <stop offset="100%" stopColor="#ef4444" />
                    </linearGradient>
                    <linearGradient id="yellow-grad" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stopColor="#fde047" />
                        <stop offset="100%" stopColor="#fbbf24" />
                    </linearGradient>
                </defs>
                <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="20" />
                {segments.map((seg, i) => {
                    const frac = seg.value / total;
                    const len = Math.max(frac * circ - gap, 0);
                    const dash = `${len} ${circ - len}`;
                    
                    let gradId = "white-grad";
                    if (seg.color === C.bench) gradId = "red-grad";
                    if (seg.color === C.other) gradId = "yellow-grad";

                    const el = (
                        <circle
                            key={seg.label}
                            cx={cx}
                            cy={cy}
                            r={r}
                            fill="none"
                            stroke={`url(#${gradId})`}
                            strokeWidth="20"
                            strokeLinecap="round"
                            strokeDasharray={dash}
                            strokeDashoffset={-offset}
                            transform={`rotate(-90 ${cx} ${cy})`}
                            className="donut-segment"
                            onMouseMove={(e) =>
                                tooltip.show(e.clientX, e.clientY,
                                    <TipBody swatch={seg.color} value={seg.value} label={seg.label}
                                        extra={`${Math.round(frac * 100)}% of total`} />)
                            }
                            onMouseLeave={tooltip.hide}
                        />
                    );
                    offset += frac * circ;
                    return el;
                })}
            </svg>
            <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', pointerEvents: 'none' }}>
                <span style={{ fontSize: '36px', fontWeight: 700, color: '#fff', textShadow: '0 2px 10px rgba(0,0,0,0.5)' }}>{centerValue}</span>
                <span style={{ fontSize: '13px', color: '#9ca3af' }}>{centerLabel}</span>
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Sleek Column Chart
// ---------------------------------------------------------------------------
function SleekColumns({ data, accent, tooltip }) {
    const max = Math.max(...data.map((d) => d.value), 1);
    const total = data.reduce((s, d) => s + d.value, 0);
    const width = 460;
    const height = 220;
    const padB = 28;
    const padT = 20;
    const plotH = height - padB - padT;
    const slot = width / data.length;
    const barW = Math.min(32, slot * 0.5);

    return (
        <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: '100%', overflow: 'visible' }} role="img">
                <defs>
                    <linearGradient id="col-grad" x1="0%" y1="0%" x2="0%" y2="100%">
                        <stop offset="0%" stopColor={accent} />
                        <stop offset="100%" stopColor="transparent" stopOpacity="0.2" />
                    </linearGradient>
                </defs>
                <line x1="0" y1={height - padB} x2={width} y2={height - padB} stroke="rgba(255,255,255,0.1)" strokeWidth="1" />
                {data.map((d, i) => {
                    const h = Math.max((d.value / max) * plotH, 4);
                    const x = i * slot + (slot - barW) / 2;
                    const y = height - padB - h;
                    return (
                        <g
                            key={d.label}
                            onMouseMove={(e) =>
                                tooltip.show(e.clientX, e.clientY,
                                    <TipBody swatch={accent} value={d.value} label={d.label}
                                        extra={total ? `${Math.round((d.value / total) * 100)}% of total` : null} />)
                            }
                            onMouseLeave={tooltip.hide}
                        >
                            <rect x={i * slot} y={padT} width={slot} height={height - padT} fill="transparent" />
                            <rect x={x} y={y} width={barW} height={h} fill="url(#col-grad)" rx={4} className="col-bar" />
                            <text x={x + barW / 2} y={y - 8} fill="#fff" fontSize="12" fontWeight="600" textAnchor="middle">{d.value}</text>
                            <text x={x + barW / 2} y={height - padB + 18} fill="#9ca3af" fontSize="11" textAnchor="middle">{d.label}</text>
                        </g>
                    );
                })}
            </svg>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Dashboard Component
// ---------------------------------------------------------------------------
export default function OverviewDashboard() {
    const [data, setData] = useState(null);
    const [tsData, setTsData] = useState(null);
    const [forecastData, setForecastData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const tooltip = useTooltip();

    // Scenario Simulator State
    const [winProbabilityFloor, setWinProbabilityFloor] = useState(50);
    const [attritionRate, setAttritionRate] = useState(0);
    const [trendScalar, setTrendScalar] = useState(100); // 100% is 1.0
    const [dailyRateScaler, setDailyRateScaler] = useState(0); // 0% shift is 1.0
    const [modelType, setModelType] = useState('hybrid');

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const [resOverview, resTs] = await Promise.all([
                    fetch('/api/overview'),
                    fetch('/api/overview/timeseries')
                ]);
                if (!resOverview.ok || !resTs.ok) throw new Error('Failed to load dashboard data');

                const jsonOverview = await resOverview.json();
                const jsonTs = await resTs.json();

                if (!cancelled) {
                    setData(jsonOverview);
                    setTsData(jsonTs);
                }
            } catch (err) {
                if (!cancelled) setError(err.message);
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, []);

    // Forecast Simulator fetch -- automatically updates when any slider changes
    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const ts = trendScalar / 100.0;
                const drs = 1.0 + (dailyRateScaler / 100.0);
                const query = `?months=3&win_probability_floor=${winProbabilityFloor}&attrition_rate=${attritionRate}&trend_scalar=${ts}&daily_rate_scaler=${drs}&model_type=${modelType}`;
                const res = await fetch(`/api/overview/forecast${query}`);
                if (!res.ok) throw new Error('forecast unavailable');
                const json = await res.json();
                if (!cancelled) setForecastData(json);
            } catch (err) {
                console.warn('Overview forecast failed to load:', err.message);
            }
        })();
        return () => { cancelled = true; };
    }, [winProbabilityFloor, attritionRate, trendScalar, dailyRateScaler, modelType]);

    if (loading) return <div className="overview-dashboard"><div style={{ margin: 'auto', color: 'var(--text-muted)' }}>Initializing Insights...</div></div>;
    if (error) return <div className="overview-dashboard"><div style={{ margin: 'auto', color: 'var(--danger)' }}>Error: {error}</div></div>;

    const billablePct = data.headcount ? Math.round((data.billable_count / data.headcount) * 100) : 0;
    const otherCount = Math.max(0, data.headcount - data.billable_count - data.bench_count);

    const donutSegments = [
        { label: 'Billable', value: data.billable_count, color: C.billable },
        { label: 'Bench', value: data.bench_count, color: C.bench },
        { label: 'Other', value: otherCount, color: C.other },
    ].filter((s) => s.value > 0);

    // Calculate Insights from Time Series
    let hcInsight = 'Active Workforce';
    let benchInsight = `${data.bench_rate}% Bench Rate`;
    let revInsight = `Avg Rate: ${fmtUsd(data.avg_daily_rate)}`;
    let billInsight = `${billablePct}% Utilization`;

    if (tsData && tsData.length >= 2) {
        const curr = tsData[tsData.length - 1];
        const prev = tsData[tsData.length - 2];
        
        const hcChange = curr.headcount - prev.headcount;
        const revChange = curr.revenue - prev.revenue;
        const billChange = curr.billable - prev.billable;
        
        const bRateCurr = (curr.benched / curr.headcount) * 100;
        const bRatePrev = (prev.benched / prev.headcount) * 100;
        const bRateChange = (bRateCurr - bRatePrev).toFixed(1);

        hcInsight = `Active Workforce (${hcChange >= 0 ? '↑' : '↓'} ${Math.abs(hcChange)} MoM)`;
        revInsight = `Avg Rate: ${fmtUsd(data.avg_daily_rate)} (${revChange >= 0 ? '↑' : '↓'} ${fmtUsdCompact(Math.abs(revChange))} MoM)`;
        benchInsight = `${data.bench_rate}% Bench Rate (${bRateChange >= 0 ? '↑' : '↓'} ${Math.abs(bRateChange)}% MoM)`;
        billInsight = `${billablePct}% Utilization (${billChange >= 0 ? '↑' : '↓'} ${Math.abs(billChange)} staff MoM)`;
    }

    const tiles = [
        { label: 'Total Headcount', value: data.headcount, sub: hcInsight, accent: C.yellow, delay: '0.1s' },
        { label: 'Billable Staff', value: data.billable_count, sub: billInsight, accent: C.white, delay: '0.2s' },
        { label: 'On Bench', value: data.bench_count, sub: benchInsight, accent: C.red, delay: '0.3s' },
        { label: 'Monthly Revenue', value: fmtUsdCompact(data.total_monthly_billing), sub: revInsight, accent: C.white, delay: '0.4s' },
        { label: 'Active Projects', value: data.active_projects_count || 0, sub: 'Client Engagements', accent: C.yellow, delay: '0.5s' }
    ];

    return (
        <div className="overview-dashboard">
            {tooltip.portal}
            
            <header className="overview-header">
                <div>
                    <h2>Workforce Insights</h2>
                    <p>Real-time analytics and telemetry of your global workforce.</p>
                </div>
            </header>

            {/* KPI Row */}
            <div className="kpi-row">
                {tiles.map((t) => (
                    <div key={t.label} className="glass-card kpi-tile" style={{ '--tile-accent': t.accent, animationDelay: t.delay }}>
                        <span className="kpi-label">{t.label}</span>
                        <div className="kpi-value" style={{ color: t.accent }}>{t.value}</div>
                        <span className="kpi-sub">{t.sub}</span>
                    </div>
                ))}
            </div>

            {/* Time Series Chart & Scenario Simulator */}
            <div className="dashboard-grid" style={{ gridTemplateColumns: '1fr', marginTop: '24px' }}>
                <div className="glass-card" style={{ animationDelay: '0.55s', padding: '24px 24px 16px 24px' }}>
                    <h3 className="card-title">Utilization Trend & Interactive Scenario Simulator</h3>
                    <p className="card-subtitle" style={{ marginBottom: '16px' }}>
                        Solid lines are actuals; dashed lines and shaded bands represent the 3-month projected window under simulated scenario parameters.
                    </p>
                    
                    <div className="forecast-section-wrapper">
                        <div className="forecast-chart-column">
                            <AnimatedAreaChart
                                data={tsData}
                                forecast={forecastData?.forecast}
                                forecastMeta={forecastData?.metrics_meta}
                                tooltip={tooltip}
                            />
                        </div>
                        <div className="forecast-simulator-column">
                            <h4 className="simulator-title">Scenario Parameters</h4>
                            <p className="simulator-subtitle">Adjust metrics to update forecast and simulation outcomes in real time.</p>
                            
                            <div className="simulator-control">
                                <label className="control-label">
                                    <span>Model Method</span>
                                    <span className="control-val">{modelType.toUpperCase()}</span>
                                </label>
                                <select 
                                    className="simulator-select" 
                                    value={modelType} 
                                    onChange={(e) => setModelType(e.target.value)}
                                >
                                    <option value="hybrid">Hybrid Simulation (Advanced Trend + Pipeline + Roll-offs)</option>
                                    <option value="ols">Advanced Holt-Winters Statistical Trend Only</option>
                                    <option value="pipeline_only">Sales Pipeline Only</option>
                                </select>
                            </div>

                            <div className="simulator-control">
                                <label className="control-label">
                                    <span>Win Probability Floor</span>
                                    <span className="control-val">{winProbabilityFloor}%</span>
                                </label>
                                <input 
                                    type="range" min="0" max="100" step="10"
                                    className="simulator-slider"
                                    value={winProbabilityFloor}
                                    onChange={(e) => setWinProbabilityFloor(Number(e.target.value))}
                                    disabled={modelType === 'ols'}
                                />
                            </div>

                            <div className="simulator-control">
                                <label className="control-label">
                                    <span>Monthly Attrition Rate</span>
                                    <span className="control-val">{attritionRate}%</span>
                                </label>
                                <input 
                                    type="range" min="0" max="10" step="0.5"
                                    className="simulator-slider"
                                    value={attritionRate}
                                    onChange={(e) => setAttritionRate(Number(e.target.value))}
                                />
                            </div>

                            <div className="simulator-control">
                                <label className="control-label">
                                    <span>Trend Scale Factor</span>
                                    <span className="control-val">{trendScalar - 100 >= 0 ? '+' : ''}{trendScalar - 100}%</span>
                                </label>
                                <input 
                                    type="range" min="0" max="200" step="10"
                                    className="simulator-slider"
                                    value={trendScalar}
                                    onChange={(e) => setTrendScalar(Number(e.target.value))}
                                    disabled={modelType === 'pipeline_only'}
                                />
                            </div>

                            <div className="simulator-control">
                                <label className="control-label">
                                    <span>Daily Billing Rate Shift</span>
                                    <span className="control-val">{dailyRateScaler >= 0 ? '+' : ''}{dailyRateScaler}%</span>
                                </label>
                                <input 
                                    type="range" min="-20" max="20" step="1"
                                    className="simulator-slider"
                                    value={dailyRateScaler}
                                    onChange={(e) => setDailyRateScaler(Number(e.target.value))}
                                />
                            </div>

                            {/* Simulated Outcomes */}
                            {forecastData && forecastData.forecast && forecastData.forecast.length >= 3 && (() => {
                                const endPoint = forecastData.forecast[2];
                                const hcDelta = endPoint.headcount - data.headcount;
                                const revDelta = endPoint.revenue - data.total_monthly_billing;
                                const benchRate = endPoint.headcount ? Math.round((endPoint.benched / endPoint.headcount) * 100) : 0;
                                
                                return (
                                    <div className="simulated-outcomes">
                                        <h5 className="outcomes-title">Simulated Outcomes (3mo)</h5>
                                        <div className="outcome-row">
                                            <span className="outcome-label">Net Hiring / Shortfall:</span>
                                            <span className={`outcome-value ${hcDelta > 0 ? 'text-success' : hcDelta < 0 ? 'text-coral' : ''}`}>
                                                {hcDelta >= 0 ? `+${hcDelta}` : hcDelta} staff
                                            </span>
                                        </div>
                                        <div className="outcome-row">
                                            <span className="outcome-label">Projected Bench Rate:</span>
                                            <span className={`outcome-value ${benchRate > 20 ? 'text-coral' : 'text-success'}`}>
                                                {benchRate}% {benchRate > 20 ? '(High Risk)' : '(Safe)'}
                                            </span>
                                        </div>
                                        <div className="outcome-row">
                                            <span className="outcome-label">Monthly Revenue Delta:</span>
                                            <span className={`outcome-value ${revDelta > 0 ? 'text-success' : revDelta < 0 ? 'text-coral' : ''}`}>
                                                {revDelta >= 0 ? `+` : ''}{fmtUsdCompact(revDelta)}/mo
                                            </span>
                                        </div>
                                    </div>
                                );
                            })()}
                        </div>
                    </div>
                </div>
            </div>

            {/* Middle Grid */}
            <div className="dashboard-grid">
                {/* Donut Chart */}
                <div className="glass-card" style={{ animationDelay: '0.6s' }}>
                    <h3 className="card-title">Deployment Distribution</h3>
                    <p className="card-subtitle">Current status of active workforce.</p>
                    <AnimatedDonut segments={donutSegments} centerValue={data.headcount} centerLabel="PEOPLE" tooltip={tooltip} />

                    <div style={{ display: 'flex', justifyContent: 'center', gap: '20px', marginTop: '16px' }}>
                        <span style={{ fontSize: '12px', color: '#9ca3af', display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span style={{ width: 8, height: 8, borderRadius: '50%', background: C.billable }}></span> Billable
                        </span>
                        <span style={{ fontSize: '12px', color: '#9ca3af', display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span style={{ width: 8, height: 8, borderRadius: '50%', background: C.bench }}></span> Bench
                        </span>
                        <span style={{ fontSize: '12px', color: '#9ca3af', display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span style={{ width: 8, height: 8, borderRadius: '50%', background: C.other }}></span> Other
                        </span>
                    </div>
                </div>

                {/* Grade Columns */}
                <div className="glass-card" style={{ animationDelay: '0.7s', display: 'flex', flexDirection: 'column' }}>
                    <h3 className="card-title">Grade Demographics</h3>
                    <p className="card-subtitle">Seniority mix from junior (L1) to senior (L5).</p>
                    <div style={{ flexGrow: 1, position: 'relative' }}>
                        <SleekColumns data={data.by_grade.map((g) => ({ label: g.grade, value: g.count }))} accent={C.white} tooltip={tooltip} />
                    </div>
                </div>
            </div>

            {/* Workforce Type + Department Grid */}
            <div className="dashboard-grid">
                {/* Workforce Type Chart */}
                <div className="glass-card" style={{ animationDelay: '0.75s', display: 'flex', flexDirection: 'column' }}>
                    <h3 className="card-title">Workforce Type</h3>
                    <p className="card-subtitle">Full-Time vs Contractual vs Probationary breakdown.</p>
                    <div style={{ flexGrow: 1, position: 'relative' }}>
                        <SleekColumns
                            data={(data.by_employee_type || []).map((e) => ({ label: e.employee_type, value: e.count }))}
                            accent={C.yellow}
                            tooltip={tooltip}
                        />
                    </div>
                </div>

                {/* Department Breakdown Table */}
                <div className="glass-card" style={{ animationDelay: '0.78s' }}>
                    <h3 className="card-title">Department Breakdown</h3>
                    <p className="card-subtitle">Headcount distribution across departments.</p>
                    <div style={{ overflowX: 'auto' }}>
                        <table className="modern-table">
                            <thead>
                                <tr>
                                    <th>Department</th>
                                    <th>Headcount</th>
                                </tr>
                            </thead>
                            <tbody>
                                {(data.by_department || []).slice(0, 8).map((d) => (
                                    <tr key={d.department}>
                                        <td style={{ fontWeight: 500, color: '#fff' }}>{d.department}</td>
                                        <td><span className="pill" style={{ backgroundColor: 'rgba(251, 191, 36, 0.2)', color: C.yellow }}>{d.headcount}</span></td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            {/* Bottom Grid */}
            <div className="dashboard-grid">
                {/* Actionable Insights */}
                <div className="glass-card" style={{ animationDelay: '0.8s' }}>
                    <h3 className="card-title">Action Center</h3>
                    <p className="card-subtitle">Automated alerts and data quality checks.</p>
                    
                    <div className="insight-list">
                        {data.bench_rate > 20 && (
                            <div className="insight-item">
                                <div className="insight-icon bg-coral-light"><IconAlert width={20} height={20} /></div>
                                <div className="insight-content">
                                    <span className="insight-title">High Bench Rate</span>
                                    <span className="insight-desc">Current bench rate is {data.bench_rate}%, above the 20% threshold.</span>
                                </div>
                            </div>
                        )}
                        {data.flags.length > 0 ? (
                            data.flags.map(f => (
                                <div key={f.flag} className="insight-item">
                                    <div className="insight-icon bg-warning-light"><IconAlert width={20} height={20} /></div>
                                    <div className="insight-content">
                                        <span className="insight-title">{FLAG_LABELS[f.flag] || f.flag}</span>
                                        <span className="insight-desc">{f.count} records require HR attention.</span>
                                    </div>
                                </div>
                            ))
                        ) : (
                            <div className="insight-item">
                                <div className="insight-icon bg-success-light">✓</div>
                                <div className="insight-content">
                                    <span className="insight-title">Data Healthy</span>
                                    <span className="insight-desc">No missing fields detected in active resources.</span>
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Locations / Dept Table */}
                <div className="glass-card" style={{ animationDelay: '0.9s' }}>
                    <h3 className="card-title">Geographic Footprint</h3>
                    <p className="card-subtitle">Headcount and bench status by location.</p>
                    <div style={{ overflowX: 'auto' }}>
                        <table className="modern-table">
                            <thead>
                                <tr>
                                    <th>Location</th>
                                    <th>Headcount</th>
                                    <th>Bench</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.by_location?.slice(0, 10).map((l) => (
                                    <tr key={l.location}>
                                        <td style={{ fontWeight: 500, color: '#fff' }}>{l.location}</td>
                                        <td>{l.headcount}</td>
                                        <td>{l.benched}</td>
                                        <td>
                                            <span className={`pill ${l.benched > 5 ? 'bg-coral-light' : 'bg-success-light'}`}>
                                                {l.benched > 5 ? 'High Risk' : 'Optimal'}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            {/* Full Width Practice Table */}
            <div className="glass-card" style={{ animationDelay: '1.0s' }}>
                <h3 className="card-title">Practice Performance Matrix</h3>
                <p className="card-subtitle">Deep dive into practice deployment and revenue generation.</p>
                <div style={{ overflowX: 'auto', marginTop: '16px' }}>
                    <table className="modern-table">
                        <thead>
                            <tr>
                                <th>Practice Area</th>
                                <th>Total Staff</th>
                                <th>Billable</th>
                                <th>Bench</th>
                                <th>Monthly Rev ($)</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.by_practice.map((p) => (
                                <tr key={p.practice}>
                                    <td style={{ fontWeight: 600, color: C.white }}>{p.practice}</td>
                                    <td><span className="pill" style={{ backgroundColor: 'rgba(251, 191, 36, 0.2)', color: C.yellow }}>{p.headcount}</span></td>
                                    <td>{p.billable}</td>
                                    <td>{p.benched > 0 ? <span style={{color: C.red}}>{p.benched}</span> : '0'}</td>
                                    <td style={{ fontFamily: 'monospace', fontSize: '15px' }}>{fmtUsd(p.monthly_billing)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

        </div>
    );
}
