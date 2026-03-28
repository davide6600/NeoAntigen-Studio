import React, { useState, useEffect } from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { ShieldAlert, Activity, UploadCloud, FileText, CheckCircle, Sun, Moon } from 'lucide-react';

const AppLayout: React.FC = () => {
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark');

  useEffect(() => {
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => (prev === 'dark' ? 'light' : 'dark'));
  };

  return (
    <div className="layout-container" data-theme={theme}>
      {/* Permanent RUO Safety Banner */}
      <div className="ruo-banner">
        <ShieldAlert size={18} />
        <span>
          <strong>RESEARCH USE ONLY.</strong> Not for use in diagnostic procedures. 
          All sequence exports require explicit human-in-the-loop approval.
        </span>
      </div>

      <div className="main-layout">
        <aside className="sidebar glass-panel">
          <div className="logo-container">
            <h2>NeoAntigen Studio</h2>
          </div>
          
          <nav className="nav-menu">
            <NavLink to="/" className={({ isActive }) => (isActive ? 'nav-item active' : 'nav-item')}>
              <Activity size={18} />
              <span>Dashboard</span>
            </NavLink>
            
            <NavLink to="/upload" className={({ isActive }) => (isActive ? 'nav-item active' : 'nav-item')}>
              <UploadCloud size={18} />
              <span>New Job</span>
            </NavLink>
            
            <NavLink to="/results" className={({ isActive }) => (isActive ? 'nav-item active' : 'nav-item')}>
              <FileText size={18} />
              <span>Results</span>
            </NavLink>
            
            <NavLink to="/approvals" className={({ isActive }) => (isActive ? 'nav-item active' : 'nav-item')}>
              <CheckCircle size={18} />
              <span>Approvals</span>
            </NavLink>
          </nav>

          <button className="nav-item theme-toggle-btn mt-auto" onClick={toggleTheme}>
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
            <span>{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>
          </button>

        </aside>

        <main className="content-area">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default AppLayout;

