# GNSS-Raw-Measurements :satellite:
This repository contains code for processing GNSS (Global Navigation Satellite System) raw measurements, developed as part of the final assignment of the course Autonomous Robots.

## Created By:
* [Shaked Levi](https://github.com/20shaked20)
* [Dana Zorohov](https://github.com/danaZo)
* [Yuval Bubnovsky](https://github.com/YuvalBubnovsky)


## Overview :pushpin:
GNSS-Raw-Measurements is a Python-based project for processing and analyzing raw GNSS (Global Navigation Satellite System) data. It includes tools for reading, preprocessing, positioning, spoofing detection, and satellite position calculation. </br></br>

## Features
- **Data Processing:** Processes raw GNSS measurements from CSV files.
- **Positioning:** Calculates satellite positions for GPS and GLONASS constellations.
- **Spoofing Detection:** Detects potential spoofing attempts using various algorithms.
- **Visualization:** Visualizes satellite positions and measurement anomalies.</br></br>


### Modules: :desktop_computer:
1. ```gnss_to_csv``` Parses GNSS raw measurements from CSV files and preprocesses data for analysis.
2. ```rms_positioning``` Computes the receiver's position using Root Mean Square (RMS) error minimization.
3. ```gnss_processing``` Orchestrates data processing flow between ```gnss_to_csv``` and ```rms_positioning``` modules.
4. ```gnss-data-viewer``` Web-based interface for visualizing GNSS data and KML files.
5. ```live_gnss_processing``` Implements live processing of GNSS data from connected Android devices, providing real-time analysis and visualization of satellite data.

More Information at our [Wiki](https://github.com/20shaked20/GNSS-Raw-Measurements/wiki)

</br>

## Visualization
### Main Page
![image](https://github.com/20shaked20/GNSS-Raw-Measurements/assets/93203695/cc1c93a9-996b-479d-a656-68d1847dbbbd)
- In this page, you can choose which processing mode you would like to use: online \ offline.
- You can select constellations to filter.
- You can see the csv output table of the processed gnss log file.
- At the upper part of the page, you can navigate to our other pages: Sat view and KML view.
- The current page is Log File Selector

### Offline Processing mode example
- When choosing the offline option you will get here:
![image](https://github.com/20shaked20/GNSS-Raw-Measurements/assets/93203695/ac03a49d-33e4-4436-add4-fc79f702117e)
- Now you can choose between the existed log files with "Select a file".
- After choosing a file and pressing on the processing button, this message will pop-up:
![image](https://github.com/20shaked20/GNSS-Raw-Measurements/assets/93203695/3ddf4ea4-af30-4895-881a-a2feb48d9118)
- Then the processed output will be displayed:
![image](https://github.com/20shaked20/GNSS-Raw-Measurements/assets/93203695/af80fd1a-793e-4e6c-aaf1-9111373adad8)

### Sat View Page
- in this page you can observe the satellites view
![image](https://github.com/20shaked20/GNSS-Raw-Measurements/assets/93203695/f3755d62-d8ed-4a23-901e-e9427640eef9)

### KML View Page
- In this page you can see the calculated location on a map
![image](https://github.com/20shaked20/GNSS-Raw-Measurements/assets/93203695/b7ef7be2-5851-468a-939f-e868ef8e1c3f)

### Example of our fixes kml:
![image](https://github.com/20shaked20/GNSS-Raw-Measurements/assets/93203695/64ea233d-3969-485e-8ba6-04af490c16c9)
- What we see on land, the black square is fix by NLP from android's cellular reception, surrounded by our GNSS calculations.
- What is on the sea, is the GPS jamming.

## Testing :mag:
To test the program, utilize the log files located in the "data" folder. These files were specifically chosen for testing purposes.
</br></br>

## How To Run :joystick:
See at our wiki page [How To Run](https://github.com/20shaked20/GNSS-Raw-Measurements/wiki/How-To-Run)
</br></br>

## Topic Overview - for the main assignment of the course :flying_saucer:
The project focuses on expanding an initial task to develop a robust navigation system based on raw Global Navigation Satellite System (GNSS) measurements. The primary goal is to calculate real-time positions using an efficient and accurate algorithm. This system will incorporate advanced functionalities such as satellite filtering by constellation and signal strength, identification of "false" satellites, and handling disruptions. The project will also implement a disturbance detection algorithm to manage and mitigate the effects of disruptions.
</br>


