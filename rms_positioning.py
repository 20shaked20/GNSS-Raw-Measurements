#!/usr/bin/python

import argparse
import traceback
import pandas as pd
import numpy as np
from scipy.optimize import least_squares
import navpy
import simplekml
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_arguments():
    parser = argparse.ArgumentParser(description='Process multi-GNSS CSV log files for positioning.')
    parser.add_argument('--input_file', type=str, default='gnss_measurements_output.csv', help='Input CSV file')
    parser.add_argument('--output_kml', type=str, default='gnss_visualization.kml', help='Output KML file')
    parser.add_argument('--output_txt', type=str, default='RmsResults.txt', help='Output RMS results text file')
    return parser.parse_args()

def read_gnss_data(filepath):
    return pd.read_csv(filepath)

def positioning_function(x, sat_positions, observed_pseudoranges, weights):
    estimated_ranges = np.sqrt(((sat_positions - x)**2).sum(axis=1))
    residuals = estimated_ranges - observed_pseudoranges
    return weights * residuals

def solve_position_and_compute_rms(sat_positions, pseudoranges, weights):
    if not (np.all(np.isfinite(sat_positions)) and np.all(np.isfinite(pseudoranges))):
        raise ValueError("Satellite positions and pseudoranges must be finite.")
    
    initial_guess = np.mean(sat_positions, axis=0)
    res = least_squares(positioning_function, initial_guess, args=(sat_positions, pseudoranges, weights))
    rms = np.sqrt(np.mean((res.fun / weights) ** 2))
    return res.x, rms

def ecef_to_lla(ecef_coords):
    return navpy.ecef2lla(ecef_coords, latlon_unit='deg')

def process_epoch(gps_time, group, kml):
    gps_time_dt = pd.to_datetime(gps_time)
    sat_positions = group[['SatX', 'SatY', 'SatZ']].values
    pseudoranges = group['Pseudo-Range'].values
    cn0 = group['CN0'].values
    doppler = group['Doppler'].values
    
    if len(sat_positions) < 4:
        raise ValueError("Not enough valid satellite data for position calculation.")

    weights = np.where(np.isnan(doppler), 1 / (cn0 + 1e-6), cn0 / (np.abs(doppler) + 1e-6))
    weights /= weights.sum()
    
    position, rms = solve_position_and_compute_rms(sat_positions, pseudoranges, weights)
    lla = ecef_to_lla(position)
    
    pnt = kml.newpoint(name=f"{gps_time}", coords=[(lla[1], lla[0], lla[2])])
    pnt.timestamp.when = gps_time_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    return {
        'GPS Time': gps_time,
        'Estimated Position ECEF': position,
        'Estimated Position LLA': lla,
        'RMS': rms
    }

def process_satellite_data(data, kml_output_path):
    grouped = data.groupby('GPS Time')
    results = []
    kml = simplekml.Kml()
    
    for gps_time, group in grouped:
        try:
            result = process_epoch(gps_time, group, kml)
            results.append(result)
        except ValueError as e:
            logging.error(f"Skipping epoch at {gps_time} due to error: {e}")
    
    kml.save(kml_output_path)
    logging.info(f"{kml_output_path} File Is Created! \n")
    
    return results

def save_results_to_text(results, output_txt):
    logging.info("Saving to RmsResults.txt... \n")
    with open(output_txt, 'w') as f:
        for result in results:
            f.write(f"GPS Time: {result['GPS Time']}\n")
            f.write(f"Estimated Position ECEF (X, Y, Z): {result['Estimated Position ECEF']}\n")
            f.write(f"Estimated Position LLA (Lat, Lon, Alt): {result['Estimated Position LLA']}\n")
            f.write(f"RMS: {result['RMS']}\n")
            f.write("-" * 50 + "\n")

def add_position_data_to_csv(results, input_csv, output_csv):
    logging.info("Adding additional data to the CSV... \n")
    add_to_csv = {
        'GPS Time': [],
        'PosX_calculated': [],
        'PosY_calculated': [],
        'PosZ_calculated': [],
        'Lat_calculated': [],
        'Lon_calculated': [],
        'Alt_calculated': [],
        'RMS': []
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
            encountered_timestamps.add(gps_time)

    add_to_csv_df = pd.DataFrame(add_to_csv)
    existing_data = pd.read_csv(input_csv)
    
    # Remove any existing calculated columns from the existing data
    columns_to_remove = ['PosX_calculated', 'PosY_calculated', 'PosZ_calculated',
                         'Lat_calculated', 'Lon_calculated', 'Alt_calculated', 'RMS']
    existing_data = existing_data.drop(columns=[col for col in columns_to_remove if col in existing_data.columns])
    
    # Merge the dataframes
    combined_data = pd.merge(existing_data, add_to_csv_df, on='GPS Time', how='left')
    combined_data.to_csv(output_csv, index=False)
    logging.info(f"Updated data saved to {output_csv}")

def main():
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