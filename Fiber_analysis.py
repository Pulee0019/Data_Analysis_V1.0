import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
from sklearn.linear_model import LinearRegression
from scipy.optimize import curve_fit
from logger import log_message

def smooth_data(animal_data=None, window_size=11, poly_order=3, target_signal="470", reference_signal="410"):
    """Apply smoothing to target signals + reference signal"""
    try:
        if animal_data is not None and not isinstance(animal_data, dict):
            log_message(f"Invalid animal_data type: {type(animal_data)}", "ERROR")
            return False
            
        if animal_data:
            fiber_data = animal_data.get('fiber_data_trimmed')
            channels = animal_data.get('channels', {})
            active_channels = animal_data.get('active_channels', [])
            channel_data = animal_data.get('channel_data', {})
            
            if fiber_data is None:
                log_message("No fiber data available", "WARNING")
                return False
                
            if 'preprocessed_data' not in animal_data:
                animal_data['preprocessed_data'] = fiber_data.copy()
            preprocessed_data = animal_data['preprocessed_data']
        else:
            fiber_data = globals().get('fiber_data_trimmed')
            channels = globals().get('channels', {})
            active_channels = globals().get('active_channels', [])
            channel_data = globals().get('channel_data', {})
            
            if fiber_data is None:
                log_message("No fiber data available", "WARNING")
                return False
                
            if not hasattr(globals(), 'preprocessed_data') or globals().get('preprocessed_data') is None:
                globals()['preprocessed_data'] = fiber_data.copy()
            preprocessed_data = globals()['preprocessed_data']
        
        if not hasattr(preprocessed_data, 'columns'):
            log_message("Preprocessed data is not a valid DataFrame", "ERROR")
            return False
            
        if fiber_data is None or not active_channels:
            log_message("Please load and crop fiber data and select channels first", "WARNING")
            return False
        
        if not isinstance(active_channels, list):
            active_channels = [active_channels] if active_channels else []
        
        # Collect wavelengths to smooth: all target wavelengths + reference (if it's a real wavelength)
        target_wavelengths = target_signal.split('+') if '+' in target_signal else [target_signal]
        wavelengths_to_process = set(target_wavelengths)
        if reference_signal and reference_signal != "baseline":
            wavelengths_to_process.add(reference_signal)  # reference is always a single wavelength
        
        smoothed_count = 0
        for channel_num in active_channels:
            if channel_num in channel_data:
                for wavelength in wavelengths_to_process:
                    target_col = channel_data[channel_num].get(wavelength)
                    if target_col and target_col in preprocessed_data.columns:
                        smoothed_col = f"CH{channel_num}_{wavelength}_smoothed"
                        preprocessed_data[smoothed_col] = savgol_filter(
                            preprocessed_data[target_col], window_size, poly_order)
                        smoothed_count += 1
        
        if animal_data:
            animal_data['preprocessed_data'] = preprocessed_data
        else:
            globals()['preprocessed_data'] = preprocessed_data
        
        log_message(f"Smoothing applied to {smoothed_count} signals (target + reference)", "INFO")
        return True
        
    except Exception as e:
        log_message(f"Smoothing failed: {str(e)}", "ERROR")
        return False

