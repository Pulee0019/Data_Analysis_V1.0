import re

import numpy as np
import pandas as pd

from infrastructure.logger import log_message

def convert_num(s):
    s = s.strip()
    try:
        if '.' in s or 'e' in s or 'E' in s:
            return float(s)
        else:
            return int(s)
    except ValueError:
        return s

def h_AST2_readData(filename):
    header = {}
    
    with open(filename, 'rb') as fid:
        header_lines = []
        while True:
            line = fid.readline().decode('utf-8').strip()
            if line == 'header_end':
                break
            header_lines.append(line)
        
        for line in header_lines:
            match = re.match(r"header\.(\w+)\s*=\s*(.*);$", line)
            if not match:
                continue
            key = match.group(1)
            value_str = match.group(2).strip()
            
            if value_str.startswith("'") and value_str.endswith("'"):
                header[key] = value_str[1:-1]
            elif value_str.startswith('[') and value_str.endswith(']'):
                inner = value_str[1:-1].strip()
                if not inner:
                    header[key] = []
                else:
                    if ';' in inner:
                        rows = inner.split(';')
                        array = []
                        for row in rows:
                            row = row.strip()
                            if row:
                                elements = row.split()
                                array.append([convert_num(x) for x in elements])
                        header[key] = array
                    else:
                        elements = inner.split()
                        header[key] = [convert_num(x) for x in elements]
            else:
                header[key] = convert_num(value_str)
        
        binary_data = np.fromfile(fid, dtype=np.int16)
    
    if 'activeChIDs' in header and 'scale' in header:
        numOfCh = len(header['activeChIDs'])
        data = binary_data.reshape((numOfCh, -1), order='F') / header['scale']
    else:
        data = None
    
    # log_message(f"header:{header}")
    # log_message(f"data:{data}")
    return header, data

def h_AST2_raw2Speed(rawData, info, voltageRange=None, invert_running=False, treadmill_diameter=22):
    if voltageRange is None or len(voltageRange) == 0:
        voltageRange = h_calibrateVoltageRange(rawData)
    
    speedDownSampleFactor = info['saveEvery']
    
    rawDataLength = len(rawData)
    segmentLength = speedDownSampleFactor
    speedDataLength = rawDataLength // segmentLength
    
    if rawDataLength % segmentLength != 0:
        log_message(f"SpeedDataLength is not integer!  speedDataLength = {rawDataLength}, speedDownSampleFactor = {segmentLength}", "ERROR")
        rawData = rawData[:speedDataLength * segmentLength]
    
    t = ((np.arange(speedDataLength) + 0.5) * speedDownSampleFactor) / info['inputRate']
    time_segment = (np.arange(1, segmentLength + 1)) / info['inputRate']
    reshapedData = rawData.reshape(segmentLength, speedDataLength, order='F')
    speedData2 = h_computeSpeed2(time_segment, reshapedData, voltageRange, treadmill_diameter)
    
    if invert_running:
        speedData2 = -speedData2
    
    speedData = {
        'timestamps': t,
        'speed': speedData2
    }
    
    return speedData

def h_calibrateVoltageRange(rawData):
    peakValue, peakPos = h_AST2_findPeaks(rawData)
    valleyValue, valleyPos = h_AST2_findPeaks(-rawData)
    valleyValue = [-x for x in valleyValue]
    
    if len(peakValue) > 0 and len(valleyValue) > 0:
        voltageRange = [np.mean(valleyValue), np.mean(peakValue)]
        if np.diff(voltageRange) > 3:
            # print(f"Calibrated voltage range is {voltageRange}")
            log_message(f"Calibrated voltage range is {voltageRange}")
        else:
            log_message("Calibration error. Range too small")
            voltageRange = [0, 5]
    else:
        voltageRange = [0, 5]
        log_message("Calibration fail! Return default: [0 5].")
    
    return voltageRange

