// src/App.js
import React, { useState } from 'react';
import './App.css';
import SatelliteView from './components/SatelliteView';
import LogFileSelectorComponent from './components/LogFileSelector';
import KmlViewerComponent from './components/KmlViewerComponent';

function App() {
  const [currentView, setCurrentView] = useState('LOG_FILE_SELECTOR');
  const [selectedKmlFile, setSelectedKmlFile] = useState('');

  const handleViewChange = (view) => {
    setCurrentView(view);
  };

  const handleKmlFileChange = (event) => {
    const file = event.target.files[0];
    if (file) {
      const url = URL.createObjectURL(file);
      setSelectedKmlFile(url);
      setCurrentView('KML_VIEWER');
    }
  };

  const startLiveProcessing = () => {
    setCurrentView('KML_VIEWER');
  };

  const stopLiveProcessing = () => {
    setCurrentView('LOG_FILE_SELECTOR');
  };

  return (
    <div className="App">
      <header>
        <nav>
          <ul>
            <li onClick={() => handleViewChange('LOG_FILE_SELECTOR')}>Log File Selector</li>
            <li onClick={() => handleViewChange('SAT_VIEW')}>Sat View</li>
            <li onClick={() => handleViewChange('KML_VIEWER')}>KML Viewer</li>
          </ul>
        </nav>
      </header>
      <main>
        {currentView === 'LOG_FILE_SELECTOR' && <LogFileSelectorComponent onStartLiveProcessing={startLiveProcessing} onStopLiveProcessing={stopLiveProcessing} />}
        {currentView === 'SAT_VIEW' && <SatelliteView />}
        {currentView === 'KML_VIEWER' && <KmlViewerComponent kmlFile={selectedKmlFile} />}
        {currentView === 'KML_VIEWER' && (
          <input
            type="file"
            accept=".kml"
            onChange={handleKmlFileChange}
            style={{
              position: 'absolute',
              top: '10px',
              right: '10px',
              zIndex: 1000,
              background: 'white',
              padding: '10px',
              borderRadius: '5px',
              boxShadow: '0 2px 10px rgba(0,0,0,0.2)',
            }}
          />
        )}
      </main>
    </div>
  );
}

export default App;
