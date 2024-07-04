import traceback
import os
import csv
import argparse
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np
from gnssutils import EphemerisManager

pd.options.mode.chained_assignment = None

# TODO: logging?

# Constants
WEEKSEC = 604800
LIGHTSPEED = 2.99792458e8
GPS_EPOCH = datetime(1980, 1, 6, 0, 0, 0)

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
    constellation_map = {
        '1': 'G',  # GPS
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

def check_agc_cn0(measurements):
    # Define thresholds
    AGC_THRESHOLD = 2.5  # This value should be adjusted based on your specific receiver
    CN0_THRESHOLD = 30  # dB-Hz, typical minimum for good signal quality

    # Check AGC (assuming AGC data is available in the measurements)
    if 'AgcDb' in measurements.columns:
        # Convert AgcDb to numeric, replacing any non-convertible values with NaN
        measurements['AgcDb'] = pd.to_numeric(measurements['AgcDb'], errors='coerce')
        measurements['AGC_suspicious'] = measurements['AgcDb'] > AGC_THRESHOLD
    else:
        measurements['AGC_suspicious'] = False

    # Check C/N0
    measurements['CN0_suspicious'] = pd.to_numeric(measurements['Cn0DbHz'], errors='coerce') < CN0_THRESHOLD

    # Flag suspicious measurements
    measurements['suspicious'] = measurements['AGC_suspicious'] | measurements['CN0_suspicious']

    return measurements

def check_svid_sanity(measurements, ephemeris):
    # Check if SVID exists in ephemeris data
    measurements['SVID_exists'] = measurements['SvName'].isin(ephemeris.index)

    # Check for duplicate SVIDs
    svid_counts = measurements.groupby('Epoch')['SvName'].value_counts()
    duplicate_svids = svid_counts[svid_counts > 1].index.get_level_values('SvName')
    measurements['SVID_duplicate'] = measurements['SvName'].isin(duplicate_svids)

    # Flag suspicious measurements
    measurements['suspicious'] |= ~measurements['SVID_exists'] | measurements['SVID_duplicate']

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
    
def check_satellite_position(sv_position, receiver_position, max_distance_error=1000):
    """
    Check if the calculated satellite position is within a reasonable range of the receiver.
    
    :param sv_position: DataFrame containing satellite positions
    :param receiver_position: Approximate receiver position (x, y, z) in ECEF coordinates
    :param max_distance_error: Maximum allowed distance error in meters
    :return: Series indicating if each satellite's position is suspicious
    """
    rx = np.array(receiver_position)
    distances = np.sqrt(((sv_position[['x_k', 'y_k', 'z_k']] - rx)**2).sum(axis=1))
    max_theoretical_distance = 26600000  # Approx. max distance to a GPS satellite in meters
    return (distances > max_theoretical_distance + max_distance_error) | (distances < max_distance_error)

def check_time_consistency(measurements, max_time_error=1):
    current_time = datetime.now(timezone.utc)
    
    # Ensure UnixTime is timezone-aware
    if measurements['UnixTime'].dt.tz is None:
        measurements['UnixTime'] = measurements['UnixTime'].dt.tz_localize('UTC')
    
    time_diff = (current_time - measurements['UnixTime']).dt.total_seconds().abs()
    return time_diff > max_time_error

def check_cross_correlation(measurements, correlation_threshold=0.95):
    suspicious = pd.Series(False, index=measurements.index)
    
    for epoch in measurements['Epoch'].unique():
        epoch_data = measurements[measurements['Epoch'] == epoch]
        
        epoch_data['UniqueID'] = epoch_data['UnixTime'].astype(str) + '_' + epoch_data['SvName']
        pivot_data = epoch_data.pivot(index='UniqueID', columns='SvName', values='PrM')
        
        # Calculate correlation matrix only if there are at least 2 columns (satellites)
        if pivot_data.shape[1] >= 2:
            corr_matrix = pivot_data.corr()
            high_corr = (corr_matrix.abs() > correlation_threshold) & (corr_matrix.abs() < 1.0)
            suspicious_sats = high_corr.index[high_corr.any()]
            suspicious.loc[epoch_data.index] |= epoch_data['SvName'].isin(suspicious_sats)
    
    return suspicious

def main():
    #cleanup incase there are old files#
    old_csv_file = "gnss_measurements_output.csv"
    if os.path.exists(old_csv_file):
        os.remove(old_csv_file)

    args = parse_arguments()
    # TODO: add cleanup of existing igs & nasa folders
    unparsed_measurements = read_data(args.input_file)
    measurements = preprocess_measurements(unparsed_measurements)
    measurements = check_agc_cn0(measurements)

    # Perform cross-correlation check
    measurements['corr_suspicious'] = check_cross_correlation(measurements)
    print(args.data_directory)
    manager = EphemerisManager(args.data_directory)
        
    receiver_position = (0, 0, 0)  # Earth's center as a fallback
    csv_output = []
    for epoch in measurements['Epoch'].unique():
        one_epoch = measurements.loc[(measurements['Epoch'] == epoch) & (measurements['prSeconds'] < 0.1)] 
        one_epoch = one_epoch.drop_duplicates(subset='SvName').set_index('SvName')
        if len(one_epoch.index) > 4:
            timestamp = one_epoch.iloc[0]['UnixTime'].to_pydatetime(warn=False)
            
            # Calculating satellite positions (ECEF)
            sats = one_epoch.index.unique().tolist()
            ephemeris = manager.get_ephemeris(timestamp, sats)
            one_epoch = check_svid_sanity(one_epoch.reset_index(), ephemeris).set_index('SvName')
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
                    "SatX": sv_position.at[sv, 'x_k'] if sv in sv_position.index else np.nan,
                    "SatY": sv_position.at[sv, 'y_k'] if sv in sv_position.index else np.nan,
                    "SatZ": sv_position.at[sv, 'z_k'] if sv in sv_position.index else np.nan,
                    "Pseudo-Range": one_epoch.at[sv, 'PrM_corrected'],
                    "CN0": one_epoch.at[sv, 'Cn0DbHz'],
                    "Doppler": one_epoch.at[sv, 'DopplerShiftHz'] if doppler_calculated else 'NaN',
                    "Suspicious": (one_epoch.at[sv, 'suspicious'] | 
                                   one_epoch.at[sv, 'corr_suspicious'])
                })
            
    # TODO: file name should be more similar to input file name
    csv_df = pd.DataFrame(csv_output)
    csv_df.to_csv("gnss_measurements_output.csv", index=False)

try:
    main()
except Exception as e:
    print(f"An error occurred: {e}")
    traceback.print_exc() 