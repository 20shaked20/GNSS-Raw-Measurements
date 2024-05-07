# GNSS-Raw-Measurements
Ex0 in Autonomous Robotics course 
just some points, will be used as the base for the readme:
- Two different file types : NMEA, Rinex
- gnss parse for NMEA explanation:
  - parse_gpgsv: parsing GPSV (Satellites in View), extracting relevant info: PRN (ID), elevation, azimuth, signal-to-noise ratio (SNR), calc satellite's position coordinates.
  - parse_gngga: parsing GNGGA (Global Navigation Satellite System Fix Data), extracts GPS time.
  - parse_gngsa: parsing GNGSA (GPS DOP and Active Satellites), extracts satellite PRN and pseudo-range.
  - parse_gnrmc: parsing GNRMC (Recommended Minimum Specific GNSS Data) , extracts the Doppler value.
  - nmea_to_csv: writing the NMEA file data to CSV, each line parsed by it's type using the previous functions.
-  gnss parse for Rinex explanation:
  - iterating over each line in the file. If a line starts with '>', it extracts GPS time information from that line. If a line matches the regular expression ^[GREC][0-9]+, it extracts satellite data from that line. for each satellite data line exctracting satellite ID, XYZ coordinates, pseudo-range, and carrier-to-noise ratio (CN0) and writing all the data to CSV.
- The folder data holds the logs we extract
- gnssutils/ephemeris_manager: this script facilitates the retrieval, processing, and management of GNSS ephemeris data from FTP servers, providing functionalities to load and manipulate the data for further analysis or applications.
- gnss_to_csv:
    - parse_arguments: handle command-line arguments for specifying the input file and data directory. (using the library argparse)
    - read_data: Reads GNSS measurements from a CSV file, distinguishing between 'Fix' and 'Raw' measurements.
    - preprocess_measurements: Formats satellite IDs, filters GPS satellites, converts columns to numeric representations, generates GPS and Unix timestamps, identifies epochs based on time gaps, and calculates additional parameters related to GNSS measurements.
    - calculate_satellite_position: Calculates the position of each satellite in Earth-Centered Earth-Fixed (ECEF) coordinates based on ephemeris data and transmit time.
      - main: initializes an EphemerisManager object, iterates over epochs in the measurements, calculates satellite positions, corrects measured pseudorange values, calculates Doppler shifts, and stores the processed data in a CSV file named "gnss_measurements_output.csv".
- rms_positioning:
  - parse_arguments: argument parser handles cmd args for specifying the input CSV log file.
  - read_gnss_data: using pandas library to read csv file
  - positioning_function: computes the residuals between observed and estimated pseudoranges, weighted by signal strength (CN0) or inverse of Doppler shift.
  - solve_position_and_compute_rms:uses the least_squares optimization routine to estimate the receiver's position and compute the Root Mean Square (RMS) error.
  - lla_from_ecef: using navpy library, converts Earth-Centered Earth-Fixed (ECEF) coordinates to latitude, longitude, and altitude (LLA)
  - process_satellite_data: processes the GNSS data, grouping it by GPS time and computing the receiver's position and RMS error for each epoch.
  - main: parses command-line arguments, reads the GNSS data, processes it, and prints the results, including GPS time, estimated position (ECEF and LLA), and RMS error.
 
## How To Run
TODO
