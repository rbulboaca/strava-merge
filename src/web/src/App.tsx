import { FC } from 'react';
import { ThemeProvider } from '@fluentui/react';
import { DarkTheme } from './ux/theme';
import HomePage from './pages/homePage';
import './App.css';

const App: FC = () => {
  return (
    <ThemeProvider applyTo="body" theme={DarkTheme}>
      <HomePage />
    </ThemeProvider>
  );
};

export default App;
