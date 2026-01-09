import numpy as np
from logger import log_message
from itertools import groupby

def running_bout_analysis_classify(running_speed, 
                                   smooth_window=5, 
                                   general_threshold=0.5, 
                                   general_min_duration=0.5, 
                                   rest_min_duration=4, 
                                   pre_locomotion_buffer=5, post_locomotion_buffer=5, 
                                   locomotion_duration=2):
    """Analyze running bouts based on locomotion criteria"""
    if running_speed['filtered_speed'] is None:
        speed = running_speed['original_speed']
        log_message("No filtered speed data found. Using original speed data for bout analysis.", "WARNING")
    else:
        speed = running_speed['filtered_speed']
        log_message("Using filtered speed data for bout analysis.")

    window_size = int(smooth_window)
    kernel = np.ones(window_size) / window_size
    speed = np.convolve(np.abs(speed), kernel, mode='same')

    timestamps = running_speed['timestamps']
    sample_interval = np.mean(np.diff(timestamps))
    sample_rate = 1.0 / sample_interval
    threshold = general_threshold
    motion_flag = speed >= threshold
    groups = groupby(enumerate(motion_flag), key=lambda x: x[1])
    general_bouts = []
    for k, g in groups:
        g = list(g)
        if k and len(g) >= general_min_duration*sample_rate:
            idxs = [i for i, _ in g]
            start_idx = idxs[0]
            end_idx = idxs[-1]
            if start_idx == 0 or end_idx == len(speed) - 1:
                continue
            bout_info = [idxs[0]+1, idxs[-1]+1]
            general_bouts.append(bout_info)
    rest_flag = speed < threshold
    groups = groupby(enumerate(rest_flag), key=lambda x: x[1])
    rest = []
    for k, g in groups:
        g = list(g)
        if k and len(g) >= rest_min_duration*sample_rate:
            idxs = [i for i, _ in g]
            start_idx = idxs[0]
            end_idx = idxs[-1]
            if start_idx == 0 or end_idx == len(speed) - 1:
                continue
            bout_info = [idxs[0]+1, idxs[-1]+1]
            rest.append(bout_info)
    locomotion, reset, jerk, other = running_bout_classify(general_bouts, speed, timestamps, threshold, pre_locomotion_buffer, post_locomotion_buffer, locomotion_duration, sample_rate)
    bouts = {
        'general_bouts': general_bouts,
        'locomotion_bouts': locomotion,
        'reset_bouts': reset,
        'jerk_bouts': jerk,
        'other_bouts': other,
        'rest_bouts': rest
    }

    log_message(f"Identified {len(general_bouts)} general bouts. Locomotion: {len(locomotion)}, Reset: {len(reset)}, Jerk: {len(jerk)}, Other: {len(other)}, Rest: {len(rest)}")
    
    return bouts, speed

def running_bout_classify(general_bouts, speed, timestamps, threshold, pre_buffer, post_buffer, duration_buffer, sample_rate):
    '''Classify running bouts into locomotion, reset, jerk, and other'''
    locomotion = []
    reset = []
    jerk = []
    other = []
    duration_buffer_samples = int(duration_buffer * sample_rate)
    for bout in general_bouts:
        start_idx, end_idx = bout
        pre_start = max(0, start_idx - int(pre_buffer * sample_rate))
        post_end = min(len(speed) - 1, end_idx + int(post_buffer * sample_rate))
        duration = end_idx - start_idx + 1
        pre_speed = speed[pre_start:start_idx]
        post_speed = speed[end_idx+1:post_end+1]
        pre_bout_mean = np.mean(pre_speed) if len(pre_speed) > 0 else 0
        post_bout_mean = np.mean(post_speed) if len(post_speed) > 0 else 0
        if pre_bout_mean < threshold and post_bout_mean < threshold and duration < duration_buffer_samples:
            jerk.append([start_idx, end_idx])
        elif pre_bout_mean < threshold and post_bout_mean < threshold and duration >= duration_buffer_samples:
            locomotion.append([start_idx, end_idx])
        elif pre_bout_mean >= threshold:
            reset.append([start_idx, end_idx])
        else:
            other.append([start_idx, end_idx])
    return locomotion, reset, jerk, other

