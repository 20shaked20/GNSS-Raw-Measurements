import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import pandas as pd
import os


class GNSSProcessingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('GNSS Processing Application')
        self.geometry('800x600')

        # Mode selection frame
        mode_frame = ttk.Frame(self)
        mode_frame.pack(pady=20)

        btn_offline = ttk.Button(mode_frame, text='Offline Mode', command=self.selectOfflineMode)
        btn_offline.pack(side=tk.LEFT, padx=10)

        btn_live = ttk.Button(mode_frame, text='Live Mode', command=self.selectLiveMode)
        btn_live.pack(side=tk.LEFT, padx=10)

        # File selection for offline mode
        self.selected_file = None
        self.log_files = self.get_available_log_files()

        self.file_label = ttk.Label(self, text="Select a GNSS log file:")
        self.file_label.pack(pady=10)

        self.file_combobox = ttk.Combobox(self, values=self.log_files, state='readonly')
        self.file_combobox.current(0)
        self.file_combobox.pack()

        # Label to display satellite count
        self.satellite_count_label = ttk.Label(self, text="Satellites received:")
        self.satellite_count_label.pack(pady=10)

    def get_available_log_files(self):
        log_dir = 'data'
        log_files = [file for file in os.listdir(log_dir) if file.endswith('.txt')]
        return log_files

    def selectOfflineMode(self):
        selected_file = self.file_combobox.get()

        if not selected_file:
            messagebox.showerror('Error', 'Please select a log file.')
            return

        try:
            # Determine the Python interpreter path
            python_executable = sys.executable

            # Call gnss_processing.py with the selected file
            log_path = os.path.join('data', selected_file)
            cmd = [python_executable, 'C:/Users/t-dzorohov/PycharmProjects/GNSS-Raw-Measurements_final/gnss_processing.py']

            # Use Popen to handle interactive subprocess
            process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate(input=f'{log_path}\n')

            if process.returncode != 0:
                messagebox.showerror('Error', f'Error running gnss_processing.py: {stderr}')
                return

            # Load processed CSV data into pandas DataFrame
            csv_output_file = "gnss_measurements_output.csv"
            df = pd.read_csv(csv_output_file)

            # Calculate number of unique satellites
            unique_satellites = df['SatPRN (ID)'].nunique()
            self.satellite_count_label.config(text=f"Satellites received: {unique_satellites}")

        except subprocess.CalledProcessError as e:
            messagebox.showerror('Error', f'Error running gnss_to_csv.py: {e}')
        except Exception as e:
            messagebox.showerror('Error', f'An error occurred: {e}')

    def selectLiveMode(self):
        # Implement logic for live mode (if needed)
        messagebox.showinfo('Live Mode', 'Live mode instructions will be displayed here.')


if __name__ == '__main__':
    app = GNSSProcessingApp()
    app.mainloop()
