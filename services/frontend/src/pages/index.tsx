import React from 'react';
import { JobTable } from '../components/jobs/JobTable';

export const Dashboard: React.FC = () => {
  return (
    <div className="page-container glass-panel">
      <h1>Dashboard</h1>
      <p className="text-muted">Job monitoring and platform metrics.</p>
      
      <JobTable />
    </div>
  );
};

import { UploadForm } from '../components/jobs/UploadForm';

export const UploadJob: React.FC = () => {
  return (
    <div className="page-container glass-panel">
      <UploadForm />
    </div>
  );
};

import { ResultsView as ResultsComponent } from '../components/results/ResultsView';

export const ResultsView: React.FC = () => {
  return (
    <div className="page-container glass-panel p-0">
      <ResultsComponent />
    </div>
  );
};

import { ApprovalsDashboard as ApprovalsComponent } from '../components/approvals/ApprovalsDashboard';

export const ApprovalsDashboard: React.FC = () => {
  return (
    <div className="page-container" style={{ padding: 0 }}>
      {/* Container styling handled inside component to allow full width headers */}
      <ApprovalsComponent />
    </div>
  );
};
