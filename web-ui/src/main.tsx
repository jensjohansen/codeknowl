/**
 * Main entry point for CodeKnowl Web UI
 * 
 * Why this exists:
 * - React application bootstrap
 * - Initializes the app and renders to DOM
 * - Supports Milestone 9 requirements for web UI
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
