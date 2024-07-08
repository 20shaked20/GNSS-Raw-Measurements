"""
GNSS Positioning Script with NLP Fixes Integration
"""

import argparse
import traceback
import pandas as pd
import numpy as np
from scipy.optimize import least_squares
import navpy
import simplekml
import logging
from tqdm import tqdm

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_arguments():
    parser = argparse.ArgumentParser(description='Process multi-GNSS CSV log files for positioning and spoofing detection.')
    parser.add_argument('--input_file', type=str, default='gnss_measurements_output.csv', help='Input CSV file')
    parser.add_argument('--output_kml', type=str, default='gnss_visualization.kml', help='Output KML file')
    parser.add_argument('--output_txt', type=str, default='RmsResults.txt', help='Output RMS results text file')
    parser.add_argument('--android_fixes', type=str, default='android_fixes.csv', help='Android fixes CSV file')
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

def process_android_fixes(csv_path, kml):
    try:
        data = pd.read_csv(csv_path)
    except FileNotFoundError:
        logging.warning(f"Android fixes file '{csv_path}' not found. Skipping Android fixes processing.")
        return kml, None
    except Exception as e:
        logging.error(f"Error reading Android fixes file: {e}")
        return kml, None

    data = data[data['Provider'].isin(['NLP', 'nlp'])]
    
    nlp_style = simplekml.Style()
    nlp_style.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/shapes/placemark_square.png'
    nlp_style.iconstyle.color = simplekml.Color.red
    
    nlp_fixes = []

    for _, row in data.iterrows():
        pnt = kml.newpoint(name=f"Android {row['Provider']} - {row['UnixTimeMillis']}")
        pnt.coords = [(row['LongitudeDegrees'], row['LatitudeDegrees'], row['AltitudeMeters'])]
        pnt.timestamp.when = pd.to_datetime(row['UnixTimeMillis'], unit='ms').strftime("%Y-%m-%dT%H:%M:%SZ")
        pnt.style = nlp_style
        nlp_fixes.append((row['UnixTimeMillis'], row['LongitudeDegrees'], row['LatitudeDegrees'], row['AltitudeMeters']))
        
    logging.info(f"Added {len(data)} Android fixes to KML.")
    return kml, nlp_fixes

def positioning_function(x, sat_positions, observed_pseudoranges, weights):
    """
    Calculates residuals between observed and estimated pseudoranges.

    The function computes the residuals (differences) between the observed pseudoranges (the distances
    measured from the receiver to each satellite) and the estimated pseudoranges (calculated based
    on the estimated position of the receiver). It then returns these residuals weighted by the
    reliability of each measurement.

    Args:
        x (np.array): Estimated receiver position (3D coordinates).
        sat_positions (np.array): Array of satellite positions (3D coordinates).
        observed_pseudoranges (np.array): Array of observed pseudoranges.
        weights (np.array): Array of weights for each satellite measurement.

    Returns:
        np.array: Weighted residuals.
    """
    # Calculate the estimated pseudoranges based on the current estimate of the receiver position.
    estimated_ranges = np.sqrt(((sat_positions - x)**2).sum(axis=1))
    
    # Compute the residuals (differences) between the observed pseudoranges and the estimated pseudoranges.
    residuals = estimated_ranges - observed_pseudoranges
    
    # Return the weighted residuals to account for the reliability of each measurement.
    return weights * residuals

def robust_positioning_function(x, sat_positions, observed_pseudoranges, weights):
    """
    Calculates residuals between observed and estimated pseudoranges with robust weighting.

    This function is similar to the `positioning_function` but includes an additional term to account for the
    receiver clock bias. It provides a more robust estimation by considering the bias.

    Args:
        x (np.array): Estimated receiver position and clock bias.
        sat_positions (np.array): Array of satellite positions.
        observed_pseudoranges (np.array): Array of observed pseudoranges.
        weights (np.array): Array of weights for each satellite measurement.

    Returns:
        np.array: Weighted residuals.
    """
    # Calculate the estimated pseudoranges including the receiver clock bias.
    estimated_ranges = np.sqrt(((sat_positions - x[:3])**2).sum(axis=1))
    residuals = estimated_ranges + x[3] - observed_pseudoranges  # Including receiver clock bias
    
    # Return the weighted residuals.
    return weights * residuals

