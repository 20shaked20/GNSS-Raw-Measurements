// server/server.js
const express = require('express');
const cors = require('cors');
const path = require('path');

const app = express();
const PORT = 5000;

app.use(cors());

app.get('/gnss-data', (req, res) => {
  res.sendFile(path.join(__dirname, '../gnss_measurements_output.csv'));
});

app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});
