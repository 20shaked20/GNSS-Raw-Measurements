import traceback
import subprocess
import sys
import os

def run_gnss_to_csv():
    print("\nParsing raw GNSS data into CSV... \n ")
    gnss_to_csv_script = "gnss_to_csv.py"
    subprocess.run([sys.executable, gnss_to_csv_script])

def run_rms_positioning():
    print("\nCalculating position based on CSV data... \n")
    rms_positioning_script = "rms_positioning.py"
    subprocess.run([sys.executable, rms_positioning_script])

def main():
    #gnss_to_csv first
    run_gnss_to_csv()

    # if CSV output file is created
    csv_output_file = "gnss_measurements_output.csv"
    if os.path.isfile(csv_output_file):
        # Run rms_positioning with the generated CSV file
        run_rms_positioning()
    else:
        print(f"CSV output file '{csv_output_file}' not found. Exiting...")


try:
    main()
except Exception as e:
    print(f"An error occurred: {e}")
    traceback.print_exc()



