import React, { useState, useEffect, useCallback } from 'react';
import './App.css';

const API_URL = process.env.REACT_APP_BACKEND_URL;

function App() {
  const [dashboardData, setDashboardData] = useState(null);
  const [leads, setLeads] = useState([]);
  const [callHistory, setCallHistory] = useState([]);
  const [configStatus, setConfigStatus] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState('');
  const [notification, setNotification] = useState(null);

  // New lead form
  const [newLead, setNewLead] = useState({ name: '', phone: '', language: '' });
  const [showAddLead, setShowAddLead] = useState(false);
  const [editingLeadId, setEditingLeadId] = useState(null);
  const [editLead, setEditLead] = useState({ name: '', phone: '', language: '' });

  const showNotification = useCallback((message, type = 'success') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 4000);
  }, []);

  const fetchDashboard = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/stats/dashboard`);
      const data = await res.json();
      setDashboardData(data);
    } catch (err) {
      console.error('Failed to fetch dashboard:', err);
    }
  }, []);

  const fetchLeads = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/leads`);
      const data = await res.json();
      setLeads(data);
    } catch (err) {
      console.error('Failed to fetch leads:', err);
    }
  }, []);

  const fetchCallHistory = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/calls/history`);
      const data = await res.json();
      setCallHistory(data);
    } catch (err) {
      console.error('Failed to fetch call history:', err);
    }
  }, []);

  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/config/status`);
      const data = await res.json();
      setConfigStatus(data);
    } catch (err) {
      console.error('Failed to fetch config:', err);
    }
  }, []);

  useEffect(() => {
    const loadAll = async () => {
      setLoading(true);
      await Promise.all([fetchDashboard(), fetchLeads(), fetchCallHistory(), fetchConfig()]);
      setLoading(false);
    };
    loadAll();
    const interval = setInterval(fetchDashboard, 30000);
    return () => clearInterval(interval);
  }, [fetchDashboard, fetchLeads, fetchCallHistory, fetchConfig]);

  const controlScheduler = async (action) => {
    setActionLoading(`scheduler-${action}`);
    try {
      const res = await fetch(`${API_URL}/api/scheduler/control`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action })
      });
      const data = await res.json();
      showNotification(data.message);
      await fetchDashboard();
    } catch (err) {
      showNotification('Failed to control scheduler', 'error');
    }
    setActionLoading('');
  };

  const initiateCall = async (leadId) => {
    setActionLoading(`call-${leadId}`);
    try {
      const res = await fetch(`${API_URL}/api/calls/initiate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lead_id: leadId })
      });
      const data = await res.json();
      showNotification(data.message || 'Call initiated');
      await fetchDashboard();
    } catch (err) {
      showNotification('Failed to initiate call', 'error');
    }
    setActionLoading('');
  };

  const addLead = async (e) => {
    e.preventDefault();
    setActionLoading('add-lead');
    try {
      const res = await fetch(`${API_URL}/api/leads`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: crypto.randomUUID(),
          name: newLead.name,
          phone: newLead.phone,
          language: newLead.language,
          status: '',
          call_attempts: 0,
          whatsapp_sent: 'No'
        })
      });
      if (res.ok) {
        showNotification('Lead added successfully');
        setNewLead({ name: '', phone: '', language: '' });
        setShowAddLead(false);
        await fetchLeads();
        await fetchDashboard();
      }
    } catch (err) {
      showNotification('Failed to add lead', 'error');
    }
    setActionLoading('');
  };

  const syncSheets = async () => {
    setActionLoading('sync');
    try {
      const res = await fetch(`${API_URL}/api/leads/sync-sheets`, { method: 'POST' });
      const data = await res.json();
      showNotification(data.message);
      await fetchLeads();
      await fetchDashboard();
    } catch (err) {
      showNotification('Failed to sync Google Sheets', 'error');
    }
    setActionLoading('');
  };

  const startEditLead = (lead) => {
    setEditingLeadId(lead.id);
    setEditLead({ name: lead.name || '', phone: lead.phone || '', language: lead.language || '' });
  };

  const cancelEditLead = () => {
    setEditingLeadId(null);
    setEditLead({ name: '', phone: '', language: '' });
  };

  const saveEditLead = async () => {
    if (!editingLeadId) return;
    setActionLoading(`update-${editingLeadId}`);
    try {
      const res = await fetch(`${API_URL}/api/leads/${editingLeadId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editLead)
      });
      if (res.ok) {
        showNotification('Lead updated');
        cancelEditLead();
        await fetchLeads();
      } else {
        showNotification('Failed to update lead', 'error');
      }
    } catch (err) {
      showNotification('Failed to update lead', 'error');
    }
    setActionLoading('');
  };

  const deleteLead = async (leadId) => {
    setActionLoading(`delete-${leadId}`);
    try {
      const res = await fetch(`${API_URL}/api/leads/${leadId}`, { method: 'DELETE' });
      if (res.ok) {
        showNotification('Lead deleted');
        await fetchLeads();
      } else {
        showNotification('Failed to delete lead', 'error');
      }
    } catch (err) {
      showNotification('Failed to delete lead', 'error');
    }
    setActionLoading('');
  };

  const getStatusBadge = (status) => {
    const colors = {
      'Interested': 'badge-interested',
      'WhatsApp Sent': 'badge-whatsapp',
      'Not Interested': 'badge-not-interested',
      'No Answer': 'badge-no-answer',
      'Busy': 'badge-busy',
      'Failed': 'badge-failed',
      '': 'badge-new'
    };
    return colors[status] || 'badge-default';
  };

  if (loading) {
    return (
      <div className="loading-screen" data-testid="loading-screen">
        <div className="loading-pulse"></div>
        <p>Initializing system...</p>
      </div>
    );
  }

  return (
    <div className="app" data-testid="app-container">
      {notification && (
        <div className={`notification ${notification.type}`} data-testid="notification">
          {notification.message}
        </div>
      )}

      <header className="app-header" data-testid="app-header">
        <div className="header-left">
          <div className="logo-mark"></div>
          <div>
            <h1>AI Caller</h1>
            <span className="header-subtitle">Outbound calling system with WhatsApp follow-up</span>
          </div>
        </div>
        <div className="header-right">
          <div className={`system-status ${dashboardData?.scheduler?.is_running ? 'status-active' : 'status-inactive'}`} data-testid="system-status-indicator">
            <span className="status-dot"></span>
            {dashboardData?.scheduler?.is_running ? 'Scheduler Active' : 'Scheduler Inactive'}
          </div>
        </div>
      </header>

      <nav className="tab-nav" data-testid="tab-navigation">
        {['overview', 'leads', 'calls', 'config'].map(tab => (
          <button
            key={tab}
            className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
            data-testid={`tab-${tab}`}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </nav>

      <main className="main-content" data-testid="main-content">
        {activeTab === 'overview' && (
          <div className="overview-tab" data-testid="overview-tab">
            <div className="stats-grid">
              <div className="stat-card" data-testid="stat-total-leads">
                <span className="stat-label">Total Leads</span>
                <span className="stat-value">{dashboardData?.leads?.total || 0}</span>
              </div>
              <div className="stat-card accent" data-testid="stat-new-leads">
                <span className="stat-label">New (Uncalled)</span>
                <span className="stat-value">{dashboardData?.leads?.new || 0}</span>
              </div>
              <div className="stat-card success" data-testid="stat-interested">
                <span className="stat-label">Interested</span>
                <span className="stat-value">{dashboardData?.leads?.interested || 0}</span>
              </div>
              <div className="stat-card warn" data-testid="stat-not-interested">
                <span className="stat-label">Not Interested</span>
                <span className="stat-value">{dashboardData?.leads?.not_interested || 0}</span>
              </div>
              <div className="stat-card info" data-testid="stat-whatsapp-sent">
                <span className="stat-label">WhatsApp Sent</span>
                <span className="stat-value">{dashboardData?.leads?.whatsapp_sent || 0}</span>
              </div>
              <div className="stat-card" data-testid="stat-total-calls">
                <span className="stat-label">Total Calls</span>
                <span className="stat-value">{dashboardData?.calls?.total || 0}</span>
              </div>
            </div>

            <div className="section-row">
              <div className="section-card scheduler-card" data-testid="scheduler-control">
                <h3>Scheduler Control</h3>
                <div className="scheduler-info">
                  <p>Status: <strong>{dashboardData?.scheduler?.is_running ? 'Running' : 'Stopped'}</strong></p>
                  <p>Interval: <strong>{dashboardData?.scheduler?.interval_minutes || 10} min</strong></p>
                  {dashboardData?.scheduler?.last_run_at && (
                    <p>Last run: <strong>{new Date(dashboardData.scheduler.last_run_at).toLocaleString()}</strong></p>
                  )}
                </div>
                <div className="scheduler-actions">
                  <button
                    className="btn btn-primary"
                    onClick={() => controlScheduler('start')}
                    disabled={actionLoading === 'scheduler-start' || dashboardData?.scheduler?.is_running}
                    data-testid="scheduler-start-btn"
                  >
                    {actionLoading === 'scheduler-start' ? 'Starting...' : 'Start'}
                  </button>
                  <button
                    className="btn btn-danger"
                    onClick={() => controlScheduler('stop')}
                    disabled={actionLoading === 'scheduler-stop' || !dashboardData?.scheduler?.is_running}
                    data-testid="scheduler-stop-btn"
                  >
                    {actionLoading === 'scheduler-stop' ? 'Stopping...' : 'Stop'}
                  </button>
                  <button
                    className="btn btn-accent"
                    onClick={() => controlScheduler('trigger')}
                    disabled={actionLoading === 'scheduler-trigger'}
                    data-testid="scheduler-trigger-btn"
                  >
                    {actionLoading === 'scheduler-trigger' ? 'Running...' : 'Trigger Now'}
                  </button>
                </div>
              </div>

              <div className="section-card integrations-card" data-testid="integrations-status">
                <h3>Integration Status</h3>
                <div className="integration-list">
                  {dashboardData?.integrations && Object.entries(dashboardData.integrations).map(([key, val]) => (
                    <div key={key} className="integration-row">
                      <span className="integration-name">{key}</span>
                      <span className={`integration-badge ${val ? 'configured' : 'not-configured'}`}>
                        {val ? 'Ready' : 'Not Configured'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="section-card" data-testid="recent-activity">
              <h3>Recent Activity</h3>
              {dashboardData?.recent_logs?.length > 0 ? (
                <div className="activity-list">
                  {dashboardData.recent_logs.map((log, i) => (
                    <div key={i} className="activity-item">
                      <div className="activity-info">
                        <span className="activity-name">{log.lead_name || 'Unknown'}</span>
                        <span className="activity-phone">{log.lead_phone}</span>
                      </div>
                      <span className={`badge ${getStatusBadge(log.status)}`}>{log.status || 'Pending'}</span>
                      <span className="activity-time">{new Date(log.timestamp).toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="empty-state">No recent activity. Add leads and start the scheduler to begin calling.</p>
              )}
            </div>
          </div>
        )}

        {activeTab === 'leads' && (
          <div className="leads-tab" data-testid="leads-tab">
            <div className="tab-actions">
              <button className="btn btn-primary" onClick={() => setShowAddLead(!showAddLead)} data-testid="add-lead-btn">
                {showAddLead ? 'Cancel' : '+ Add Lead'}
              </button>
              <button
                className="btn btn-secondary"
                onClick={syncSheets}
                disabled={actionLoading === 'sync'}
                data-testid="sync-sheets-btn"
              >
                {actionLoading === 'sync' ? 'Syncing...' : 'Sync Google Sheets'}
              </button>
            </div>

            {showAddLead && (
              <form className="add-lead-form" onSubmit={addLead} data-testid="add-lead-form">
                <input
                  type="text"
                  placeholder="Name"
                  value={newLead.name}
                  onChange={e => setNewLead({...newLead, name: e.target.value})}
                  required
                  data-testid="lead-name-input"
                />
                <input
                  type="text"
                  placeholder="Phone (with country code, e.g. +919876543210)"
                  value={newLead.phone}
                  onChange={e => setNewLead({...newLead, phone: e.target.value})}
                  required
                  data-testid="lead-phone-input"
                />
                <select
                  value={newLead.language}
                  onChange={e => setNewLead({...newLead, language: e.target.value})}
                  data-testid="lead-language-select"
                >
                  <option value="">Preferred Language</option>
                  <option value="english">English</option>
                  <option value="telugu">Telugu</option>
                </select>
                <button type="submit" className="btn btn-primary" disabled={actionLoading === 'add-lead'} data-testid="submit-lead-btn">
                  {actionLoading === 'add-lead' ? 'Adding...' : 'Add Lead'}
                </button>
              </form>
            )}

            <div className="leads-table-wrapper" data-testid="leads-table">
              <div className="data-table">
                <div className="data-table-header">
                  <div className="data-table-row">
                    <div className="data-table-th">Name</div>
                    <div className="data-table-th">Phone</div>
                    <div className="data-table-th">Status</div>
                    <div className="data-table-th">Attempts</div>
                    <div className="data-table-th">Language</div>
                    <div className="data-table-th">WhatsApp</div>
                    <div className="data-table-th">Last Called</div>
                    <div className="data-table-th">Actions</div>
                  </div>
                </div>
                <div className="data-table-body">
                  {leads.length > 0 ? leads.map((lead, i) => (
                    <div key={lead.id || i} className="data-table-row">
                      <div className="data-table-td">
                        {editingLeadId === lead.id ? (
                          <input
                            type="text"
                            value={editLead.name}
                            onChange={e => setEditLead({ ...editLead, name: e.target.value })}
                            data-testid={`edit-name-${lead.id}`}
                          />
                        ) : lead.name}
                      </div>
                      <div className="data-table-td mono">
                        {editingLeadId === lead.id ? (
                          <input
                            type="text"
                            value={editLead.phone}
                            onChange={e => setEditLead({ ...editLead, phone: e.target.value })}
                            data-testid={`edit-phone-${lead.id}`}
                          />
                        ) : lead.phone}
                      </div>
                      <div className="data-table-td"><span className={`badge ${getStatusBadge(lead.status)}`}>{lead.status || 'New'}</span></div>
                      <div className="data-table-td">{lead.call_attempts || 0}</div>
                      <div className="data-table-td">
                        {editingLeadId === lead.id ? (
                          <select
                            value={editLead.language}
                            onChange={e => setEditLead({ ...editLead, language: e.target.value })}
                            data-testid={`edit-language-${lead.id}`}
                          >
                            <option value="">Preferred Language</option>
                            <option value="english">English</option>
                            <option value="telugu">Telugu</option>
                          </select>
                        ) : (lead.language || '-')}
                      </div>
                      <div className="data-table-td">{lead.whatsapp_sent || 'No'}</div>
                      <div className="data-table-td">{lead.last_called_at ? new Date(lead.last_called_at).toLocaleString() : '-'}</div>
                      <div className="data-table-td">
                        {editingLeadId === lead.id ? (
                          <>
                            <button
                              className="btn btn-sm btn-primary"
                              onClick={saveEditLead}
                              disabled={actionLoading === `update-${lead.id}`}
                              data-testid={`save-lead-${lead.id}`}
                            >
                              {actionLoading === `update-${lead.id}` ? '...' : 'Save'}
                            </button>
                            <button
                              className="btn btn-sm btn-secondary"
                              onClick={cancelEditLead}
                              data-testid={`cancel-lead-${lead.id}`}
                              style={{ marginLeft: 8 }}
                            >
                              Cancel
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              className="btn btn-sm btn-primary"
                              onClick={() => initiateCall(lead.id)}
                              disabled={actionLoading === `call-${lead.id}` || lead.status === 'Not Interested'}
                              data-testid={`call-lead-${lead.id}`}
                            >
                              {actionLoading === `call-${lead.id}` ? '...' : 'Call'}
                            </button>
                            <button
                              className="btn btn-sm btn-secondary"
                              onClick={() => startEditLead(lead)}
                              disabled={actionLoading === `update-${lead.id}`}
                              data-testid={`edit-lead-${lead.id}`}
                              style={{ marginLeft: 8 }}
                            >
                              Edit
                            </button>
                            <button
                              className="btn btn-sm btn-danger"
                              onClick={() => deleteLead(lead.id)}
                              disabled={actionLoading === `delete-${lead.id}`}
                              data-testid={`delete-lead-${lead.id}`}
                              style={{ marginLeft: 8 }}
                            >
                              Delete
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  )) : (
                    <div className="data-table-row"><div className="data-table-td empty-state" style={{ width: '100%', display: 'table-cell' }}>No leads yet. Add leads manually or sync from Google Sheets.</div></div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'calls' && (
          <div className="calls-tab" data-testid="calls-tab">
            <h3>Call History</h3>
            <div className="calls-table-wrapper">
              <div className="data-table">
                <div className="data-table-header">
                  <div className="data-table-row">
                    <div className="data-table-th">Lead</div>
                    <div className="data-table-th">Phone</div>
                    <div className="data-table-th">Status</div>
                    <div className="data-table-th">Interest</div>
                    <div className="data-table-th">WhatsApp</div>
                    <div className="data-table-th">State</div>
                    <div className="data-table-th">Time</div>
                    <div className="data-table-th">Notes</div>
                  </div>
                </div>
                <div className="data-table-body">
                  {callHistory.length > 0 ? callHistory.map((log, i) => (
                    <div key={log.id || i} className="data-table-row">
                      <div className="data-table-td">{log.lead_name}</div>
                      <div className="data-table-td mono">{log.lead_phone}</div>
                      <div className="data-table-td"><span className={`badge ${getStatusBadge(log.status)}`}>{log.status || 'Pending'}</span></div>
                      <div className="data-table-td">{log.interest_detected ? 'Yes' : 'No'}</div>
                      <div className="data-table-td">{log.whatsapp_sent ? 'Sent' : 'No'}</div>
                      <div className="data-table-td"><span className="state-badge">{log.conversation_state}</span></div>
                      <div className="data-table-td">{new Date(log.timestamp).toLocaleString()}</div>
                      <div className="data-table-td">{log.notes}</div>
                    </div>
                  )) : (
                    <div className="data-table-row"><div className="data-table-td empty-state" style={{ width: '100%', display: 'table-cell' }}>No call history yet.</div></div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'config' && (
          <div className="config-tab" data-testid="config-tab">
            <h3>System Configuration</h3>
            <p className="config-note">Configure API keys in the backend .env file and restart the server.</p>

            {configStatus && (
              <div className="config-grid">
                {Object.entries(configStatus).map(([key, val]) => (
                  <div key={key} className="config-card" data-testid={`config-${key}`}>
                    <h4>{key.replace(/_/g, ' ').toUpperCase()}</h4>
                    {typeof val === 'object' ? (
                      <div className="config-details">
                        {Object.entries(val).map(([k, v]) => (
                          <div key={k} className="config-row">
                            <span className="config-key">{k}</span>
                            <span className={`config-val ${k === 'configured' ? (v ? 'val-ok' : 'val-missing') : ''}`}>
                              {typeof v === 'boolean' ? (v ? 'Yes' : 'No') : String(v)}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <span className="config-val">{String(val)}</span>
                    )}
                  </div>
                ))}
              </div>
            )}

            <div className="config-instructions">
              <h4>Setup Instructions</h4>
              <ol>
                <li><strong>Twilio:</strong> Add TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER to .env</li>
                <li><strong>ElevenLabs:</strong> Add ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID to .env</li>
                <li><strong>WhatsApp:</strong> Add TWILIO_WHATSAPP_NUMBER to .env (uses Twilio credentials)</li>
                <li><strong>Google Sheets:</strong> Add GOOGLE_SHEET_ID and base64-encoded GOOGLE_SERVICE_ACCOUNT_JSON</li>
                <li><strong>Webhook URL:</strong> Set WEBHOOK_BASE_URL to your public HTTPS URL</li>
                <li>Restart the backend after updating .env</li>
              </ol>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
