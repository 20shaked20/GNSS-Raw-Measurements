import argparse
import traceback
import pandas as pd
import numpy as np
import simplekml
import logging
from tqdm import tqdm
from gnssutils import positioning_function, robust_positioning_function, solve_position_and_compute_rms, ecef_to_lla, detect_spoofing, check_nlp_fix_consistency

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_arguments():
    parser = argparse.ArgumentParser(description='Process multi-GNSS CSV log files for positioning and spoofing detection.')
    parser.add_argument('--input_file', type=str, default='gnss_measurements_output.csv', help='Input CSV file')
    parser.add_argument('--output_kml', type=str, default='gnss_visualization.kml', help='Output KML file')
    parser.add_argument('--output_txt', type=str, default='RmsResults.txt', help='Output RMS results text file')
    parser.add_argument('--android_fixes', type=str, default='android_fixes.csv', help='Android fixes CSV file')
    return parser.parse_args()

def read_gnss_data(filepath):
    return pd.read_csv(filepath)

def process_android_fixes(csv_path, kml):
    try:
        data = pd.read_csv(csv_path)
        if data.empty:
            logging.warning(f"Android fixes file '{csv_path}' is empty. Skipping Android fixes processing.")
            return kml, None
    except FileNotFoundError:
        logging.warning(f"Android fixes file '{csv_path}' not found. Skipping Android fixes processing.")
        return kml, None
    except Exception as e:
        logging.error(f"Error reading Android fixes file: {e}")
        return kml, None

    data = data[data['Provider'].isin(['NLP', 'nlp'])]
    
    nlp_style = simplekml.Style()
    nlp_style.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/shapes/placemark_square.png'
    nlp_style.iconstyle.color = simplekml.Color.red
    
    nlp_fixes = []

    for _, row in data.iterrows():
        pnt = kml.newpoint(name=f"Android {row['Provider']} - {row['UnixTimeMillis']}")
        pnt.coords = [(row['LongitudeDegrees'], row['LatitudeDegrees'], row['AltitudeMeters'])]
        pnt.timestamp.when = pd.to_datetime(row['UnixTimeMillis'], unit='ms').strftime("%Y-%m-%dT%H:%M:%SZ")
        pnt.style = nlp_style
        nlp_fixes.append((row['UnixTimeMillis'], row['LongitudeDegrees'], row['LatitudeDegrees'], row['AltitudeMeters']))
        
    logging.info(f"Added {len(data)} Android fixes to KML.")
    return kml, nlp_fixes

def process_epoch(gps_time, group, kml, previous_position, nlp_fixes):
    gps_time_dt = pd.to_datetime(gps_time)
    sat_positions = group[['SatX', 'SatY', 'SatZ']].values
    pseudoranges = group['Pseudo-Range'].values
    cn0 = group['CN0'].values
    doppler = group['Doppler'].values
    signal_type = group['Frequency-Band'].values
    
    if len(sat_positions) < 4:
        raise ValueError("Not enough valid satellite data for position calculation.")

    l5_indices = np.where(signal_type == 'L5')[0]
    if len(l5_indices) >= 4:
        sat_positions = sat_positions[l5_indices]
        pseudoranges = pseudoranges[l5_indices]
        cn0 = cn0[l5_indices]
        doppler = doppler[l5_indices]

    weights = np.where(np.isnan(doppler), 1 / (cn0 + 1e-6), cn0 / (np.abs(doppler) + 1e-6))
    weights /= weights.sum()

    position, rms, clock_bias, excluded_satellites = solve_position_and_compute_rms(sat_positions, pseudoranges, weights)
    lla = ecef_to_lla(position)

    pnt = kml.newpoint(name=f"{gps_time}", coords=[(lla[1], lla[0], lla[2])])
    pnt.timestamp.when = gps_time_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    estimated_ranges = np.sqrt(((sat_positions - position)**2).sum(axis=1))
    residuals = estimated_ranges + clock_bias - pseudoranges

    all_satellites = group['SatPRN (ID)'].tolist()
    spoofed_satellites, spoofing_reasons = detect_spoofing(group, residuals, rms, lla)
    
    nlp_inconsistent_satellites = []
    for nlp_fix in nlp_fixes:
        if abs(nlp_fix[0] - gps_time_dt.timestamp() * 1000) <= 60000:
            inconsistent_satellites = check_nlp_fix_consistency(nlp_fix, sat_positions, pseudoranges, clock_bias)
            new_inconsistent = group.iloc[inconsistent_satellites]['SatPRN (ID)'].tolist()
            nlp_inconsistent_satellites.extend(new_inconsistent)

    nlp_inconsistent_satellites = list(set(nlp_inconsistent_satellites))

    if nlp_inconsistent_satellites:
        spoofed_satellites.extend(nlp_inconsistent_satellites)
        spoofing_reasons.append("Inconsistent with NLP fix")

    spoofed_satellites = list(set(spoofed_satellites))

    if previous_position is not None:
        distance = np.linalg.norm(position - previous_position)
        if distance > 1000:
            spoofed_satellites = group['SatPRN (ID)'].tolist()
            spoofing_reasons.append("Sudden position jump")
    
    return {
        'GPS Time': gps_time,
        'Estimated Position ECEF': position,
        'Estimated Position LLA': lla,
        'RMS': rms,
        'Spoofed Satellites': spoofed_satellites,
        'Non_spoofed Satellites': [sat for sat in all_satellites if sat not in spoofed_satellites],
        'Excluded Satellites': [all_satellites[i] for i in excluded_satellites],
        'Spoofing Reason': ', '.join(spoofing_reasons)
    }

