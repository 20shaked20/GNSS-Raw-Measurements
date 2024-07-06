"""
GNSS Data Processing and Satellite Position Calculation

This script provides functions for processing GNSS (Global Navigation Satellite System) data
and calculating satellite positions based on ephemeris data. It supports various GNSS
constellations, with a focus on GPS and GLONASS.

Key features:
- Reading and preprocessing raw GNSS measurements from CSV files
- Calculating satellite positions for GPS and GLONASS constellations
- Converting between different time formats (Unix, GPS)
"""

import csv
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np
from .constants import WEEKSEC, LIGHTSPEED, GPS_EPOCH, MU, OMEGA_E_DOT, GLONASS_TIME_OFFSET

def read_data(input_filepath):
    """
    Reads GNSS log data from a CSV file.

    Args:
        input_filepath (str): Path to the input CSV file.

    Returns:
        pd.DataFrame: DataFrame containing the raw GNSS measurements.
        pd.DataFrame: DataFrame containing Android Fix data.
    """
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

    return pd.DataFrame(measurements[1:], columns=measurements[0]), pd.DataFrame(android_fixes[1:], columns = android_fixes[0])

def preprocess_measurements(measurements):
    """
    Preprocesses the raw GNSS measurements.

    Args:
        measurements (pd.DataFrame): DataFrame containing the raw GNSS measurements.

    Returns:
        pd.DataFrame: DataFrame containing the preprocessed GNSS measurements.
    """
    # Format satellite IDs
    measurements.loc[measurements['Svid'].str.len() == 1, 'Svid'] = '0' + measurements['Svid']
    constellation_map = {
        '1': 'G',  # GPS
        # Uncomment below lines to include other constellations
        #'3': 'R',  # GLONASS
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
    measurements['UnixTime'] = pd.to_datetime(measurements['GpsTimeNanos'], unit='ns', origin=GPS_EPOCH).dt.tz_localize('UTC')

    # Identify epochs based on time gaps
    measurements['Epoch'] = 0
    time_diff = measurements['UnixTime'] - measurements['UnixTime'].shift()
    measurements.loc[time_diff > timedelta(milliseconds=200), 'Epoch'] = 1
    measurements['Epoch'] = measurements['Epoch'].cumsum()

    # Ensure UnixTime is unique within each epoch
    measurements['UnixTime'] = measurements.groupby('Epoch')['UnixTime'].transform(lambda x: x + pd.to_timedelta(range(len(x)), unit='ns'))

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

def calculate_glonass_position(ephemeris, transmit_time):
    """
    Calculates the satellite positions for GLONASS based on ephemeris data.

    Args:
        ephemeris (pd.DataFrame): DataFrame containing the ephemeris data for GLONASS.
        transmit_time (pd.Series): Series containing the transmit times.

    Returns:
        pd.DataFrame: DataFrame containing the calculated satellite positions.
    """

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
    rotation_angle = OMEGA_E_DOT * sv_position['t_k']
    cos_angle = np.cos(rotation_angle)
    sin_angle = np.sin(rotation_angle)

    sv_position['x_k_corrected'] = sv_position['x_k'] * cos_angle + sv_position['y_k'] * sin_angle
    sv_position['y_k_corrected'] = -sv_position['x_k'] * sin_angle + sv_position['y_k'] * cos_angle
    sv_position['z_k_corrected'] = sv_position['z_k']  # Z-coordinate remains the same

    # Calculate the clock correction
    sv_position['delT_sv'] = ephemeris['SVclockBias'] + ephemeris['SVrelFreqBias'] * (adjusted_transmit_time - ephemeris['t_oc'])

    return sv_position


def calculate_satellite_position(ephemeris, transmit_time):
    """
    Calculates the satellite positions based on ephemeris data.

    Args:
        ephemeris (pd.DataFrame): DataFrame containing the ephemeris data.
        transmit_time (pd.Series): Series containing the transmit times.

    Returns:
        pd.DataFrame: DataFrame containing the calculated satellite positions.
    """
    F = -4.442807633e-10
    sv_position = pd.DataFrame()
    sv_position['sv'] = ephemeris.index
    sv_position.set_index('sv', inplace=True)
    sv_position['t_k'] = transmit_time - ephemeris['t_oe']
    A = ephemeris['sqrtA'].pow(2)
    n_0 = np.sqrt(MU / A.pow(3))
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

    v_k = np.arctan2(np.sqrt(1-ephemeris['e'].pow(2))*sinE_k, (cosE_k - ephemeris['e']))

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

    Omega_k = ephemeris['Omega_0'] + (ephemeris['OmegaDot'] - OMEGA_E_DOT)*sv_position['t_k'] - OMEGA_E_DOT*ephemeris['t_oe']

    sv_position['x_k'] = x_k_prime*np.cos(Omega_k) - y_k_prime*np.cos(i_k)*np.sin(Omega_k)
    sv_position['y_k'] = x_k_prime*np.sin(Omega_k) + y_k_prime*np.cos(i_k)*np.cos(Omega_k)
    sv_position['z_k'] = y_k_prime*np.sin(i_k)
    
    return sv_position

def unix_millis_to_gps_time(unix_millis):
    """Convert Unix milliseconds to GPS Time string format."""
    unix_time = datetime.fromtimestamp(float(unix_millis) / 1000.0, tz=timezone.utc)
    return unix_time.isoformat()