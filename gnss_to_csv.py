"""
GNSS Data Processing Script

This script processes GNSS log files to extract, preprocess, and analyze GNSS measurements. It performs various checks to
ensure data quality, including AGC/CN0 checks, SVID sanity checks, cross-correlation checks, and time consistency checks.
The script also calculates satellite positions and flags suspicious measurements (which might indicate on satellite spoofing, etc..)

"""

import traceback
import os
import argparse
import pandas as pd
import numpy as np

from gnssutils import (
    EphemerisManager, read_data, preprocess_measurements, calculate_satellite_position,
    check_agc_cn0, check_svid_sanity, check_time_consistency,
    check_cross_correlation, LIGHTSPEED, unix_millis_to_gps_time
)

pd.options.mode.chained_assignment = None

def parse_arguments():
    """
    Parses command-line arguments and gets the GNSS log file name from the user.

    Returns:
        args (argparse.Namespace): Parsed command-line arguments including the data directory and input file.
    """
    parser = argparse.ArgumentParser(description='Process GNSS log files for positioning.')

    # Add --data_directory argument
    parser.add_argument('--data_directory', type=str, help='Directory for ephemeris data', default=os.getcwd())

    args = parser.parse_args()

    # Get the input file name from the user
    input_file = input("Enter the GNSS log file name: ")
    args.input_file = input_file

    return args

def main():
    """
    Main function that orchestrates the GNSS data processing.
    """
    # Cleanup in case there are old files
    old_csv_file = "gnss_measurements_output.csv"
    if os.path.exists(old_csv_file):
        os.remove(old_csv_file)

    args = parse_arguments()
    # TODO: add cleanup of existing igs & nasa folders
    unparsed_measurements, android_fixes = read_data(args.input_file)
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
            
    csv_df = pd.DataFrame(csv_output)
    csv_df.to_csv("gnss_measurements_output.csv", index=False)
    android_fixes.to_csv("android_fixes.csv", index=False)

try:
    main()
except Exception as e:
    print(f"An error occurred: {e}")
    traceback.print_exc() 
