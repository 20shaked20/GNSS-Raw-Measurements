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

        # Status box
        self.status_label = ttk.Label(self, text="")
        self.status_label.pack(pady=10)

        # Satellite information selection
        self.info_label = ttk.Label(self, text="Select information to display:")
        self.info_label.pack(pady=10)

        self.info_var = tk.StringVar()
        self.info_var.set("Total number of satellites")
        self.info_dropdown = ttk.OptionMenu(self, self.info_var, "Total number of satellites", "Total number of satellites", "Satellite names and counts")
        self.info_dropdown.pack()

        # Label to display satellite count or names
        self.satellite_info_label = ttk.Label(self, text="")
        self.satellite_info_label.pack(pady=10)

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

            # Update status label
            self.status_label.config(text="Processing...")

            # Use Popen to handle interactive subprocess
            process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate(input=f'{log_path}\n')

            if process.returncode != 0:
                messagebox.showerror('Error', f'Error running gnss_processing.py: {stderr}')
                self.status_label.config(text="Error")
                return

            # Load processed CSV data into pandas DataFrame
            csv_output_file = "gnss_measurements_output.csv"
            df = pd.read_csv(csv_output_file)

            # Calculate number of unique satellites
            unique_satellites = df['SatPRN (ID)'].nunique()
            satellite_names_counts = df['SatPRN (ID)'].value_counts()

            # Update status label
            self.status_label.config(text="CSV generated")

            # Display selected satellite information
            selected_info = self.info_var.get()
            if selected_info == "Total number of satellites":
                self.satellite_info_label.config(text=f"Total number of satellites: {unique_satellites}")
            elif selected_info == "Satellite names and counts":
                self.satellite_info_label.config(text=f"Satellite names and counts:\n{satellite_names_counts}")

        except subprocess.CalledProcessError as e:
            messagebox.showerror('Error', f'Error running gnss_processing.py: {e}')
            self.status_label.config(text="Error")
        except Exception as e:
            messagebox.showerror('Error', f'An error occurred: {e}')
            self.status_label.config(text="Error")

    def selectLiveMode(self):
        # Implement logic for live mode (if needed)
        messagebox.showinfo('Live Mode', 'Live mode instructions will be displayed here.')


if __name__ == '__main__':
    app = GNSSProcessingApp()
    app.mainloop()