def process_satellite_data(data, kml, nlp_fixes):
    grouped = data.groupby('GPS Time')
    results = []
    previous_position = None
    
    for gps_time, group in tqdm(grouped, desc="Processing Satellite Data"):
        try:
            result = process_epoch(gps_time, group, kml, previous_position, nlp_fixes)
            results.append(result)
            previous_position = result['Estimated Position ECEF']
        except ValueError as e:
            logging.error(f"Skipping epoch at {gps_time} due to error: {e}")
    
    return results

def process_satellite_data_no_nlp(data, kml):
    grouped = data.groupby('GPS Time')
    results = []
    previous_position = None
    
    for gps_time, group in tqdm(grouped, desc="Processing Satellite Data"):
        try:
            gps_time_dt = pd.to_datetime(gps_time)
            sat_positions = group[['SatX', 'SatY', 'SatZ']].values
            pseudoranges = group['Pseudo-Range'].values
            cn0 = group['CN0'].values
            doppler = group['Doppler'].values
            signal_type = group['Frequency-Band'].values
            
            if len(sat_positions) < 4:
                raise ValueError("Not enough valid satellite data for position calculation.")

            l5_indices = np.where(signal_type == 'L5')[0]
            if len(l5_indices) >= 4:
                sat_positions = sat_positions[l5_indices]
                pseudoranges = pseudoranges[l5_indices]
                cn0 = cn0[l5_indices]
                doppler = doppler[l5_indices]

            weights = np.where(np.isnan(doppler), 1 / (cn0 + 1e-6), cn0 / (np.abs(doppler) + 1e-6))
            weights /= weights.sum()

            position, rms, clock_bias, excluded_satellites = solve_position_and_compute_rms(sat_positions, pseudoranges, weights)
            lla = ecef_to_lla(position)

            pnt = kml.newpoint(name=f"{gps_time}", coords=[(lla[1], lla[0], lla[2])])
            pnt.timestamp.when = gps_time_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

            estimated_ranges = np.sqrt(((sat_positions - position)**2).sum(axis=1))
            residuals = estimated_ranges + clock_bias - pseudoranges

            all_satellites = group['SatPRN (ID)'].tolist()
            spoofed_satellites, spoofing_reasons = detect_spoofing(group, residuals, rms, lla)

            if previous_position is not None:
                distance = np.linalg.norm(position - previous_position)
                if distance > 1000:
                    spoofed_satellites = group['SatPRN (ID)'].tolist()
                    spoofing_reasons.append("Sudden position jump")

            result = {
                'GPS Time': gps_time,
                'Estimated Position ECEF': position,
                'Estimated Position LLA': lla,
                'RMS': rms,
                'Spoofed Satellites': spoofed_satellites,
                'Non_spoofed Satellites': [sat for sat in all_satellites if sat not in spoofed_satellites],
                'Excluded Satellites': [all_satellites[i] for i in excluded_satellites],
                'Spoofing Reason': ', '.join(spoofing_reasons)
            }

            results.append(result)
            previous_position = result['Estimated Position ECEF']
        except ValueError as e:
            logging.error(f"Skipping epoch at {gps_time} due to error: {e}")
    
    return results

