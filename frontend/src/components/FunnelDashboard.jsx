import React, { useState, useEffect } from 'react';
import {
    IconPlus, IconHistory, IconPin, IconCalendar, IconBriefcase,
    IconUser, IconCheck, IconAlert, IconEdit, IconTrash,
} from './icons';
import '../funnel.css';

export default function FunnelDashboard() {
    // Filters state
    const [filters, setFilters] = useState({
        month: '',
        role: '',
        practice: '',
        stage: '',
        probability_floor: ''
    });

    // Calculations & match results
    const [funnelData, setFunnelData] = useState({
        cautious_estimate: 0,
        hopeful_estimate: 0,
        recommendations: [],
        benched: { "Data Engineer": [], "BI": [], "DBA": [], "Other": [] }
    });

    // Choices for filter dropdowns
    const [choices, setChoices] = useState({
        stages: ["Prospecting", "Proposal", "Won"],
        roles: ["Data Engineer", "BI", "DBA", "Other"],
        practices: ["Analytics & Insights", "Software - TSF"],
        months: ["2026-07", "2026-08", "2026-09"]
    });

    // Modals state
    const [showAddModal, setShowAddModal] = useState(false);
    const [showEditModal, setShowEditModal] = useState(false);

    // Form states
    const [newDeal, setNewDeal] = useState({
        client_project: '',
        stage: 'Proposal',
        probability: 70,
        role: 'Data Engineer',
        quantity: 1,
        target_month: '2026-07',
        practice: 'Analytics & Insights',
        notes: ''
    });

    const [editingDeal, setEditingDeal] = useState(null);

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // History panel state
    const [showHistory, setShowHistory] = useState(false);
    const [historyTab, setHistoryTab] = useState('deals');
    const [historyDealFilter, setHistoryDealFilter] = useState('');
    const [dealHistory, setDealHistory] = useState([]);
    const [funnelHistory, setFunnelHistory] = useState([]);
    const [historyLoading, setHistoryLoading] = useState(false);

    // Fetch dynamic options for filters
    const fetchChoices = async () => {
        try {
            const res = await fetch('/api/choices');
            if (res.ok) {
                const data = await res.json();
                setChoices(data);
            }
        } catch (err) {
            console.error("Failed to fetch choices", err);
        }
    };

    // Fetch calculations & recommendations
    const fetchFunnelData = async () => {
        setLoading(true);
        setError(null);
        try {
            const queryParams = new URLSearchParams();
            if (filters.month) queryParams.append('month', filters.month);
            if (filters.role) queryParams.append('role', filters.role);
            if (filters.practice) queryParams.append('practice', filters.practice);
            if (filters.stage) queryParams.append('stage', filters.stage);
            if (filters.probability_floor) queryParams.append('probability_floor', filters.probability_floor);

            const res = await fetch(`/api/funnel?${queryParams.toString()}`);
            if (!res.ok) throw new Error("Failed to fetch demand calculations");
            
            const data = await res.json();
            setFunnelData(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchChoices();
    }, []);

    useEffect(() => {
        fetchFunnelData();
    }, [filters]);

    const fetchHistory = async () => {
        setHistoryLoading(true);
        try {
            const dealParam = historyDealFilter ? `?deal_id=${historyDealFilter}` : '';
            const [dealRes, funnelRes] = await Promise.all([
                fetch(`/api/deals/history${dealParam}`),
                fetch(`/api/funnel/history${dealParam}`)
            ]);
            if (dealRes.ok) setDealHistory(await dealRes.json());
            if (funnelRes.ok) setFunnelHistory(await funnelRes.json());
        } catch (err) {
            console.error("Failed to fetch history", err);
        } finally {
            setHistoryLoading(false);
        }
    };

    useEffect(() => {
        if (showHistory) fetchHistory();
    }, [showHistory, historyDealFilter]);

    const handleFilterChange = (e) => {
        const { name, value } = e.target;
        setFilters(prev => ({ ...prev, [name]: value }));
    };

    const handleClearFilters = () => {
        setFilters({
            month: '',
            role: '',
            practice: '',
            stage: '',
            probability_floor: ''
        });
    };

    const handleAddDealSubmit = async (e) => {
        e.preventDefault();
        try {
            const res = await fetch('/api/deals', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newDeal)
            });
            if (res.ok) {
                const data = await res.json();
                setShowAddModal(false);
                setNewDeal({
                    client_project: '',
                    stage: 'Proposal',
                    probability: 70,
                    role: 'Data Engineer',
                    quantity: 1,
                    target_month: '2026-07',
                    practice: 'Analytics & Insights',
                    notes: ''
                });
                fetchFunnelData();
                fetchChoices();
                if (showHistory) fetchHistory();
                if (data.excel_synced === false) {
                    alert('Deal saved, but the Excel file couldn\'t be updated right away (it may be open elsewhere). It will sync automatically within about 20 seconds.');
                }
            } else {
                alert("Error adding deal");
            }
        } catch (err) {
            console.error("Add deal failed", err);
        }
    };

    const handleEditDealClick = (deal) => {
        setEditingDeal(deal);
        setShowEditModal(true);
    };

    const handleEditDealSubmit = async (e) => {
        e.preventDefault();
        try {
            const res = await fetch(`/api/deals/${editingDeal.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(editingDeal)
            });
            if (res.ok) {
                setShowEditModal(false);
                setEditingDeal(null);
                fetchFunnelData();
                fetchChoices();
                if (showHistory) fetchHistory();
            } else {
                alert("Error updating deal");
            }
        } catch (err) {
            console.error("Update deal failed", err);
        }
    };

    const handleDeleteDeal = async (id) => {
        if (!confirm("Are you sure you want to delete this sales deal?")) return;
        try {
            const res = await fetch(`/api/deals/${id}`, {
                method: 'DELETE'
            });
            if (res.ok) {
                fetchFunnelData();
                fetchChoices();
                if (showHistory) fetchHistory();
            } else {
                alert("Error deleting deal");
            }
        } catch (err) {
            console.error("Delete deal failed", err);
        }
    };

    const formatTimestamp = (iso) => {
        if (!iso) return '';
        const d = new Date(iso);
        return d.toLocaleString();
    };

    // Shortfall-first ordering so the deals that need hiring lead the list.
    const sortedRecommendations = [...funnelData.recommendations].sort(
        (a, b) => b.shortfall - a.shortfall
    );
    // Total open hiring need — the single most actionable number.
    const openHiringNeed = funnelData.recommendations.reduce((sum, r) => sum + (r.shortfall || 0), 0);
    const dealsWithShortfall = funnelData.recommendations.filter(r => r.shortfall > 0).length;
    // Cautious as a share of hopeful — a real ratio for the progress bar.
    const cautiousShare = funnelData.hopeful_estimate > 0
        ? Math.round((funnelData.cautious_estimate / funnelData.hopeful_estimate) * 100)
        : 0;

    return (
        <div className="funnel-container">
            <header className="funnel-header">
                <div className="header-info">
                    <h2>Sales Pipeline & Demand Funnel</h2>
                    <p>Track resources needed for upcoming sales opportunities, benched matches, and hiring forecasts.</p>
                </div>
                <div className="header-actions">
                    <button
                        className={`history-toggle-btn ${showHistory ? 'active' : ''}`}
                        onClick={() => setShowHistory(prev => !prev)}
                    >
                        <IconHistory width={16} height={16} /> {showHistory ? 'Hide history' : 'View history'}
                    </button>
                    <button className="add-deal-btn" onClick={() => setShowAddModal(true)}>
                        <IconPlus width={16} height={16} /> Add deal
                    </button>
                </div>
            </header>

            {showHistory && (
                <section className="dashboard-section-card funnel-history-panel">
                    <div className="history-panel-header">
                        <div>
                            <h3>Funnel history</h3>
                            <p className="section-subtitle">Track deal changes and how recommendations evolved over time.</p>
                        </div>
                        <div className="history-controls">
                            <select
                                value={historyDealFilter}
                                onChange={e => setHistoryDealFilter(e.target.value)}
                                aria-label="Filter history by deal"
                            >
                                <option value="">All deals</option>
                                {funnelData.recommendations.map(d => (
                                    <option key={d.id} value={d.id}>{d.client_project}</option>
                                ))}
                            </select>
                            <button className="refresh-history-btn" onClick={fetchHistory}>Refresh</button>
                        </div>
                    </div>

                    <div className="history-tabs">
                        <button
                            className={`history-tab ${historyTab === 'deals' ? 'active' : ''}`}
                            onClick={() => setHistoryTab('deals')}
                        >
                            Deal changes ({dealHistory.length})
                        </button>
                        <button
                            className={`history-tab ${historyTab === 'recommendations' ? 'active' : ''}`}
                            onClick={() => setHistoryTab('recommendations')}
                        >
                            Recommendation snapshots ({funnelHistory.length})
                        </button>
                    </div>

                    {historyLoading ? (
                        <div className="funnel-loading">Loading history...</div>
                    ) : historyTab === 'deals' ? (
                        dealHistory.length === 0 ? (
                            <div className="funnel-empty">No deal changes recorded yet. Add or edit a deal to start tracking.</div>
                        ) : (
                            <div className="history-timeline">
                                {dealHistory.map(h => (
                                    <div key={h.history_id} className="history-entry">
                                        <div className="history-entry-time">{formatTimestamp(h.changed_at)}</div>
                                        <div className="history-entry-body">
                                            <span className={`history-action action-${h.action}`}>{h.action}</span>
                                            <strong>{h.deal_name || `Deal #${h.deal_id}`}</strong>
                                            {h.action === 'updated' && (
                                                <span className="history-detail">
                                                    {h.field_name}: <em>{h.old_value}</em> → <em>{h.new_value}</em>
                                                </span>
                                            )}
                                            {h.action === 'created' && h.new_value && (
                                                <span className="history-detail">Initial: {h.new_value}</span>
                                            )}
                                            <span className="history-source">via {h.source}</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )
                    ) : (
                        funnelHistory.length === 0 ? (
                            <div className="funnel-empty">No recommendation snapshots yet. Snapshots are saved when suggestions change.</div>
                        ) : (
                            <div className="history-timeline">
                                {funnelHistory.map(s => (
                                    <div key={s.snapshot_id} className="history-entry">
                                        <div className="history-entry-time">{formatTimestamp(s.computed_at)}</div>
                                        <div className="history-entry-body">
                                            <strong>{s.client_project}</strong>
                                            <span className="history-detail">
                                                {s.role} × {s.quantity} — shortfall: {s.shortfall}
                                            </span>
                                            {s.suggested_matches?.length > 0 ? (
                                                <span className="history-detail">
                                                    Matches: {s.suggested_matches.join(', ')}
                                                </span>
                                            ) : (
                                                <span className="history-detail">No bench matches</span>
                                            )}
                                            <span className="history-detail rec-text">{s.recommendation}</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )
                    )}
                </section>
            )}

            {/* Filters panel */}
            <section className="funnel-filters-card">
                <div className="filters-grid">
                    <div className="filter-group">
                        <label>Target month</label>
                        <select name="month" value={filters.month} onChange={handleFilterChange}>
                            <option value="">All months</option>
                            {choices.months.map(m => <option key={m} value={m}>{m}</option>)}
                        </select>
                    </div>
                    <div className="filter-group">
                        <label>Role</label>
                        <select name="role" value={filters.role} onChange={handleFilterChange}>
                            <option value="">All roles</option>
                            {choices.roles.map(r => <option key={r} value={r}>{r}</option>)}
                        </select>
                    </div>
                    <div className="filter-group">
                        <label>Practice</label>
                        <select name="practice" value={filters.practice} onChange={handleFilterChange}>
                            <option value="">All practices</option>
                            {choices.practices.map(p => <option key={p} value={p}>{p}</option>)}
                        </select>
                    </div>
                    <div className="filter-group">
                        <label>Deal stage</label>
                        <select name="stage" value={filters.stage} onChange={handleFilterChange}>
                            <option value="">All stages</option>
                            {choices.stages.map(s => <option key={s} value={s}>{s}</option>)}
                        </select>
                    </div>
                    <div className="filter-group">
                        <label>Min. win probability</label>
                        <div className="slider-row">
                            <input
                                type="range"
                                name="probability_floor"
                                min="0"
                                max="100"
                                step="10"
                                value={filters.probability_floor || 0}
                                onChange={handleFilterChange}
                                className="range-slider"
                                aria-label="Minimum win probability"
                            />
                            <span className="slider-val">{filters.probability_floor ? `${filters.probability_floor}%+` : 'No minimum'}</span>
                        </div>
                    </div>
                </div>
                <div className="filter-actions">
                    <button className="clear-filters-btn" onClick={handleClearFilters}>
                        Clear filters
                    </button>
                </div>
            </section>

            {/* Estimate + hiring-need summary */}
            <section className="estimates-row">
                <div className="estimate-card hiring">
                    <div className="card-header">
                        <h3>Open hiring need</h3>
                        <span className="badge">Action needed</span>
                    </div>
                    <div className="card-body">
                        <div className="metric-val">{openHiringNeed}</div>
                        <p className="metric-desc">
                            {openHiringNeed === 0
                                ? 'Every filtered deal can be staffed from the bench.'
                                : `Roles to hire across ${dealsWithShortfall} deal${dealsWithShortfall === 1 ? '' : 's'} with a bench shortfall.`}
                        </p>
                    </div>
                </div>

                <div className="estimate-card cautious">
                    <div className="card-header">
                        <h3>Cautious estimate</h3>
                        <span className="badge">Likely deals · 70%+</span>
                    </div>
                    <div className="card-body">
                        <div className="metric-val">{funnelData.cautious_estimate}</div>
                        <p className="metric-desc">Expected headcount for deals at or above 70% win probability.</p>
                        <div className="progress-bar-container" title={`${cautiousShare}% of the full-pipeline estimate`}>
                            <div className="progress-bar fill-cautious" style={{ width: `${cautiousShare}%` }}></div>
                        </div>
                        <p className="metric-foot">{cautiousShare}% of full-pipeline demand</p>
                    </div>
                </div>

                <div className="estimate-card hopeful">
                    <div className="card-header">
                        <h3>Hopeful estimate</h3>
                        <span className="badge">Full pipeline</span>
                    </div>
                    <div className="card-body">
                        <div className="metric-val">{funnelData.hopeful_estimate}</div>
                        <p className="metric-desc">Expected headcount counting every deal currently in play.</p>
                        <div className="progress-bar-container">
                            <div className="progress-bar fill-hopeful" style={{ width: '100%' }}></div>
                        </div>
                        <p className="metric-foot">Baseline — all filtered deals</p>
                    </div>
                </div>
            </section>

            {/* Content area: Recommendations, Deals table, Benched side list */}
            <div className="funnel-content-grid">
                
                {/* Left side: Recommendations & Pipeline */}
                <div className="left-content">
                    
                    {/* Recommendations and Matches */}
                    <div className="dashboard-section-card">
                        <h3>Pipeline deals & bench matching</h3>
                        <p className="section-subtitle">Deals needing hires appear first. Each shows suggested benched matches and the staffing gap.</p>

                        {loading ? (
                            <div className="funnel-loading">Recalculating allocations…</div>
                        ) : error ? (
                            <div className="funnel-error">Error: {error}</div>
                        ) : funnelData.recommendations.length === 0 ? (
                            <div className="funnel-empty">No deals match the selected filters. Add a deal or adjust filters.</div>
                        ) : (
                            <div className="scrollable-panel">
                                <div className="recommendations-list">
                                {sortedRecommendations.map((rec) => {
                                    const isShortfall = rec.shortfall > 0;
                                    return (
                                        <div key={rec.id} className={`recommendation-item-card ${isShortfall ? 'shortfall-border' : 'staffed-border'}`}>
                                            <div className="rec-item-header">
                                                <div>
                                                    <h4>{rec.client_project}</h4>
                                                    <div className="rec-metadata">
                                                        <span><IconPin width={14} height={14} /> {rec.practice}</span>
                                                        <span><IconCalendar width={14} height={14} /> {rec.target_month}</span>
                                                        <span><IconBriefcase width={14} height={14} /> {rec.role}</span>
                                                    </div>
                                                </div>
                                                <div className="rec-header-right">
                                                    <div className="rec-badges">
                                                        <span className={`stage-pill stage-${rec.stage.toLowerCase()}`}>{rec.stage}</span>
                                                        <span className="prob-badge">{rec.probability}% win probability</span>
                                                    </div>
                                                    <div className="deal-actions">
                                                        <button className="edit-btn" onClick={() => handleEditDealClick(rec)} title="Edit deal" aria-label={`Edit ${rec.client_project}`}><IconEdit width={16} height={16} /></button>
                                                        <button className="delete-btn-icon" onClick={() => handleDeleteDeal(rec.id)} title="Delete deal" aria-label={`Delete ${rec.client_project}`}><IconTrash width={16} height={16} /></button>
                                                    </div>
                                                </div>
                                            </div>

                                            <div className="rec-item-body">
                                                <div className="metric-pair-row">
                                                    <div><strong>Headcount needed</strong> {rec.quantity}</div>
                                                    <div><strong>Expected demand</strong> {rec.expected_demand}</div>
                                                    {isShortfall && <div className="rec-shortfall"><strong>Shortfall</strong> {rec.shortfall}</div>}
                                                </div>

                                                <div className="matches-box">
                                                    <strong>Suggested matches from bench</strong>
                                                    {rec.suggested_matches.length > 0 ? (
                                                        <ul className="suggested-names-list">
                                                            {rec.suggested_matches.map((name) => (
                                                                <li key={name}><IconUser width={14} height={14} /> {name}</li>
                                                            ))}
                                                        </ul>
                                                    ) : (
                                                        <p className="no-matches-text">No benched talent matched this role.</p>
                                                    )}
                                                </div>

                                                <div className={`recommendation-callout ${isShortfall ? 'warn-callout' : 'success-callout'}`}>
                                                    <span className="rec-icon">{isShortfall ? <IconAlert width={16} height={16} /> : <IconCheck width={16} height={16} />}</span>
                                                    <p>{rec.recommendation}</p>
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })}
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Right side: Available Benched Resources Reference */}
                <div className="right-content">
                    <div className="dashboard-section-card benched-registry-card">
                        <h3>Benched registry</h3>
                        <p className="section-subtitle">Active employees without current billing allocations.</p>
                        
                        <div className="scrollable-panel">
                            <div className="benched-list-roles">
                            {Object.entries(funnelData.benched).map(([roleName, list]) => (
                                <div key={roleName} className="role-benched-section">
                                    <div className="role-benched-header">
                                        <h4>{roleName}</h4>
                                        <span className="benched-count-badge">{list.length} benched</span>
                                    </div>
                                    <ul className="benched-person-list">
                                        {list.length === 0 ? (
                                            <li className="no-person">No benched resources for this role.</li>
                                        ) : (
                                            list.map((p) => (
                                                <li key={p.emp_id} className="benched-person-item">
                                                    <div className="person-name">
                                                        {p.resource_name}
                                                        {p.grade && <span className="person-grade-badge">{p.grade}</span>}
                                                    </div>
                                                    <div className="person-details">
                                                        <span><IconPin width={13} height={13} /> {p.practice}</span>
                                                        <span><IconBriefcase width={13} height={13} /> {p.job_title}</span>
                                                        {p.location_name && <span>📍 {p.location_name}</span>}
                                                        {p.employee_type && <span>👤 {p.employee_type}</span>}
                                                    </div>
                                                </li>
                                            ))
                                        )}
                                    </ul>
                                </div>
                            ))}
                            </div>
                        </div>
                    </div>
                </div>

            </div>

            {/* Add Deal Modal */}
            {showAddModal && (
                <div className="modal-overlay">
                    <div className="modal-content glass-card">
                        <h3>Add Pipeline Deal</h3>
                        <form onSubmit={handleAddDealSubmit}>
                            <div className="form-group">
                                <label>Client / Project Name</label>
                                <input 
                                    type="text" 
                                    required 
                                    value={newDeal.client_project} 
                                    onChange={e => setNewDeal(prev => ({ ...prev, client_project: e.target.value }))}
                                    placeholder="e.g. ClientCo - API Setup"
                                />
                            </div>
                            <div className="form-row">
                                <div className="form-group">
                                    <label>Stage</label>
                                    <select value={newDeal.stage} onChange={e => setNewDeal(prev => ({ ...prev, stage: e.target.value }))}>
                                        <option value="Prospecting">Prospecting</option>
                                        <option value="Proposal">Proposal</option>
                                        <option value="Won">Won (Committed)</option>
                                    </select>
                                </div>
                                <div className="form-group">
                                    <label>Probability (%)</label>
                                    <input 
                                        type="number" 
                                        required 
                                        min="0" 
                                        max="100" 
                                        value={newDeal.probability} 
                                        onChange={e => setNewDeal(prev => ({ ...prev, probability: parseFloat(e.target.value) }))}
                                    />
                                </div>
                            </div>
                            <div className="form-row">
                                <div className="form-group">
                                    <label>Role Required</label>
                                    <select value={newDeal.role} onChange={e => setNewDeal(prev => ({ ...prev, role: e.target.value }))}>
                                        <option value="Data Engineer">Data Engineer</option>
                                        <option value="BI">BI</option>
                                        <option value="DBA">DBA</option>
                                        <option value="Other">Other</option>
                                    </select>
                                </div>
                                <div className="form-group">
                                    <label>Quantity</label>
                                    <input 
                                        type="number" 
                                        required 
                                        min="1" 
                                        value={newDeal.quantity} 
                                        onChange={e => setNewDeal(prev => ({ ...prev, quantity: parseInt(e.target.value) }))}
                                    />
                                </div>
                            </div>
                            <div className="form-row">
                                <div className="form-group">
                                    <label>Target Month (YYYY-MM)</label>
                                    <input 
                                        type="text" 
                                        required 
                                        pattern="\d{4}-\d{2}"
                                        placeholder="e.g. 2026-07"
                                        value={newDeal.target_month} 
                                        onChange={e => setNewDeal(prev => ({ ...prev, target_month: e.target.value }))}
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Practice / Team</label>
                                    <select value={newDeal.practice} onChange={e => setNewDeal(prev => ({ ...prev, practice: e.target.value }))}>
                                        <option value="Analytics & Insights">Analytics & Insights</option>
                                        <option value="Software - TSF">Software - TSF</option>
                                    </select>
                                </div>
                            </div>
                            <div className="form-group">
                                <label>Notes</label>
                                <textarea 
                                    rows="3" 
                                    value={newDeal.notes} 
                                    onChange={e => setNewDeal(prev => ({ ...prev, notes: e.target.value }))}
                                    placeholder="Add any extra deal info..."
                                />
                            </div>
                            <div className="modal-actions">
                                <button type="button" className="btn-cancel" onClick={() => setShowAddModal(false)}>Cancel</button>
                                <button type="submit" className="btn-save">Save Deal</button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Edit Deal Modal */}
            {showEditModal && editingDeal && (
                <div className="modal-overlay">
                    <div className="modal-content glass-card">
                        <h3>Edit Pipeline Deal</h3>
                        <form onSubmit={handleEditDealSubmit}>
                            <div className="form-group">
                                <label>Client / Project Name</label>
                                <input 
                                    type="text" 
                                    required 
                                    value={editingDeal.client_project} 
                                    onChange={e => setEditingDeal(prev => ({ ...prev, client_project: e.target.value }))}
                                />
                            </div>
                            <div className="form-row">
                                <div className="form-group">
                                    <label>Stage</label>
                                    <select value={editingDeal.stage} onChange={e => setEditingDeal(prev => ({ ...prev, stage: e.target.value }))}>
                                        <option value="Prospecting">Prospecting</option>
                                        <option value="Proposal">Proposal</option>
                                        <option value="Won">Won (Committed)</option>
                                    </select>
                                </div>
                                <div className="form-group">
                                    <label>Probability (%)</label>
                                    <input 
                                        type="number" 
                                        required 
                                        min="0" 
                                        max="100" 
                                        value={editingDeal.probability} 
                                        onChange={e => setEditingDeal(prev => ({ ...prev, probability: parseFloat(e.target.value) }))}
                                    />
                                </div>
                            </div>
                            <div className="form-row">
                                <div className="form-group">
                                    <label>Role Required</label>
                                    <select value={editingDeal.role} onChange={e => setEditingDeal(prev => ({ ...prev, role: e.target.value }))}>
                                        <option value="Data Engineer">Data Engineer</option>
                                        <option value="BI">BI</option>
                                        <option value="DBA">DBA</option>
                                        <option value="Other">Other</option>
                                    </select>
                                </div>
                                <div className="form-group">
                                    <label>Quantity</label>
                                    <input 
                                        type="number" 
                                        required 
                                        min="1" 
                                        value={editingDeal.quantity} 
                                        onChange={e => setEditingDeal(prev => ({ ...prev, quantity: parseInt(e.target.value) }))}
                                    />
                                </div>
                            </div>
                            <div className="form-row">
                                <div className="form-group">
                                    <label>Target Month (YYYY-MM)</label>
                                    <input 
                                        type="text" 
                                        required 
                                        pattern="\d{4}-\d{2}"
                                        value={editingDeal.target_month} 
                                        onChange={e => setEditingDeal(prev => ({ ...prev, target_month: e.target.value }))}
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Practice / Team</label>
                                    <select value={editingDeal.practice} onChange={e => setEditingDeal(prev => ({ ...prev, practice: e.target.value }))}>
                                        <option value="Analytics & Insights">Analytics & Insights</option>
                                        <option value="Software - TSF">Software - TSF</option>
                                    </select>
                                </div>
                            </div>
                            <div className="form-group">
                                <label>Notes</label>
                                <textarea 
                                    rows="3" 
                                    value={editingDeal.notes || ''} 
                                    onChange={e => setEditingDeal(prev => ({ ...prev, notes: e.target.value }))}
                                />
                            </div>
                            <div className="modal-actions">
                                <button type="button" className="btn-cancel" onClick={() => { setShowEditModal(false); setEditingDeal(null); }}>Cancel</button>
                                <button type="submit" className="btn-save">Update Deal</button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

        </div>
    );
}
