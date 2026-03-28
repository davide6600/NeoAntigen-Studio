import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import AppLayout from './layouts/AppLayout'
import { Dashboard, UploadJob, ResultsView, ApprovalsDashboard } from './pages'
import { ErrorBoundary } from './components/common/ErrorBoundary'

function App() {
  return (
    <Router>
      <ErrorBoundary>
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="upload" element={<UploadJob />} />
            <Route path="results" element={<ResultsView />} />
            <Route path="results/:jobId" element={<ResultsView />} />
            <Route path="approvals" element={<ApprovalsDashboard />} />
          </Route>
        </Routes>
      </ErrorBoundary>
    </Router>
  )
}

export default App
