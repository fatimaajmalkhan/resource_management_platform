import React, { useState, useEffect } from 'react';
import { IconTrash, IconPlus, IconHistory, IconTrendUp } from './icons';
import AnimatedAreaChart, { useTooltip } from './charts/AnimatedAreaChart';
import '../overview.css';

export default function ResourceMaster() {
    const [resources, setResources] = useState([]);
    const [resourceLoading, setResourceLoading] = useState(false);
    const [resourceError, setResourceError] = useState(null);
    const [showAddResourceModal, setShowAddResourceModal] = useState(false);
    const [historyResource, setHistoryResource] = useState(null);
    const [resourceHistory, setResourceHistory] = useState([]);
    const [historyLoading, setHistoryLoading] = useState(false);
    const [showForecast, setShowForecast] = useState(false);
    const [tsData, setTsData] = useState(null);
    const [forecastData, setForecastData] = useState(null);
    const [hiringData, setHiringData] = useState(null);
    const tooltip = useTooltip();
    const [filters, setFilters] = useState({
        search: '',
        practice: '',
        status: ''
    });
    const [choices, setChoices] = useState({
        stages: ["Prospecting", "Proposal", "Won"],
        roles: ["Data Engineer", "BI", "DBA", "Other"],
        practices: ["Analytics & Insights", "Software - TSF"],
        months: ["2026-07", "2026-08", "2026-09"]
    });
    const [resourceForm, setResourceForm] = useState({
        emp_id: '',
        resource_name: '',
        job_title: '',
        line_manager: '',
        line_manager_id: '',
        practice: 'Analytics & Insights',
        sub_practice: '',
        grade: '',
        employee_type: '',
        project_client_squad: '',
        billable_flag: false,
        billable_pct: '',
        daily_rate_usd: '',
        days_billed: '',
        monthly_billing_usd: '',
        engagement_start: '',
        release_date: '',
        resource_status: '',
        hire_date: '',
        hrbp: '',
        department: '',
        location_name: '',
        email_address: '',
        comments: ''
    });

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

    const fetchResources = async () => {
        setResourceLoading(true);
        setResourceError(null);
        try {
            const res = await fetch('/api/resources');
            if (!res.ok) throw new Error('Failed to load resources');
            const data = await res.json();
            setResources(data);
        } catch (err) {
            setResourceError(err.message);
            console.error('Resource load failed', err);
        } finally {
            setResourceLoading(false);
        }
    };

    useEffect(() => {
        fetchChoices();
        fetchResources();
    }, []);

    // Forecast is additive, not core -- fetched independently so a broken/slow
    // forecast call never affects the resources table.
    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const res = await fetch('/api/overview/timeseries');
                if (!res.ok) throw new Error('timeseries unavailable');
                const json = await res.json();
                if (!cancelled) setTsData(json);
            } catch (err) {
                console.warn('Resource forecast timeseries failed to load:', err.message);
            }
        })();
        return () => { cancelled = true; };
    }, []);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const res = await fetch('/api/overview/forecast?months=3');
                if (!res.ok) throw new Error('forecast unavailable');
                const json = await res.json();
                if (!cancelled) setForecastData(json);
            } catch (err) {
                console.warn('Resource forecast failed to load:', err.message);
            }
        })();
        return () => { cancelled = true; };
    }, []);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const res = await fetch('/api/hiring-forecast?months=3');
                if (!res.ok) throw new Error('hiring forecast unavailable');
                const json = await res.json();
                if (!cancelled) setHiringData(json);
            } catch (err) {
                console.warn('Hiring forecast failed to load:', err.message);
            }
        })();
        return () => { cancelled = true; };
    }, []);

    const statuses = [...new Set(resources.map(r => r.resource_status).filter(Boolean))].sort();

    const filteredResources = resources.filter(r => {
        if (filters.practice && r.practice !== filters.practice) return false;
        if (filters.status && r.resource_status !== filters.status) return false;
        if (filters.search) {
            const q = filters.search.toLowerCase();
            const haystack = `${r.resource_name || ''} ${r.job_title || ''} ${r.emp_id || ''}`.toLowerCase();
            if (!haystack.includes(q)) return false;
        }
        return true;
    });

    const handleFilterChange = (e) => {
        const { name, value } = e.target;
        setFilters(prev => ({ ...prev, [name]: value }));
    };

    const handleClearFilters = () => {
        setFilters({ search: '', practice: '', status: '' });
    };

    const resetResourceForm = () => {
        setResourceForm({
            emp_id: '',
            resource_name: '',
            job_title: '',
            line_manager: '',
            line_manager_id: '',
            practice: 'Analytics & Insights',
            sub_practice: '',
            grade: '',
            employee_type: '',
            project_client_squad: '',
            billable_flag: false,
            billable_pct: '',
            daily_rate_usd: '',
            days_billed: '',
            monthly_billing_usd: '',
            engagement_start: '',
            release_date: '',
            resource_status: '',
            hire_date: '',
            hrbp: '',
            department: '',
            location_name: '',
            email_address: '',
            comments: ''
        });
    };

    const handleAddResourceSubmit = async (e) => {
        e.preventDefault();
        try {
            const payload = {
                ...resourceForm,
                emp_id: parseInt(resourceForm.emp_id, 10),
                billable_flag: Boolean(resourceForm.billable_flag) || null,
                billable_pct: resourceForm.billable_pct !== '' ? parseFloat(resourceForm.billable_pct) : null,
                daily_rate_usd: resourceForm.daily_rate_usd !== '' ? parseFloat(resourceForm.daily_rate_usd) : null,
                days_billed: resourceForm.days_billed !== '' ? parseFloat(resourceForm.days_billed) : null,
                monthly_billing_usd: resourceForm.monthly_billing_usd !== '' ? parseFloat(resourceForm.monthly_billing_usd) : null,
                line_manager_id: resourceForm.line_manager_id ? parseInt(resourceForm.line_manager_id, 10) : null,
                engagement_start: resourceForm.engagement_start || null,
                release_date: resourceForm.release_date || null,
                hire_date: resourceForm.hire_date || null,
            };

            const res = await fetch('/api/resources', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                const data = await res.json();
                setShowAddResourceModal(false);
                resetResourceForm();
                fetchResources();
                fetchChoices();
                if (data.excel_synced === false) {
                    alert('Resource saved, but the Excel file couldn\'t be updated right away (it may be open elsewhere). It will sync automatically within about 20 seconds.');
                }
            } else {
                const errorData = await res.json();
                alert(errorData.detail || 'Error adding resource');
            }
        } catch (err) {
            console.error('Add resource failed', err);
            alert('Error adding resource');
        }
    };

    const formatTimestamp = (iso) => {
        if (!iso) return '';
        const d = new Date(iso);
        return d.toLocaleString();
    };

    const handleViewHistory = async (resource) => {
        setHistoryResource(resource);
        setHistoryLoading(true);
        try {
            const res = await fetch(`/api/resources/${resource.emp_id}/history`);
            if (res.ok) setResourceHistory(await res.json());
        } catch (err) {
            console.error('Failed to fetch resource history', err);
        } finally {
            setHistoryLoading(false);
        }
    };

    const handleCloseHistory = () => {
        setHistoryResource(null);
        setResourceHistory([]);
    };

    const handleDeleteResource = async (empId) => {
        if (!confirm('Are you sure you want to delete this resource?')) return;
        try {
            const res = await fetch(`/api/resources/${empId}`, {
                method: 'DELETE'
            });
            if (res.ok) {
                fetchResources();
                fetchChoices();
            } else {
                const errorData = await res.json();
                alert(errorData.detail || 'Error deleting resource');
            }
        } catch (err) {
            console.error('Delete resource failed', err);
            alert('Error deleting resource');
        }
    };

    return (
        <div className="funnel-container">
            {tooltip.portal}
            <header className="funnel-header">
                <div className="header-info">
                    <h2>Resource Master</h2>
                    <p>View and manage employee resource records across all practices.</p>
                </div>
                <div className="header-actions">
                    <button
                        className={`forecast-toggle-btn ${showForecast ? 'active' : ''}`}
                        onClick={() => setShowForecast(prev => !prev)}
                    >
                        <IconTrendUp width={16} height={16} /> {showForecast ? 'Hide forecast' : 'Forecast'}
                    </button>
                    <button className="add-resource-btn" onClick={() => setShowAddResourceModal(true)}>
                        <IconPlus width={16} height={16} /> Add resource
                    </button>
                </div>
            </header>

            {showForecast && (
                <section className="glass-card" style={{ marginBottom: '24px' }}>
                    <h3 className="card-title">Workforce Forecast</h3>
                    <p className="card-subtitle">
                        Solid lines are actuals; dashed lines and shaded bands are a 3-month history-based forecast
                        projection with an approximate 80% range — directional, not a committed plan.
                        Reflects the entire workforce; it is not filtered by the practice/status filters below.
                    </p>
                    {tsData ? (
                        <AnimatedAreaChart
                            data={tsData}
                            forecast={forecastData?.forecast}
                            forecastMeta={forecastData?.metrics_meta}
                            tooltip={tooltip}
                        />
                    ) : (
                        <div className="funnel-loading">Loading forecast...</div>
                    )}

                    <h3 className="card-title" style={{ marginTop: '28px' }}>Recommended Hires</h3>
                    {hiringData ? (
                        <>
                            <p className="card-subtitle">{hiringData.pipeline_driven.data_note}</p>
                            <p className="card-subtitle">{hiringData.trend_driven.disclaimer}</p>
                            <div style={{ overflowX: 'auto' }}>
                                <table className="modern-table">
                                    <thead>
                                        <tr>
                                            <th>Month</th>
                                            <th>Pipeline (cautious / hopeful)</th>
                                            <th>Trend</th>
                                            <th>Recommended total</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {hiringData.months.map((month) => {
                                            const p = hiringData.pipeline_driven.by_month.find(m => m.month === month);
                                            const t = hiringData.trend_driven.by_month.find(m => m.month === month);
                                            const total = hiringData.recommended_total_by_month.find(m => m.month === month);
                                            return (
                                                <tr key={month}>
                                                    <td style={{ fontWeight: 500, color: '#fff' }}>{month}</td>
                                                    <td>
                                                        {p?.has_data
                                                            ? `${p.cautious} / ${p.hopeful}`
                                                            : <span style={{ color: 'var(--text-muted)' }}>No pipeline data</span>}
                                                        {p?.by_role?.length > 0 && (
                                                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '4px' }}>
                                                                {p.by_role.map(r => (
                                                                    <span key={r.role} className="pill" style={{ backgroundColor: 'rgba(251, 191, 36, 0.15)' }}>
                                                                        {r.role}: {r.shortfall}
                                                                    </span>
                                                                ))}
                                                            </div>
                                                        )}
                                                    </td>
                                                    <td>{t?.recommended_hires ?? '-'}</td>
                                                    <td>
                                                        {total ? `${total.conservative}–${total.upper_bound}` : '-'}
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        </>
                    ) : (
                        <div className="funnel-loading">Loading hiring forecast...</div>
                    )}
                </section>
            )}

            <section className="funnel-filters-card">
                <div className="filters-grid">
                    <div className="filter-group">
                        <label>Search</label>
                        <input
                            type="text"
                            name="search"
                            placeholder="Name, title, or emp ID..."
                            value={filters.search}
                            onChange={handleFilterChange}
                        />
                    </div>
                    <div className="filter-group">
                        <label>Practice / Team</label>
                        <select name="practice" value={filters.practice} onChange={handleFilterChange}>
                            <option value="">All Practices</option>
                            {choices.practices.map(p => <option key={p} value={p}>{p}</option>)}
                        </select>
                    </div>
                    <div className="filter-group">
                        <label>Status</label>
                        <select name="status" value={filters.status} onChange={handleFilterChange}>
                            <option value="">All Statuses</option>
                            {statuses.map(s => <option key={s} value={s}>{s}</option>)}
                        </select>
                    </div>
                </div>
                <div className="filter-actions">
                    <button className="clear-filters-btn" onClick={handleClearFilters}>
                        Clear Filters
                    </button>
                </div>
            </section>

            <div className="dashboard-section-card resource-management-card">
                {resourceLoading ? (
                    <div className="funnel-loading">Loading resources...</div>
                ) : resourceError ? (
                    <div className="funnel-error">Error: {resourceError}</div>
                ) : (
                    <div className="table-responsive table-scroll">
                        <table className="resources-table">
                            <thead>
                                <tr>
                                    <th>Emp ID</th>
                                    <th>Name</th>
                                    <th>Practice</th>
                                    <th>Job Title</th>
                                    <th>Status</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filteredResources.length === 0 ? (
                                    <tr>
                                        <td colSpan="6" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '20px' }}>
                                            {resources.length === 0
                                                ? 'No resources currently available. Add a resource to begin.'
                                                : 'No resources match the selected filters.'}
                                        </td>
                                    </tr>
                                ) : (
                                    filteredResources.map((resource) => (
                                        <tr key={resource.emp_id}>
                                            <td>{resource.emp_id}</td>
                                            <td>{resource.resource_name}</td>
                                            <td>{resource.practice || '-'}</td>
                                            <td>{resource.job_title || '-'}</td>
                                            <td>{resource.resource_status || '-'}</td>
                                            <td>
                                                <button className="history-resource-btn" onClick={() => handleViewHistory(resource)} title="View history" aria-label={`View history for ${resource.resource_name}`}>
                                                    <IconHistory width={15} height={15} />
                                                    <span>History</span>
                                                </button>
                                                <button className="delete-resource-btn" onClick={() => handleDeleteResource(resource.emp_id)} title="Delete resource" aria-label={`Delete ${resource.resource_name}`}>
                                                    <IconTrash width={15} height={15} />
                                                    <span>Delete</span>
                                                </button>
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {showAddResourceModal && (
                <div className="modal-overlay">
                    <div className="modal-content glass-card resource-modal">
                        <h3>Add New Resource</h3>
                        <form onSubmit={handleAddResourceSubmit}>
                            <div className="form-row">
                                <div className="form-group">
                                    <label>Emp ID</label>
                                    <input
                                        type="number"
                                        required
                                        value={resourceForm.emp_id}
                                        onChange={e => setResourceForm(prev => ({ ...prev, emp_id: e.target.value }))}
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Resource Name</label>
                                    <input
                                        type="text"
                                        required
                                        value={resourceForm.resource_name}
                                        onChange={e => setResourceForm(prev => ({ ...prev, resource_name: e.target.value }))}
                                    />
                                </div>
                            </div>
                            <div className="form-row">
                                <div className="form-group">
                                    <label>Job Title</label>
                                    <input
                                        type="text"
                                        value={resourceForm.job_title}
                                        onChange={e => setResourceForm(prev => ({ ...prev, job_title: e.target.value }))}
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Practice</label>
                                    <select
                                        value={resourceForm.practice}
                                        onChange={e => setResourceForm(prev => ({ ...prev, practice: e.target.value }))}
                                    >
                                        {choices.practices.map(pr => <option key={pr} value={pr}>{pr}</option>)}
                                        <option value="">Other</option>
                                    </select>
                                </div>
                            </div>
                            <div className="form-row">
                                <div className="form-group">
                                    <label>Sub Practice</label>
                                    <input
                                        type="text"
                                        value={resourceForm.sub_practice}
                                        onChange={e => setResourceForm(prev => ({ ...prev, sub_practice: e.target.value }))}
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Employee Type</label>
                                    <input
                                        type="text"
                                        value={resourceForm.employee_type}
                                        onChange={e => setResourceForm(prev => ({ ...prev, employee_type: e.target.value }))}
                                    />
                                </div>
                            </div>
                            <div className="form-row">
                                <div className="form-group checkbox-group">
                                    <label>
                                        <input
                                            type="checkbox"
                                            checked={Boolean(resourceForm.billable_flag)}
                                            onChange={e => setResourceForm(prev => ({ ...prev, billable_flag: e.target.checked }))}
                                        />
                                        Billable
                                    </label>
                                </div>
                                <div className="form-group">
                                    <label>Billable %</label>
                                    <input
                                        type="number"
                                        min="0"
                                        max="100"
                                        value={resourceForm.billable_pct}
                                        onChange={e => setResourceForm(prev => ({ ...prev, billable_pct: e.target.value }))}
                                    />
                                </div>
                            </div>
                            <div className="form-row">
                                <div className="form-group">
                                    <label>Daily Rate USD</label>
                                    <input
                                        type="number"
                                        min="0"
                                        step="0.01"
                                        value={resourceForm.daily_rate_usd}
                                        onChange={e => setResourceForm(prev => ({ ...prev, daily_rate_usd: e.target.value }))}
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Days Billed</label>
                                    <input
                                        type="number"
                                        min="0"
                                        value={resourceForm.days_billed}
                                        onChange={e => setResourceForm(prev => ({ ...prev, days_billed: e.target.value }))}
                                    />
                                </div>
                            </div>
                            <div className="form-row">
                                <div className="form-group">
                                    <label>Monthly Billing USD</label>
                                    <input
                                        type="number"
                                        min="0"
                                        step="0.01"
                                        value={resourceForm.monthly_billing_usd}
                                        onChange={e => setResourceForm(prev => ({ ...prev, monthly_billing_usd: e.target.value }))}
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Release Date</label>
                                    <input
                                        type="date"
                                        value={resourceForm.release_date}
                                        onChange={e => setResourceForm(prev => ({ ...prev, release_date: e.target.value }))}
                                    />
                                </div>
                            </div>
                            <div className="form-row">
                                <div className="form-group">
                                    <label>HRBP</label>
                                    <input
                                        type="text"
                                        value={resourceForm.hrbp}
                                        onChange={e => setResourceForm(prev => ({ ...prev, hrbp: e.target.value }))}
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Department</label>
                                    <input
                                        type="text"
                                        value={resourceForm.department}
                                        onChange={e => setResourceForm(prev => ({ ...prev, department: e.target.value }))}
                                    />
                                </div>
                            </div>
                            <div className="form-group">
                                <label>Location Name</label>
                                <input
                                    type="text"
                                    value={resourceForm.location_name}
                                    onChange={e => setResourceForm(prev => ({ ...prev, location_name: e.target.value }))}
                                />
                            </div>
                            <div className="form-row">
                                <div className="form-group">
                                    <label>Project / Client / Squad</label>
                                    <input
                                        type="text"
                                        value={resourceForm.project_client_squad}
                                        onChange={e => setResourceForm(prev => ({ ...prev, project_client_squad: e.target.value }))}
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Resource Status</label>
                                    <input
                                        type="text"
                                        value={resourceForm.resource_status}
                                        onChange={e => setResourceForm(prev => ({ ...prev, resource_status: e.target.value }))}
                                    />
                                </div>
                            </div>
                            <div className="form-row">
                                <div className="form-group">
                                    <label>Grade</label>
                                    <input
                                        type="text"
                                        value={resourceForm.grade}
                                        onChange={e => setResourceForm(prev => ({ ...prev, grade: e.target.value }))}
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Email Address</label>
                                    <input
                                        type="email"
                                        value={resourceForm.email_address}
                                        onChange={e => setResourceForm(prev => ({ ...prev, email_address: e.target.value }))}
                                    />
                                </div>
                            </div>
                            <div className="form-row">
                                <div className="form-group">
                                    <label>Line Manager</label>
                                    <input
                                        type="text"
                                        value={resourceForm.line_manager}
                                        onChange={e => setResourceForm(prev => ({ ...prev, line_manager: e.target.value }))}
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Line Manager ID</label>
                                    <input
                                        type="number"
                                        value={resourceForm.line_manager_id}
                                        onChange={e => setResourceForm(prev => ({ ...prev, line_manager_id: e.target.value }))}
                                    />
                                </div>
                            </div>
                            <div className="form-row">
                                <div className="form-group">
                                    <label>Hire Date</label>
                                    <input
                                        type="date"
                                        value={resourceForm.hire_date}
                                        onChange={e => setResourceForm(prev => ({ ...prev, hire_date: e.target.value }))}
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Engagement Start</label>
                                    <input
                                        type="date"
                                        value={resourceForm.engagement_start}
                                        onChange={e => setResourceForm(prev => ({ ...prev, engagement_start: e.target.value }))}
                                    />
                                </div>
                            </div>
                            <div className="form-group">
                                <label>Notes</label>
                                <textarea
                                    rows="3"
                                    value={resourceForm.comments}
                                    onChange={e => setResourceForm(prev => ({ ...prev, comments: e.target.value }))}
                                />
                            </div>
                            <div className="modal-actions">
                                <button type="button" className="btn-cancel" onClick={() => setShowAddResourceModal(false)}>Cancel</button>
                                <button type="submit" className="btn-save">Save Resource</button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {historyResource && (
                <div className="modal-overlay">
                    <div className="modal-content glass-card resource-history-modal">
                        <h3>History — {historyResource.resource_name}</h3>
                        <p className="section-subtitle">Every change recorded for this resource, from any source.</p>

                        {historyLoading ? (
                            <div className="funnel-loading">Loading history...</div>
                        ) : resourceHistory.length === 0 ? (
                            <div className="funnel-empty">No changes recorded yet for this resource.</div>
                        ) : (
                            <div className="history-timeline">
                                {resourceHistory.map(h => (
                                    <div key={h.history_id} className="history-entry">
                                        <div className="history-entry-time">{formatTimestamp(h.changed_at)}</div>
                                        <div className="history-entry-body">
                                            {h.field_name === 'record' ? (
                                                <span className={`history-action action-${h.new_value}`}>{h.new_value}</span>
                                            ) : (
                                                <span className="history-detail">
                                                    {h.field_name}: <em>{h.old_value}</em> → <em>{h.new_value}</em>
                                                </span>
                                            )}
                                            <span className="history-source">via {h.source}</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}

                        <div className="modal-actions">
                            <button type="button" className="btn-cancel" onClick={handleCloseHistory}>Close</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
