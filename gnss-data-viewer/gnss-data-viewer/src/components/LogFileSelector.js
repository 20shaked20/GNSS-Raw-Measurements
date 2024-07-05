// src/components/LogFileSelector.js
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import CSVReaderComponent from './CSVReader';

const LogFileSelector = () => {
  const [logFiles, setLogFiles] = useState([]);
  const [selectedFile, setSelectedFile] = useState('');
  const [processingMode, setProcessingMode] = useState('online');

  useEffect(() => {
    const fetchLogFiles = async () => {
      try {
        const response = await axios.get('http://localhost:5000/log-files');
        setLogFiles(response.data);
      } catch (error) {
        console.error('Error fetching log files:', error);
      }
    };

    fetchLogFiles();
  }, []);

  const handleFileSelection = (event) => {
    const fileName = event.target.value;
    setSelectedFile(fileName);
  };

  const handleRunProcessing = async () => {
    try {
      if (processingMode === 'online') {
        await axios.post('http://localhost:5000/run-live-gnss');
      } else if (processingMode === 'offline' && selectedFile) {
        await axios.post('http://localhost:5000/run-gnss', { fileName: selectedFile });
      }
      alert('Processing started');
    } catch (error) {
      console.error('Error running processing:', error);
    }
  };

  return (
    <div>
      <h2>Select Processing Mode</h2>
      <div>
        <input
          type="radio"
          id="online"
          name="processingMode"
          value="online"
          checked={processingMode === 'online'}
          onChange={() => setProcessingMode('online')}
        />
        <label htmlFor="online">Online</label>
        <input
          type="radio"
          id="offline"
          name="processingMode"
          value="offline"
          checked={processingMode === 'offline'}
          onChange={() => setProcessingMode('offline')}
        />
        <label htmlFor="offline">Offline</label>
      </div>

      {processingMode === 'offline' && (
        <>
          <h2>Select a Log File</h2>
          <select value={selectedFile} onChange={handleFileSelection}>
            <option value="">Select a file</option>
            {logFiles.map((file, index) => (
              <option key={index} value={file}>
                {file}
              </option>
            ))}
          </select>
        </>
      )}

      <button onClick={handleRunProcessing}>Run Processing</button>

      {(processingMode === 'online' || (processingMode === 'offline' && selectedFile)) && (
        <CSVReaderComponent />
      )}
    </div>
  );
};

export default LogFileSelector;