def h_AST2_findPeaks(data):
    transitionPos = np.where(np.abs(np.diff(data)) > 2)[0]
    
    transitionPos = transitionPos[(transitionPos > 50) & (transitionPos < len(data) - 50)]
    
    if len(transitionPos) >= 1:
        peakValue = np.zeros(len(transitionPos))
        peakPos = np.zeros(len(transitionPos))
        
        for i, pos in enumerate(transitionPos):
            segment = data[pos-50:pos+51]
            peakValue[i] = np.max(segment)
            peakPos[i] = pos - 50 + np.argmax(segment)
    else:
        return [], []
    
    avg = np.mean(data)
    maxData = np.max(data)
    thresh = avg + 0.8 * (maxData - avg)
    
    mask = peakValue > thresh
    peakValue = peakValue[mask]
    peakPos = peakPos[mask]
    
    return peakValue, peakPos

def h_computeSpeed2(time, data, voltageRange, treadmill_diameter):
    deltaVoltage = voltageRange[1] - voltageRange[0]
    thresh = 3/5 * deltaVoltage
    
    diffData = np.diff(data, axis=0)
    I = np.abs(diffData) > thresh
    
    data = data.copy()
    for j in range(data.shape[1]):
        if np.any(I[:, j]):
            ind = np.where(I[:, j])[0]
            for i in ind:
                if diffData[i, j] < thresh:
                    data[i+1:, j] = data[i+1:, j] + deltaVoltage
                elif diffData[i, j] > thresh:
                    data[i+1:, j] = data[i+1:, j] - deltaVoltage
    
    dataInDegree = (data / deltaVoltage) * 360
    
    deltaDegree = np.mean(dataInDegree[-11:, :], axis=0) - np.mean(dataInDegree[:11, :], axis=0)
    
    I1 = deltaDegree > 200
    I2 = deltaDegree < -200
    deltaDegree[I1] = deltaDegree[I1] - 360
    deltaDegree[I2] = deltaDegree[I2] + 360
    
    duration = np.mean(time[-11:]) - np.mean(time[:11])
    speed = deltaDegree / duration
    
    diameter = treadmill_diameter
    speed2 = speed / 360 * diameter * np.pi
    
    return speed2

def read_dlc_file(file_path):
    """Read dlc CSV file and parse bodyparts data"""
    if file_path:
        log_message(f"Selected: {file_path}")
        try:
            # Read CSV file, don't use first row as header
            df = pd.read_csv(file_path, header=None, low_memory=False)
            
            # Check if file has enough rows
            if len(df) < 4:
                log_message("CSV file doesn't have enough rows, at least 4 rows needed", "ERROR")
                return
            
            # Get bodyparts information from second row (index 1)
            if len(df) > 1:
                bodyparts_row = df.iloc[1].values
            else:
                log_message("Cannot find bodyparts information in second row", "ERROR")
                return
            
            # Find all unique bodyparts
            global unique_bodyparts
            unique_bodyparts = []
            for i in range(1, len(bodyparts_row), 3):  # Start from index 1, skip "bodyparts" title
                if i < len(bodyparts_row):
                    part = bodyparts_row[i]
                    if pd.notna(part) and str(part).strip() != '':
                        bodypart_name = str(part).strip()
                        if bodypart_name not in unique_bodyparts:
                            unique_bodyparts.append(bodypart_name)
            
            if not unique_bodyparts:
                log_message("No valid bodyparts information found", "ERROR")
                return
                
            log_message(f"Detected bodyparts: {unique_bodyparts}")
            log_message(f"CSV file total columns: {df.shape[1]}")
            
            # Create dictionary to store x, y, likelihood data for each bodypart
            bodypart_data = {}
            
            # Extract data starting from fourth row (index 3)
            data_start_row = 3
            if len(df) <= data_start_row:
                log_message("Not enough data rows, cannot extract data from fourth row", "ERROR")
                return
                
            data_rows = df.iloc[data_start_row:]
            
            # Check if there are enough columns
            expected_cols = len(unique_bodyparts) * 3
            if df.shape[1] < expected_cols:
                log_message(f"Not enough columns, expected {expected_cols}, got {df.shape[1]}", "ERROR")
                return
            
            # Create data vectors for each bodypart
            col_index = 1  # Start from second column, skip "bodyparts" title
            for bodypart in unique_bodyparts:
                try:
                    # Each bodypart occupies 3 columns: x, y, likelihood
                    if col_index + 2 < df.shape[1]:
                        x_data = data_rows.iloc[:, col_index].dropna().astype(float).values
                        y_data = data_rows.iloc[:, col_index + 1].dropna().astype(float).values
                        likelihood_data = data_rows.iloc[:, col_index + 2].dropna().astype(float).values
                        
                        bodypart_data[bodypart] = {
                            'x': x_data,
                            'y': y_data,
                            'likelihood': likelihood_data
                        }
                    else:
                        log_message("Bodypart '{bodypart}' column index out of range", "WARNING")
                        break
                except Exception as col_error:
                    log_message(f"Error processing bodypart '{bodypart}': {col_error}", "ERROR")
                    continue
                
                col_index += 3
            
            # Display parsing results
            result_info = f"File parsed successfully!\n"
            result_info += f"Found {len(unique_bodyparts)} bodyparts: {', '.join(unique_bodyparts)}\n"
            result_info += f"Data rows: {len(data_rows)}\n"
            
            for bodypart, data in bodypart_data.items():
                result_info += f"{bodypart}: x({len(data['x'])}), y({len(data['y'])}), likelihood({len(data['likelihood'])})"
            log_message(result_info, "INFO")
            
            # Print first few rows for verification
            log_message(f"Bodyparts found: {unique_bodyparts}")
            for bodypart, data in bodypart_data.items():
                log_message(f"\n{bodypart}:")
                log_message(f"  X (first 5): {data['x'][:5]}")
                log_message(f"  Y (first 5): {data['y'][:5]}")
                log_message(f"  Likelihood (first 5): {data['likelihood'][:5]}")
            
            # Store data as global variable for later use
            global parsed_data
            parsed_data = bodypart_data

            return parsed_data
        
        except Exception as e:
            log_message(f"Failed to read file: {e}", "ERROR")
            return None

