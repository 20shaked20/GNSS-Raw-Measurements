import re
import csv

def parse_rinex_to_csv(input_file, output_file):
    with open(input_file, 'r') as f:
        lines = f.readlines()

    # Initialize CSV writer
    with open(output_file, 'w', newline='') as csvfile:
        fieldnames = ['GPS time', 'SatPRN (ID)', 'Sat.X', 'Sat.Y', 'Sat.Z', 'Pseudo-Range', 'CN0']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        # Extract data from RINEX lines
        for line in lines:
            if line.startswith('>'):
                # Extract GPS time
                gps_time = line.split()[1:7]
                gps_time_str = ' '.join(gps_time)

            elif re.match(r'^[GREC][0-9]+', line):
                # Extract satellite data
                satellite_data = line.split()
                if len(satellite_data) >= 6:
                    sat_id = satellite_data[0]
                    sat_xyz = [float(x) for x in satellite_data[1:4]]
                    pseudo_range = float(satellite_data[4])
                    cn0 = float(satellite_data[5])

                    # Write to CSV
                    writer.writerow({
                        'GPS time': gps_time_str,
                        'SatPRN (ID)': sat_id,
                        'Sat.X': sat_xyz[0],
                        'Sat.Y': sat_xyz[1],
                        'Sat.Z': sat_xyz[2],
                        'Pseudo-Range': pseudo_range,
                        'CN0': cn0
                    })

if __name__ == "__main__":
    parse_rinex_to_csv('RinexFile\gnss_log_2024_04_13_19_51_17.24o', 'output.csv')