def solve_position_and_compute_rms(sat_positions, pseudoranges, weights):
    """
    Solves for receiver position and computes RMS error of pseudoranges with an improved algorithm.

    This function iteratively refines the position estimate and adjusts the weights of the satellite measurements
    to reduce the influence of outliers. It computes the root mean square (RMS) error of the pseudoranges to
    assess the quality of the solution.

    Args:
        sat_positions (np.array): Array of satellite positions.
        pseudoranges (np.array): Array of observed pseudoranges.
        weights (np.array): Array of weights for each satellite measurement.

    Returns:
        tuple: Estimated receiver position, RMS error, clock bias, and list of excluded satellites.
    """
    if not (np.all(np.isfinite(sat_positions)) and np.all(np.isfinite(pseudoranges))):
        raise ValueError("Satellite positions and pseudoranges must be finite.")

    # Initial guess using weighted average of satellite positions.
    initial_guess = np.average(sat_positions, axis=0, weights=weights)
    initial_guess = np.append(initial_guess, 0)  # Including receiver clock bias
    
    # Iterative least squares with robust outlier detection.
    for _ in range(5):  # Iterative refinement
        res = least_squares(robust_positioning_function, initial_guess, args=(sat_positions, pseudoranges, weights))
        position = res.x[:3]
        clock_bias = res.x[3]
        residuals = robust_positioning_function(res.x, sat_positions, pseudoranges, weights)
        
        # Detect outliers based on residuals.
        z_scores = np.abs((residuals - np.mean(residuals)) / np.std(residuals))
        outliers = z_scores > 3  # Outlier threshold
        
        # Recalculate weights to reduce the influence of outliers.
        weights[outliers] *= 0.1
        initial_guess = res.x  # Update guess for next iteration

    rms = np.sqrt(np.mean(residuals**2))
    excluded_satellites = list(np.where(outliers)[0])
    
    return position, rms, clock_bias, excluded_satellites

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

    The function uses various checks, such as high RMS error, unreasonable altitude,
    and individual satellite residual anomalies, to detect spoofed satellites.

    Args:
        group (pd.DataFrame): DataFrame containing satellite measurements for a single epoch.
        residuals (np.array): Residuals between observed and estimated pseudoranges.
        rms (float): Root mean square error of pseudoranges.
        lla (np.array): Latitude, Longitude, and Altitude of the estimated position.

    Returns:
        tuple: List of spoofed satellites and the reason for spoofing detection.
    """
    spoofed_satellites = []
    spoofing_reasons = []
    
    # Check if the RMS error is excessively high.
    if rms > 2000:
        spoofed_satellites.extend(group['SatPRN (ID)'].tolist())
        spoofing_reasons.append("High RMS")
    
    # Check for unreasonable altitude.
    if lla[2] < -1000 or lla[2] > 100000:  # -1km to 100km range
        spoofed_satellites.extend(group['SatPRN (ID)'].tolist())
        spoofing_reasons.append("Unreasonable altitude")
    
    # Individual satellite checks using Z-scores.
    z_scores = np.abs((residuals - np.mean(residuals)) / np.std(residuals))
    threshold = 3 
    spoofed_indices = np.where(z_scores > threshold)[0]
    if len(spoofed_indices) > 0:
        spoofed_satellites.extend(group.iloc[spoofed_indices]['SatPRN (ID)'].tolist())
        spoofing_reasons.append("Individual satellite anomalies")
    
    return spoofed_satellites, spoofing_reasons if spoofing_reasons else [""]

def check_nlp_fix_consistency(nlp_fix, sat_positions, pseudoranges, clock_bias):
    """
    Checks consistency of NLP fix with satellite data.

    Args:
        nlp_fix (tuple): NLP fix coordinates (UnixTimeMillis, Longitude, Latitude, Altitude).
        sat_positions (np.array): Array of satellite positions.
        pseudoranges (np.array): Array of observed pseudoranges.
        clock_bias (float): Receiver clock bias.

    Returns:
        np.array: Boolean array indicating inconsistent satellites.
    """
    nlp_position_ecef = navpy.lla2ecef(nlp_fix[2], nlp_fix[1], nlp_fix[3], latlon_unit='deg')
    estimated_ranges = np.sqrt(((sat_positions - nlp_position_ecef)**2).sum(axis=1)) + clock_bias
    deviations = np.abs(estimated_ranges - pseudoranges)
    
    threshold = 1000  # meters
    return deviations > threshold

def process_epoch(gps_time, group, kml, previous_position, nlp_fixes):
    """
    Processes data for a single epoch to compute position and detect spoofing.

    This function handles the processing of satellite measurements for a single time epoch.
    It computes the receiver's position, detects spoofing, and adds the position data to a KML file for visualization.

    Args:
        gps_time (str): GPS time of the epoch.
        group (pd.DataFrame): DataFrame containing satellite measurements for the epoch.
        kml (simplekml.Kml): KML object for visualization.
        previous_position (np.array): Previous estimated position for detecting sudden jumps.
        nlp_fixes (list): List of NLP fixes.

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

    # Calculate weights based on carrier-to-noise ratio (CN0) and Doppler shift.
    weights = np.where(np.isnan(doppler), 1 / (cn0 + 1e-6), cn0 / (np.abs(doppler) + 1e-6))
    weights /= weights.sum()
    
    position, rms, clock_bias, excluded_satellites = solve_position_and_compute_rms(sat_positions, pseudoranges, weights)
    lla = ecef_to_lla(position)
    
    # Add the estimated position to the KML file.
    pnt = kml.newpoint(name=f"{gps_time}", coords=[(lla[1], lla[0], lla[2])])
    pnt.timestamp.when = gps_time_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Detect spoofing.
    estimated_ranges = np.sqrt(((sat_positions - position)**2).sum(axis=1))
    residuals = estimated_ranges + clock_bias - pseudoranges  # Including receiver clock bias

    all_satellites = group['SatPRN (ID)'].tolist()
    spoofed_satellites, spoofing_reasons = detect_spoofing(group, residuals, rms, lla)
    
    nlp_inconsistent_satellites = []
    for nlp_fix in nlp_fixes:
        if abs(nlp_fix[0] - gps_time_dt.timestamp() * 1000) <= 60000:  # Within one minute
            inconsistent_satellites = check_nlp_fix_consistency(nlp_fix, sat_positions, pseudoranges, clock_bias)
            new_inconsistent = group.iloc[inconsistent_satellites]['SatPRN (ID)'].tolist()
            nlp_inconsistent_satellites.extend(new_inconsistent)

    # Remove duplicates
    nlp_inconsistent_satellites = list(set(nlp_inconsistent_satellites))

    if nlp_inconsistent_satellites:
        spoofed_satellites.extend(nlp_inconsistent_satellites)
        spoofing_reasons.append("Inconsistent with NLP fix")

    # Remove duplicates from spoofed_satellites
    spoofed_satellites = list(set(spoofed_satellites))

    # Check for sudden position jumps.
    if previous_position is not None:
        distance = np.linalg.norm(position - previous_position)
        if distance > 1000:  # 1km threshold, adjust as needed
            spoofed_satellites = group['SatPRN (ID)'].tolist()
            spoofing_reasons.append("Sudden position jump")
    
    return {
        'GPS Time': gps_time,
        'Estimated Position ECEF': position,
        'Estimated Position LLA': lla,
        'RMS': rms,
        'Spoofed Satellites': spoofed_satellites,
        'Non_spoofed Satellites': [sat for sat in all_satellites if sat not in spoofed_satellites],
        'Excluded Satellites': [all_satellites[i] for i in excluded_satellites],
        'Spoofing Reason': ', '.join(spoofing_reasons)
    }

