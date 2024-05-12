import traceback
import subprocess
import os

def run_gnss_to_csv():
    # Run gnss_to_csv.py
    print("\nRunning gnss_to_csv... \n ")
    gnss_to_csv_script = "gnss_to_csv.py"
    subprocess.run(["python3", gnss_to_csv_script])

def run_rms_positioning():
    # Run rms_positioning.py
    print("\nRunning rms_positioning... \n")
    rms_positioning_script = "rms_positioning.py"
    subprocess.run(["python3", rms_positioning_script])

def main():
    # Run gnss_to_csv first
    run_gnss_to_csv()

    # Check if CSV output file is created
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
    traceback.print_exc()  # Print the stack trace to standard error



