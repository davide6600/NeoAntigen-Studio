import React, { useState } from 'react';
import { apiClient } from '../../api/client';
import { Save, X, Edit2, Play } from 'lucide-react';
import './StepDetailPanel.css';

interface StepDetailPanelProps {
  jobId: string;
  step: any;
  onClose: () => void;
  onUpdate: () => void;
}

export const StepDetailPanel: React.FC<StepDetailPanelProps> = ({ jobId, step, onClose, onUpdate }) => {
  const [editMode, setEditMode] = useState(false);
  const [editedData, setEditedData] = useState(JSON.stringify(step.output_data, null, 2));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const parsed = JSON.parse(editedData);
      await apiClient.post(`/jobs/${jobId}/steps/${step.step_id}/update`, {
        status: 'completed',
        output_data: parsed,
        is_manually_edited: true
      });
      setEditMode(false);
      onUpdate();
    } catch (err: any) {
      setError(err.message || 'Failed to save changes. Ensure JSON is valid.');
    } finally {
      setSaving(false);
    }
  };

  const handleResume = async () => {
    setSaving(true);
    try {
      await apiClient.post(`/jobs/${jobId}/steps/${step.step_id}/resume`, {});
      onUpdate();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to resume job.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="step-detail-overlay">
      <div className="step-detail-panel glass-panel">
        <div className="panel-header">
          <h3>Step Detail: {step.name}</h3>
          <button onClick={onClose} className="btn-close"><X size={18} /></button>
        </div>

        <div className="panel-content">
          <div className="step-info">
            <span className={`badge ${step.status}`}>{step.status}</span>
            {step.is_manually_edited && <span className="badge warning">Edited Manually</span>}
            <span className="timestamp text-muted">Updated: {new Date(step.updated_at).toLocaleString()}</span>
          </div>

          <div className="data-section">
            <div className="section-header">
              <h4>Output Data</h4>
                {!editMode && step.status !== 'failed' && (
                    <button onClick={() => setEditMode(true)} className="btn-icon">
                      <Edit2 size={14} /> Edit
                    </button>
                )}
                {step.status === 'paused' && (
                  <button onClick={handleResume} className="btn-resume" disabled={saving}>
                  <Play size={14} /> Resume Job
                </button>
              )}
            </div>

            {editMode ? (
              <div className="editor-container">
                <textarea 
                  className="json-editor font-mono"
                  value={editedData}
                  onChange={(e) => setEditedData(e.target.value)}
                />
                {error && <div className="editor-error">{error}</div>}
                <div className="editor-actions">
                  <button onClick={() => setEditMode(false)} className="btn-cancel" disabled={saving}>Cancel</button>
                  <button onClick={handleSave} className="btn-save" disabled={saving}>
                    <Save size={14} /> {saving ? 'Saving...' : 'Save Changes'}
                  </button>
                </div>
              </div>
            ) : (
              <pre className="data-view font-mono">
                {JSON.stringify(step.output_data, null, 2) || 'No output data yet.'}
              </pre>
            )}
          </div>

          <div className="data-section">
            <h4>Input Data</h4>
            <pre className="data-view font-mono muted">
              {JSON.stringify(step.input_data, null, 2) || 'No input data.'}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
};
