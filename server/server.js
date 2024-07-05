const express = require('express');
const cors = require('cors');
const path = require('path');
const bodyParser = require('body-parser');
const fs = require('fs');
const { spawn, execSync } = require('child_process');

const app = express();
const PORT = 5000;

let liveProcess = null;

app.use(cors());
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));

app.get('/gnss-data', (req, res) => {
  res.sendFile(path.join(__dirname, '../gnss_measurements_output.csv'));
});

app.get('/log-files', (req, res) => {
  const logsDirectory = path.join(__dirname, '../data');
  fs.readdir(logsDirectory, (err, files) => {
    if (err) {
      res.status(500).json({ error: 'Unable to list log files' });
      return;
    }
    const logFiles = files.filter(file => file.endsWith('.txt'));
    res.json(logFiles);
  });
});

app.post('/run-gnss', (req, res) => {
  const logFileName = req.body.fileName;
  if (!logFileName) {
    res.status(400).json({ error: 'No file name provided' });
    return;
  }

  const pythonExecutable = execSync('python3 -c "import sys; print(sys.executable)"').toString().trim();
  const process = spawn(pythonExecutable, ['gnss_processing.py'], { cwd: path.join(__dirname, '../') });
  const filePath = path.join(__dirname, '../data', logFileName);

  process.stdout.on('data', (data) => {
    console.log(`stdout: ${data}`);
    if (data.toString().includes('Enter the GNSS log file name: ')) {
      process.stdin.write(filePath + '\n');
    }
  });

  process.stderr.on('data', (data) => {
    console.error(`stderr: ${data}`);
  });

  process.on('close', (code) => {
    if (code !== 0) {
      res.status(500).json({ error: `gnss_processing.py process exited with code ${code}` });
    } else {
      const csvFilePath = path.join(__dirname, '../gnss_measurements_output.csv');
      fs.access(csvFilePath, fs.constants.F_OK, (err) => {
        if (err) {
          res.status(500).json({ error: 'Failed to find generated CSV file' });
        } else {
          res.json({ message: 'Processing completed successfully' });
        }
      });
    }
  });
});

app.post('/run-live-gnss', (req, res) => {
  const pythonExecutable = execSync('python3 -c "import sys; print(sys.executable)"').toString().trim();
  liveProcess = spawn(pythonExecutable, ['live_gnss_processing.py'], { cwd: path.join(__dirname, '../') });

  liveProcess.stdout.on('data', (data) => {
    console.log(`stdout: ${data}`);
  });

  liveProcess.stderr.on('data', (data) => {
    console.error(`stderr: ${data}`);
  });

  liveProcess.on('close', (code) => {
    if (code !== 0) {
      console.error(`live_gnss_processing.py process exited with code ${code}`);
    }
  });

  res.json({ message: 'Live processing started' });
});

app.post('/stop-live-gnss', (req, res) => {
  if (liveProcess) {
    liveProcess.kill();
    liveProcess = null;
    res.json({ message: 'Live processing stopped' });
  } else {
    res.status(400).json({ error: 'No live processing running' });
  }
});

app.get('/live-kml', (req, res) => {
  res.sendFile(path.join(__dirname, '../gnss_visualization.kml'));
});

app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});