def apply_running_filters(speed_data, timestamps, filter_type, **kwargs):
    """
    Apply various filters to running speed data
    
    Parameters:
    - speed_data: array of running speed values
    - timestamps: array of corresponding timestamps
    - filter_type: type of filter to apply ('moving_average', 'median', 'savitzky_golay', 'butterworth')
    - **kwargs: filter-specific parameters
    
    Returns:
    - filtered_speed: filtered speed data
    """
    import numpy as np
    from scipy.signal import savgol_filter, butter, filtfilt
    
    if filter_type == 'moving_average':
        window_size = kwargs.get('window_size', 5)
        if window_size % 2 == 0:
            window_size += 1  # Make window size odd
        
        # Apply moving average filter
        kernel = np.ones(window_size) / window_size
        filtered_speed = np.convolve(speed_data, kernel, mode='same')
        
    elif filter_type == 'median':
        window_size = kwargs.get('window_size', 5)
        if window_size % 2 == 0:
            window_size += 1  # Make window size odd
        
        # Apply median filter
        filtered_speed = []
        half_window = window_size // 2
        
        for i in range(len(speed_data)):
            start_idx = max(0, i - half_window)
            end_idx = min(len(speed_data), i + half_window + 1)
            window_data = speed_data[start_idx:end_idx]
            filtered_speed.append(np.median(window_data))
        
        filtered_speed = np.array(filtered_speed)
        
    elif filter_type == 'savitzky_golay':
        window_size = kwargs.get('window_size', 11)
        poly_order = kwargs.get('poly_order', 3)
        
        if window_size % 2 == 0:
            window_size += 1  # Make window size odd
        
        # Apply Savitzky-Golay filter
        filtered_speed = savgol_filter(speed_data, window_size, poly_order)
        
    elif filter_type == 'butterworth':
        sampling_rate = kwargs.get('sampling_rate', 10)  # Hz
        cutoff_freq = kwargs.get('cutoff_freq', 2.0)  # Hz
        filter_order = kwargs.get('filter_order', 2)
        
        # Design Butterworth low-pass filter
        nyquist_freq = 0.5 * sampling_rate
        normal_cutoff = cutoff_freq / nyquist_freq
        b, a = butter(filter_order, normal_cutoff, btype='low', analog=False)
        
        # Apply zero-phase filtering
        filtered_speed = filtfilt(b, a, speed_data)
        
    else:
        # No filtering
        filtered_speed = speed_data.copy()
    
    return filtered_speed

def preprocess_running_data(ast2_data, filter_settings):
    """
    Preprocess running data with specified filters
    
    Parameters:
    - ast2_data: dictionary containing running data
    - filter_settings: dictionary with filter configuration
    
    Returns:
    - processed_data: dictionary with original and filtered data
    """
    if ast2_data is None:
        return None
    
    try:
        speed = ast2_data['data']['speed']
        timestamps = ast2_data['data']['timestamps']
        
        # Apply filters sequentially
        filtered_speed = speed.copy()
        filter_history = ["original"]
        
        for filter_config in filter_settings:
            filter_type = filter_config['type']
            if filter_type != 'none':
                filtered_speed = apply_running_filters(
                    filtered_speed, timestamps, 
                    filter_type, **filter_config.get('params', {})
                )
                filter_history.append(filter_type)
        
        # Create processed data structure
        processed_data = {
            'original_speed': speed,
            'filtered_speed': filtered_speed,
            'timestamps': timestamps,
            'filter_history': filter_history,
            'filter_settings': filter_settings
        }
        
        return processed_data
        
    except Exception as e:
        log_message(f"Error in running data preprocessing: {str(e)}", "ERROR")
        return None