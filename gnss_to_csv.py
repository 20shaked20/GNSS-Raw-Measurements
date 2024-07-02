#!/usr/bin/python

import sys
import traceback
import os
import csv
import argparse
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import navpy
from gnssutils import EphemerisManager
from gnss_lib_py.parsers.rinex_nav import RinexNav
from gnss_lib_py.utils.ephemeris_downloader import load_ephemeris
import re

pd.options.mode.chained_assignment = None


# Constants
WEEKSEC = 604800
LIGHTSPEED = 2.99792458e8
GPS_EPOCH = datetime(1980, 1, 6, 0, 0, 0)
MU = 3.986005e14  # Earth's universal gravitational parameter
OMEGA_E_DOT = 7.2921151467e-5  # Earth's rotation rate

def parse_arguments():
    parser = argparse.ArgumentParser(description='Process GNSS log files for positioning.')

    # add --data_directory argument
    parser.add_argument('--data_directory', type=str, help='Directory for ephemeris data', default=os.getcwd())

    args = parser.parse_args()

    # Get the input file name from the user
    input_file = input("Enter the GNSS log file name: ")

    args.input_file = input_file

    return args

def read_data(input_filepath):
    # TODO: fix and remove all android related stuff
    measurements, android_fixes= [], []
    with open(input_filepath) as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if row[0][0] == '#':
                if 'Fix' in row[0]:
                    android_fixes = [row[1:]]
                elif 'Raw' in row[0]:
                    measurements = [row[1:]]
            else:
                if row[0] == 'Fix':
                    android_fixes.append(row[1:])
                elif row[0] == 'Raw':
                    measurements.append(row[1:])

    return pd.DataFrame(measurements[1:], columns=measurements[0])

def preprocess_measurements(measurements):
    measurements.loc[measurements['Svid'].str.len() == 1, 'Svid'] = '0' + measurements['Svid']
    constellation_map = {
        '1': 'G',  # GPS
        '3': 'R',  # GLONASS
        '5': 'E',  # Galileo
        '6': 'C',  # Beidou
    }
    measurements['Constellation'] = measurements['ConstellationType'].map(constellation_map)
    measurements['SvName'] = measurements['Constellation'] + measurements['Svid']
    measurements = measurements[measurements['Constellation'].isin(constellation_map.values())]
    numeric_cols = ['Cn0DbHz', 'TimeNanos', 'FullBiasNanos', 'ReceivedSvTimeNanos',
                    'PseudorangeRateMetersPerSecond', 'ReceivedSvTimeUncertaintyNanos',
                    'BiasNanos', 'TimeOffsetNanos']
    for col in numeric_cols:
        measurements[col] = pd.to_numeric(measurements[col], errors='coerce').fillna(0)
    measurements['GpsTimeNanos'] = measurements['TimeNanos'] - (measurements['FullBiasNanos'] - measurements['BiasNanos'])
    measurements['UnixTime'] = pd.to_datetime(measurements['GpsTimeNanos'], utc=True, origin=GPS_EPOCH)
    measurements['Epoch'] = 0
    time_diff = measurements['UnixTime'] - measurements['UnixTime'].shift()
    measurements.loc[time_diff > timedelta(milliseconds=200), 'Epoch'] = 1
    measurements['Epoch'] = measurements['Epoch'].cumsum()
    measurements['tRxGnssNanos'] = measurements['TimeNanos'] + measurements['TimeOffsetNanos'] - \
                                   (measurements['FullBiasNanos'].iloc[0] + measurements['BiasNanos'].iloc[0])
    measurements['GpsWeekNumber'] = np.floor(1e-9 * measurements['tRxGnssNanos'] / WEEKSEC)
    measurements['tRxSeconds'] = 1e-9 * measurements['tRxGnssNanos'] - WEEKSEC * measurements['GpsWeekNumber']
    measurements['tTxSeconds'] = 1e-9 * (measurements['ReceivedSvTimeNanos'] + measurements['TimeOffsetNanos'])
    measurements['prSeconds'] = measurements['tRxSeconds'] - measurements['tTxSeconds']
    measurements['PrM'] = LIGHTSPEED * measurements['prSeconds']
    measurements['PrSigmaM'] = LIGHTSPEED * 1e-9 * measurements['ReceivedSvTimeUncertaintyNanos']
    return measurements

