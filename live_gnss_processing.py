#!/usr/bin/python

import subprocess
import os
import csv
import argparse
import sys
import traceback
import time
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import navpy
from gnss_lib_py.utils.ephemeris_downloader import load_ephemeris
import gnss_lib_py.utils.time_conversions as tc
from gnss_lib_py.navdata.navdata import NavData


pd.options.mode.chained_assignment = None

# Constants
WEEKSEC = 604800
LIGHTSPEED = 2.99792458e8
GPS_EPOCH = datetime(1980, 1, 6, 0, 0, 0)
MU = 3.986005e14  # Earth's universal gravitational parameter
OMEGA_E_DOT = 7.2921151467e-5  # Earth's rotation rate


"FETCH DATA USING ADB"
def run_adb_command(command):
    result = subprocess.run(['adb'] + command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise Exception(f"Command failed with error: {result.stderr}")
    return result.stdout

def get_files_in_directory(directory):
    list_command = ['shell', 'ls', directory]
    files = run_adb_command(list_command).splitlines()
    return files

def append_new_data(file_path, new_data):
    with open(file_path, 'a') as file:
        file.write(new_data)

def read_existing_file(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            return file.read()
    return ""

def delete_files_in_directory(directory):
    try:
        files = get_files_in_directory(directory)
        for file in files:
            file_to_delete = f'{directory}/{file}'
            delete_command = ['shell', 'rm', file_to_delete]
            run_adb_command(delete_command)
            print(f"Deleted {file_to_delete}")
    except Exception as e:
        print(e)

def pull_and_append_files(directory_to_pull, destination):
    try:
        files = get_files_in_directory(directory_to_pull)
        for file in files:
            file_to_pull = f'{directory_to_pull}/{file}'
            destination_file = f'{destination}{file}'
            pull_command = ['shell', 'cat', file_to_pull]
            new_data = run_adb_command(pull_command)
            existing_data = read_existing_file(destination_file)
            if new_data.startswith(existing_data):
                new_content_to_append = new_data[len(existing_data):]
            else:
                new_content_to_append = new_data
            if new_content_to_append:
                append_new_data(destination_file, new_content_to_append)
                print(f"Appended new data to {destination_file}")
                process_file(destination_file)  # Process the new data
    except Exception as e:
        print(e)

def parse_arguments():
    parser = argparse.ArgumentParser(description='Process GNSS log files for positioning.')
    parser.add_argument('--data_directory', type=str, help='Directory for ephemeris data', default=os.getcwd())
    args = parser.parse_args()
    return args

def read_data(input_filepath):
    measurements, android_fixes = [], []
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
        '6': 'C',  #Beido
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
            # Handle the exception
            pass
    
    result_df = pd.DataFrame(positions, columns=['sv_id', 'x_k', 'y_k', 'z_k'])
    return result_df

from gnss_lib_py.parsers.rinex_nav import RinexNav
import re

def process_file(file_path):
    args = parse_arguments()
    try:
        unparsed_measurements = read_data(file_path)
        measurements = preprocess_measurements(unparsed_measurements)
        # print(f"Data Directory: {args.data_directory}")
        

        ## TODO: fix this to get the data from the datacdenter, its having issues with C import
        
        gps_millis = measurements['GpsTimeNanos'].values / 1e6  # Convert nanoseconds to milliseconds

        # Check and print the min and max gps_millis to ensure they are after January 1, 2013
        min_gps_millis = np.min(gps_millis)
        max_gps_millis = np.max(gps_millis)
        # print(f"Min gps_millis: {min_gps_millis}, Max gps_millis: {max_gps_millis}")

        ephemeris_files = load_ephemeris('rinex_nav', gps_millis.astype(np.int64), constellations=['gps'], download_directory=args.data_directory, verbose=True)
        # print(f"Ephemeris files loaded: {ephemeris_files}")
        
        # parser = RINEXParser("C:/Users/shake/OneDrive/Desktop/VsCode/GNSS-Raw-Measurements/rinex/nav/BRDC00WRD_S_20241810000_01D_MN.rnx")
        # parser.parse()
        # ephemeris = parser.get_data()
        # print(f"Ephemeris data: {ephemeris}")  # Print the first few rows of ephemeris data

        

        csv_output = []
        for epoch in measurements['Epoch'].unique():
            one_epoch = measurements.loc[(measurements['Epoch'] == epoch)].drop_duplicates(subset='SvName').set_index('SvName')
            if len(one_epoch.index) > 4:
                timestamp = one_epoch.iloc[0]['UnixTime'].to_pydatetime(warn=False)
                gps_time = gps_millis[epoch]

                sats = one_epoch.index.unique().tolist()
                rinex_data = RinexNav("./rinex/nav/BRDC00WRD_S_20241810000_01D_MN.rnx",sats)
                rinex_nav_df = rinex_data.pandas_df()

                sv_positions = calculate_satellite_position(rinex_nav_df, gps_time)
                
                for sv in one_epoch.index:
                    id = int(re.search(r'\d+', sv).group())

                    if id in sv_positions['sv_id'].values:
                        pos = sv_positions[sv_positions['sv_id'] == id].iloc[0]
                        csv_output.append({
                            "GPS Time": timestamp.isoformat(),
                            "SatPRN (ID)": sv,
                            "Constellation": sv[0],
                            "Sat.X": pos['x_k'],
                            "Sat.Y": pos['y_k'],
                            "Sat.Z": pos['z_k'],
                            "Pseudo-Range": one_epoch.at[sv, 'PrM'],
                            "CN0": one_epoch.at[sv, 'Cn0DbHz'],
                            "Doppler": one_epoch.at[sv, 'DopplerShiftHz'] if 'DopplerShiftHz' in one_epoch.columns else 'NaN'
                        })

        csv_df = pd.DataFrame(csv_output)
        csv_df.to_csv("gnss_measurements_output.csv", index=False)
        print("CSV output generated successfully.")
    except Exception as e:
        print(f"An error occurred while processing {file_path}: {e}")
        traceback.print_exc()
def main():
    args = parse_arguments()
    directory_to_pull = '/storage/emulated/0/Android/data/com.android.gpstest/files/gnss_log/'
    destination = './'
    delete_files_in_directory('/storage/emulated/0/Android/data/com.android.gpstest/files/gnss_log/')

    while True:
        pull_and_append_files(directory_to_pull, destination)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"An error occurred: {e}")
        traceback.print_exc()
