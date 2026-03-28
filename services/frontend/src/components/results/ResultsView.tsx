import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Download, CheckCircle, Search, AlertTriangle, Loader2 } from 'lucide-react';
import { apiClient } from '../../api/client';
import './Results.css';

interface Candidate {
  peptide: string;
  gene: string;
  affinity_nm: number;
  percentile_rank: number;
  expression_tpm?: number;
  hla_allele: string;
}

interface PipelineSummary {
  total_variants: number;
  somatic_mutations: number;
  strong_binders: number;
  candidates: Candidate[];
}

export const ResultsView: React.FC = () => {
  const { jobId: routeJobId } = useParams<{ jobId?: string }>();
  const navigate = useNavigate();
  const [jobId, setJobId] = useState(routeJobId || '');
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [summary, setSummary] = useState<PipelineSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (routeJobId) {
      setJobId(routeJobId);
      fetchResults(routeJobId);
      return;
    }
    // On mount, if no route param, find the latest completed job
    const fetchLatestJob = async () => {
      try {
        const jobs = await apiClient.get<any[]>('/jobs');
        const completedJob = jobs.find(j => j.status === 'completed');
        if (completedJob) {
          setJobId(completedJob.job_id);
          fetchResults(completedJob.job_id);
          // Optional: navigate(`../results/${completedJob.job_id}`, { replace: true });
        } else {
          setLoading(false);
        }
      } catch (err: any) {
        setError(err.message || 'Failed to fetch jobs');
        setLoading(false);
      }
    };
    fetchLatestJob();
  }, [routeJobId]);

  const fetchResults = async (id: string) => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.get<any>(`/jobs/${id}/results`);
      setActiveJobId(id);
      if (data.pipeline_summary) {
        setSummary(data.pipeline_summary);
      } else {
        setSummary(null);
        setError('No pipeline summary available for this job.');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to fetch results');
      setSummary(null);
      setActiveJobId(null);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (jobId) {
      navigate(`/results/${jobId}`);
    }
  };

  const getStatusBadge = (affinity: number | undefined) => {
    if (affinity === undefined || affinity === null) return { label: 'Unknown', class: 'text-muted' };
    if (affinity < 50) return { label: 'Strong Binder', class: 'binder' };
    if (affinity < 500) return { label: 'Weak Binder', class: 'weak_binder' };
    return { label: 'Non Binder', class: 'high_priority' };
  };

  const exportTsv = () => {
    if (!summary || !summary.candidates || summary.candidates.length === 0) return;
    
    const headers = ['Peptide', 'Gene', 'MHC Allele', 'Affinity (nM)', '% Rank', 'Expression (TPM)'];
    const rows = summary.candidates.map(c => [
      c.peptide || '-',
      c.gene || '-',
      c.hla_allele || '-',
      (c.affinity_nm !== undefined && c.affinity_nm !== null) ? c.affinity_nm.toFixed(2) : 'N/A',
      c.percentile_rank ?? 'N/A',
      c.expression_tpm ?? 'N/A'
    ]);
    
    const tsvContent = [
      headers.join('\t'),
      ...rows.map(r => r.join('\t'))
    ].join('\n');
    
    const blob = new Blob([tsvContent], { type: 'text/tab-separated-values' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `neoantigen_candidates_${activeJobId || 'export'}.tsv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="results-container">
      <div className="results-header glass-panel">
          <div>
            <h2>Variant Analysis & Peptide Predictions</h2>
            <p className="text-muted">Review MHC binding affinities and neoantigen candidates.</p>
          </div>
          
          <form className="search-box" onSubmit={handleSearch}>
            <Search size={18} className="text-muted" />
            <input 
              type="text" 
              placeholder="Search by Job ID..." 
              value={jobId}
              onChange={(e) => setJobId(e.target.value)}
              className="search-input"
            />
          </form>
      </div>

      {loading ? (
        <div className="glass-panel p-12 text-center text-muted">
          <Loader2 className="animate-spin mx-auto mb-4" size={32} />
          <p>Loading results...</p>
        </div>
      ) : error ? (
        <div className="glass-panel p-6 text-center" style={{ color: 'var(--accent-danger)' }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '8px' }}>
            <AlertTriangle size={24} />
          </div>
          <div>{error}</div>
        </div>
      ) : !summary ? (
        <div className="glass-panel p-6 text-center text-muted">
          No results available. Please run a job or search by a completed Job ID.
        </div>
      ) : (
        <>
          <div className="results-grid">
            <div className="metric-card glass-panel">
              <h3>Total Variants</h3>
              <div className="metric-value">{summary.total_variants?.toLocaleString() || 0}</div>
            </div>
            <div className="metric-card glass-panel">
              <h3>Somatic Mutations</h3>
              <div className="metric-value">{summary.somatic_mutations?.toLocaleString() || 0}</div>
            </div>
            <div className="metric-card glass-panel highlight">
              <h3>Strong Binders ({"<"}50nM)</h3>
              <div className="metric-value">{summary.strong_binders?.toLocaleString() || 0}</div>
            </div>
          </div>

          <div className="glass-panel mt-6 p-0 overflow-hidden">
            <div className="table-header p-4 border-b">
              <h3>Top Neoantigen Candidates {activeJobId && <span className="text-muted text-sm" style={{ marginLeft: '8px' }}>({activeJobId.substring(0,8)}...)</span>}</h3>
              <button className="btn-secondary" onClick={exportTsv} disabled={!summary.candidates || summary.candidates.length === 0}>
                <Download size={16} /> Export TSV
              </button>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table className="peptide-table">
                <thead>
                  <tr>
                    <th>Sequence</th>
                    <th>Gene</th>
                    <th>MHC Allele</th>
                    <th>Affinity (IC50)</th>
                    <th>% Rank</th>
                    <th>Status</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.candidates?.map((p, i) => {
                    const status = getStatusBadge(p.affinity_nm);
                    return (
                      <tr key={i}>
                        <td className="font-mono text-primary">{p.peptide || '-'}</td>
                        <td>{p.gene || '-'}</td>
                        <td>{p.hla_allele || '-'}</td>
                        <td>{(p.affinity_nm !== undefined && p.affinity_nm !== null) ? `${p.affinity_nm.toFixed(2)} nM` : 'N/A'}</td>
                        <td>{p.percentile_rank ?? 'N/A'}</td>
                        <td><span className={`badge ${status.class}`}>{status.label}</span></td>
                        <td>
                          <button className="btn-icon" title="Flag for Review">
                            <CheckCircle size={16} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                  {(!summary.candidates || summary.candidates.length === 0) && (
                    <tr>
                      <td colSpan={7} className="p-4 text-center text-muted">No candidates found in this job.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
