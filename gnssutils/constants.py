from datetime import datetime

# Physical constants
WEEKSEC = 604800
LIGHTSPEED = 2.99792458e8
MU = 3.986005e14  # Earth's universal gravitational parameter
OMEGA_E_DOT = 7.2921151467e-5  # Earth's rotation rate

# GPS constants
GPS_EPOCH = datetime(1980, 1, 6, 0, 0, 0)

# GLONASS constants
GLONASS_TIME_OFFSET = 3 * 3600  # 3 hours in seconds