def baseline_correction(animal_data=None, model_type="Polynomial", target_signal="470",
                        reference_signal="410", apply_smooth=False):
    """Apply baseline correction to target signals + reference signal"""
    try:
        if animal_data:
            if 'preprocessed_data' not in animal_data:
                animal_data['preprocessed_data'] = animal_data.get('fiber_data_trimmed').copy()
            preprocessed_data = animal_data['preprocessed_data']
            fiber_data = animal_data.get('fiber_data_trimmed')
            channels = animal_data.get('channels', {})
            active_channels = animal_data.get('active_channels', [])
            channel_data = animal_data.get('channel_data', {})
        else:
            if not hasattr(globals(), 'preprocessed_data') or globals().get('preprocessed_data') is None:
                globals()['preprocessed_data'] = globals().get('fiber_data_trimmed').copy()
            preprocessed_data = globals()['preprocessed_data']
            fiber_data = globals().get('fiber_data_trimmed')
            channels = globals().get('channels', {})
            active_channels = globals().get('active_channels', [])
            channel_data = globals().get('channel_data', {})
        
        if not isinstance(active_channels, list):
            active_channels = [active_channels] if active_channels else []
        
        time_col = channels['time']
        time_data = preprocessed_data[time_col]
        
        # Collect wavelengths to correct: all target wavelengths + reference (if it's a real wavelength)
        target_wavelengths = target_signal.split('+') if '+' in target_signal else [target_signal]
        wavelengths_to_process = set(target_wavelengths)
        if reference_signal and reference_signal != "baseline":
            wavelengths_to_process.add(reference_signal)  # reference is always a single wavelength
        
        corrected_count = 0
        for channel_num in active_channels:
            if channel_num in channel_data:
                for wavelength in wavelengths_to_process:
                    target_col = channel_data[channel_num].get(wavelength)
                    if not target_col or target_col not in fiber_data.columns:
                        continue
                    
                    smoothed_col = f"CH{channel_num}_{wavelength}_smoothed"
                    if apply_smooth and smoothed_col in preprocessed_data.columns:
                        signal_col = smoothed_col
                    else:
                        signal_col = target_col
                    
                    signal_data = preprocessed_data[signal_col].values
                    
                    def exp_model(t, a, b, c):
                        return a * np.exp(-b * t) + c
                    
                    events_col = channels.get('events')
                    if events_col and events_col in fiber_data.columns:
                        drug_events = fiber_data[fiber_data[events_col].str.contains('Event1', na=False)]
                        if drug_events.empty:
                            baseline_mask = np.ones_like(time_data, dtype=bool)
                        else:
                            drug_start_time = drug_events[time_col].iloc[0]
                            baseline_mask = time_data < drug_start_time
                    else:
                        baseline_mask = np.ones_like(time_data, dtype=bool)
                        
                    if model_type.lower() == "exponential":
                        p0 = [
                            np.max(signal_data) - np.min(signal_data),
                            0.01,
                            np.min(signal_data)
                        ]
                        try:
                            params, _ = curve_fit(exp_model, time_data[baseline_mask], signal_data[baseline_mask], p0=p0, maxfev=5000)
                            baseline_pred = exp_model(time_data, *params)
                        except Exception as e:
                            log_message(f"Exponential fit failed for CH{channel_num}_{wavelength}: {str(e)}, using polynomial", "INFO")
                            params = np.polyfit(time_data[baseline_mask], signal_data[baseline_mask], 1)
                            baseline_pred = np.polyval(params, time_data)
                    else:
                        params = np.polyfit(time_data[baseline_mask], signal_data[baseline_mask], 1)
                        baseline_pred = np.polyval(params, time_data)
                    
                    baseline_corrected_col = f"CH{channel_num}_{wavelength}_baseline_corrected"
                    preprocessed_data[baseline_corrected_col] = signal_data - baseline_pred
                    preprocessed_data[f"CH{channel_num}_{wavelength}_baseline_pred"] = baseline_pred
                    corrected_count += 1
        
        if animal_data:
            animal_data['preprocessed_data'] = preprocessed_data
        else:
            globals()['preprocessed_data'] = preprocessed_data
        
        log_message(f"Baseline correction applied to {corrected_count} signals (target + reference)", "INFO")
        return True
        
    except Exception as e:
        log_message(f"Baseline correction failed: {str(e)}", "ERROR")
        return False

