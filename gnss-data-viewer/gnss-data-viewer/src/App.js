import React, { useState } from 'react';
import './App.css';
import CSVReaderComponent from './components/CSVReader';
import SatelliteView from './components/SatelliteView';
import LogFileSelectorComponent from './components/LogFileSelector';

function App() {
  const [currentView, setCurrentView] = useState('GNSS_DATA_VIEWER');

  const handleViewChange = (view) => {
    setCurrentView(view);
  };

  return (
    <div className="App">
      <header>
        <nav>
          <ul>
            <li onClick={() => handleViewChange('GNSS_DATA_VIEWER')}>GNSS Data Viewer</li>
            <li onClick={() => handleViewChange('SAT_VIEW')}>Sat View</li>
            <li onClick={() => handleViewChange('LOG_FILE_SELECTOR')}>Log File Selector</li>
          </ul>
        </nav>
      </header>
      {currentView === 'GNSS_DATA_VIEWER' && <CSVReaderComponent />}
      {currentView === 'SAT_VIEW' && <SatelliteView />}
      {currentView === 'LOG_FILE_SELECTOR' && <LogFileSelectorComponent />}
    </div>
  );
}

export default App;
