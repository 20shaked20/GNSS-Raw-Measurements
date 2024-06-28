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
from gnssutils import EphemerisManager

pd.options.mode.chained_assignment = None

# Constants
WEEKSEC = 604800
LIGHTSPEED = 2.99792458e8
GPS_EPOCH = datetime(1980, 1, 6, 0, 0, 0)


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
        # Get list of files in the directory
        files = get_files_in_directory(directory)
        
        for file in files:
            file_to_delete = f'{directory}/{file}'
            
            # Delete the file
            delete_command = ['shell', 'rm', file_to_delete]
            run_adb_command(delete_command)
            print(f"Deleted {file_to_delete}")
    
    except Exception as e:
        print(e)

def pull_and_append_files(directory_to_pull, destination):
    try:
        # Get list of files in the directory
        files = get_files_in_directory(directory_to_pull)
        
        for file in files:
            file_to_pull = f'{directory_to_pull}/{file}'
            destination_file = f'{destination}{file}'
            
            # Pull the file content from the device
            pull_command = ['shell', 'cat', file_to_pull]
            new_data = run_adb_command(pull_command)
            
            # Read existing file content if it exists
            existing_data = read_existing_file(destination_file)
            
            # Find the new data to append
            if new_data.startswith(existing_data):
                new_content_to_append = new_data[len(existing_data):]
            else:
                new_content_to_append = new_data
            
            # Append new data if there's any new content
            if new_content_to_append:
                append_new_data(destination_file, new_content_to_append)
                print(f"Appended new data to {destination_file}")
                process_file(destination_file)  # Process the new data
            else:
                # print(f"No new data to append for {destination_file}")
                pass
    
    except Exception as e:
        print(e)


""""""""""""""""""""""""""""""""""""""""""""""""
def parse_arguments():
    parser = argparse.ArgumentParser(description='Process GNSS log files for positioning.')

    # add --data_directory argument
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
    measurements['Constellation'] = measurements['ConstellationType'].map({'1': 'G', '3': 'R'})
    measurements['SvName'] = measurements['Constellation'] + measurements['Svid']
    measurements = measurements[measurements['Constellation'] == 'G']
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

def process_file(file_path):
    args = parse_arguments()
    try:
        unparsed_measurements = read_data(file_path)
        measurements = preprocess_measurements(unparsed_measurements)
        print(args.data_directory)
        manager = EphemerisManager(args.data_directory)

        csv_output = []
        for epoch in measurements['Epoch'].unique():
            one_epoch = measurements.loc[(measurements['Epoch'] == epoch) & (measurements['prSeconds'] < 0.1)] 
            one_epoch = one_epoch.drop_duplicates(subset='SvName').set_index('SvName')
            if len(one_epoch.index) > 4:
                timestamp = one_epoch.iloc[0]['UnixTime'].to_pydatetime(warn=False)

                # Calculating satellite positions (ECEF)
                sats = one_epoch.index.unique().tolist()
                ephemeris = manager.get_ephemeris(timestamp, sats)
                sv_position = calculate_satellite_position(ephemeris, one_epoch['tTxSeconds'])

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
                        "Sat.X": sv_position.at[sv, 'x_k'] if sv in sv_position.index else np.nan,
                        "Sat.Y": sv_position.at[sv, 'y_k'] if sv in sv_position.index else np.nan,
                        "Sat.Z": sv_position.at[sv, 'z_k'] if sv in sv_position.index else np.nan,
                        "Pseudo-Range": one_epoch.at[sv, 'PrM_corrected'],
                        "CN0": one_epoch.at[sv, 'Cn0DbHz'],
                        "Doppler": one_epoch.at[sv, 'DopplerShiftHz'] if doppler_calculated else 'NaN'
                    })

        csv_df = pd.DataFrame(csv_output)
        csv_df.to_csv("gnss_measurements_output.csv", index=False)
    except Exception as e:
        print(f"An error occurred while processing {file_path}: {e}")
        traceback.print_exc()

def main():
    args = parse_arguments()
    directory_to_pull = '/storage/emulated/0/Android/data/com.android.gpstest/files/gnss_log/'
    destination = './'

    #clear the data from the directory so we can append the new file
    delete_files_in_directory('/storage/emulated/0/Android/data/com.android.gpstest/files/gnss_log/')

    while True:
        pull_and_append_files(directory_to_pull, destination)
        # time.sleep(1)  # Polling interval, adjust as needed

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"An error occurred: {e}")
        traceback.print_exc()
