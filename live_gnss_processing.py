import cProfile
from io import StringIO
from multiprocessing import Queue, Process, cpu_count
import os
import csv
import argparse
import pstats
import timeit
import traceback
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from gnss_lib_py.utils.ephemeris_downloader import load_ephemeris
from gnss_lib_py.parsers.rinex_nav import RinexNav
import re
import time
from concurrent.futures import ProcessPoolExecutor
import logging
import subprocess

# Set up logging
def setup_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(processName)s - %(levelname)s - %(message)s')
    log_file = os.path.join(os.getcwd(), 'process_log.log')
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger

pd.options.mode.chained_assignment = None

# Constants
WEEKSEC = 604800
LIGHTSPEED = 2.99792458e8
GPS_EPOCH = datetime(1980, 1, 6, 0, 0, 0)
MU = 3.986005e14  # Earth's universal gravitational parameter
OMEGA_E_DOT = 7.2921151467e-5  # Earth's rotation rate

def run_adb_command(command):
    result = subprocess.run(['adb'] + command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise Exception(f"Command failed with error: {result.stderr}")
    return result.stdout

def get_files_in_directory(directory):
    list_command = ['shell', 'ls', directory]
    try:
        files = run_adb_command(list_command).splitlines()
        files = [f for f in files if not f.endswith('/')]  # Filter out directories
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
            pass
    
    result_df = pd.DataFrame(positions, columns=['sv_id', 'x_k', 'y_k', 'z_k'])
    return result_df

def pull_data_process(directory_to_pull, destination, input_queue):
    logger = setup_logger("pull_data_process")
    logger.info("Pull data process started")
    delete_files_in_directory(directory_to_pull)
    last_checked_times = {}

    while True:
        try:
            files = get_files_in_directory(directory_to_pull)
            if not files:
                time.sleep(2)
                continue

            for file in files:
                file_to_pull = f'{directory_to_pull}/{file}'
                destination_file = f'{destination}/{file}'

                try:
                    modification_time = int(run_adb_command(['shell', 'stat', '-c', '%Y', file_to_pull]).strip())
                except Exception as e:
                    logger.error(f"Failed to get modification time for {file_to_pull}: {e}")
                    continue

                if file not in last_checked_times or last_checked_times[file] != modification_time:
                    try:
                        new_data = run_adb_command(['shell', 'cat', file_to_pull])
                    except Exception as e:
                        logger.error(f"Failed to pull data from {file_to_pull}: {e}")
                        continue

                    existing_data = read_existing_file(destination_file)
                    new_content_to_append = new_data[len(existing_data):] if new_data.startswith(existing_data) else new_data

                    if new_content_to_append:
                        append_new_data(destination_file, new_content_to_append)
                        logger.info(f"Appended new data to {destination_file}")
                        input_queue.put(destination_file)

                    last_checked_times[file] = modification_time

            time.sleep(2) 
        except Exception as e:
            logger.error(f"Error in pull_data_process: {e}", exc_info=True)
            time.sleep(5)



def process_file(input_queue, output_queue, data_directory):
    logger = setup_logger("process_file")
    logger.info("Process file started")
    last_positions = {}

    while True:
        try:
            if input_queue.empty():
                time.sleep(1)
                continue
            else:
                file_path = input_queue.get()
                logger.info(f"Processing file: {file_path}")
                if file_path not in last_positions:
                    last_positions[file_path] = 0

                start_time = timeit.default_timer()
                with open(file_path, 'r') as file:
                    file.seek(last_positions[file_path])
                    new_data = file.read()
                    if new_data:
                        read_data_start = timeit.default_timer()
                        unparsed_measurements = read_data(file_path)
                        read_data_time = timeit.default_timer() - read_data_start

                        preprocess_start = timeit.default_timer()
                        measurements = preprocess_measurements(unparsed_measurements)
                        preprocess_time = timeit.default_timer() - preprocess_start

                        gps_millis = measurements['GpsTimeNanos'].values / 1e6
                        load_ephemeris_start = timeit.default_timer()
                        ephemeris_files = load_ephemeris('rinex_nav', gps_millis.astype(np.int64), constellations=['gps'], download_directory=data_directory, verbose=True)
                        load_ephemeris_time = timeit.default_timer() - load_ephemeris_start

                        csv_output = []
                        for epoch in measurements['Epoch'].unique():
                            one_epoch = measurements.loc[(measurements['Epoch'] == epoch)].drop_duplicates(subset='SvName').set_index('SvName')
                            if len(one_epoch.index) > 4:
                                timestamp = one_epoch.iloc[0]['UnixTime'].to_pydatetime(warn=False)
                                gps_time = gps_millis[epoch]

                                sats = one_epoch.index.unique().tolist()
                                rinex_data = RinexNav(ephemeris_files, sats)
                                rinex_nav_df = rinex_data.pandas_df()

                                calculate_satellite_position_start = timeit.default_timer()
                                sv_positions = calculate_satellite_position(rinex_nav_df, gps_time)
                                calculate_satellite_position_time = timeit.default_timer() - calculate_satellite_position_start

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
                        logger.info(f"Processed {len(csv_output)} measurements from {file_path}")

                        last_positions[file_path] = file.tell()
                        output_queue.put(csv_df)

                total_time = timeit.default_timer() - start_time
                logger.info(f"Total time for processing file: {total_time:.4f}s")
                logger.info(f"Time for read_data: {read_data_time:.4f}s")
                logger.info(f"Time for preprocess_measurements: {preprocess_time:.4f}s")
                logger.info(f"Time for load_ephemeris: {load_ephemeris_time:.4f}s")
                logger.info(f"Time for calculate_satellite_position: {calculate_satellite_position_time:.4f}s")

        except Exception as e:
            logger.error(f"An error occurred while processing {file_path}: {e}", exc_info=True)
            time.sleep(5)

def write_csv_task(output_queue):
    logger = setup_logger("write_csv_task")
    logger.info("Write CSV task started")

    while True:
        try:
            if output_queue.empty():
                time.sleep(1)
            else:
                logger.info("Checking output queue for DataFrame")
                csv_df = output_queue.get()
                logger.info(f"Received DataFrame with shape: {csv_df.shape}")
                if not csv_df.empty:
                    csv_df.to_csv("gnss_measurements_output.csv", mode='a', header=False, index=False)
                    logger.info(f"Appended {csv_df.shape[0]} rows to gnss_measurements_output.csv")
        except Exception as e:
            logger.error("An error occurred in write_csv_task", exc_info=True)
            time.sleep(5)

import psutil

def set_affinity(process, core_id):
    p = psutil.Process(process.pid)
    p.cpu_affinity([core_id])

def main():
    logger = setup_logger("main")

    directory_to_pull = '/storage/emulated/0/Android/data/com.android.gpstest/files/gnss_log/'
    destination = './'
    args = parse_arguments()

    input_queue = Queue()
    output_queue = Queue()

    pull_process = Process(target=pull_data_process, args=(directory_to_pull, destination, input_queue))
    process_process = Process(target=process_file, args=(input_queue, output_queue, args.data_directory))
    write_process = Process(target=write_csv_task, args=(output_queue,))

    pull_process.start()
    set_affinity(pull_process, 0)

    process_process.start()
    set_affinity(process_process, 1)

    write_process.start()
    set_affinity(write_process, 2)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, stopping processes.")
        pull_process.terminate()
        process_process.terminate()
        write_process.terminate()

    pull_process.join()
    process_process.join()
    write_process.join()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"An error occurred: {e}")
        traceback.print_exc()
