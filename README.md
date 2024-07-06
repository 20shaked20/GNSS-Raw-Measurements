# GNSS-Raw-Measurements :satellite:
This repository contains code for processing GNSS (Global Navigation Satellite System) raw measurements, developed as part of the final assignment of the course Autonomous Robots.

## Created By:
* [Shaked Levi](https://github.com/20shaked20)
* [Dana Zorohov](https://github.com/danaZo)
* [Yuval Bubnovsky](https://github.com/YuvalBubnovsky)


## Overview :pushpin:
The project includes modules for processing GNSS measurements from raw data files, performing positioning calculations, and visualizing results. </br></br>

### Modules: :desktop_computer:
1. ```gnss_to_csv``` Parses GNSS raw measurements from CSV files and preprocesses data for analysis.
2. ```rms_positioning``` Computes the receiver's position using Root Mean Square (RMS) error minimization.
3. ```gnss_processing``` Orchestrates data processing flow between ```gnss_to_csv``` and ```rms_positioning``` modules.
4. ```gnss-data-viewer``` Web-based interface for visualizing GNSS data and KML files.
5. ```live_gnss_processing``` Implements live processing of GNSS data from connected Android devices, providing real-time analysis and visualization of satellite data.

More Information at our [Wiki](https://github.com/20shaked20/GNSS-Raw-Measurements/wiki)

</br>

## Testing :mag:
To test the program, utilize the log files located in the "data" folder. These files were specifically chosen for testing purposes.
</br></br>

## How To Run :joystick:
See at our wiki page [How To Run](https://github.com/20shaked20/GNSS-Raw-Measurements/wiki/How-To-Run)
</br></br>

## Topic Overview - for the main assignment of the course :flying_saucer:
The project focuses on expanding an initial task to develop a robust navigation system based on raw Global Navigation Satellite System (GNSS) measurements. The primary goal is to calculate real-time positions using an efficient and accurate algorithm. This system will incorporate advanced functionalities such as satellite filtering by constellation and signal strength, identification of "false" satellites, and handling disruptions. The project will also implement a disturbance detection algorithm to manage and mitigate the effects of disruptions.
</br>


