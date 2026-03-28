import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { Upload, AlertCircle } from 'lucide-react';
import './UploadForm.css';

export const UploadForm: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const [formData, setFormData] = useState({
    run_mode: 'ruo_standard',
    requested_by: 'demo_user',
    patient_id: '',
    sample_id: '',
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const toBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => {
        const result = reader.result as string;
        // Strip out the data:application/octet-stream;base64, prefix
        const base64Content = result.split(',')[1];
        resolve(base64Content);
      };
      reader.onerror = error => reject(error);
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const inputs = [];
      if (selectedFile) {
        const base64_content = await toBase64(selectedFile);
        inputs.push({
          name: selectedFile.name,
          base64_content,
          content_type: 'application/octet-stream' // or map from selectedFile.type
        });
      }

      const payload = {
        run_mode: formData.run_mode,
        requested_by: formData.requested_by,
        metadata: {
          patient_id: formData.patient_id,
          sample_id: formData.sample_id,
          ruo_verification: true
        },
        inputs: inputs
      };

      const result = await apiClient.post<any>('/jobs', payload);

      // Navigate to dashboard on success
      if (result.job_id) {
        navigate('/');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to submit job.');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  return (
    <div className="upload-container glass-panel">
      <div className="upload-header">
        <h2>Submit New Sequence Job</h2>
        <div className="badge warning">
          <AlertCircle size={14} /> RUO Context
        </div>
      </div>

      {error && <div className="error-alert">{error}</div>}

      <form onSubmit={handleSubmit} className="upload-form">
        <div className="form-group">
          <label htmlFor="run_mode">Pipeline Mode</label>
          <select 
            id="run_mode" 
            name="run_mode" 
            value={formData.run_mode}
            onChange={handleChange}
            className="form-control"
          >
            <option value="ruo_standard">Standard RUO</option>
            <option value="ruo_fast">Fast RUO (Test)</option>
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="patient_id">Patient ID</label>
          <input 
            type="text" 
            id="patient_id" 
            name="patient_id"
            value={formData.patient_id}
            onChange={handleChange}
            required
            className="form-control"
            placeholder="e.g. PAT-123"
          />
        </div>

        <div className="form-group">
          <label htmlFor="sample_id">Sample ID</label>
          <input 
            type="text" 
            id="sample_id" 
            name="sample_id"
            value={formData.sample_id}
            onChange={handleChange}
            required
            className="form-control"
            placeholder="e.g. SMP-456"
          />
        </div>

        <div className="form-group">
          <label htmlFor="requested_by">Requester Email / ID</label>
          <input 
            type="text" 
            id="requested_by" 
            name="requested_by"
            value={formData.requested_by}
            onChange={handleChange}
            required
            className="form-control"
          />
        </div>

        {/* Real dropzone for files */}
        <div 
          className={`dropzone ${selectedFile ? 'has-file' : ''}`}
          onClick={() => document.getElementById('fileUpload')?.click()}
        >
          <input
            type="file"
            id="fileUpload"
            style={{ display: 'none' }}
            onChange={handleFileChange}
            accept=".fastq,.vcf,.fasta,.txt"
          />
          <Upload size={32} className="text-muted" />
          {selectedFile ? (
             <p className="file-name text-success">Selected: {selectedFile.name}</p>
          ) : (
            <>
              <p>Click to browse sequence files (.fastq, .vcf, .fasta)</p>
              <p className="text-sm text-muted">Supports raw genomic unaligned inputs</p>
            </>
          )}
        </div>

        <div className="form-actions">
          <button type="submit" disabled={loading} className="btn-primary">
            {loading ? 'Submitting...' : 'Submit Job'}
          </button>
        </div>
      </form>
    </div>
  );
};
