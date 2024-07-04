1. understand why the hell is not working.. :(
def calculate_glonass_position(ephemeris, transmit_time).

2. better naming here - 
def raim_algorithm(sat_positions, pseudoranges, weights, confidence_level=0.95):

3. adds logs where we dont have

4. add more commentings and explanations for each functions (if necessary)

5. maybe doctesting?

6. connect KML with live data to present in the UI

7. create math_utils.py / data_utils.py  - for data parsing and mathemtaical calcualtions that are being used in more than one script to avoid code dupe

8. consider mergins live-gnss & offline-gnss into one script, but with a choice from cmd on how to operate them.

