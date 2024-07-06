# GNSS-Raw-Measurements :satellite:
This repository contains code for processing GNSS (Global Navigation Satellite System) raw measurements, developed as part of the final assignment of the course Autonomous Robots.

## Created By:
* [Shaked Levi](https://github.com/20shaked20)
* [Dana Zorohov](https://github.com/danaZo)
* [Yuval Bubnovsky](https://github.com/YuvalBubnovsky)


## Overview :pushpin:
The project includes modules for processing GNSS measurements from raw data files, performing positioning calculations, and visualizing results. </br></br>

### Modules:
1. ```gnss_to_csv``` Parses GNSS raw measurements from CSV files and preprocesses data for analysis.
2. ```rms_positioning``` Computes the receiver's position using Root Mean Square (RMS) error minimization.
3. ```gnss_processing``` Orchestrates data processing flow between ```gnss_to_csv``` and ```rms_positioning``` modules.
4. ```gnss-data-viewer``` Web-based interface for visualizing GNSS data and KML files.
5. ```live_gnss_processing``` Implements live processing of GNSS data from connected Android devices, providing real-time analysis and visualization of satellite data.


### Functions :desktop_computer:
  
#### gnss_to_csv.py:
- `parse_arguments`: Handles command-line arguments for specifying the input file and data directory using the argparse library.
- `read_data`: Reads GNSS measurements from a CSV file, distinguishing between 'Fix' and 'Raw' measurements.
- `preprocess_measurements`: Preprocesses GNSS measurements, including formatting satellite IDs, filtering GPS satellites, converting columns to numeric representations, generating timestamps, identifying epochs, and calculating additional parameters related to GNSS measurements.
- `calculate_satellite_position`: Calculates the position of each satellite in ECEF coordinates based on ephemeris data and transmit time.
- `main`: Initializes an EphemerisManager object, iterates over epochs in the measurements, calculates satellite positions, corrects measured pseudorange values, calculates Doppler shifts, and stores the processed data in a CSV file named "gnss_measurements_output.csv".

#### rms_positioning.py:
- `parse_arguments`: Parses command-line arguments for specifying the input CSV log file.
- `read_gnss_data`: Reads GNSS data from a CSV file using the pandas library.
- `positioning_function`: Computes the residuals between observed and estimated pseudoranges, weighted by signal strength (CN0) or inverse of Doppler shift.
- `solve_position_and_compute_rms`: Uses the least_squares optimization routine to estimate the receiver's position and compute the RMS error.
- `lla_from_ecef`: Converts ECEF coordinates to LLA using the navpy library.
- `process_satellite_data`: Processes GNSS data, grouping it by GPS time and computing the receiver's position and RMS error for each epoch.
- `main`: Parses command-line arguments, reads the GNSS data, processes it, and prints the results, including GPS time, estimated position (ECEF and LLA), and RMS error.
  
#### gnss_processing.py:
This is a simple wrapping python program.</br>
It calls the `gnss_to_csv.py` and then executes the `rms_positioning.py` according to the output given by `gnss_to_csv.py`.

#### live_gnss_processing.py:
- `parse_arguments`: Parses command-line arguments for specifying the input device and output directory.
- `initialize_device`: Sets up the connection to the Android device using adb.
- `record_gnss_data`: Records live GNSS data from the connected Android device and stores it in a specified directory.
- `process_live_data`: Processes the recorded live GNSS data using `gnss_to_csv` and `rms_positioning` modules.
- `main`: Initializes the device, records live data, and processes it.

#### gnss-data-viewer Directory:
This directory contains a React-based web application for visualizing GNSS data.
- `App.js`: Main application file that handles view changes and renders components based on user interactions.
- `App.css`: Styling for the web application.

#### components Directory:
- `CSVReader.js`: Fetches GNSS data, parses the CSV file, and displays it in a table with filtering options for different constellations.
- `LogFileSelector.js`: Provides an interface for selecting log files for processing.
- `SatelliteView.js`: Visualizes satellite positions.
- `KmlViewerComponent.js`: Renders KML files for geographic visualization.

#### gnssutils Directory:
- `android_adb_utils.py`: Utility functions for interacting with Android devices using adb.
- `constants.py`: Defines constants used across multiple modules.
- `ephemeris_manager.py`: Manages ephemeris data for satellite position calculations.

#### Data Directory:
This directory contains GNSS log files categorized into good recordings and spoof recordings.

- Good Recordings:
  - gnss_log_2024_04_13_19_51_17.txt
  - gnss_log_2024_04_13_19_52_00.txt
  - gnss_log_2024_04_13_19_53_33.txt
- Spoof Recordings:
  - Beirut.txt
  - Beirut2.txt
  - Cairo.txt

#### Android Platform Tools Directory:
This directory contains tools for connecting Android devices to a PC to record live GNSS data.
</br></br>


## Testing :mag:
To test the program, utilize the log files located in the "data" folder. These files were specifically chosen for testing purposes.
</br>

## How To Run :joystick:
* Clone repositoy
* Navigate to the directory containing the cloned repository.
  
> [!NOTE]
> It is very recommended to create a virtual environment for this project.

* How to Create a Python virtual environment (venv) where you install required packages:
* In the terminal, navigate to the project directory if you're not already there. You can use the `cd` command to change directories.
* Run the following command to create a virtual environment. You can name it anything, but venv is a common choice:
```
python -m venv venv
```
* Activate the Virtual Environment: Use the Activate script directly from the virtual environment's Scripts folder.
```
python3 -m venv myenv
source myenv/bin/activate  # Activate the virtual environment on Unix/macOS
```
For Windows:
```
myenv\Scripts\activate
```
* Once activated, you should see the name of your virtual environment in the terminal prompt, indicating that the environment is active.
* Install Dependencies: With the virtual environment activated, install the necessary packages:
```
pip install -r requirements.txt
```

### Running gnss_processing.py:
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

> [!NOTE]
> in case you want to run only rms_positioning.py or gnss_to_csv.py, you can do that, just make sure to follow the instructions: first run gnss_to_csv.py, get the correct outputting csv (the name is important, as the rms_positoning using it to get the data), and then run the rms_positoning.

### Running live_gnss_processing.py:
* Connect your Android device to your PC using a USB cable.
* Enable USB debugging on your Android device.
* Make sure you have the Android Platform Tools installed and accessible in your PATH.
* Run `live_gnss_processing.py` with the required arguments:
```
python live_gnss_processing.py --device <device_serial> --output_dir <output_directory>
```
  - Replace <device_serial> with your Android device's serial number and <output_directory> with the directory where you want to save the recorded data.
* The script will record live GNSS data from your device and process it.

### Running the UI:
* Navigate to the GNSS-RAW-MEASUREMENTS/gnss-data-viewer/gnss-data-viewer directory.
* Install the required dependencies:
```
npm install  
```
* On Linux OS, run the command:
```
export NODE_OPTIONS=--openssl-legacy-provider
```
* On Windows OS, run the command:
```
$env:NODE_OPTIONS="--openssl-legacy-provider"
```
* Start the fronted React:
```
npm start
```
* Open an additional terminal to run the server.
* Navigate to the GNSS-RAW-MEASUREMENTS/server directory.
* Install the required dependencies:
```
npm install  
```
* Start the development server:
```
node server.js
```
* Open your web browser and go to http://localhost:3000 to view the application.
* Use the UI to select log files, view satellite data, and visualize KML files.
</br></br>

## Topic Overview - for the main assignment of the course :flying_saucer:
The project focuses on expanding an initial task to develop a robust navigation system based on raw Global Navigation Satellite System (GNSS) measurements. The primary goal is to calculate real-time positions using an efficient and accurate algorithm. This system will incorporate advanced functionalities such as satellite filtering by constellation and signal strength, identification of "false" satellites, and handling disruptions. The project will also implement a disturbance detection algorithm to manage and mitigate the effects of disruptions.
</br>

## Previous Works :artificial_satellite:
Previous works in the field of GNSS-based navigation systems have laid the foundation for this project. Early GNSS systems primarily focused on providing basic positioning services using pseudorange measurements from satellites. Over time, the introduction of advanced algorithms, such as those leveraging least squares optimization, has improved the accuracy and reliability of GNSS positioning.
</br>
Several studies have explored methods for filtering satellites based on various criteria, including signal strength (Carrier-to-Noise density ratio, CN0) and constellation (e.g., GPS, GLONASS, Galileo). Techniques for identifying and mitigating the impact of multipath and "false" satellites have also been investigated, aiming to enhance the reliability of GNSS measurements in challenging environments.
</br>
Furthermore, the detection and handling of disruptions, such as those caused by intentional jamming or environmental factors, have been critical areas of research. Algorithms for disturbance detection and mitigation, including those that can distinguish between genuine signal anomalies and intentional interference, have been developed to ensure the robustness of GNSS-based navigation systems.
</br>
By building on these previous works, this project aims to create a comprehensive navigation system capable of real-time position calculation, effective satellite filtering, and robust handling of disruptions, providing a significant advancement in GNSS-based navigation technology.
</br>

## References :paperclip:
1. **Advanced GNSS Algorithms for Real-Time Positioning** - A special issue of Remote Sensing focuses on GNSS advanced positioning algorithms and innovative applications. It covers topics related to precise point positioning (PPP), real-time kinematic (RTK) schemes, low-cost GNSS, and more. </br>
- [Performance of Smartphone BDS-3/GPS/Galileo Multi-Frequency Ionosphere-Free Precise Code Positioning](https://www.mdpi.com/2072-4292/15/22/5371)   - Wang, R., Hu, C., Wang, Z., Yuan, F., & Wang, Y. (2023). Remote Sens., 15(22), 5371. School of Environmental and Spatial Informatics, China University of Mining and Technology, Xuzhou, China; School of Spatial Information and Geomatics Engineering, Anhui University of Science and Technology, Huainan, China; Qianxun Spatial Intelligence Inc., Shanghai, China. </br>
- [Signal Occlusion-Resistant Satellite Selection for Global Navigation Applications Using Large-Scale LEO Constellations](https://www.mdpi.com/2072-4292/15/20/4978) - Guo, J., Wang, Y., & Sun, C. (2023). Remote Sens., 15(20), 4978. The School of Electronics and Information Engineering, Harbin Institute of Technology (Shenzhen), Shenzhen, China.</br>
- [PPP-RTK with Rapid Convergence Based on SSR Corrections and Its Application in Transportation
](https://www.mdpi.com/2072-4292/15/19/4770) - An, X., Ziebold, R., & Lass, C. (2023). Remote Sens., 15(19), 4770. Institute of Communications and Navigation, German Aerospace Center (DLR), Neustrelitz, Germany. </br>
- [Joint Retrieval of Sea Surface Rainfall Intensity, Wind Speed, and Wave Height Based on Spaceborne GNSS-R: A Case Study of the Oceans near China](https://www.mdpi.com/2072-4292/15/11/2757) - Bu, J., Yu, K., Zhu, F., Zuo, X., & Huang, W. (2023). Remote Sens., 15(11), 2757. Faculty of Land Resources Engineering, Kunming University of Science and Technology, Kunming, China; School of Environment Science and Spatial Informatics, China University of Mining and Technology, Xuzhou, China; Department of Electrical and Computer Engineering, Memorial University of Newfoundland, St. John’s, Canada. </br>
- [Improving Smartphone GNSS Positioning Accuracy Using Inequality Constraints](https://www.mdpi.com/2072-4292/15/8/2062) - Peng, Z., Gao, Y., Gao, C., Shang, R., & Gan, L. (2023). Remote Sens., 15(8), 2062. School of Transportation, Southeast University, Nanjing, China; Department of Geomatics Engineering, University of Calgary, Calgary, Canada.</br>
- [Robust GNSS Positioning Using Unbiased Finite Impulse Response Filter](https://www.mdpi.com/2072-4292/15/18/4528) - Dou, J., Xu, B., & Dou, L. (2023). Remote Sens., 15(18), 4528. School of National Key Laboratory of Transient Physics, Nanjing University of Science and Technology, Nanjing, China; Department of Aeronautical and Aviation Engineering, The Hong Kong Polytechnic University, Kowloon, Hong Kong, China.</br>
   
2. **Satellite Filtering Techniques in GNSS Systems** - An article discusses different GNSS data filtering techniques and compares linear and non-linear time series solutions. It explores methods for improving GNSS positioning accuracy by mitigating multipath effects.
- [Analysis of Different GNSS Data Filtering Techniques and Comparison of Linear and Non-Linear Times Series Solutions: Application to GNSS Stations in Central America for Regional Geodynamic Model Determination](https://www.mdpi.com/2673-4591/5/1/29) - Ramírez-Zelaya, J., Rosado, B., Barba, P., Gárate, J., & Berrocoso, M. (2021). Eng. Proc. 2021, 5(1), 29. Laboratorio de Astronomía, Geodesia y Cartografía, Departamento de Matemáticas, Facultad de Ciencias, Campus de Puerto Real, Universidad de Cádiz, Puerto Real, Spain. </br>
  
3. **Multipath Mitigation Strategies in GNSS** - Research investigates multipath mitigation in GNSS precise point positioning (PPP) using multipath hierarchy (MH) for changing environments. The proposed method improves positioning accuracy and residual reduction. </br>
- [Multipath mitigation in GNSS precise point positioning using multipath hierarchy for changing environments](https://link.springer.com/article/10.1007/s10291-023-01531-4) - Yuan, H., Zhang, Z., He, X., Dong, Y., Zeng, J., & Li, B. (2023). Original Article. Published: 28 August 2023, Volume 27, article number 193.   </br>

4. **Detection and Mitigation of GNSS Signal Disruptions** - A thesis explores techniques for detecting, characterizing, and mitigating GNSS jamming interference using pre-correlation methods. It addresses the impact of civil jammers on GPS receivers. </br>
[Detection and mitigation of non-authentic GNSS signals: Preliminary sensitivity analysis of receiver tracking loops](https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=6423121) - Parro-Jimenez, J. M., Ioannides, R. T., Crisci, M., & López-Salcedo, J. A. (2023). TEC-ETN ESA/ESTEC, European Space Agency, Noordwijk, The Netherlands; SPCOMNAV Engineering School, Universitat Autonoma de Barcelona, Bellaterra, Spain. 