def motion_correction(animal_data=None, target_signal="470", reference_signal="410",
                     apply_smooth=False, apply_baseline=False):
    """Apply motion correction to target signals using selected reference wavelength"""
    try:
        if animal_data:
            if 'preprocessed_data' not in animal_data:
                animal_data['preprocessed_data'] = animal_data.get('fiber_data_trimmed').copy()
            preprocessed_data = animal_data['preprocessed_data']
            fiber_data = animal_data.get('fiber_data_trimmed')
            channels = animal_data.get('channels', {})
            active_channels = animal_data.get('active_channels', [])
            channel_data = animal_data.get('channel_data', {})
        else:
            if not hasattr(globals(), 'preprocessed_data') or globals().get('preprocessed_data') is None:
                globals()['preprocessed_data'] = globals().get('fiber_data_trimmed').copy()
            preprocessed_data = globals()['preprocessed_data']
            fiber_data = globals().get('fiber_data_trimmed')
            channels = globals().get('channels', {})
            active_channels = globals().get('active_channels', [])
            channel_data = globals().get('channel_data', {})
        
        if not isinstance(active_channels, list):
            active_channels = [active_channels] if active_channels else []
        
        # reference_signal must be a single wavelength, not 'baseline'
        if not reference_signal or reference_signal == "baseline":
            log_message("Motion correction requires a wavelength-based reference signal (not 'baseline')", "WARNING")
            return False
        
        # reference_signal is a single wavelength string (e.g. "410")
        target_wavelengths = target_signal.split('+') if '+' in target_signal else [target_signal]
        
        corrected_count = 0
        for channel_num in active_channels:
            if channel_num not in channel_data:
                continue
            
            # Get the raw column for the reference wavelength
            ref_col_raw = channel_data[channel_num].get(reference_signal)
            if not ref_col_raw or ref_col_raw not in fiber_data.columns:
                log_message(f"No {reference_signal}nm data for channel CH{channel_num}", "INFO")
                continue
            
            # Determine which version of the reference signal to use
            if apply_baseline:
                ref_bc_col = f"CH{channel_num}_{reference_signal}_baseline_corrected"
                if ref_bc_col in preprocessed_data.columns:
                    ref_data = preprocessed_data[ref_bc_col]
                    ref_source = f"baseline-corrected {reference_signal}"
                elif apply_smooth and f"CH{channel_num}_{reference_signal}_smoothed" in preprocessed_data.columns:
                    ref_data = preprocessed_data[f"CH{channel_num}_{reference_signal}_smoothed"]
                    ref_source = f"smoothed {reference_signal}"
                else:
                    ref_data = preprocessed_data[ref_col_raw]
                    ref_source = f"raw {reference_signal}"
                    log_message(f"Baseline corrected {reference_signal} not found for CH{channel_num}, using raw", "INFO")
            else:
                if apply_smooth and f"CH{channel_num}_{reference_signal}_smoothed" in preprocessed_data.columns:
                    ref_data = preprocessed_data[f"CH{channel_num}_{reference_signal}_smoothed"]
                    ref_source = f"smoothed {reference_signal}"
                else:
                    ref_data = preprocessed_data[ref_col_raw]
                    ref_source = f"raw {reference_signal}"
            
            # Process each target wavelength (skip if it happens to equal reference_signal)
            for wavelength in target_wavelengths:
                if wavelength == reference_signal:
                    continue
                
                target_col = channel_data[channel_num].get(wavelength)
                if not target_col or target_col not in fiber_data.columns:
                    continue
                
                baseline_col = f"CH{channel_num}_{wavelength}_baseline_corrected"
                smoothed_col = f"CH{channel_num}_{wavelength}_smoothed"
                
                if apply_baseline and baseline_col in preprocessed_data.columns:
                    signal_col = baseline_col
                    signal_source = "baseline-corrected"
                elif apply_smooth and smoothed_col in preprocessed_data.columns:
                    signal_col = smoothed_col
                    signal_source = "smoothed"
                else:
                    signal_col = target_col
                    signal_source = "raw"
                
                signal_data = preprocessed_data[signal_col]
                
                X = ref_data.values.reshape(-1, 1)
                y = signal_data.values
                model = LinearRegression()
                model.fit(X, y)
                predicted_signal = model.predict(X)
                
                motion_corrected_col = f"CH{channel_num}_{wavelength}_motion_corrected"
                preprocessed_data[motion_corrected_col] = signal_data - predicted_signal
                preprocessed_data[f"CH{channel_num}_{wavelength}_fitted_ref"] = predicted_signal
                corrected_count += 1
                
                log_message(f"CH{channel_num}_{wavelength}: {signal_source} signal fitted against {ref_source}", "INFO")
        
        if animal_data:
            animal_data['preprocessed_data'] = preprocessed_data
        else:
            globals()['preprocessed_data'] = preprocessed_data
        
        log_message(f"Motion correction applied to {corrected_count} target signals", "INFO")
        return True
        
    except Exception as e:
        log_message(f"Motion correction failed: {str(e)}", "ERROR")
        return False

def apply_preprocessing(animal_data=None, target_signal="470", reference_signal="410", 
                       baseline_period=(0, 60), apply_smooth=False, window_size=11, 
                       poly_order=3, apply_baseline=False, baseline_model="Polynomial", 
                       apply_motion=False):
    """Apply all selected preprocessing steps"""
    try:
        apply_smooth = bool(apply_smooth)
        apply_baseline = bool(apply_baseline)
        apply_motion = bool(apply_motion)
        
        if apply_smooth:
            if not smooth_data(animal_data, window_size, poly_order, target_signal, reference_signal):
                return False
        
        if apply_baseline:
            if not baseline_correction(animal_data, baseline_model, target_signal, reference_signal, apply_smooth):
                return False
        
        # Motion correction requires a real wavelength reference (not 'baseline')
        if apply_motion and reference_signal != "baseline":
            if not motion_correction(animal_data, target_signal, reference_signal,
                                   apply_smooth, apply_baseline):
                return False

        return True
        
    except Exception as e:
        log_message(f"Preprocessing failed: {str(e)}", "ERROR")
        return False

