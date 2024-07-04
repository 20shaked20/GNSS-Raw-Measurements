"""
GNSS Data Processing Script

This script processes multi-GNSS CSV log files for positioning and spoofing detection. It includes functions to read GNSS data,
perform positioning calculations, detect spoofing, and output results in various formats including KML and text files.

Functions:
- parse_arguments(): Parses command-line arguments for input and output file paths.
- read_gnss_data(filepath): Reads GNSS data from a CSV file into a pandas DataFrame.
- positioning_function(x, sat_positions, observed_pseudoranges, weights): Calculates residuals between observed and estimated pseudoranges.
- raim_algorithm(sat_positions, pseudoranges, weights, confidence_level): Performs Receiver Autonomous Integrity Monitoring (RAIM) to detect faults.
- solve_position_and_compute_rms(sat_positions, pseudoranges, weights): Solves for receiver position and computes RMS error.
- ecef_to_lla(ecef_coords): Converts ECEF coordinates to LLA (Latitude, Longitude, Altitude).
- detect_spoofing(group, residuals, rms, lla): Detects spoofing based on RMS error and satellite data consistency.
- process_epoch(gps_time, group, kml, previous_position): Processes data for a single epoch to compute position and detect spoofing.
- process_satellite_data(data, kml_output_path): Processes GNSS data and generates KML visualization.
- save_results_to_text(results, output_txt): Saves RMS results and spoofing information to a text file.
- add_position_data_to_csv(results, input_csv, output_csv): Adds computed position data to the original CSV file.

"""