def calculate_satellite_position(rinex_nav, gps_time):
    positions = []
    for _, eph in rinex_nav.iterrows():
        try:
            a = eph['sqrtA'] ** 2
            n0 = np.sqrt(MU / a ** 3)
            n = n0 + eph['deltaN']
            tk = gps_time - eph['t_oe']
            mk = eph['M_0'] + n * tk
            ek = mk
            for _ in range(10):
                ek = mk + eph['e'] * np.sin(ek)
            vk = np.arctan2(np.sqrt(1 - eph['e'] ** 2) * np.sin(ek), np.cos(ek) - eph['e'])
            phi_k = vk + eph['omega']
            delta_uk = eph['C_us'] * np.sin(2 * phi_k) + eph['C_uc'] * np.cos(2 * phi_k)
            delta_rk = eph['C_rs'] * np.sin(2 * phi_k) + eph['C_rc'] * np.cos(2 * phi_k)
            delta_ik = eph['C_is'] * np.sin(2 * phi_k) + eph['C_ic'] * np.cos(2 * phi_k)
            uk = phi_k + delta_uk
            rk = a * (1 - eph['e'] * np.cos(ek)) + delta_rk
            ik = eph['i_0'] + delta_ik + eph['IDOT'] * tk
            xk_prime = rk * np.cos(uk)
            yk_prime = rk * np.sin(uk)
            omega_k = eph['Omega_0'] + (eph['OmegaDot'] - OMEGA_E_DOT) * tk - OMEGA_E_DOT * eph['t_oe']
            xk = xk_prime * np.cos(omega_k) - yk_prime * np.sin(omega_k) * np.cos(ik)
            yk = xk_prime * np.sin(omega_k) + yk_prime * np.cos(omega_k) * np.cos(ik)
            zk = yk_prime * np.sin(ik)
            positions.append((eph['sv_id'], xk, yk, zk))
        except Exception as e:
            pass  # Handle the exception
    
    result_df = pd.DataFrame(positions, columns=['sv_id', 'x_k', 'y_k', 'z_k'])
    return result_df


def process_new_data(file_path):
    try:
        unparsed_measurements = read_data(file_path)
        measurements = preprocess_measurements(unparsed_measurements)
        gps_millis = measurements['GpsTimeNanos'].values / 1e6  # Convert nanoseconds to milliseconds
        
        ephemeris_files = load_ephemeris('rinex_nav', gps_millis.astype(np.int64), constellations=['gps'], download_directory=os.getcwd(), verbose=True)


        # Reindex epochs to be sequential starting from zero
        measurements['Epoch'] = measurements['Epoch'].rank(method='dense').astype(int) - 1

        # Identify satellites
        rinex_nav = RinexNav(ephemeris_files, measurements['SvName'].unique())
        rinex_nav_df = rinex_nav.pandas_df()

        # Combine cached satellite data with new data
        csv_output = []
        for epoch in measurements['Epoch'].unique():
            one_epoch = measurements.loc[(measurements['Epoch'] == epoch)].drop_duplicates(subset='SvName').set_index('SvName')
            if len(one_epoch.index) > 4:
                timestamp = one_epoch.iloc[0]['UnixTime'].to_pydatetime(warn=False)
                
                if epoch >= len(gps_millis):
                    print(f"Epoch index {epoch} out of bounds for gps_millis with length {len(gps_millis)}.")
                    continue

                gps_time = gps_millis[epoch]

                sv_positions = calculate_satellite_position(rinex_nav_df, gps_time)

                for sv in one_epoch.index:
                    id = int(re.search(r'\d+', sv).group())

                    if id in sv_positions['sv_id'].values:
                        pos = sv_positions[sv_positions['sv_id'] == id].iloc[0]
                        csv_output.append({
                            "GPS Time": timestamp.isoformat(),
                            "SatPRN (ID)": sv,
                            "Constellation": sv[0],
                            "SatX": pos['x_k'],
                            "SatY": pos['y_k'],
                            "SatZ": pos['z_k'],
                            "Pseudo-Range": one_epoch.at[sv, 'PrM'],
                            "CN0": one_epoch.at[sv, 'Cn0DbHz'],
                            "Doppler": one_epoch.at[sv, 'DopplerShiftHz'] if 'DopplerShiftHz' in one_epoch.columns else 'NaN'
                        })

        if csv_output:
            csv_df = pd.DataFrame(csv_output)
            csv_file_path = "gnss_measurements_output.csv"
            if not os.path.isfile(csv_file_path):
                csv_df.to_csv(csv_file_path, mode='w', header=True, index=False)
            else:
                csv_df.to_csv(csv_file_path, mode='a', header=False, index=False)
            print("CSV output updated successfully.")
        
    except Exception as e:
        print(f"An error occurred while processing new data from {file_path}: {e}")
        traceback.print_exc()
    
    
def main():
    old_csv_file = "gnss_measurements_output.csv"
    if os.path.exists(old_csv_file):
        os.remove(old_csv_file)
        
    args = parse_arguments()
    file_path = args.input_file
    print(file_path)
    process_new_data(file_path)
    
try:
    main()
except Exception as e:
    print(f"An error occurred: {e}")
    traceback.print_exc() 