def load_fiber_data(file_path=None):
    """Modified to return data structure for channel splitting"""
    path = file_path
    try:
        fiber_data = pd.read_csv(path, skiprows=1, delimiter=',', low_memory=False)
        fiber_data = fiber_data.loc[:, ~fiber_data.columns.str.contains('^Unnamed')]
        fiber_data.columns = fiber_data.columns.str.strip()

        time_col = None
        possible_time_columns = ['timestamp', 'time', 'time(ms)']
        for col in fiber_data.columns:
            col_lower = col.lower()
            if any(keyword in col_lower for keyword in possible_time_columns):
                time_col = col
                break
        
        if not time_col:
            numeric_cols = fiber_data.select_dtypes(include=np.number).columns
            if len(numeric_cols) > 0:
                time_col = numeric_cols[0]
        
        fiber_data[time_col] = fiber_data[time_col] / 1000
        
        events_col = None
        for col in fiber_data.columns:
            if 'event' in col.lower():
                events_col = col
                break
        
        channels = {'time': time_col, 'events': events_col}
        
        # Parse channel data
        channel_data = {}
        channel_pattern = re.compile(r'CH(\d+)-(\d+)', re.IGNORECASE)
        
        for col in fiber_data.columns:
            match = channel_pattern.match(col)
            if match:
                channel_num = int(match.group(1))
                wavelength = int(match.group(2))
                
                if channel_num not in channel_data:
                    channel_data[channel_num] = {'410': None, '470': None, '560': None, '640': None}
                
                if wavelength == 410:
                    channel_data[channel_num]['410'] = col
                elif wavelength == 470:
                    channel_data[channel_num]['470'] = col
                elif wavelength == 560:
                    channel_data[channel_num]['560'] = col
                elif wavelength == 640:
                    channel_data[channel_num]['640'] = col
                    
        log_message(f"Fiber data loaded, {len(channel_data)} channels detected", "INFO")
        
        return {
            'fiber_data': fiber_data,
            'channels': channels,
            'channel_data': channel_data
        }
    except Exception as e:
        log_message(f"Failed to load fiber data: {str(e)}", "ERROR")
        return None

def load_fiber_events(file_path):
    """Load fiber events from Events.csv file"""
    path = file_path
    try:
        events_data = pd.read_csv(path, delimiter=',', low_memory=False)
        log_message("Fiber events data loaded", "INFO")

        return events_data
    except Exception as e:
        log_message(f"Failed to load fiber events data: {str(e)}", "ERROR")
        return None
