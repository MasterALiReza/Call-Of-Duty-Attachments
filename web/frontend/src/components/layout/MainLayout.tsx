import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';

export const MainLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState<boolean>(false);

  return (
    <div className="min-h-screen bg-background text-mainText flex flex-col font-sans transition-colors duration-300">
      {/* Sidebar */}
      <Sidebar collapsed={collapsed} setCollapsed={setCollapsed} />

      {/* Header */}
      <Header sidebarCollapsed={collapsed} />

      {/* Main Content Area */}
      <main
        className={`flex-1 mt-16 p-6 transition-all duration-300 ${
          collapsed ? 'mr-20' : 'mr-64'
        }`}
      >
        <div className="max-w-7xl mx-auto space-y-6 animate-in fade-in duration-300">
          <Outlet />
        </div>
      </main>
    </div>
  );
};
