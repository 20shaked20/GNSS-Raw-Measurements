# TODO: Clean up imports

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

pd.options.mode.chained_assignment = None

# TODO: logging?

# Constants
WEEKSEC = 604800
LIGHTSPEED = 2.99792458e8
GPS_EPOCH = datetime(1980, 1, 6, 0, 0, 0)

def parse_arguments():
    # TODO: simplify names
    parser = argparse.ArgumentParser(description='Process GNSS log files for positioning.')
    parser.add_argument('--input_file', type=str, help='Input GNSS log file', required=True)
    parser.add_argument('--data_directory', type=str, help='Directory for ephemeris data', default=os.getcwd())
    return parser.parse_args()

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
    # Format satellite IDs
    measurements.loc[measurements['Svid'].str.len() == 1, 'Svid'] = '0' + measurements['Svid']
    measurements.loc[measurements['ConstellationType'] == '1', 'Constellation'] = 'G'
    measurements.loc[measurements['ConstellationType'] == '3', 'Constellation'] = 'R'
    measurements['SvName'] = measurements['Constellation'] + measurements['Svid']

    # Remove all non-GPS measurements
    measurements = measurements.loc[measurements['Constellation'] == 'G']

    # Convert columns to numeric representation
    measurements['Cn0DbHz'] = pd.to_numeric(measurements['Cn0DbHz'])
    measurements['TimeNanos'] = pd.to_numeric(measurements['TimeNanos'])
    measurements['FullBiasNanos'] = pd.to_numeric(measurements['FullBiasNanos'])
    measurements['ReceivedSvTimeNanos']  = pd.to_numeric(measurements['ReceivedSvTimeNanos'])
    measurements['PseudorangeRateMetersPerSecond'] = pd.to_numeric(measurements['PseudorangeRateMetersPerSecond'])
    measurements['ReceivedSvTimeUncertaintyNanos'] = pd.to_numeric(measurements['ReceivedSvTimeUncertaintyNanos'])

    # A few measurement values are not provided by all phones
    # We'll check for them and initialize them with zeros if missing
    if 'BiasNanos' in measurements.columns:
        measurements['BiasNanos'] = pd.to_numeric(measurements['BiasNanos'])
    else:
        measurements['BiasNanos'] = 0
    if 'TimeOffsetNanos' in measurements.columns:
        measurements['TimeOffsetNanos'] = pd.to_numeric(measurements['TimeOffsetNanos'])
    else:
        measurements['TimeOffsetNanos'] = 0
        
    # TIMESTAMP GENERATION
    measurements['GpsTimeNanos'] = measurements['TimeNanos'] - (measurements['FullBiasNanos'] - measurements['BiasNanos'])
    measurements['UnixTime'] = pd.to_datetime(measurements['GpsTimeNanos'], utc = True, origin=GPS_EPOCH)
    measurements['UnixTime'] = measurements['UnixTime']

    # Split data into measurement epochs
    measurements['Epoch'] = 0
    measurements.loc[measurements['UnixTime'] - measurements['UnixTime'].shift() > timedelta(milliseconds=200), 'Epoch'] = 1
    measurements['Epoch'] = measurements['Epoch'].cumsum()
    
    measurements['tRxGnssNanos'] = measurements['TimeNanos'] + measurements['TimeOffsetNanos'] - (measurements['FullBiasNanos'].iloc[0] + measurements['BiasNanos'].iloc[0])
    measurements['GpsWeekNumber'] = np.floor(1e-9 * measurements['tRxGnssNanos'] / WEEKSEC)
    measurements['tRxSeconds'] = 1e-9*measurements['tRxGnssNanos'] - WEEKSEC * measurements['GpsWeekNumber']
    measurements['tTxSeconds'] = 1e-9*(measurements['ReceivedSvTimeNanos'] + measurements['TimeOffsetNanos'])
    # Calculate pseudorange in seconds
    measurements['prSeconds'] = measurements['tRxSeconds'] - measurements['tTxSeconds']

    # Convert to meters
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

def main():
    args = parse_arguments()
    # TODO: add cleanup of existing igs & nasa folders
    unparsed_measurements = read_data(args.input_file)
    measurements = preprocess_measurements(unparsed_measurements)
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
            one_epoch['PseudorangeRateMetersPerSecond'] = pd.to_numeric(one_epoch['PseudorangeRateMetersPerSecond'])
            one_epoch['CarrierFrequencyHz'] = pd.to_numeric(one_epoch['CarrierFrequencyHz'])
            one_epoch['DopplerShiftHz'] = -(one_epoch['PseudorangeRateMetersPerSecond'] / LIGHTSPEED) * one_epoch['CarrierFrequencyHz']
        
            for sv in one_epoch.index:
                csv_output.append({
                    "GPS Time": timestamp.isoformat(),
                    "SatPRN (ID)": sv,
                    "Sat.X": sv_position.at[sv, 'x_k'] if sv in sv_position.index else np.nan,
                    "Sat.Y": sv_position.at[sv, 'y_k'] if sv in sv_position.index else np.nan,
                    "Sat.Z": sv_position.at[sv, 'z_k'] if sv in sv_position.index else np.nan,
                    "Pseudo-Range": one_epoch.at[sv, 'PrM_corrected'],
                    "CN0": one_epoch.at[sv, 'Cn0DbHz'],
                    "Doppler": one_epoch.at[sv, 'DopplerShiftHz']
                })
                
            # TODO: Positioning algo goes here
            #x, b, dp = least_squares(xs, pr, x, b) 
            #ecef_list.append(x)
            
    csv_df = pd.DataFrame(csv_output)
    csv_df.to_csv("gnss_measurements_output.csv", index=False)

try:
    main()
except Exception as e:
    print(f"An error occurred: {e}")
    traceback.print_exc()  # This prints the stack trace to the standard error