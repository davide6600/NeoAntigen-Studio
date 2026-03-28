import React, { useState, useEffect } from 'react';
import { ShieldCheck, ShieldAlert, Check, X, Loader2 } from 'lucide-react';
import { apiClient } from '../../api/client';
import './Approvals.css';

interface Approval {
  proposal_id: string;
  action: string;
  details: any;
  created_at: string;
  status: 'pending' | 'approved' | 'rejected';
}

export const ApprovalsDashboard: React.FC = () => {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchApprovals = async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<any>('/approvals');
      // The backend returns {"pending_approvals": [...]}
      if (data && data.pending_approvals) {
        const pending = data.pending_approvals.map((p: any) => ({
          ...p,
          status: 'pending'
        }));
        setApprovals(pending);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to fetch approvals');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchApprovals();
  }, []);

  const handleApprove = async (id: string) => {
    try {
      await apiClient.post(`/approvals/${id}/approve`, {
        approved_by: 'QA_Agent',
        token: 'debug-token-123'
      });
      // Update local state to show as approved
      setApprovals(prev => prev.map(a => 
        a.proposal_id === id ? { ...a, status: 'approved' } : a
      ));
    } catch (err: any) {
      alert(`Approval failed: ${err.message}`);
    }
  };

  const handleReject = (id: string) => {
    // Backend doesn't have a direct reject endpoint for general proposals yet,
    // so we'll just remove it from the view for now or mark as rejected locally.
    setApprovals(prev => prev.map(a => 
      a.proposal_id === id ? { ...a, status: 'rejected' } : a
    ));
  };

  if (loading && approvals.length === 0) {
    return (
      <div className="approvals-container">
        <div className="glass-panel p-12 text-center">
          <Loader2 className="animate-spin mx-auto mb-4" size={32} />
          <p className="text-muted">Loading pending approvals...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="approvals-container">
      <div className="approvals-header glass-panel border-warning">
        <div className="header-icon">
          <ShieldAlert size={32} className="text-warning" />
        </div>
        <div>
          <h2>Export Approvals (Human-in-the-Loop)</h2>
          <p className="text-muted">Review and authorize sequence exports for external use.</p>
        </div>
      </div>

      {error && <div className="glass-panel border-danger p-4 mb-4 text-danger">{error}</div>}

      <div className="approvals-list">
        {approvals.length === 0 ? (
          <div className="glass-panel p-6 text-center text-muted">
            No pending approvals found.
          </div>
        ) : (
          approvals.map(req => (
            <div key={req.proposal_id} className={`approval-card glass-panel ${req.status}`}>
              <div className="approval-info">
                <div className="req-header">
                  <h3>{req.proposal_id}</h3>
                  <span className={`badge ${req.status}`}>{req.status}</span>
                </div>
                <div className="req-details">
                  <p><strong>Action:</strong> {req.action}</p>
                  <p><strong>Requester:</strong> {req.details?.requested_by || 'Unknown'}</p>
                  <p><strong>Patient ID:</strong> {req.details?.patient_id || '-'}</p>
                  <p className="text-sm text-muted">Requested: {new Date(req.created_at).toLocaleString()}</p>
                </div>
              </div>
              
              {req.status === 'pending' && (
                <div className="approval-actions">
                  <button className="btn-approve" onClick={() => handleApprove(req.proposal_id)}>
                    <Check size={18} /> Approve Export
                  </button>
                  <button className="btn-reject" onClick={() => handleReject(req.proposal_id)}>
                    <X size={18} /> Reject
                  </button>
                </div>
              )}
              {req.status === 'approved' && (
                <div className="approval-actions centered">
                   <ShieldCheck size={24} className="text-success mx-auto mb-2" />
                   <span className="text-sm text-success">Authorized</span>
                </div>
              )}
              {req.status === 'rejected' && (
                <div className="approval-actions centered">
                   <ShieldAlert size={24} className="text-danger mx-auto mb-2" />
                   <span className="text-sm text-danger">Rejected</span>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};