def process_satellite_data(data, kml, nlp_fixes):
    """
    Processes GNSS data and generates KML visualization.

    This function handles the entire processing workflow for GNSS data. It groups the data by epoch,
    processes each epoch, and generates a KML file for visualization. It also stores results in a list.

    Args:
        data (pd.DataFrame): DataFrame containing GNSS measurements.
        kml_output_path (str): Path to the output KML file.

    Returns:
        list: List of results for each epoch.
    """
    grouped = data.groupby('GPS Time')
    results = []
    previous_position = None
    
    for gps_time, group in tqdm(grouped, desc="Processing Satellite Data"):  # Adding progress bar for epoch processing
        try:
            result = process_epoch(gps_time, group, kml, previous_position, nlp_fixes)
            results.append(result)
            previous_position = result['Estimated Position ECEF']
        except ValueError as e:
            logging.error(f"Skipping epoch at {gps_time} due to error: {e}")
    
    return results

def save_results_to_text(results, output_txt):
    """
    Saves RMS results and spoofing information to a text file.

    This function writes the processed results, including position estimates and spoofing detection information,
    to a text file for further analysis or reporting.

    Args:
        results (list): List of results for each epoch.
        output_txt (str): Path to the output text file.
    """
    logging.info("Saving to RmsResults.txt... \n")
    with open(output_txt, 'w') as f:
        for result in tqdm(results, desc="Saving results to text"):  # Adding progress bar for saving results
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
            f.write("-" * 50 + "\n")

def add_position_data_to_csv(results, input_csv, output_csv):
    """
    Adds computed position data to the original CSV file.

    This function merges the computed position data with the original GNSS measurements and saves the updated
    information to a new CSV file.

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

    for result in tqdm(results, desc="Adding position data to CSV"):  # Adding progress bar for CSV update
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
    
    # Remove any existing calculated columns from the existing data.
    columns_to_remove = ['PosX_calculated', 'PosY_calculated', 'PosZ_calculated',
                         'Lat_calculated', 'Lon_calculated', 'Alt_calculated', 'RMS',
                         'Spoofed_Satellites', 'Spoofing_Reason', 'Excluded_Satellites']
    existing_data = existing_data.drop(columns=[col for col in columns_to_remove if col in existing_data.columns])
    
    # Merge the dataframes.
    combined_data = pd.merge(existing_data, add_to_csv_df, on='GPS Time', how='left')
    combined_data.to_csv(output_csv, index=False)
    logging.info(f"Updated data saved to {output_csv}")

def main():
    args = parse_arguments()
    data = read_gnss_data(args.input_file)
    kml = simplekml.Kml()
    kml, nlp_fixes = process_android_fixes(args.android_fixes, kml)
    results = process_satellite_data(data, kml, nlp_fixes)
    kml.save(args.output_kml)
    save_results_to_text(results, args.output_txt)
    add_position_data_to_csv(results, args.input_file, args.input_file)

try:
    main()
except Exception as e:
    logging.error(f"An error occurred: {e}")
    traceback.print_exc()
