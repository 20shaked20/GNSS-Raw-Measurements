// src/components/CSVReader.js
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useTable } from 'react-table';
import Papa from 'papaparse';
import Select from 'react-select';

const CSVReaderComponent = () => {
  const [data, setData] = useState([]);
  const [filteredData, setFilteredData] = useState([]);
  const [selectedConstellations, setSelectedConstellations] = useState([]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await axios.get('http://localhost:5000/gnss-data');
        console.log('Raw CSV Data:', response.data);  // Debugging log

        const parsedData = Papa.parse(response.data, { header: true, skipEmptyLines: true }).data;
        console.log('Parsed Data:', parsedData);  // Debugging log

        // Replace empty strings with null for better handling in the table and convert strings to numbers
        const cleanedData = parsedData.map(row => {
          Object.keys(row).forEach(key => {
            if (row[key] === '') {
              row[key] = null;
            } else if (['Sat.X', 'Sat.Y', 'Sat.Z'].includes(key)) {
              row[key] = parseFloat(row[key]);
            }
          });
          return row;
        });
        console.log('Cleaned Data:', cleanedData);  // Debugging log
        setData(cleanedData);
        setFilteredData(cleanedData);
      } catch (error) {
        console.error('Error fetching the CSV file:', error);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5000); // Fetch data every 5 seconds

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (selectedConstellations.length > 0) {
      const filtered = data.filter(row => selectedConstellations.includes(row['Constellation']));
      setFilteredData(filtered);
    } else {
      setFilteredData(data);
    }
  }, [selectedConstellations, data]);

  const handleFilterChange = (selectedOptions) => {
    const constellations = selectedOptions ? selectedOptions.map(option => option.value) : [];
    setSelectedConstellations(constellations);
  };

  const columns = React.useMemo(() => {
    if (filteredData.length > 0) {
      console.log('Columns:', Object.keys(filteredData[0]));  // Debugging log
      return Object.keys(filteredData[0]).map((key) => ({
        Header: key,
        accessor: key,
      }));
    }
    return [];
  }, [filteredData]);

  const tableInstance = useTable({ columns, data: filteredData });

  const { getTableProps, getTableBodyProps, headerGroups, rows, prepareRow } = tableInstance;

  const constellationOptions = [
    { value: 'G', label: 'GPS' },
    { value: 'R', label: 'GLONASS' },
    { value: 'E', label: 'Galileo' },
    { value: 'C', label: 'Beidou' },
    // Add other constellations as needed
  ];

  return (
    <div>
      <h1>GNSS Data Viewer</h1>
      <Select
        isMulti
        options={constellationOptions}
        onChange={handleFilterChange}
        placeholder="Select constellations to filter"
      />
      {filteredData.length > 0 ? (
        <table {...getTableProps()} style={{ border: 'solid 1px black', margin: '20px auto', borderCollapse: 'collapse' }}>
          <thead>
            {headerGroups.map(headerGroup => (
              <tr {...headerGroup.getHeaderGroupProps()}>
                {headerGroup.headers.map(column => (
                  <th {...column.getHeaderProps()} style={{ borderBottom: 'solid 3px red', background: 'aliceblue', color: 'black', fontWeight: 'bold' }}>
                    {column.render('Header')}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody {...getTableBodyProps()}>
            {rows.map(row => {
              prepareRow(row);
              return (
                <tr {...row.getRowProps()}>
                  {row.cells.map(cell => (
                    <td {...cell.getCellProps()} style={{ padding: '10px', border: 'solid 1px gray', background: 'papayawhip' }}>
                      {cell.value !== null && cell.value !== undefined ? cell.render('Cell') : ''}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : (
        <p>No data available</p>
      )}
    </div>
  );
};

export default CSVReaderComponent;
