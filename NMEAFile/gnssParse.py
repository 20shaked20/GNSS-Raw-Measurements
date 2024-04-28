import csv
import math

def nmea_to_csv(input_file, output_file):
    # Open input and output files
    with open(input_file, 'r') as f_in, open(output_file, 'w', newline='') as f_out:
        writer = csv.writer(f_out)
        writer.writerow(["GPS Time", "SatPRN (ID)", "Sat.X", "Sat.Y", "Sat.Z", "Pseudo-Range", "CN0", "Doppler"])

        # Define constants
        SPEED_OF_LIGHT = 299792458  # Speed of light in meters per second

        # Parse NMEA log
        for line in f_in:
            fields = line.strip().split(',')
            if len(fields) > 1:  # Check if fields contain enough elements
                sentence_type = fields[1][1:6]  # Extracting the sentence type correctly, removing the $
                print("Sentence Type:", sentence_type)

                if sentence_type in ['GPGSV', 'GLGSV', 'GAGSV', 'GBGSV']:
                    if len(fields) >= 4:
                        num_sentences = int(fields[2])
                        sentence_num = int(fields[3])
                        num_sats = int(fields[4])
                        print("Num of Satellites:", num_sats)
                        for i in range(5, num_sats * 4 + 5, 4):
                            if i + 3 < len(fields):  # Ensure we have enough elements in fields
                                sat_prn = fields[i]
                                elevation = int(fields[i + 1])
                                azimuth = int(fields[i + 2])
                                snr = int(fields[i + 3])

                                # Calculate satellite position in ECEF coordinates
                                # (Assuming elevation and azimuth are available)
                                sat_x = math.cos(math.radians(elevation)) * math.sin(math.radians(azimuth))
                                sat_y = math.cos(math.radians(elevation)) * math.cos(math.radians(azimuth))
                                sat_z = math.sin(math.radians(elevation))

                                # Write satellite information to CSV
                                writer.writerow([None, sat_prn, sat_x, sat_y, sat_z, None, snr, None])
                                print("Satellite:", sat_prn, sat_x, sat_y, sat_z, snr)
                elif sentence_type == 'GNGGA':
                    if len(fields) >= 3:
                        gps_time = fields[2]
                        print("GPS Time:", gps_time)

                        # Write GPS time to CSV for subsequent GSV sentences
                        writer.writerow([gps_time, None, None, None, None, None, None, None])
                elif sentence_type in ['GNGSA', 'PSSGR']:
                    if len(fields) >= 16:
                        for i in range(4, 16):
                            if i + 12 < len(fields) and fields[i + 12]:  # Ensure we have enough elements and not empty
                                sat_prn = fields[i]
                                pseudo_range = fields[i + 12].split('*')[0]

                                # Convert pseudo-range to float
                                pseudo_range = float(pseudo_range) if pseudo_range else None

                                # Write pseudo-range to CSV
                                writer.writerow([None, sat_prn, None, None, None, pseudo_range, None, None])
                                print("Pseudo-range:", sat_prn, pseudo_range)
                elif sentence_type == 'GNRMC':
                    if len(fields) >= 11:
                        for i in range(8, 11):
                            doppler = float(fields[i]) if fields[i] else None

                            # Write Doppler to CSV
                            writer.writerow([None, None, None, None, None, None, None, doppler])
                            print("Doppler:", doppler)


# Example usage
input_file = "gnss_log_2024_04_13_19_51_17.nmea"
output_file = "parsed_nmea.csv"
nmea_to_csv(input_file, output_file)
