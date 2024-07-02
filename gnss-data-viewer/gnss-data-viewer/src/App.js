// src/App.js
import React from 'react';
import './App.css';
// import CSVReaderComponent from './components/CSVReader';
import LogFileSelectorComponent from './components/LogFileSelector';

function App() {
  return (
    <div className="App">
      {/* <CSVReaderComponent /> */}
      <LogFileSelectorComponent />
    </div>
  );
}

export default App;
