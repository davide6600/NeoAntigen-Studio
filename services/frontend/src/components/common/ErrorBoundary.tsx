import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCcw } from 'lucide-react';

interface Props {
  children?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null
  };

  public static getDerivedStateFromError(error: Error): State {
    // Update state so the next render will show the fallback UI.
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo);
  }

  private handleReset = () => {
    // Clear potentially corrupt storage if requested by the user flow
    localStorage.clear();
    sessionStorage.clear();
    window.location.href = '/';
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary-container" style={{
          height: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '24px',
          textAlign: 'center',
          background: 'var(--bg-glass)',
          backdropFilter: 'blur(20px)',
          color: 'var(--text-primary)'
        }}>
          <div style={{ marginBottom: '24px', color: 'var(--accent-danger)' }}>
            <AlertTriangle size={64} />
          </div>
          <h1 style={{ fontSize: '2rem', marginBottom: '16px' }}>Application Error</h1>
          <p style={{ maxWidth: '600px', marginBottom: '32px', color: 'var(--text-muted)' }}>
            Something went wrong while rendering the application. This could be due to unexpected API data or a temporary system issue.
          </p>
          <div style={{ 
            background: 'rgba(255, 0, 0, 0.1)', 
            padding: '16px', 
            borderRadius: '8px', 
            fontFamily: 'monospace', 
            fontSize: '14px',
            marginBottom: '32px',
            maxWidth: '100%',
            overflow: 'auto',
            border: '1px solid var(--accent-danger)'
          }}>
            {this.state.error?.toString()}
          </div>
          <button 
            onClick={this.handleReset}
            className="btn-primary"
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            <RefreshCcw size={18} /> Hard Reset & Reload
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