def calculate_dff(animal_data=None, target_signal="470", reference_signal="410", 
                  baseline_period=(0, 60), apply_baseline=False):
    """Calculate ΔF/F - can work without preprocessing"""
    try:
        if animal_data:
            # Check if preprocessed_data exists, if not use fiber_data_trimmed
            if 'preprocessed_data' not in animal_data:
                animal_data['preprocessed_data'] = animal_data.get('fiber_data_trimmed').copy()
            preprocessed_data = animal_data['preprocessed_data']
            fiber_data = animal_data.get('fiber_data_trimmed')
            channels = animal_data.get('channels', {})
            active_channels = animal_data.get('active_channels', [])
            channel_data = animal_data.get('channel_data', {})
        else:
            if not hasattr(globals(), 'preprocessed_data') or globals().get('preprocessed_data') is None:
                globals()['preprocessed_data'] = globals().get('fiber_data_trimmed').copy()
            preprocessed_data = globals()['preprocessed_data']
            fiber_data = globals().get('fiber_data_trimmed')
            channels = globals().get('channels', {})
            active_channels = globals().get('active_channels', [])
            channel_data = globals().get('channel_data', {})
        
        if not active_channels:
            log_message("No active channels selected", "WARNING")
            return
            
        time_col = channels['time']
        time_data = preprocessed_data[time_col]
        
        baseline_mask = (time_data >= baseline_period[0]) & (time_data <= baseline_period[1])
        
        if not baseline_mask.any():
            log_message("No data in baseline period", "ERROR")
            return
        
        dff_data_dict = {}
        
        # Parse target signal
        target_wavelengths = target_signal.split('+') if '+' in target_signal else [target_signal]
        
        for channel_num in active_channels:
            if channel_num in channel_data:
                # Calculate dFF for each wavelength separately
                for wavelength in target_wavelengths:
                    target_col = channel_data[channel_num].get(wavelength)
                    if not target_col or target_col not in fiber_data.columns:
                        continue
                    
                    # Determine which data to use as raw signal
                    smoothed_col = f"CH{channel_num}_{wavelength}_smoothed"
                    if smoothed_col in preprocessed_data.columns:
                        raw_col = smoothed_col
                    else:
                        raw_col = target_col
                    
                    raw_target = preprocessed_data[raw_col]
                    
                    if reference_signal != "baseline" and apply_baseline:
                        motion_corrected_col = f"CH{channel_num}_{wavelength}_motion_corrected"
                        if motion_corrected_col in preprocessed_data.columns:
                            dff_data = preprocessed_data[motion_corrected_col] / np.median(raw_target)
                        else:
                            log_message("Motion correction data not found, using baseline method", "WARNING")
                            baseline_median = np.median(raw_target[baseline_mask])
                            if baseline_median == 0:
                                baseline_median = np.finfo(float).eps
                            dff_data = (raw_target - baseline_median) / baseline_median
                    elif reference_signal != "baseline" and not apply_baseline:
                        fitted_ref_col = f"CH{channel_num}_{wavelength}_fitted_ref"
                        if fitted_ref_col in preprocessed_data.columns:
                            denominator = preprocessed_data[fitted_ref_col]
                            denominator = denominator.replace(0, np.finfo(float).eps)
                            dff_data = (raw_target - preprocessed_data[fitted_ref_col]) / denominator
                        else:
                            log_message("Fitted reference not found, using baseline method", "WARNING")
                            baseline_median = np.median(raw_target[baseline_mask])
                            if baseline_median == 0:
                                baseline_median = np.finfo(float).eps
                            dff_data = (raw_target - baseline_median) / baseline_median
                    elif reference_signal == "baseline" and apply_baseline:
                        baseline_pred_col = f"CH{channel_num}_{wavelength}_baseline_pred"
                        if baseline_pred_col in preprocessed_data.columns:
                            baseline_median = np.median(raw_target[baseline_mask])
                            if baseline_median == 0:
                                baseline_median = np.finfo(float).eps
                            dff_data = (raw_target - preprocessed_data[baseline_pred_col]) / baseline_median
                        else:
                            log_message("Baseline prediction not found, using simple baseline", "WARNING")
                            baseline_median = np.median(raw_target[baseline_mask])
                            if baseline_median == 0:
                                baseline_median = np.finfo(float).eps
                            dff_data = (raw_target - baseline_median) / baseline_median
                    elif reference_signal == "baseline" and not apply_baseline:
                        baseline_median = np.median(raw_target[baseline_mask])
                        if baseline_median == 0:
                            baseline_median = np.finfo(float).eps
                        dff_data = (raw_target - baseline_median) / baseline_median
                    
                    dff_col = f"CH{channel_num}_{wavelength}_dff"
                    preprocessed_data[dff_col] = dff_data
                    
                    # Store with wavelength identifier
                    key = f"{channel_num}_{wavelength}"
                    dff_data_dict[key] = dff_data
        
        if animal_data:
            animal_data['preprocessed_data'] = preprocessed_data
            animal_data['dff_data'] = dff_data_dict
            animal_data['target_signal'] = target_signal
        else:
            globals()['preprocessed_data'] = preprocessed_data
            globals()['dff_data'] = dff_data_dict
        
        log_message(f"ΔF/F calculated for {len(dff_data_dict)} signals", "INFO")
        
    except Exception as e:
        log_message(f"ΔF/F calculation failed: {str(e)}", "ERROR")
        import traceback
        traceback.print_exc()

