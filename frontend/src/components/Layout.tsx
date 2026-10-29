import React, { useState, ReactNode, useEffect } from 'react';
import Sidebar from './Sidebar';
import { Menu, Moon, Sun } from 'lucide-react';

interface LayoutProps {
  children: ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  // The initial theme is applied by public/theme.js before the page is drawn
  const [darkMode, setDarkMode] = useState(() => document.documentElement.classList.contains('dark'));

  const toggleSidebar = () => setSidebarOpen(!sidebarOpen);

  const toggleTheme = () => {
    const newDarkMode = !darkMode;
    setDarkMode(newDarkMode);
    localStorage.setItem('darkMode', JSON.stringify(newDarkMode));
  };

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [darkMode]);

  return (
    <div className="flex h-dvh bg-gray-200/70 dark:bg-gray-900 transition-colors duration-200">
      {/* Sidebar */}
      <div
        className={`fixed md:static inset-y-0 left-0 transform ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        } md:translate-x-0 transition duration-200 ease-in-out z-30 w-64 bg-gray-100 md:bg-gray-100/80 dark:bg-gray-800 border-r border-gray-300 dark:border-gray-700 h-full overflow-y-auto`}
      >
        <Sidebar onCloseMobile={() => setSidebarOpen(false)} />
      </div>

      {/* Backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-20 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main content */}
      <div className="flex-1 min-w-0 flex flex-col">
        {/* Header: sidebar toggle and name on mobile, theme toggle on every screen */}
        <header className="flex items-center gap-2 px-3 py-2 md:px-6 md:pt-4 md:pb-0 border-b md:border-b-0 border-gray-300 dark:border-gray-700 bg-gray-100/80 dark:bg-gray-800 md:bg-transparent md:dark:bg-transparent">
          <button
            className="md:hidden p-2 rounded-lg text-gray-700 dark:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
            onClick={toggleSidebar}
            aria-label="Abrir menu"
          >
            <Menu size={24} />
          </button>
          <img src="/poligpt_icon.svg" alt="" className="md:hidden h-7 w-7" />
          <span className="md:hidden font-semibold text-gray-800 dark:text-gray-100">PoliGPT</span>
          <button
            className="ml-auto p-2 rounded-full bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-amber-400 hover:bg-gray-300 dark:hover:bg-gray-600 shadow-sm transition-colors"
            onClick={toggleTheme}
            aria-label={darkMode ? 'Usar tema claro' : 'Usar tema escuro'}
            title={darkMode ? 'Tema claro' : 'Tema escuro'}
          >
            {darkMode ? <Sun size={20} /> : <Moon size={20} />}
          </button>
        </header>
        <main className="flex-1 min-h-0 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
};

export default Layout;
