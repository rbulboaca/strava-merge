import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx';
import { mergeStyles } from '@fluentui/react';

// Inject some global styles
mergeStyles({
  ':global(body,html,#root)': {
    margin: 0,
    padding: 0,
    height: '100vh',
  },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
 <React.StrictMode>
    <App />
 </React.StrictMode>,
)
