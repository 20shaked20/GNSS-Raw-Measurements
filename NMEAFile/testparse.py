import csv
import math

def parse_gpgsv(fields):
    satellites = []
    for i in range(5, len(fields), 4):
        if i + 3 < len(fields):  # Check if we have enough elements in fields
            sat_prn = fields[i]
            elevation_with_checksum = fields[i + 1]
            elevation = int(elevation_with_checksum.split('*')[0])  # Extract numeric elevation
            azimuth = int(fields[i + 2])
            snr = int(fields[i + 3])

            # Calculate satellite position in ECEF coordinates
            sat_x = math.cos(math.radians(elevation)) * math.sin(math.radians(azimuth))
            sat_y = math.cos(math.radians(elevation)) * math.cos(math.radians(azimuth))
            sat_z = math.sin(math.radians(elevation))

            satellites.append((sat_prn, sat_x, sat_y, sat_z, snr))

    return satellites



def parse_gngga(fields):
    gps_time = fields[2]
    return gps_time


def parse_gngsa(fields):
    satellites = []
    for i in range(4, min(len(fields), 16)):  # Limit the range to avoid IndexError
        if i + 12 < len(fields) and fields[i + 12]:  # Check if we have enough elements and not empty
            sat_prn = fields[i]
            pseudo_range = fields[i + 12].split('*')[0]
            pseudo_range = float(pseudo_range) if pseudo_range else None
            satellites.append((sat_prn, pseudo_range))

    return satellites


def parse_gnrmc(fields):
    doppler = float(fields[9]) if fields[9] else None
    return doppler

def nmea_to_csv(input_file, output_file):
    with open(input_file, 'r') as f_in, open(output_file, 'w', newline='') as f_out:
        writer = csv.writer(f_out)
        writer.writerow(["GPS Time", "SatPRN (ID)", "Sat.X", "Sat.Y", "Sat.Z", "Pseudo-Range", "CN0", "Doppler"])

        for line in f_in:
            fields = line.strip().split(',')
            if len(fields) > 1:
                sentence_type = fields[1][1:6]

                if sentence_type in ['GPGSV', 'GLGSV', 'GAGSV', 'GBGSV']:
                    satellites = parse_gpgsv(fields)
                    for satellite in satellites:
                        writer.writerow([None, *satellite, None, None, None])
                
                elif sentence_type == 'GNGGA':
                    gps_time = parse_gngga(fields)
                    writer.writerow([gps_time, None, None, None, None, None, None, None])
                
                elif sentence_type in ['GNGSA', 'PSSGR']:
                    satellites = parse_gngsa(fields)
                    for satellite in satellites:
                        writer.writerow([None, *satellite, None, None, None])
                
                elif sentence_type == 'GNRMC':
                    doppler = parse_gnrmc(fields)
                    writer.writerow([None, None, None, None, None, None, None, doppler])

# Example usage
input_file = "gnss_log_2024_04_13_19_51_17.nmea"
output_file = "parsed_nmea.csv"
nmea_to_csv(input_file, output_file)