def save_results_to_text(results, output_txt, nlp_fixes=None):
    logging.info("Saving to RmsResults.txt... \n")
    with open(output_txt, 'w') as f:
        for result in tqdm(results, desc="Saving results to text"):
            f.write(f"GPS Time: {result['GPS Time']}\n")
            f.write(f"Estimated Position ECEF (X, Y, Z): {result['Estimated Position ECEF']}\n")
            f.write(f"Estimated Position LLA (Lat, Lon, Alt): {result['Estimated Position LLA']}\n")
            f.write(f"RMS: {result['RMS']}\n")
            f.write(f"Spoofing Detected: {'Yes' if result['Spoofed Satellites'] else 'No'}\n")
            f.write(f"Spoofing Reason: {result['Spoofing Reason']}\n")
            
            all_satellites = set(result['Spoofed Satellites']) | set(result.get('Non_spoofed Satellites', []))
            non_spoofed_satellites = all_satellites - set(result['Spoofed Satellites'])
            
            f.write(f"Spoofed Satellites: {', '.join(map(str, result['Spoofed Satellites']))}\n")
            f.write(f"Non-spoofed Satellites: {', '.join(map(str, non_spoofed_satellites))}\n")

            if 'Inconsistent with NLP fix' in result['Spoofing Reason'] and nlp_fixes:
                nlp_fix_lla = next((fix[1:4] for fix in nlp_fixes if abs(fix[0] - pd.to_datetime(result['GPS Time']).timestamp() * 1000) <= 60000), None)
                if nlp_fix_lla:
                    f.write(f"Position From NLP (Lat, Lon, Alt): {nlp_fix_lla}\n")
            else:
                f.write(f"Position From NLP: No\n")

            f.write("-" * 50 + "\n")

def add_position_data_to_csv(results, input_csv, output_csv):
    logging.info("Adding additional data to the CSV... \n")
    add_to_csv = {
        'GPS Time': [],
        'PosX_calculated': [],
        'PosY_calculated': [],
        'PosZ_calculated': [],
        'Lat_calculated': [],
        'Lon_calculated': [],
        'Alt_calculated': [],
        'RMS': [],
        'Spoofed_Satellites': [],
        'Spoofing_Reason': [],
        'Excluded_Satellites': []
    }
    encountered_timestamps = set()

    for result in tqdm(results, desc="Adding position data to CSV"):
        gps_time = result['GPS Time']
        if gps_time not in encountered_timestamps:
            add_to_csv['GPS Time'].append(gps_time)
            add_to_csv['PosX_calculated'].append(result['Estimated Position ECEF'][0])
            add_to_csv['PosY_calculated'].append(result['Estimated Position ECEF'][1])
            add_to_csv['PosZ_calculated'].append(result['Estimated Position ECEF'][2])
            add_to_csv['Lat_calculated'].append(result['Estimated Position LLA'][0])
            add_to_csv['Lon_calculated'].append(result['Estimated Position LLA'][1])
            add_to_csv['Alt_calculated'].append(result['Estimated Position LLA'][2])
            add_to_csv['RMS'].append(result['RMS'])
            add_to_csv['Spoofed_Satellites'].append(','.join(map(str, result['Spoofed Satellites'])))
            add_to_csv['Spoofing_Reason'].append(result['Spoofing Reason'])
            add_to_csv['Excluded_Satellites'].append(','.join(map(str, result['Excluded Satellites'])))
            encountered_timestamps.add(gps_time)

    add_to_csv_df = pd.DataFrame(add_to_csv)
    existing_data = pd.read_csv(input_csv)
    
    columns_to_remove = ['PosX_calculated', 'PosY_calculated', 'PosZ_calculated',
                         'Lat_calculated', 'Lon_calculated', 'Alt_calculated', 'RMS',
                         'Spoofed_Satellites', 'Spoofing_Reason', 'Excluded_Satellites']
    existing_data = existing_data.drop(columns=[col for col in columns_to_remove if col in existing_data.columns])
    
    combined_data = pd.merge(existing_data, add_to_csv_df, on='GPS Time', how='left')
    combined_data.to_csv(output_csv, index=False)
    logging.info(f"Updated data saved to {output_csv}")

def main():
    args = parse_arguments()
    data = read_gnss_data(args.input_file)
    kml = simplekml.Kml()
    kml, nlp_fixes = process_android_fixes(args.android_fixes, kml)

    if nlp_fixes:
        results = process_satellite_data(data, kml, nlp_fixes)
        kml.save(args.output_kml)
        save_results_to_text(results, args.output_txt, nlp_fixes)
        add_position_data_to_csv(results, args.input_file, args.input_file)
    else:
        results = process_satellite_data_no_nlp(data, kml)
        kml.save(args.output_kml)
        save_results_to_text(results, args.output_txt)
        add_position_data_to_csv(results, args.input_file, args.input_file)

try:
    main()
except Exception as e:
    logging.error(f"An error occurred: {e}")
    traceback.print_exc()
