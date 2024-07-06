"""
Live GNSS Data Processing Script

"""

import os
import argparse
import traceback
import pandas as pd
import numpy as np
import time
import simplekml

from gnssutils.android_adb_utils import *
from gnssutils import (
    EphemerisManager, read_data, preprocess_measurements, calculate_satellite_position,
    check_agc_cn0, check_svid_sanity, check_time_consistency,
    check_cross_correlation, LIGHTSPEED
)

from rms_positioning import process_satellite_data, save_results_to_text, add_position_data_to_csv


pd.options.mode.chained_assignment = None

# Cache for satellite data
satellite_cache = {}
seen_satellites = set()

def parse_arguments():
    """
    Parses command-line arguments for the script.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(description='Process GNSS log files for positioning.')
    parser.add_argument('--data_directory', type=str, help='Directory for ephemeris data', default=os.getcwd())
    args = parser.parse_args()
    return args


def process_new_data(file_path, measurements, EphemManager, last_processed_time):
    """
    Processes new GNSS data from a file and updates the measurements DataFrame.

    Args:
        file_path (str): Path to the GNSS log file.
        measurements (pd.DataFrame): DataFrame containing the existing measurements.
        EphemManager (EphemerisManager): EphemerisManager object for fetching ephemeris data.
        last_processed_time (datetime): Timestamp of the last processed measurement.

    Returns:
        datetime: Updated timestamp of the last processed measurement.
    """
    try:
        unparsed_new_data, _ = read_data(file_path)
        new_measurements = preprocess_measurements(unparsed_new_data)
        new_measurements = check_agc_cn0(new_measurements)
        new_measurements['corr_suspicious'] = check_cross_correlation(new_measurements)
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
                    one_epoch = check_svid_sanity(one_epoch.reset_index(), ephemeris).set_index('SvName')
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
                sv_position = calculate_satellite_position(cached_data, one_epoch['tTxSeconds'])

                """"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
                # TODO:(not working for now)
                # Separate by constellation type 
                # gps_ephemeris = cached_data[cached_data['ConstellationType'] == "G"]
                # glonass_ephemeris = cached_data[cached_data['ConstellationType'] == "R"]

                # gps_sv_position = pd.DataFrame()
                # glonass_sv_position = pd.DataFrame()

                # # Separate transmit times by constellation type
                # gps_transmit_times = one_epoch[one_epoch['ConstellationType'] == 'G']['tTxSeconds']
                # glonass_transmit_times = one_epoch[one_epoch['ConstellationType'] == 'R']['tTxSeconds']

                # if not gps_ephemeris.empty and not gps_transmit_times.empty:
                #     gps_sv_position = calculate_satellite_position(gps_ephemeris, gps_transmit_times)

                # if not glonass_ephemeris.empty and not glonass_transmit_times.empty:
                #     glonass_sv_position = calculate_glonass_position(glonass_ephemeris, glonass_transmit_times)

                # Combine GPS and GLONASS positions
                # sv_position = pd.concat([gps_sv_position, glonass_sv_position])
                """"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

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

def clean_data():
    old_csv_file = "gnss_measurements_output.csv"
    if os.path.exists(old_csv_file):
        os.remove(old_csv_file)

    old_init_gnss = "initial_gnss_log.txt"
    if os.path.exists(old_init_gnss):
        os.remove(old_init_gnss)

    old_kml = "gnss_visualization.kml"
    if os.path.exists(old_kml):
        os.remove(old_kml)

    old_results = "RmsResults.txt"
    if os.path.exists(old_results):
        os.remove(old_results)


def main():
    
    clean_data()
    
    directory_to_pull = '/storage/emulated/0/Android/data/com.android.gpstest/files/gnss_log/'
    destination = './'
    delete_files_in_directory(directory_to_pull)

    last_checked_times = {}
    last_processed_time = None

    initial_file = None
    while not initial_file:
        files = get_files_in_directory(directory_to_pull)
        if files:
            time.sleep(5)
            initial_file = f'{directory_to_pull}/{files[0]}'
        else:
            print("Waiting for the initial file to be generated...")
            time.sleep(5)

    initial_data = pull_file(initial_file)
    destination_file = f'{destination}/initial_gnss_log.txt'
    with open(destination_file, 'w') as file:
        file.write(initial_data)

    unparsed_measurements, _ = read_data(destination_file)
    measurements = preprocess_measurements(unparsed_measurements)
    last_processed_time = measurements['UnixTime'].max()
    
    EphemManager = EphemerisManager()

    kml_update_interval = 1  # Update KML 1 sec
    last_kml_update_time = time.time()

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

            current_time = time.time()
            if current_time - last_kml_update_time >= kml_update_interval:
                kml = simplekml.Kml()
                data = pd.read_csv("gnss_measurements_output.csv")

                latest_gps_time = data['GPS Time'].max() # Group by latest GPS time
                latest_data = data[data['GPS Time'] == latest_gps_time]
                print(latest_data)

                results = process_satellite_data(latest_data, kml)
                save_results_to_text(results, "RmsResults.txt")
                add_position_data_to_csv(results, "gnss_measurements_output.csv", "gnss_measurements_output.csv")
                last_kml_update_time = current_time
                
                kml.save("gnss_visualization.kml")
                print("KML file updated successfully.")

        except Exception as e:
            print(f"Error in main loop: {e}")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"An error occurred: {e}")
        traceback.print_exc()
