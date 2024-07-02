//calcualtions are some ideas from - https://github.com/Stanford-NavLab/gnss_lib_py/blob/main/gnss_lib_py/visualizations/plot_skyplot.py

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import Papa from 'papaparse';
import Select from 'react-select';
import * as d3 from 'd3';

const colorMap = {
  'G': 'red',     // GPS
  'R': 'blue',    // GLONASS
  'E': 'green',   // Galileo
  'C': 'purple',  // Beidou
};

const SatelliteView = () => {
  const [satelliteData, setSatelliteData] = useState([]);
  const [filteredData, setFilteredData] = useState([]);
  const [selectedConstellations, setSelectedConstellations] = useState([]);
  const [showInactiveSatellites, setShowInactiveSatellites] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await axios.get('http://localhost:5000/gnss-data');
        const parsedData = Papa.parse(response.data, { header: true, skipEmptyLines: true }).data;

        const cleanedData = parsedData.map(row => ({
          ...row,
          SatX: parseFloat(row['SatX']),
          SatY: parseFloat(row['SatY']),
          SatZ: parseFloat(row['SatZ']),
          timestamp: new Date(row['GPS Time']).getTime(),
        }));

        const latestData = getLatestSatelliteData(cleanedData);
        setSatelliteData(latestData);
        setFilteredData(latestData);
      } catch (error) {
        console.error('Error fetching satellite data:', error);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5000); // Fetch data every 5 seconds

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    let data = satelliteData;
    if (selectedConstellations.length > 0) {
      data = data.filter(row => selectedConstellations.includes(row['Constellation']));
    }
    if (!showInactiveSatellites) {
      const currentTime = Date.now();
      data = data.filter(row => currentTime - row.timestamp <= 10000); // TTL - Keep only satellites active in the last 10 seconds 
    }
    setFilteredData(data);
  }, [selectedConstellations, satelliteData, showInactiveSatellites]);

  const handleFilterChange = (selectedOptions) => {
    const constellations = selectedOptions ? selectedOptions.map(option => option.value) : [];
    setSelectedConstellations(constellations);
  };

  const handleCheckboxChange = () => {
    setShowInactiveSatellites(!showInactiveSatellites);
  };

  const getLatestSatelliteData = (data) => {
    const latestDataMap = new Map();

    data.forEach(row => {
      const satID = row['SatPRN (ID)'];
      const timestamp = row.timestamp;
      if (!latestDataMap.has(satID) || timestamp > latestDataMap.get(satID).timestamp) {
        latestDataMap.set(satID, { ...row, timestamp });
      }
    });

    return Array.from(latestDataMap.values());
  };

  const calculateElAz = (satX, satY, satZ, recX, recY, recZ) => {
    const deltaX = satX - recX;
    const deltaY = satY - recY;
    const deltaZ = satZ - recZ;

    const horizDist = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
    const el = Math.atan2(deltaZ, horizDist) * (180 / Math.PI);
    const az = Math.atan2(deltaY, deltaX) * (180 / Math.PI);

    return { el, az };
  };

  const receiverState = { x: 0, y: 0, z: 0 }; // setting receiver state to the origin for simplicity

  const renderSatellites = () => {
    const maxRadius = 200; // Radius of the circle, this can be adjusted if we want a bigger circle 
    return filteredData.map((satellite, index) => {
      const { el, az } = calculateElAz(satellite.SatX, satellite.SatY, satellite.SatZ, receiverState.x, receiverState.y, receiverState.z);
      
      if (el < 0) {
        return null; // Ignore satellites below the horizon
      }
    
      
      const r = d3.scaleLinear().domain([0, 90]).range([maxRadius, 0])(el); // Elevation: 0 at edge, 90 at center
      const theta = d3.scaleLinear().domain([0, 360]).range([0, 2 * Math.PI])(az); // Azimuth

      const x = r * Math.cos(theta) + 250;
      const y = r * Math.sin(theta) + 250;
      const color = colorMap[satellite.Constellation] || 'black';

      let symbol;
      switch (satellite.Constellation) {
        case 'G':
          symbol = '▲'; // GPS
          break;
        case 'R':
          symbol = '■'; // GLONASS
          break;
        case 'E':
          symbol = '●'; // Galileo
          break;
        case 'C':
          symbol = '★'; // Beidou
          break;
        default:
          symbol = '✦'; // Default symbol
          break;
      }

      return (
        <React.Fragment key={index}>
          <text x={x} y={y} fontSize="25" textAnchor="middle" fill={color}>
            {symbol}
          </text>
          <text x={x + 10} y={y} fontSize="10" textAnchor="start" fill="black">
            {satellite['SatPRN (ID)']}
          </text>
        </React.Fragment>
      );
    });
  };

  const renderSatelliteList = () => {
    return (
      <ul>
        {filteredData.map((satellite, index) => (
          <li key={index} style={{ color: colorMap[satellite.Constellation] || 'black' }}>
            {satellite['SatPRN (ID)']} ({satellite.Constellation})
          </li>
        ))}
      </ul>
    );
  };

  const constellationOptions = [
    { value: 'G', label: 'GPS' },
    { value: 'R', label: 'GLONASS' },
    { value: 'E', label: 'Galileo' },
    { value: 'C', label: 'Beidou' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <div style={{ width: '100%' }}>
        <h1>Satellite View</h1>
        <Select
          isMulti
          options={constellationOptions}
          onChange={handleFilterChange}
          placeholder="Select constellations to filter"
        />
        <label>
          <input
            type="checkbox"
            checked={!showInactiveSatellites}
            onChange={handleCheckboxChange}
          />
          Time to leave (remove inactive satellites)
        </label>
      </div>
      <div style={{ width: '70%', marginTop: '20px' }}>
        <svg width="500" height="500">
          <circle cx="250" cy="250" r="200" stroke="black" strokeWidth="2" fill="none" />
          {renderSatellites()}
        </svg>
      </div>
      <div style={{ width: '70%', marginTop: '20px' }}>
        <h3>Visible Satellites</h3>
        {renderSatelliteList()}
      </div>
    </div>
  );
};

export default SatelliteView;