def calculate_zscore(animal_data=None, target_signal="470", reference_signal="410", 
                     baseline_period=(0, 60), apply_baseline=False):
    """Calculate Z-score - requires ΔF/F"""
    try:
        if animal_data:
            preprocessed_data = animal_data.get('preprocessed_data')
            dff_data = animal_data.get('dff_data')
            channels = animal_data.get('channels', {})
            active_channels = animal_data.get('active_channels', [])
            
            # Check if dFF has been calculated
            if not dff_data:
                log_message("Please calculate ΔF/F first before Z-score", "WARNING")
                return None
        else:
            preprocessed_data = globals().get('preprocessed_data')
            dff_data = globals().get('dff_data')
            channels = globals().get('channels', {})
            active_channels = globals().get('active_channels', [])
            
            if not dff_data:
                log_message("Please calculate ΔF/F first before Z-score", "WARNING")
                return None
        
        if not active_channels:
            log_message("No active channels selected", "WARNING")
            return None
        
        time_col = channels.get('time')
        if time_col is None or time_col not in preprocessed_data.columns:
            log_message("Time column not found in preprocessed data", "ERROR")
            return None
        
        time_data = preprocessed_data[time_col]
        baseline_mask = (time_data >= baseline_period[0]) & (time_data <= baseline_period[1])
        
        if not any(baseline_mask):
            log_message("No data in baseline period", "ERROR")
            return None
        
        zscore_data_dict = {}
        
        # Parse target signal
        target_wavelengths = target_signal.split('+') if '+' in target_signal else [target_signal]
        
        for channel_num in active_channels:
            for wavelength in target_wavelengths:
                dff_col = f"CH{channel_num}_{wavelength}_dff"
                if dff_col not in preprocessed_data.columns:
                    continue
                
                dff_data_series = preprocessed_data[dff_col]
                baseline_dff = dff_data_series[baseline_mask]
                
                if len(baseline_dff) < 2:
                    continue
            
                mean_dff = np.mean(baseline_dff)
                std_dff = np.std(baseline_dff)
                
                if std_dff == 0:
                    zscore_data = np.zeros_like(dff_data_series)
                else:
                    zscore_data = (dff_data_series - mean_dff) / std_dff
                
                zscore_col = f"CH{channel_num}_{wavelength}_zscore"
                preprocessed_data[zscore_col] = zscore_data
                
                # Store with wavelength identifier
                key = f"{channel_num}_{wavelength}"
                zscore_data_dict[key] = zscore_data
        
        if animal_data:
            animal_data['preprocessed_data'] = preprocessed_data
            animal_data['zscore_data'] = zscore_data_dict
        else:
            globals()['preprocessed_data'] = preprocessed_data
            globals()['zscore_data'] = zscore_data_dict

        log_message(f"Z-score calculated for {len(zscore_data_dict)} signals", "INFO")
        return zscore_data_dict
        
    except Exception as e:
        log_message(f"Z-score calculation failed: {str(e)}", "ERROR")
        import traceback
        traceback.print_exc()
        return None