import subprocess
import os
import csv
import argparse
import traceback
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from gnss_lib_py.utils.ephemeris_downloader import load_ephemeris
import re
from gnss_lib_py.parsers.rinex_nav import RinexNav

pd.options.mode.chained_assignment = None

# Constants
WEEKSEC = 604800
LIGHTSPEED = 2.99792458e8
GPS_EPOCH = datetime(1980, 1, 6, 0, 0, 0)
MU = 3.986005e14  # Earth's universal gravitational parameter
OMEGA_E_DOT = 7.2921151467e-5  # Earth's rotation rate

# Cache for satellite data
satellite_cache = {}
seen_satellites = set()

def run_adb_command(command):
    result = subprocess.run(['adb'] + command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise Exception(f"Command failed with error: {result.stderr}")
    return result.stdout

def get_files_in_directory(directory):
    list_command = ['shell', 'ls', directory]
    try:
        files = run_adb_command(list_command).splitlines()
        return files
    except Exception as e:
        print(f"Error getting files in directory: {e}")
        return []

def append_new_data(file_path, new_data):
    try:
        with open(file_path, 'a') as file:
            file.write(new_data)
    except Exception as e:
        print(f"Error appending new data: {e}")

def read_existing_file(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as file:
                return file.read()
        except Exception as e:
            print(f"Error reading existing file: {e}")
            return ""
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
        print(f"Error deleting files in directory: {e}")

def pull_file(file_to_pull):
    pull_command = ['shell', 'cat', file_to_pull]
    new_data = run_adb_command(pull_command)
    return new_data

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

def process_new_data(file_path, measurements, ephemeris_files, last_processed_time):
    try:
        unparsed_new_data = read_data(file_path)
        new_measurements = preprocess_measurements(unparsed_new_data)
        new_measurements = new_measurements[new_measurements['UnixTime'] > last_processed_time]

        if new_measurements.empty:
            print("No new data to process.")
            return last_processed_time

        measurements = pd.concat([measurements, new_measurements]).reset_index(drop=True)
        gps_millis = new_measurements['GpsTimeNanos'].values / 1e6  # Convert nanoseconds to milliseconds

        # Reindex epochs to be sequential starting from zero
        new_measurements['Epoch'] = new_measurements['Epoch'].rank(method='dense').astype(int) - 1

        # Identify new satellites
        new_satellites = set(new_measurements['SvName'].unique()) - seen_satellites

        # Only call RinexNav if there are new satellites
        if new_satellites:
            print(f"New satellites detected: {new_satellites}")
            rinex_nav = RinexNav(ephemeris_files, list(new_satellites))
            rinex_nav_df = rinex_nav.pandas_df()
            if rinex_nav_df.empty:  # case where we do not have the data for the satellite (which might happen)
                return
            
            # Update the cache
            for sv in new_satellites:
                satellite_cache[sv] = rinex_nav_df[rinex_nav_df['sv_id'] == int(re.search(r'\d+', sv).group())]
            # Update seen satellites
            seen_satellites.update(new_satellites)
        else:
            rinex_nav_df = pd.DataFrame()

        # Combine cached satellite data with new data
        cached_data = pd.concat(satellite_cache.values())
        csv_output = []
        for epoch in new_measurements['Epoch'].unique():
            one_epoch = new_measurements.loc[(new_measurements['Epoch'] == epoch)].drop_duplicates(subset='SvName').set_index('SvName')
            if len(one_epoch.index) > 4:
                timestamp = one_epoch.iloc[0]['UnixTime'].to_pydatetime(warn=False)
                
                if epoch >= len(gps_millis):
                    print(f"Epoch index {epoch} out of bounds for gps_millis with length {len(gps_millis)}.")
                    continue

                gps_time = gps_millis[epoch]

                sats = one_epoch.index.unique().tolist()

                sv_positions = calculate_satellite_position(cached_data, gps_time)

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
        
        return new_measurements['UnixTime'].max()
    except Exception as e:
        print(f"An error occurred while processing new data from {file_path}: {e}")
        traceback.print_exc()
        return last_processed_time


import time

def main():
    old_csv_file = "gnss_measurements_output.csv"
    if os.path.exists(old_csv_file):
        os.remove(old_csv_file)
    
    directory_to_pull = '/storage/emulated/0/Android/data/com.android.gpstest/files/gnss_log/'
    destination = './'
    delete_files_in_directory(directory_to_pull)

    last_checked_times = {}
    last_processed_time = None

    # Wait for the initial file to be generated
    initial_file = None
    while not initial_file:
        files = get_files_in_directory(directory_to_pull)
        if files:
            time.sleep(5)
            initial_file = f'{directory_to_pull}/{files[0]}'
        else:
            print("Waiting for the initial file to be generated...")
            time.sleep(5)  # Wait for 5 seconds before checking again

    # Initial setup
    initial_data = pull_file(initial_file)
    destination_file = f'{destination}/initial_gnss_log.txt'
    with open(destination_file, 'w') as file:
        file.write(initial_data)

    measurements = preprocess_measurements(read_data(destination_file))
    last_processed_time = measurements['UnixTime'].max()
    
    gps_millis = measurements['GpsTimeNanos'].values / 1e6
    ephemeris_files = load_ephemeris('rinex_nav', gps_millis.astype(np.int64), constellations=['gps'], download_directory=os.getcwd(), verbose=True)

    while True:
        try:
            files = get_files_in_directory(directory_to_pull)
            for file in files:
                file_to_pull = f'{directory_to_pull}/{file}'
                destination_file = f'{destination}/{file}'

                stat_command = ['shell', 'stat', '-c', '%Y', file_to_pull]
                modification_time = int(run_adb_command(stat_command).strip())

                if file not in last_checked_times or last_checked_times[file] != modification_time:
                    new_data = pull_file(file_to_pull)

                    existing_data = read_existing_file(destination_file)
                    new_content_to_append = new_data[len(existing_data):] if new_data.startswith(existing_data) else new_data

                    if new_content_to_append:
                        append_new_data(destination_file, new_content_to_append)
                        print(f"Appended new data to {destination_file}")
                        last_processed_time = process_new_data(destination_file, measurements, ephemeris_files, last_processed_time)

                    last_checked_times[file] = modification_time
        except Exception as e:
            print(f"Error in main loop: {e}")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"An error occurred: {e}")
        traceback.print_exc()
