import pandas as pd

def calculate_glonass_position(ephemeris, transmit_time):
    sv_position = pd.DataFrame()
    sv_position['sv'] = ephemeris.index
    sv_position.set_index('sv', inplace=True)

    # Ensure transmit_time and MessageFrameTime are in the same units
    transmit_time = transmit_time.astype(float)
    MessageFrameTime = ephemeris['MessageFrameTime'].astype(float)

    # Print raw time values for diagnostics
    print("transmit_time (seconds):", transmit_time)
    print("MessageFrameTime (seconds):", MessageFrameTime)

    # Time from ephemeris reference epoch
    sv_position['t_k'] = transmit_time - MessageFrameTime

    # Print t_k for diagnostics
    print("t_k (seconds):", sv_position['t_k'])

    # Simplified position and velocity at reference time
    sv_position['x_k'] = ephemeris['X'] + ephemeris['dX'] * sv_position['t_k']
    sv_position['y_k'] = ephemeris['Y'] + ephemeris['dY'] * sv_position['t_k']
    sv_position['z_k'] = ephemeris['Z'] + ephemeris['dZ'] * sv_position['t_k']

    # Calculate the clock correction
    sv_position['delT_sv'] = ephemeris['SVclockBias'] + ephemeris['SVrelFreqBias'] * (transmit_time - ephemeris['t_oc'])

    # Print position values for diagnostics
    print("x_k (meters):", sv_position['x_k'])
    print("y_k (meters):", sv_position['y_k'])
    print("z_k (meters):", sv_position['z_k'])
    print("delT_sv (seconds):", sv_position['delT_sv'])

    return sv_position

# Sample data for testing
ephemeris_data = {
    'SVclockBias': [9.02e-05],
    'SVrelFreqBias': [9.09e-13],
    'MessageFrameTime': [259200],
    'X': [-3166469.238],
    'dX': [-3042.001724],
    'dX2': [9.31e-07],
    'Y': [11415466.31],
    'dY': [561.3451004],
    'dY2': [-9.31e-07],
    'FreqNum': [1],
    'Z': [-22588762.21],
    'dZ': [711.5707397],
    'dZ2': [2.79e-06],
    'source': ["C:\\Users\\shake\\OneDrive\\Desktop\\VsCode\\GNSS-Raw-Measurements\\data\\ephemeris\\nasa\\BRDC00WRD_S_20241850000_01D_MN.rnx"],
    't_oc': [260100]
}
ephemeris_df = pd.DataFrame(ephemeris_data, index=['R01'])

# Example transmit_time for testing
transmit_time_series = pd.Series([84221.348373], index=['R01'], name='tTxSeconds')

# Call the function
glonass_position = calculate_glonass_position(ephemeris_df, transmit_time_series)

# Print results
print(glonass_position)
