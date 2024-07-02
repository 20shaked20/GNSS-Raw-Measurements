import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import pandas as pd
import os
import xml.etree.ElementTree as ET
import tkintermapview

class KMLViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("KML and GNSS Viewer")
        self.geometry("800x600")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        self.create_kml_tab()
        self.create_gnss_tab()

    def create_kml_tab(self):
        kml_frame = ttk.Frame(self.notebook)
        self.notebook.add(kml_frame, text="KML Viewer")

        self.map_widget = tkintermapview.TkinterMapView(kml_frame, width=800, height=600)
        self.map_widget.pack(fill="both", expand=True)

        self.load_button = tk.Button(kml_frame, text="Load KML File", command=self.load_kml_file)
        self.load_button.pack(pady=10)

    def create_gnss_tab(self):
        gnss_frame = ttk.Frame(self.notebook)
        self.notebook.add(gnss_frame, text="GNSS Processing")

        mode_frame = ttk.Frame(gnss_frame)
        mode_frame.pack(pady=20)

        btn_offline = ttk.Button(mode_frame, text='Offline Mode', command=self.selectOfflineMode)
        btn_offline.pack(side=tk.LEFT, padx=10)

        btn_live = ttk.Button(mode_frame, text='Live Mode', command=self.selectLiveMode)
        btn_live.pack(side=tk.LEFT, padx=10)

        self.selected_file = None
        self.log_files = self.get_available_log_files()

        self.file_label = ttk.Label(gnss_frame, text="Select a GNSS log file:")
        self.file_label.pack(pady=10)

        self.file_combobox = ttk.Combobox(gnss_frame, values=self.log_files, state='readonly')
        self.file_combobox.current(0)
        self.file_combobox.pack()

        self.status_label = ttk.Label(gnss_frame, text="")
        self.status_label.pack(pady=10)

        self.info_label = ttk.Label(gnss_frame, text="Select information to display:")
        self.info_label.pack(pady=10)

        self.info_var = tk.StringVar()
        self.info_var.set("Total number of satellites")
        self.info_dropdown = ttk.OptionMenu(gnss_frame, self.info_var, "Total number of satellites", "Total number of satellites", "Satellite names and counts")
        self.info_dropdown.pack()

        self.satellite_info_label = ttk.Label(gnss_frame, text="")
        self.satellite_info_label.pack(pady=10)

    def load_kml_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("KML files", "*.kml")])
        if not file_path:
            return

        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            namespace = {"kml": "http://www.opengis.net/kml/2.2"}

            for placemark in root.findall(".//kml:Placemark", namespace):
                name = placemark.find("kml:name", namespace).text if placemark.find("kml:name", namespace) is not None else "Unknown"
                coordinates = placemark.find(".//kml:coordinates", namespace).text.strip() if placemark.find(".//kml:coordinates", namespace) is not None else None

                if coordinates:
                    lon, lat, _ = map(float, coordinates.split(","))
                    self.map_widget.set_position(lat, lon)
                    self.map_widget.set_marker(lat, lon)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load KML file: {e}")

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
            python_executable = sys.executable
            log_path = os.path.join('data', selected_file)
            cmd = [python_executable, 'C:/Users/t-dzorohov/PycharmProjects/GNSS-Raw-Measurements_final/gnss_processing.py']

            self.status_label.config(text="Processing...")

            process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate(input=f'{log_path}\n')

            if process.returncode != 0:
                messagebox.showerror('Error', f'Error running gnss_processing.py: {stderr}')
                self.status_label.config(text="Error")
                return

            csv_output_file = "gnss_measurements_output.csv"
            df = pd.read_csv(csv_output_file)

            unique_satellites = df['SatPRN (ID)'].nunique()
            satellite_names_counts = df['SatPRN (ID)'].value_counts()

            self.status_label.config(text="CSV generated")

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
        messagebox.showinfo('Live Mode', 'Live mode instructions will be displayed here.')

if __name__ == "__main__":
    app = KMLViewer()
    app.mainloop()
