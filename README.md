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
