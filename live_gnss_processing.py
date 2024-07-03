import subprocess
import os
import csv
import argparse
import traceback
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import time
from gnssutils import EphemerisManager

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

#TODO: make the ADB commands outside file that we can use, instead on this one 
def run_adb_command(command):
    result = subprocess.run(['android_platform_tools/adb'] + command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
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

""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

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
    # Format satellite IDs
    measurements.loc[measurements['Svid'].str.len() == 1, 'Svid'] = '0' + measurements['Svid']
    constellation_map = {
        '1': 'G',  # GPS
        # '3': 'R',  # GLONASS
        #'5': 'E',  # Galileo
        #'6': 'C',  # Beidou
    }
    measurements['Constellation'] = measurements['ConstellationType'].map(constellation_map)
    measurements['SvName'] = measurements['Constellation'] + measurements['Svid']
    measurements = measurements[measurements['Constellation'].isin(constellation_map.values())]
    # Convert columns to numeric representation and handle missing data robustly
    numeric_cols = ['Cn0DbHz', 'TimeNanos', 'FullBiasNanos', 'ReceivedSvTimeNanos',
                    'PseudorangeRateMetersPerSecond', 'ReceivedSvTimeUncertaintyNanos',
                    'BiasNanos', 'TimeOffsetNanos']
    for col in numeric_cols:
        measurements[col] = pd.to_numeric(measurements[col], errors='coerce').fillna(0)
    # Generate GPS and Unix timestamps
    measurements['GpsTimeNanos'] = measurements['TimeNanos'] - (measurements['FullBiasNanos'] - measurements['BiasNanos'])
    measurements['UnixTime'] = pd.to_datetime(measurements['GpsTimeNanos'], utc=True, origin=GPS_EPOCH)
    # Identify epochs based on time gaps
    measurements['Epoch'] = 0
    time_diff = measurements['UnixTime'] - measurements['UnixTime'].shift()
    measurements.loc[time_diff > timedelta(milliseconds=200), 'Epoch'] = 1
    measurements['Epoch'] = measurements['Epoch'].cumsum()
    # Calculations related to GNSS Nanos, week number, seconds, pseudorange
    measurements['tRxGnssNanos'] = measurements['TimeNanos'] + measurements['TimeOffsetNanos'] - \
                                   (measurements['FullBiasNanos'].iloc[0] + measurements['BiasNanos'].iloc[0])
    measurements['GpsWeekNumber'] = np.floor(1e-9 * measurements['tRxGnssNanos'] / WEEKSEC)
    measurements['tRxSeconds'] = 1e-9 * measurements['tRxGnssNanos'] - WEEKSEC * measurements['GpsWeekNumber']
    measurements['tTxSeconds'] = 1e-9 * (measurements['ReceivedSvTimeNanos'] + measurements['TimeOffsetNanos'])
    measurements['prSeconds'] = measurements['tRxSeconds'] - measurements['tTxSeconds']
    # Convert pseudorange from seconds to meters
    measurements['PrM'] = LIGHTSPEED * measurements['prSeconds']
    measurements['PrSigmaM'] = LIGHTSPEED * 1e-9 * measurements['ReceivedSvTimeUncertaintyNanos']
    return measurements


def calculate_satellite_position(ephemeris, transmit_time):
    mu = 3.986005e14
    OmegaDot_e = 7.2921151467e-5
    F = -4.442807633e-10
    sv_position = pd.DataFrame()
    sv_position['sv']= ephemeris.index
    sv_position.set_index('sv', inplace=True)
    sv_position['t_k'] = transmit_time - ephemeris['t_oe']

    A = ephemeris['sqrtA'].pow(2)
    n_0 = np.sqrt(mu / A.pow(3))
    n = n_0 + ephemeris['deltaN']
    M_k = ephemeris['M_0'] + n * sv_position['t_k']
    E_k = M_k
    err = pd.Series(data=[1]*len(sv_position.index))
    i = 0
    while err.abs().min() > 1e-8 and i < 10:
        new_vals = M_k + ephemeris['e']*np.sin(E_k)
        err = new_vals - E_k
        E_k = new_vals
        i += 1
        
    sinE_k = np.sin(E_k)
    cosE_k = np.cos(E_k)
    delT_r = F * ephemeris['e'].pow(ephemeris['sqrtA']) * sinE_k
    delT_oc = transmit_time - ephemeris['t_oc']
    sv_position['delT_sv'] = ephemeris['SVclockBias'] + ephemeris['SVclockDrift'] * delT_oc + ephemeris['SVclockDriftRate'] * delT_oc.pow(2)

    v_k = np.arctan2(np.sqrt(1-ephemeris['e'].pow(2))*sinE_k,(cosE_k - ephemeris['e']))

    Phi_k = v_k + ephemeris['omega']

    sin2Phi_k = np.sin(2*Phi_k)
    cos2Phi_k = np.cos(2*Phi_k)

    du_k = ephemeris['C_us']*sin2Phi_k + ephemeris['C_uc']*cos2Phi_k
    dr_k = ephemeris['C_rs']*sin2Phi_k + ephemeris['C_rc']*cos2Phi_k
    di_k = ephemeris['C_is']*sin2Phi_k + ephemeris['C_ic']*cos2Phi_k

    u_k = Phi_k + du_k

    r_k = A*(1 - ephemeris['e']*np.cos(E_k)) + dr_k

    i_k = ephemeris['i_0'] + di_k + ephemeris['IDOT']*sv_position['t_k']

    x_k_prime = r_k*np.cos(u_k)
    y_k_prime = r_k*np.sin(u_k)

    Omega_k = ephemeris['Omega_0'] + (ephemeris['OmegaDot'] - OmegaDot_e)*sv_position['t_k'] - OmegaDot_e*ephemeris['t_oe']

    sv_position['x_k'] = x_k_prime*np.cos(Omega_k) - y_k_prime*np.cos(i_k)*np.sin(Omega_k)
    sv_position['y_k'] = x_k_prime*np.sin(Omega_k) + y_k_prime*np.cos(i_k)*np.cos(Omega_k)
    sv_position['z_k'] = y_k_prime*np.sin(i_k)
    return sv_position

def calculate_glonass_position(ephemeris, transmit_time):
    # Constants
    Omega_e = 7.2921151467e-5  # Earth's rotation rate in rad/s
    GLONASS_TIME_OFFSET = 3 * 3600  # 3 hours in seconds

    # Initialize DataFrame to store satellite positions
    sv_position = pd.DataFrame()
    sv_position['sv'] = ephemeris.index
    sv_position.set_index('sv', inplace=True)

    # Adjust transmit time by GLONASS time offset
    adjusted_transmit_time = transmit_time + GLONASS_TIME_OFFSET

    # Compute the time from ephemeris reference epoch
    sv_position['t_k'] = adjusted_transmit_time - ephemeris['MessageFrameTime']

    # Compute the satellite position at t_k
    sv_position['x_k'] = ephemeris['X'] + ephemeris['dX'] * sv_position['t_k']
    sv_position['y_k'] = ephemeris['Y'] + ephemeris['dY'] * sv_position['t_k']
    sv_position['z_k'] = ephemeris['Z'] + ephemeris['dZ'] * sv_position['t_k']

    # Apply Earth rotation correction
    rotation_angle = Omega_e * sv_position['t_k']
    cos_angle = np.cos(rotation_angle)
    sin_angle = np.sin(rotation_angle)

    sv_position['x_k_corrected'] = sv_position['x_k'] * cos_angle + sv_position['y_k'] * sin_angle
    sv_position['y_k_corrected'] = -sv_position['x_k'] * sin_angle + sv_position['y_k'] * cos_angle
    sv_position['z_k_corrected'] = sv_position['z_k']  # Z-coordinate remains the same

    # Calculate the clock correction
    sv_position['delT_sv'] = ephemeris['SVclockBias'] + ephemeris['SVrelFreqBias'] * (adjusted_transmit_time - ephemeris['t_oc'])

    return sv_position


def process_new_data(file_path, measurements, EphemManager, last_processed_time):
    try:
        unparsed_new_data = read_data(file_path)
        new_measurements = preprocess_measurements(unparsed_new_data)
        new_measurements = new_measurements[new_measurements['UnixTime'] > last_processed_time]

        if new_measurements.empty:
            print("No new data to process.")
            return last_processed_time

        measurements = pd.concat([measurements, new_measurements]).reset_index(drop=True)

        csv_output = []
        for epoch in measurements['Epoch'].unique():
            one_epoch = new_measurements.loc[(new_measurements['Epoch'] == epoch) & (new_measurements['prSeconds'] < 0.1)]
            one_epoch = new_measurements.loc[(new_measurements['Epoch'] == epoch)].drop_duplicates(subset='SvName').set_index('SvName')
            if len(one_epoch.index) > 4:
                timestamp = one_epoch.iloc[0]['UnixTime'].to_pydatetime(warn=False)

                # Calculating satellite positions (ECEF)
                sats = one_epoch.index.unique().tolist()

                # Caching
                new_satellites = set(sats) - seen_satellites
                if new_satellites:
                    ephemeris = EphemManager.get_ephemeris(timestamp, sats)
                    # Update the cache
                    for sv in new_satellites:
                        if sv in ephemeris.index:
                            # Extract constellation type from the satellite ID (first character of sv)
                            constellation_type = sv[0]
                            # Add constellation type to the ephemeris data before caching
                            ephemeris.loc[sv, 'ConstellationType'] = constellation_type
                            # Filter based on index and store in satellite_cache
                            satellite_cache[sv] = ephemeris.loc[[sv]]

                    seen_satellites.update(new_satellites)

                # Combine cached satellite data with new data
                cached_data = pd.concat(satellite_cache.values())

                # Separate by constellation type
                gps_ephemeris = cached_data[cached_data['ConstellationType'] == "G"]
                glonass_ephemeris = cached_data[cached_data['ConstellationType'] == "R"]

                gps_sv_position = pd.DataFrame()
                glonass_sv_position = pd.DataFrame()

                # Ensure ConstellationType is assigned in one_epoch
                one_epoch['ConstellationType'] = one_epoch.index.str[0]

                # Separate transmit times by constellation type
                gps_transmit_times = one_epoch[one_epoch['ConstellationType'] == 'G']['tTxSeconds']
                glonass_transmit_times = one_epoch[one_epoch['ConstellationType'] == 'R']['tTxSeconds']

                if not gps_ephemeris.empty and not gps_transmit_times.empty:
                    gps_sv_position = calculate_satellite_position(gps_ephemeris, gps_transmit_times)

                if not glonass_ephemeris.empty and not glonass_transmit_times.empty:
                    glonass_sv_position = calculate_glonass_position(glonass_ephemeris, glonass_transmit_times)

                # Combine GPS and GLONASS positions
                sv_position = pd.concat([gps_sv_position, glonass_sv_position])

                # Apply satellite clock bias to correct the measured pseudorange values
                # Ensure sv_position's index matches one_epoch's index
                sv_position.index = sv_position.index.map(str)  # Ensuring index types match; adjust as needed
                one_epoch = one_epoch.join(sv_position[['delT_sv']], how='left')
                one_epoch['PrM_corrected'] = one_epoch['PrM'] + LIGHTSPEED * one_epoch['delT_sv']

                # Doppler shift calculation
                doppler_calculated = False
                try:
                    one_epoch['CarrierFrequencyHz'] = pd.to_numeric(one_epoch['CarrierFrequencyHz'])
                    one_epoch['DopplerShiftHz'] = -(one_epoch['PseudorangeRateMetersPerSecond'] / LIGHTSPEED) * one_epoch['CarrierFrequencyHz']
                    doppler_calculated = True
                except Exception:
                    pass

                for sv in one_epoch.index:
                    csv_output.append({
                        "GPS Time": timestamp.isoformat(),
                        "SatPRN (ID)": sv,
                        "SatX": sv_position.at[sv, 'x_k'] if sv in sv_position.index else np.nan,
                        "SatY": sv_position.at[sv, 'y_k'] if sv in sv_position.index else np.nan,
                        "SatZ": sv_position.at[sv, 'z_k'] if sv in sv_position.index else np.nan,
                        "Pseudo-Range": one_epoch.at[sv, 'PrM_corrected'],
                        "CN0": one_epoch.at[sv, 'Cn0DbHz'],
                        "Doppler": one_epoch.at[sv, 'DopplerShiftHz'] if doppler_calculated else 'NaN'
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


def main():
    #cleanup incase there are old files#
    old_csv_file = "gnss_measurements_output.csv"
    if os.path.exists(old_csv_file):
        os.remove(old_csv_file)
    
    old_init_gnss = "initial_gnss_log.txt"
    if os.path.exists(old_init_gnss):
        os.remove(old_init_gnss)
    
    directory_to_pull = '/storage/emulated/0/Android/data/com.android.gpstest/files/gnss_log/'
    destination = './'
    delete_files_in_directory(directory_to_pull)

    last_checked_times = {}
    last_processed_time = None

    #waiting for the initial file to be generated
    initial_file = None
    while not initial_file:
        files = get_files_in_directory(directory_to_pull)
        if files:
            time.sleep(5)
            initial_file = f'{directory_to_pull}/{files[0]}'
        else:
            print("Waiting for the initial file to be generated...")
            time.sleep(5) 

    # Initial setup
    initial_data = pull_file(initial_file)
    destination_file = f'{destination}/initial_gnss_log.txt'
    with open(destination_file, 'w') as file:
        file.write(initial_data)

    unparsed_measurments = read_data(destination_file)
    measurements = preprocess_measurements(unparsed_measurments)
    last_processed_time = measurements['UnixTime'].max()
    
    EphemManager = EphemerisManager()

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
                        last_processed_time = process_new_data(destination_file, measurements, EphemManager, last_processed_time)

                    last_checked_times[file] = modification_time
        except Exception as e:
            print(f"Error in main loop: {e}")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"An error occurred: {e}")
        traceback.print_exc()
