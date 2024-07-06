"""
spoofing_detection.py

This script provides functions for detecting potential GNSS spoofing attempts
by analyzing various aspects of GNSS measurements and satellite data.

Functions:
- check_agc_cn0: Checks AGC and C/N0 values for suspicious measurements
- check_svid_sanity: Verifies the sanity of Satellite Vehicle IDs (SVIDs)
- check_satellite_position: Validates satellite positions
- check_time_consistency: Ensures time consistency of measurements
- check_cross_correlation: Detects high cross-correlation in measurements

These functions can be used individually or combined to create a comprehensive
GNSS spoofing detection system.

Usage:
1. Import the required functions from this script.
2. Prepare your GNSS measurement data as a pandas DataFrame.
3. Call the functions with your data to detect potential spoofing.

Example:
    from spoofing_detection import check_agc_cn0, check_svid_sanity
    
    measurements = pd.read_csv('gnss_data.csv')
    suspicious_measurements = check_agc_cn0(measurements)
    suspicious_measurements = check_svid_sanity(suspicious_measurements, ephemeris_data)

Notes:
- Adjust thresholds in each function based on your specific GNSS receiver and environment.
- Ensure your input data matches the expected format for each function.
- These methods provide indicators of potential spoofing but should be used in 
  conjunction with other verification techniques for comprehensive detection.
"""

from datetime import datetime, timezone
import pandas as pd
import numpy as np
from .constants import AGC_THRESHOLD, CN0_THRESHOLD

def check_agc_cn0(measurements):
    """
    Checks the AGC and C/N0 values for suspicious measurements.

    Args:
        measurements (pd.DataFrame): DataFrame containing the GNSS measurements.

    Returns:
        pd.DataFrame: DataFrame with additional columns indicating suspicious measurements.
    """

    if 'AgcDb' in measurements.columns:
        # Convert AgcDb to numeric, replacing any non-convertible values with NaN
        measurements['AgcDb'] = pd.to_numeric(measurements['AgcDb'], errors='coerce')
        measurements['AGC_suspicious'] = measurements['AgcDb'] > AGC_THRESHOLD
    else:
        measurements['AGC_suspicious'] = False
    measurements['CN0_suspicious'] = pd.to_numeric(measurements['Cn0DbHz'], errors='coerce') < CN0_THRESHOLD
    measurements['suspicious'] = measurements['AGC_suspicious'] | measurements['CN0_suspicious']

    return measurements

def check_svid_sanity(measurements, ephemeris):
    """
    Checks the sanity of SVIDs in the measurements.

    Args:
        measurements (pd.DataFrame): DataFrame containing the GNSS measurements.
        ephemeris (pd.DataFrame): DataFrame containing the ephemeris data.

    Returns:
        pd.DataFrame: DataFrame with additional columns indicating SVID sanity checks.
    """
    measurements['SVID_exists'] = measurements['SvName'].isin(ephemeris.index)
    svid_counts = measurements.groupby('Epoch')['SvName'].value_counts()
    duplicate_svids = svid_counts[svid_counts > 1].index.get_level_values('SvName')
    measurements['SVID_duplicate'] = measurements['SvName'].isin(duplicate_svids)
    measurements['suspicious'] |= ~measurements['SVID_exists'] | measurements['SVID_duplicate']

    return measurements

def check_satellite_position(sv_position, receiver_position, max_distance_error=1000):
    """
    Checks the sanity of satellite positions.

    Args:
        sv_position (pd.DataFrame): DataFrame containing the satellite positions.
        receiver_position (tuple): Tuple containing the receiver position (x, y, z).
        max_distance_error (int): Maximum allowed distance error in meters.

    Returns:
        pd.Series: Series indicating whether each satellite position is suspicious.
    """
    rx = np.array(receiver_position)
    distances = np.sqrt(((sv_position[['x_k', 'y_k', 'z_k']] - rx)**2).sum(axis=1))
    max_theoretical_distance = 26600000  # Approx. max distance to a GPS satellite in meters
    
    return (distances > max_theoretical_distance + max_distance_error) | (distances < max_distance_error)

def check_time_consistency(measurements, max_time_error=1):
    """
    Checks the time consistency of the measurements.

    Args:
        measurements (pd.DataFrame): DataFrame containing the GNSS measurements.
        max_time_error (int): Maximum allowed time error in seconds.

    Returns:
        pd.Series: Series indicating whether each measurement is time-consistent.
    """
    current_time = datetime.now(timezone.utc)
    if measurements['UnixTime'].dt.tz is None:
        measurements['UnixTime'] = measurements['UnixTime'].dt.tz_localize('UTC')
    time_diff = (current_time - measurements['UnixTime']).dt.total_seconds().abs()

    return time_diff > max_time_error

def check_cross_correlation(measurements, correlation_threshold=0.95):
    """
    Checks for high cross-correlation in the measurements.

    Args:
        measurements (pd.DataFrame): DataFrame containing the GNSS measurements.
        correlation_threshold (float): Threshold for identifying high cross-correlation.

    Returns:
        pd.Series: Series indicating whether each measurement is suspicious due to high cross-correlation.
    """
    suspicious = pd.Series(False, index=measurements.index)
    
    for epoch in measurements['Epoch'].unique():
        epoch_data = measurements[measurements['Epoch'] == epoch]
        
        epoch_data['UniqueID'] = epoch_data['UnixTime'].astype(str) + '_' + epoch_data['SvName']
        pivot_data = epoch_data.pivot(index='UniqueID', columns='SvName', values='PrM')
        
        # Calculate correlation matrix only if there are at least 2 columns (satellites)
        if pivot_data.shape[1] >= 2:
            corr_matrix = pivot_data.corr()
            high_corr = (corr_matrix.abs() > correlation_threshold) & (corr_matrix.abs() < 1.0)
            suspicious_sats = high_corr.index[high_corr.any()]
            suspicious.loc[epoch_data.index] |= epoch_data['SvName'].isin(suspicious_sats)
    
    return suspicious