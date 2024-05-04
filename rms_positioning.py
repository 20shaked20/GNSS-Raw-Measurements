import argparse
import traceback
import pandas as pd
import numpy as np
from scipy.optimize import least_squares
import navpy

def parse_arguments():
    parser = argparse.ArgumentParser(description='Process CSV log files for positioning.')
    parser.add_argument('--file', type=str, help='Input CSV log file', required=True)
    return parser.parse_args()

def read_gnss_data(filepath):
    return pd.read_csv(filepath)

def positioning_function(x, sat_positions, observed_pseudoranges, weights):
    estimated_ranges = np.sqrt(((sat_positions - x)**2).sum(axis=1))
    residuals = estimated_ranges - observed_pseudoranges
    return weights * residuals

def solve_position_and_compute_rms(sat_positions, pseudoranges, weights):
    initial_guess = np.zeros(3)  # XYZ coordinates only
    res = least_squares(positioning_function, initial_guess, args=(sat_positions, pseudoranges, weights))
    rms = np.sqrt(np.mean((res.fun / weights) ** 2))
    return res.x, rms

def lla_from_ecef(ecef_coords):
    lla = navpy.ecef2lla(ecef_coords, latlon_unit='deg')
    return lla

def process_satellite_data(data):
    grouped = data.groupby('GPS Time')
    results = []
    
    for gps_time, group in grouped:
        sat_positions = group[['Sat.X', 'Sat.Y', 'Sat.Z']].values
        pseudoranges = group['Pseudo-Range'].values
        cn0 = group['CN0'].values
        doppler = group['Doppler'].values
        
        # Weighing the SatPRN's using carrier-noise ratio and doppler measurement
        weights = cn0 / np.abs(doppler)
        weights /= weights.sum()
        
        position, rms = solve_position_and_compute_rms(sat_positions, pseudoranges, weights)
        lla = lla_from_ecef(position)
        
        results.append({
            'GPS Time': gps_time,
            'Estimated Position ECEF': position,
            'Estimated Position LLA': lla,
            'RMS': rms
        })
    
    return results

def main():
    args = parse_arguments()
    data = read_gnss_data(args.file)
    results = process_satellite_data(data)
    
    for result in results:
        print(f"GPS Time: {result['GPS Time']}")
        print(f"Estimated Position ECEF (X, Y, Z): {result['Estimated Position ECEF']}")
        print(f"Estimated Position LLA (Lat, Lon, Alt): {result['Estimated Position LLA']}")
        print(f"RMS: {result['RMS']}")
        print("-" * 50)

try:
    main()
except Exception as e:
    print(f"An error occurred: {e}")
    traceback.print_exc()  # Print the stack trace to standard error
