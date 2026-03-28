import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { Activity, Clock, CheckCircle, XCircle, AlertTriangle, ChevronDown, ChevronRight, Download, Settings, FileText } from 'lucide-react';
import { StepDetailPanel } from './StepDetailPanel';
import './JobTable.css';

interface Job {
  job_id: string;
  run_mode: string;
  status: string;
  created_at: string;
  updated_at: string;
  message?: string;
  requested_by: string;
  metadata?: Record<string, any>;
}

export const JobTable: React.FC = () => {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [steps, setSteps] = useState<any[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [stepsLoading, setStepsLoading] = useState(false);
  const [selectedStep, setSelectedStep] = useState<any | null>(null);

  const fetchJobs = async () => {
    try {
      const data = await apiClient.get<Job[]>('/jobs');
      setJobs(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load jobs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 10000); // Poll every 10s
    return () => clearInterval(interval);
  }, []);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircle className="status-icon success" size={16} />;
      case 'failed': return <XCircle className="status-icon danger" size={16} />;
      case 'running': return <Activity className="status-icon warning spin" size={16} />;
      case 'pending': return <Clock className="status-icon muted" size={16} />;
      default: return <AlertTriangle className="status-icon muted" size={16} />;
    }
  };

  const handleRowClick = async (jobId: string) => {
    if (expandedJobId === jobId) {
      setExpandedJobId(null);
      return;
    }
    setExpandedJobId(jobId);
    setLogsLoading(true);
    setStepsLoading(true);
    
    // Fetch logs and steps in parallel
    const logsPromise = apiClient.get<any>(`/jobs/${jobId}/logs`);
    const stepsPromise = apiClient.get<any>(`/jobs/${jobId}/steps`);

    try {
      const [logsData, stepsData] = await Promise.all([logsPromise, stepsPromise]);
      setLogs(logsData.logs || []);
      setSteps(stepsData.steps || []);
    } catch (err) {
      console.error("Failed to load details", err);
      setLogs([]);
      setSteps([]);
    } finally {
      setLogsLoading(false);
      setStepsLoading(false);
    }
  };

  const handleUpdate = () => {
    if (expandedJobId) {
       handleRowClick(expandedJobId); // Refresh logs and steps
    }
  };

  const handleDownloadLogs = (jobId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    // Prompt the browser to download the text format
    window.location.href = `/api/jobs/${jobId}/logs?format=text`;
  };

  if (loading && jobs.length === 0) {
    return <div className="loading-state glass-panel">Loading jobs...</div>;
  }

  if (error) {
    return <div className="error-state glass-panel">Error: {error}</div>;
  }

  return (
    <div className="job-table-container glass-panel">
      <div className="table-header">
        <h3>Recent Jobs</h3>
        <button onClick={fetchJobs} className="btn-refresh">Refresh</button>
      </div>
      
      {jobs.length === 0 ? (
        <div className="empty-state">No jobs found in the system.</div>
      ) : (
        <table className="job-table">
          <thead>
            <tr>
              <th className="w-8"></th>
              <th>Job ID</th>
              <th>Patient ID</th>
              <th>Mode</th>
              <th>Status</th>
              <th>Created At</th>
              <th>Requester</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <React.Fragment key={job.job_id}>
                <tr
                  className={`cursor-pointer ${expandedJobId === job.job_id ? 'expanded' : ''}`}
                  onClick={() => handleRowClick(job.job_id)}
                >
                  <td className="w-8">
                    {expandedJobId === job.job_id ? <ChevronDown size={16} className="text-muted" /> : <ChevronRight size={16} className="text-muted" />}
                  </td>
                  <td className="font-mono text-sm">{job.job_id.substring(0, 8)}...</td>
                  <td className="font-mono text-xs">{job.metadata?.patient_id || '-'}</td>
                  <td><span className="badge">{job.run_mode}</span></td>
                  <td>
                    <div className="status-cell">
                      {getStatusIcon(job.status)}
                      <span className={`status-text ${job.status}`}>{job.status}</span>
                    </div>
                  </td>
                  <td className="text-sm text-muted">
                    {new Date(job.created_at).toLocaleString()}
                  </td>
                  <td className="text-sm">{job.requested_by}</td>
                </tr>
                {expandedJobId === job.job_id && (
                  <tr className="log-panel-row">
                    <td colSpan={6} className="log-panel-cell">
                      <div className="details-container">
                        
                        <div className="steps-panel">
                          <div className="panel-header-mini">
                            <h4>Pipeline Timeline</h4>
                            <span className="text-xs text-muted">Click a step to view or edit</span>
                          </div>
                          
                          {stepsLoading ? (
                             <div className="loading-mini">Loading timeline...</div>
                          ) : steps.length === 0 ? (
                             <div className="empty-mini">No steps recorded for this engine.</div>
                          ) : (
                            <div className="timeline">
                              {steps.map((step) => (
                                <div 
                                  key={step.step_id} 
                                  className={`timeline-item ${step.status} ${step.is_manually_edited ? 'is-edited' : ''}`}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setSelectedStep(step);
                                  }}
                                >
                                  <div className="timeline-connector"></div>
                                  <div className="timeline-marker">
                                    {step.status === 'completed' ? <CheckCircle size={12} /> : 
                                     step.status === 'running' ? <Activity size={12} className="spin" /> :
                                     step.status === 'paused' ? <Settings size={12} className="pulse" /> :
                                     <Clock size={12} />}
                                  </div>
                                  <div className="timeline-content">
                                    <div className="step-name">{step.name}</div>
                                    <div className="step-meta">
                                      {step.status} {step.is_manually_edited && '• Edited'}
                                    </div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        <div className="log-panel">
                            <div className="log-panel-header" style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                              <h4>Process Logs</h4>
                              <div style={{ flex: 1 }}></div>
                              {job.status === 'completed' && (
                                <button
                                  className="btn-download"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    navigate(`/results/${job.job_id}`);
                                  }}
                                  style={{ backgroundColor: 'var(--brand-primary)', color: 'white', borderColor: 'var(--brand-primary)' }}
                                >
                                  <FileText size={14} /> View Results
                                </button>
                              )}
                            <button 
                              className="btn-download"
                              onClick={(e) => handleDownloadLogs(job.job_id, e)}
                            >
                              <Download size={14} /> Download Logs
                            </button>
                          </div>
                          <div className="log-content">
                            {logsLoading ? (
                              <div className="log-loading">Loading logs...</div>
                            ) : logs.length === 0 ? (
                              <div className="log-empty">No logs available for this job.</div>
                            ) : (
                              <pre className="log-pre">
                                {logs.map((log, i) => (
                                  <div key={i} className="log-line">
                                    <span className="log-ts">[{new Date(log.created_at).toISOString()}]</span>
                                    <span className="log-action">{log.action || '-'}</span>
                                    <span className={`log-status ${log.status || ''}`}>{log.status || '-'}</span>
                                    <span className="log-msg">
                                      {log.details?.message || log.details?.error || ''}
                                    </span>
                                  </div>
                                ))}
                              </pre>
                            )}
                          </div>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      )}

      {selectedStep && expandedJobId && (
        <StepDetailPanel 
          jobId={expandedJobId}
          step={selectedStep}
          onClose={() => setSelectedStep(null)}
          onUpdate={handleUpdate}
        />
      )}
    </div>
  );
};
