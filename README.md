# GNSS-Raw-Measurements
Ex0 in Autonomous Robotics course 

## Created By:
* [Shaked Levi](https://github.com/20shaked20)
* [Dana Zorohov](https://github.com/danaZo)
* [Yuval Bubnovsky](https://github.com/YuvalBubnovsky)

## The Project:

- ```gnss_to_csv.py```:
    - parse_arguments: handle command-line arguments for specifying the input file and data directory. (using the library argparse)
    - read_data: Reads GNSS measurements from a CSV file, distinguishing between 'Fix' and 'Raw' measurements.
    - preprocess_measurements: Formats satellite IDs, filters GPS satellites, converts columns to numeric representations, generates GPS and Unix timestamps, identifies epochs based on time gaps, and calculates additional parameters related to GNSS measurements.
    - calculate_satellite_position: Calculates the position of each satellite in Earth-Centered Earth-Fixed (ECEF) coordinates based on ephemeris data and transmit time.
      - main: initializes an EphemerisManager object, iterates over epochs in the measurements, calculates satellite positions, corrects measured pseudorange values, calculates Doppler shifts, and stores the processed data in a CSV file named   gnss_measurements_output.csv". </br>
  </br>
- ```rms_positioning.py```:
  - parse_arguments: argument parser handles cmd args for specifying the input CSV log file.
  - read_gnss_data: using pandas library to read csv file
  - positioning_function: computes the residuals between observed and estimated pseudoranges, weighted by signal strength (CN0) or inverse of Doppler shift.
  - solve_position_and_compute_rms:uses the least_squares optimization routine to estimate the receiver's position and compute the Root Mean Square (RMS) error.
  - lla_from_ecef: using navpy library, converts Earth-Centered Earth-Fixed (ECEF) coordinates to latitude, longitude, and altitude (LLA)
  - process_satellite_data: processes the GNSS data, grouping it by GPS time and computing the receiver's position and RMS error for each epoch.
  - main: parses command-line arguments, reads the GNSS data, processes it, and prints the results, including GPS time, estimated position (ECEF and LLA), and RMS error.
</br>
  
- ```gnss_processing.py```:
  - This is a simple wrapping python program. </br>
  - it calls the gnss_to_csv.py and then exectues the rms_positioning.py according to the output was given by gnss_to_csv.py. </br>
 
## How To Run
* Clone repositoy
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
