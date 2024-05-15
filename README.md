# GNSS-Raw-Measurements
This repository contains code for processing GNSS (Global Navigation Satellite System) raw measurements, developed as part of the Ex0 assignment in the Autonomous Robotics course.

## Created By:
* [Shaked Levi](https://github.com/20shaked20)
* [Dana Zorohov](https://github.com/danaZo)
* [Yuval Bubnovsky](https://github.com/YuvalBubnovsky)

</br>

## Overview
The project consists of two main modules: </br></br>
**1. gnss_to_csv:** This module focuses on parsing GNSS measurements from a CSV file and preprocessing them for further analysis. It includes functions for formatting satellite IDs, filtering GPS satellites, converting columns to numeric representations, calculating timestamps, identifying epochs, and more.

**2. rms_positioning:** This module implements a positioning algorithm based on Root Mean Square (RMS) error minimization. It computes the receiver's position using observed and estimated pseudoranges, considering signal strength (CN0) or inverse Doppler shift for weighting. Additionally, it converts Earth-Centered Earth-Fixed (ECEF) coordinates to latitude, longitude, and altitude (LLA).
</br>
</br>

## Modules and Functions

- ```gnss_to_csv.py```:
    - parse_arguments: Handles command-line arguments for specifying the input file and data directory using the argparse library.
    - read_data: Reads GNSS measurements from a CSV file, distinguishing between 'Fix' and 'Raw' measurements.
    - preprocess_measurements: Preprocesses GNSS measurements, including formatting satellite IDs, filtering GPS satellites, converting columns to numeric representations, generating timestamps, identifying epochs, and calculating additional                                 parameters related to GNSS measurements.
    - calculate_satellite_position: Calculates the position of each satellite in ECEF coordinates based on ephemeris data and transmit time.
    - main: Initializes an EphemerisManager object, iterates over epochs in the measurements, calculates satellite positions, corrects measured pseudorange values, calculates Doppler shifts, and stores the processed data in a CSV file named         "gnss_measurements_output.csv". </br>
  </br>
- ```rms_positioning.py```:
  - parse_arguments: Parses command-line arguments for specifying the input CSV log file.
  - read_gnss_data: Reads GNSS data from a CSV file using the pandas library.
  - positioning_function: Computes the residuals between observed and estimated pseudoranges, weighted by signal strength (CN0) or inverse of Doppler shift.
  - solve_position_and_compute_rms: Uses the least_squares optimization routine to estimate the receiver's position and compute the RMS error.
  - lla_from_ecef: Converts ECEF coordinates to LLA using the navpy library.
  - process_satellite_data: Processes GNSS data, grouping it by GPS time and computing the receiver's position and RMS error for each epoch.
  - main: Parses command-line arguments, reads the GNSS data, processes it, and prints the results, including GPS time, estimated position (ECEF and LLA), and RMS error.
</br>
  
- ```gnss_processing.py```:
  - This is a simple wrapping python program. </br>
  - it calls the gnss_to_csv.py and then exectues the rms_positioning.py according to the output was given by gnss_to_csv.py. </br>
</br>


## Testing
To test the program, utilize the log files located in the "data" folder. These files were specifically chosen for testing purposes.


</br>

## How To Run
* Clone repositoy
* Navigate to the directory containing the cloned repository.
* Make sure you have installed ``requirements.txt`` - write in terminal -> ``pip install -r requirements.txt`` </br>
* Run the program ``gnss_processing.py``
* it will ask to input a file location: </br>
![image](https://github.com/20shaked20/GNSS-Raw-Measurements/assets/73894107/5fa65198-0bee-4e0a-9d3f-e5dd8002fa6c) </br>
  Make sure that the file is placed inside ``data`` folder and then copy its relative path to the cmd as presented above! </br>
  ![image](https://github.com/20shaked20/GNSS-Raw-Measurements/assets/73894107/46ed2c74-e3b6-4623-b92e-daea2a0eef3c)
* After doing that, the program will process the log and output 3 files: </br>
  1. ``gnss_measurments_output.csv`` - this file includes all the required data + lan,lot,alt columns at the end representing our location. </br>
  2. ``gnss_visualition.kml`` - a KML file that can be used to present the coordiantes of our trip visually. </br>
  3. ``Rms_Results.txt`` - we used this mainly for debbuging, but we kept it as it's a nice to have - presents some details about our calculations of RMS </br>

</br>
</br>

Some notes - 
- in case you want to run only rms_positioning.py or gnss_to_csv.py, you can do that,
- just make sure to follow the instructions as below:
  - first run gnss_to_csv.py, get the correct outputting csv (the name is important, as the rms_positoning using it to get the data), and then run the rms_positoning.
