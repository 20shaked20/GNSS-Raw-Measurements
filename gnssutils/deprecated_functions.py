def raim_algorithm(sat_positions, pseudoranges, weights, confidence_level=0.95):
    """
    Performs Receiver Autonomous Integrity Monitoring (RAIM) to detect faults in satellite measurements.

    RAIM aims to improve the reliability of GNSS by identifying and excluding faulty satellite measurements.
    It compares the residuals of pseudoranges to a statistical threshold to detect outliers.

    Args:
        sat_positions (np.array): Array of satellite positions (3D coordinates).
        pseudoranges (np.array): Array of observed pseudoranges.
        weights (np.array): Array of weights for each satellite measurement.
        confidence_level (float): Confidence level for RAIM detection.

    Returns:
        tuple: Estimated receiver position and list of excluded satellites.
    """
    num_satellites = len(sat_positions)
    degrees_of_freedom = num_satellites - 4  # 4 parameters: x, y, z, and receiver clock bias
    threshold = chi2.ppf(confidence_level, degrees_of_freedom)

    # Initial position calculation using the mean of satellite positions as a guess.
    initial_guess = np.mean(sat_positions, axis=0)
    
    # Perform least squares optimization to minimize the residuals and find the best estimate of the receiver's position.
    res = least_squares(positioning_function, initial_guess, args=(sat_positions, pseudoranges, weights))
    position = res.x
    
    # Calculate residuals and test statistic for the initial solution.
    residuals = positioning_function(position, sat_positions, pseudoranges, weights)
    test_statistic = np.sum(residuals**2)

    # If the test statistic is below the threshold, no satellites are excluded.
    if test_statistic < threshold:
        return position, []

    excluded_satellites = []
    
    # Try excluding each satellite one by one to see if the test statistic improves.
    for i in range(len(sat_positions)):
        temp_sat_positions = np.delete(sat_positions, i, axis=0)
        temp_pseudoranges = np.delete(pseudoranges, i)
        temp_weights = np.delete(weights, i)
        temp_position = least_squares(positioning_function, initial_guess, args=(temp_sat_positions, temp_pseudoranges, temp_weights)).x
        temp_residuals = positioning_function(temp_position, temp_sat_positions, temp_pseudoranges, temp_weights)
        temp_test_statistic = np.sum(temp_residuals**2)

        if temp_test_statistic < test_statistic:
            position = temp_position
            test_statistic = temp_test_statistic
            excluded_satellites = [i]

    return position, excluded_satellites


#TODO : understand why the hell is not working.. :(
def calculate_glonass_position(ephemeris, transmit_time):
    """
    Calculates the satellite positions for GLONASS based on ephemeris data.

    Args:
        ephemeris (pd.DataFrame): DataFrame containing the ephemeris data for GLONASS.
        transmit_time (pd.Series): Series containing the transmit times.

    Returns:
        pd.DataFrame: DataFrame containing the calculated satellite positions.
    """

    # Initialize DataFrame to store satellite positions
    sv_position = pd.DataFrame()
    sv_position['sv'] = ephemeris.index
    sv_position.set_index('sv', inplace=True)

    # Adjust transmit time by GLONASS time offset
    adjusted_transmit_time = transmit_time + GLONASS_TIME_OFFSET

    # Compute the time from ephemeris reference epoch
    sv_position['t_k'] = adjusted_transmit_time - ephemeris['MessageFrameTime']

    # Compute the satellite position at t_k
    sv_position['x_k'] = ephemeris['X'] + ephemeris['dX'] * sv_position['t_k']
    sv_position['y_k'] = ephemeris['Y'] + ephemeris['dY'] * sv_position['t_k']
    sv_position['z_k'] = ephemeris['Z'] + ephemeris['dZ'] * sv_position['t_k']

    # Apply Earth rotation correction
    rotation_angle = OMEGA_E_DOT * sv_position['t_k']
    cos_angle = np.cos(rotation_angle)
    sin_angle = np.sin(rotation_angle)

    sv_position['x_k_corrected'] = sv_position['x_k'] * cos_angle + sv_position['y_k'] * sin_angle
    sv_position['y_k_corrected'] = -sv_position['x_k'] * sin_angle + sv_position['y_k'] * cos_angle
    sv_position['z_k_corrected'] = sv_position['z_k']  # Z-coordinate remains the same

    # Calculate the clock correction
    sv_position['delT_sv'] = ephemeris['SVclockBias'] + ephemeris['SVrelFreqBias'] * (adjusted_transmit_time - ephemeris['t_oc'])

    return sv_position