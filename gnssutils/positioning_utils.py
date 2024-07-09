import numpy as np
import pandas as pd
import navpy
from scipy.optimize import least_squares

def positioning_function(x, sat_positions, observed_pseudoranges, weights):
    estimated_ranges = np.sqrt(((sat_positions - x)**2).sum(axis=1))
    residuals = estimated_ranges - observed_pseudoranges
    return weights * residuals

def robust_positioning_function(x, sat_positions, observed_pseudoranges, weights):
    estimated_ranges = np.sqrt(((sat_positions - x[:3])**2).sum(axis=1))
    residuals = estimated_ranges + x[3] - observed_pseudoranges
    return weights * residuals

def solve_position_and_compute_rms(sat_positions, pseudoranges, weights):
    if not (np.all(np.isfinite(sat_positions)) and np.all(np.isfinite(pseudoranges))):
        raise ValueError("Satellite positions and pseudoranges must be finite.")

    initial_guess = np.average(sat_positions, axis=0, weights=weights)
    initial_guess = np.append(initial_guess, 0)
    
    for _ in range(5):
        res = least_squares(robust_positioning_function, initial_guess, args=(sat_positions, pseudoranges, weights))
        position = res.x[:3]
        clock_bias = res.x[3]
        residuals = robust_positioning_function(res.x, sat_positions, pseudoranges, weights)
        
        z_scores = np.abs((residuals - np.mean(residuals)) / np.std(residuals))
        outliers = z_scores > 3
        
        weights[outliers] *= 0.1
        initial_guess = res.x

    rms = np.sqrt(np.mean(residuals**2))
    excluded_satellites = list(np.where(outliers)[0])
    
    return position, rms, clock_bias, excluded_satellites

def ecef_to_lla(ecef_coords):
    return navpy.ecef2lla(ecef_coords, latlon_unit='deg')

def detect_spoofing(group, residuals, rms, lla):
    spoofed_satellites = []
    spoofing_reasons = []
    
    if rms > 2000:
        spoofed_satellites.extend(group['SatPRN (ID)'].tolist())
        spoofing_reasons.append("High RMS")
    
    if lla[2] < -1000 or lla[2] > 100000:
        spoofed_satellites.extend(group['SatPRN (ID)'].tolist())
        spoofing_reasons.append("Unreasonable altitude")
    
    z_scores = np.abs((residuals - np.mean(residuals)) / np.std(residuals))
    threshold = 3 
    spoofed_indices = np.where(z_scores > threshold)[0]
    if len(spoofed_indices) > 0:
        spoofed_satellites.extend(group.iloc[spoofed_indices]['SatPRN (ID)'].tolist())
        spoofing_reasons.append("Individual satellite anomalies")
    
    return spoofed_satellites, spoofing_reasons if spoofing_reasons else [""]

def check_nlp_fix_consistency(nlp_fix, sat_positions, pseudoranges, clock_bias):
    nlp_position_ecef = navpy.lla2ecef(nlp_fix[2], nlp_fix[1], nlp_fix[3], latlon_unit='deg')
    estimated_ranges = np.sqrt(((sat_positions - nlp_position_ecef)**2).sum(axis=1)) + clock_bias
    deviations = np.abs(estimated_ranges - pseudoranges)
    
    threshold = 1000
    return deviations > threshold