import argparse
import traceback
import pandas as pd
import numpy as np
from scipy.optimize import least_squares
import navpy
import simplekml
import logging
from scipy.stats import chi2

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_arguments():
    """
    Parses command-line arguments for input and output file paths.

    Returns:
        args (argparse.Namespace): Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description='Process multi-GNSS CSV log files for positioning and spoofing detection.')
    parser.add_argument('--input_file', type=str, default='gnss_measurements_output.csv', help='Input CSV file')
    parser.add_argument('--output_kml', type=str, default='gnss_visualization.kml', help='Output KML file')
    parser.add_argument('--output_txt', type=str, default='RmsResults.txt', help='Output RMS results text file')
    return parser.parse_args()

def read_gnss_data(filepath):
    """
    Reads GNSS data from a CSV file into a pandas DataFrame.

    Args:
        filepath (str): Path to the input CSV file.

    Returns:
        pd.DataFrame: DataFrame containing GNSS measurements.
    """
    return pd.read_csv(filepath)

def positioning_function(x, sat_positions, observed_pseudoranges, weights):
    """
    Calculates residuals between observed and estimated pseudoranges.

    Args:
        x (np.array): Estimated receiver position.
        sat_positions (np.array): Array of satellite positions.
        observed_pseudoranges (np.array): Array of observed pseudoranges.
        weights (np.array): Array of weights for each satellite measurement.

    Returns:
        np.array: Weighted residuals.
    """
    estimated_ranges = np.sqrt(((sat_positions - x)**2).sum(axis=1))
    residuals = estimated_ranges - observed_pseudoranges
    return weights * residuals

#TODO: better naming here
def raim_algorithm(sat_positions, pseudoranges, weights, confidence_level=0.95):
    """
    Performs Receiver Autonomous Integrity Monitoring (RAIM) to detect faults in satellite measurements.
    https://en.wikipedia.org/wiki/Receiver_autonomous_integrity_monitoring

    Args:
        sat_positions (np.array): Array of satellite positions.
        pseudoranges (np.array): Array of observed pseudoranges.
        weights (np.array): Array of weights for each satellite measurement.
        confidence_level (float): Confidence level for RAIM detection.

    Returns:
        tuple: Estimated receiver position and list of excluded satellites.
    """
    num_satellites = len(sat_positions)
    degrees_of_freedom = num_satellites - 4
    threshold = chi2.ppf(confidence_level, degrees_of_freedom)

    # Initial position calculation
    initial_guess = np.mean(sat_positions, axis=0)
    res = least_squares(positioning_function, initial_guess, args=(sat_positions, pseudoranges, weights))
    position = res.x
    residuals = positioning_function(position, sat_positions, pseudoranges, weights)
    test_statistic = np.sum(residuals**2)

    if test_statistic < threshold:
        return position, []

    excluded_satellites = []
    for i in range(len(sat_positions)):
        temp_sat_positions = np.delete(sat_positions, i, axis=0)
        temp_pseudoranges = np.delete(pseudoranges, i)
        temp_weights = np.delete(weights, i)
        temp_position = least_squares(positioning_function, initial_guess, args=(temp_sat_positions, temp_pseudoranges, temp_weights)).x
        temp_residuals = positioning_function(temp_position, temp_sat_positions, temp_pseudoranges, temp_weights)
        temp_test_statistic = np.sum(temp_residuals**2)

        if temp_test_statistic < test_statistic:
            position = temp_position
            test_statistic = temp_test_statistic
            excluded_satellites = [i]

    return position, excluded_satellites

def solve_position_and_compute_rms(sat_positions, pseudoranges, weights):
    """
    Solves for receiver position and computes RMS error of pseudoranges.

    Args:
        sat_positions (np.array): Array of satellite positions.
        pseudoranges (np.array): Array of observed pseudoranges.
        weights (np.array): Array of weights for each satellite measurement.

    Returns:
        tuple: Estimated receiver position, RMS error, and list of excluded satellites.
    """
    if not (np.all(np.isfinite(sat_positions)) and np.all(np.isfinite(pseudoranges))):
        raise ValueError("Satellite positions and pseudoranges must be finite.")
    
    position, excluded_satellites = raim_algorithm(sat_positions, pseudoranges, weights)
    residuals = positioning_function(position, sat_positions, pseudoranges, weights)
    rms = np.sqrt(np.mean(residuals**2))
    return position, rms, excluded_satellites

def ecef_to_lla(ecef_coords):
    """
    Converts ECEF coordinates to LLA (Latitude, Longitude, Altitude).

    Args:
        ecef_coords (np.array): ECEF coordinates.

    Returns:
        np.array: LLA coordinates.
    """
    return navpy.ecef2lla(ecef_coords, latlon_unit='deg')

def detect_spoofing(group, residuals, rms, lla):
    """
    Detects spoofing based on RMS error and satellite data consistency.

    Args:
        group (pd.DataFrame): DataFrame containing satellite measurements for a single epoch.
        residuals (np.array): Residuals between observed and estimated pseudoranges.
        rms (float): Root mean square error of pseudoranges.
        lla (np.array): Latitude, Longitude, and Altitude of the estimated position.

    Returns:
        tuple: List of spoofed satellites and the reason for spoofing detection.
    """
    spoofed_satellites = []
    
    if rms > 2000:
        spoofed_satellites.extend(group['SatPRN (ID)'].tolist())
        return spoofed_satellites, "High RMS"
    
    # Check for unreasonable altitude
    if lla[2] < -1000 or lla[2] > 100000:  # -1km to 100km range
        spoofed_satellites.extend(group['SatPRN (ID)'].tolist())
        return spoofed_satellites, "Unreasonable altitude"
    
    # Individual satellite checks using Z-scores
    z_scores = np.abs((residuals - np.mean(residuals)) / np.std(residuals))
    threshold = 3 
    spoofed_indices = np.where(z_scores > threshold)[0]
    spoofed_satellites.extend(group.iloc[spoofed_indices]['SatPRN (ID)'].tolist())
    
    return spoofed_satellites, "Individual satellite anomalies" if spoofed_satellites else "No spoofing detected"

def process_epoch(gps_time, group, kml, previous_position):
    """
    Processes data for a single epoch to compute position and detect spoofing.

    Args:
        gps_time (str): GPS time of the epoch.
        group (pd.DataFrame): DataFrame containing satellite measurements for the epoch.
        kml (simplekml.Kml): KML object for visualization.
        previous_position (np.array): Previous estimated position for detecting sudden jumps.

    Returns:
        dict: Results including position, RMS error, spoofed satellites, and reason for spoofing detection.
    """
    gps_time_dt = pd.to_datetime(gps_time)
    sat_positions = group[['SatX', 'SatY', 'SatZ']].values
    pseudoranges = group['Pseudo-Range'].values
    cn0 = group['CN0'].values
    doppler = group['Doppler'].values
    
    if len(sat_positions) < 4:
        raise ValueError("Not enough valid satellite data for position calculation.")

    weights = np.where(np.isnan(doppler), 1 / (cn0 + 1e-6), cn0 / (np.abs(doppler) + 1e-6))
    weights /= weights.sum()
    
    position, rms, excluded_satellites = solve_position_and_compute_rms(sat_positions, pseudoranges, weights)
    lla = ecef_to_lla(position)
    
    pnt = kml.newpoint(name=f"{gps_time}", coords=[(lla[1], lla[0], lla[2])])
    pnt.timestamp.when = gps_time_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Detect spoofing
    estimated_ranges = np.sqrt(((sat_positions - position)**2).sum(axis=1))
    residuals = estimated_ranges - pseudoranges

    all_satellites = group['SatPRN (ID)'].tolist()
    spoofed_satellites, spoofing_reason = detect_spoofing(group, residuals, rms, lla)
    
    # Check for sudden position jumps
    if previous_position is not None:
        distance = np.linalg.norm(position - previous_position)
        if distance > 1000:  # 1km threshold, adjust as needed
            spoofed_satellites = group['SatPRN (ID)'].tolist()
            spoofing_reason = "Sudden position jump"
    
    return {
        'GPS Time': gps_time,
        'Estimated Position ECEF': position,
        'Estimated Position LLA': lla,
        'RMS': rms,
        'Spoofed Satellites': spoofed_satellites,
        'Non_spoofed Satellites': [sat for sat in all_satellites if sat not in spoofed_satellites],
        'Excluded Satellites': [all_satellites[i] for i in excluded_satellites],
        'Spoofing Reason': spoofing_reason
    }

def process_satellite_data(data, kml_output_path):
    """
    Processes GNSS data and generates KML visualization.

    Args:
        data (pd.DataFrame): DataFrame containing GNSS measurements.
        kml_output_path (str): Path to the output KML file.

    Returns:
        list: List of results for each epoch.
    """
    grouped = data.groupby('GPS Time')
    results = []
    kml = simplekml.Kml()
    previous_position = None
    
    for gps_time, group in grouped:
        try:
            result = process_epoch(gps_time, group, kml, previous_position)
            results.append(result)
            previous_position = result['Estimated Position ECEF']
        except ValueError as e:
            logging.error(f"Skipping epoch at {gps_time} due to error: {e}")
    
    kml.save(kml_output_path)
    logging.info(f"{kml_output_path} File Is Created! \n")
    
    return results

def save_results_to_text(results, output_txt):
    """
    Saves RMS results and spoofing information to a text file.

    Args:
        results (list): List of results for each epoch.
        output_txt (str): Path to the output text file.
    """
    logging.info("Saving to RmsResults.txt... \n")
    with open(output_txt, 'w') as f:
        for result in results:
            f.write(f"GPS Time: {result['GPS Time']}\n")
            f.write(f"Estimated Position ECEF (X, Y, Z): {result['Estimated Position ECEF']}\n")
            f.write(f"Estimated Position LLA (Lat, Lon, Alt): {result['Estimated Position LLA']}\n")
            f.write(f"RMS: {result['RMS']}\n")
            f.write(f"Spoofing Detected: {'Yes' if result['Spoofed Satellites'] else 'No'}\n")
            f.write(f"Spoofing Reason: {result['Spoofing Reason']}\n")
            
            all_satellites = set(result['Spoofed Satellites']) | set(result.get('Non_spoofed Satellites', []))
            non_spoofed_satellites = all_satellites - set(result['Spoofed Satellites'])
            
            f.write(f"Spoofed Satellites: {', '.join(map(str, result['Spoofed Satellites']))}\n")
            f.write(f"Non-spoofed Satellites: {', '.join(map(str, non_spoofed_satellites))}\n")
            f.write(f"Excluded Satellites: {', '.join(map(str, result['Excluded Satellites']))}\n")
            f.write("-" * 50 + "\n")

def add_position_data_to_csv(results, input_csv, output_csv):
    """
    Adds computed position data to the original CSV file.

    Args:
        results (list): List of results for each epoch.
        input_csv (str): Path to the input CSV file.
        output_csv (str): Path to the output CSV file.
    """
    logging.info("Adding additional data to the CSV... \n")
    add_to_csv = {
        'GPS Time': [],
        'PosX_calculated': [],
        'PosY_calculated': [],
        'PosZ_calculated': [],
        'Lat_calculated': [],
        'Lon_calculated': [],
        'Alt_calculated': [],
        'RMS': [],
        'Spoofed_Satellites': [],
        'Spoofing_Reason': [],
        'Excluded_Satellites': []
    }
    encountered_timestamps = set()

    for result in results:
        gps_time = result['GPS Time']
        if gps_time not in encountered_timestamps:
            add_to_csv['GPS Time'].append(gps_time)
            add_to_csv['PosX_calculated'].append(result['Estimated Position ECEF'][0])
            add_to_csv['PosY_calculated'].append(result['Estimated Position ECEF'][1])
            add_to_csv['PosZ_calculated'].append(result['Estimated Position ECEF'][2])
            add_to_csv['Lat_calculated'].append(result['Estimated Position LLA'][0])
            add_to_csv['Lon_calculated'].append(result['Estimated Position LLA'][1])
            add_to_csv['Alt_calculated'].append(result['Estimated Position LLA'][2])
            add_to_csv['RMS'].append(result['RMS'])
            add_to_csv['Spoofed_Satellites'].append(','.join(map(str, result['Spoofed Satellites'])))
            add_to_csv['Spoofing_Reason'].append(result['Spoofing Reason'])
            add_to_csv['Excluded_Satellites'].append(','.join(map(str, result['Excluded Satellites'])))
            encountered_timestamps.add(gps_time)

    add_to_csv_df = pd.DataFrame(add_to_csv)
    existing_data = pd.read_csv(input_csv)
    
    # Remove any existing calculated columns from the existing data
    columns_to_remove = ['PosX_calculated', 'PosY_calculated', 'PosZ_calculated',
                         'Lat_calculated', 'Lon_calculated', 'Alt_calculated', 'RMS',
                         'Spoofed_Satellites', 'Spoofing_Reason', 'Excluded_Satellites']
    existing_data = existing_data.drop(columns=[col for col in columns_to_remove if col in existing_data.columns])
    
    # Merge the dataframes
    combined_data = pd.merge(existing_data, add_to_csv_df, on='GPS Time', how='left')
    combined_data.to_csv(output_csv, index=False)
    logging.info(f"Updated data saved to {output_csv}")

def main():
    """
    Main function that orchestrates the GNSS data processing and output generation.
    """
    args = parse_arguments()
    data = read_gnss_data(args.input_file)
    results = process_satellite_data(data, args.output_kml)
    save_results_to_text(results, args.output_txt)
    add_position_data_to_csv(results, args.input_file, args.input_file)

try:
    main()
except Exception as e:
    logging.error(f"An error occurred: {e}")
    traceback.print_exc()
