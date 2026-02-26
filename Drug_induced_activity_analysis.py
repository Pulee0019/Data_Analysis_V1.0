"""
Drug-induced activity analysis with table configuration
Supports multi-animal drug event analysis
"""
import os
import json
import tkinter as tk
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib import colors

from logger import log_message
from Multimodal_analysis import (
    export_statistics, identify_drug_sessions,create_control_panel, 
    create_table_window, initialize_table, create_parameter_panel,
    get_parameters_from_ui, FIBER_COLORS, DAY_COLORS
)

def show_drug_induced_analysis(root, multi_animal_data):
    """
    Show drug-induced analysis configuration window with parameters and table
    """
    if not multi_animal_data:
        log_message("No animal data available", "ERROR")
        return
    
    # Create main window
    main_window = tk.Toplevel(root)
    main_window.title("Drug-Induced Activity Analysis")
    main_window.geometry("900x700")
    main_window.transient(root)
    main_window.grab_set()
    
    # Main container
    container = tk.Frame(main_window, bg="#f8f8f8")
    container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # Left panel: Parameters
    param_config = {
        'start_time': "-1000",
        'end_time': "2000",
        'baseline_start': "-1000",
        'baseline_end': "0",
    }
    param_frame = create_parameter_panel(container, param_config)
    param_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 5))
    
    # Right panel: Table
    table_frame = tk.Frame(container, bg="#f8f8f8")
    table_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
    
    # Bottom button frame
    btn_frame = tk.Frame(main_window, bg="#f8f8f8")
    btn_frame.pack(fill=tk.X, padx=10, pady=10)
    
    # Initialize table manager
    table_manager = TableManager(root, table_frame, btn_frame, multi_animal_data)
    
    def run_analysis():
        params = get_parameters_from_ui(param_frame)
        if params:
            table_manager.run_analysis(params)
    
    tk.Button(btn_frame, text="Run Analysis", command=run_analysis,
             bg="#ffffff", fg="#000000", font=("Microsoft YaHei", 9, "bold"),
             relief=tk.FLAT, padx=10, pady=5).pack(side=tk.LEFT, padx=5)

class TableManager:
    """Manage table for multi-animal configuration"""
    def __init__(self, root, table_frame, btn_frame, multi_animal_data):
        self.root = root
        self.table_frame = table_frame
        self.btn_frame = btn_frame
        self.multi_animal_data = multi_animal_data
        
        self.table_data = {}
        self.row_headers = {}
        self.col_headers = {}
        self.used_animals = set()
        self.num_rows = 6
        self.num_cols = 6
        
        # Initialize default headers
        for i in range(self.num_rows):
            self.row_headers[i] = f"Row{i+1}"
        for j in range(self.num_cols):
            self.col_headers[j] = f"Column{j+1}"
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup table UI"""
        create_control_panel(
            self.btn_frame,
            self.add_row, self.remove_row,
            self.add_column, self.remove_column
        )
        
        create_table_window(self.table_frame)
        self.rebuild_table()
    
    def rebuild_table(self):
        """Rebuild table"""
        initialize_table(self.table_frame, self.num_rows, self.num_cols,
                        self.row_headers, self.col_headers, self.table_data,
                        self.rename_row, self.rename_column, self.show_animal_selector)
    
    def add_row(self):
        self.num_rows += 1
        self.row_headers[self.num_rows - 1] = f"Row{self.num_rows}"
        self.rebuild_table()
    
    def remove_row(self):
        if self.num_rows <= 1:
            return
        last_row = self.num_rows - 1
        for j in range(self.num_cols):
            if (last_row, j) in self.table_data:
                self.used_animals.discard(self.table_data[(last_row, j)])
                del self.table_data[(last_row, j)]
        del self.row_headers[last_row]
        self.num_rows -= 1
        self.rebuild_table()
    
    def add_column(self):
        self.num_cols += 1
        self.col_headers[self.num_cols - 1] = f"Column{self.num_cols}"
        self.rebuild_table()
    
    def remove_column(self):
        if self.num_cols <= 1:
            return
        last_col = self.num_cols - 1
        for i in range(self.num_rows):
            if (i, last_col) in self.table_data:
                self.used_animals.discard(self.table_data[(i, last_col)])
                del self.table_data[(i, last_col)]
        del self.col_headers[last_col]
        self.num_cols -= 1
        self.rebuild_table()
    
    def rename_row(self, row_idx):
        """Rename row header"""
        current_name = self.row_headers.get(row_idx, f"Row{row_idx+1}")
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Rename Row")
        dialog.geometry("300x120")
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="Enter new row name:", 
                font=("Microsoft YaHei", 10)).pack(pady=10)
        
        entry = tk.Entry(dialog, font=("Microsoft YaHei", 10), width=20)
        entry.insert(0, current_name)
        entry.pack(pady=5)
        entry.focus_set()
        entry.select_range(0, tk.END)
        
        def save_name():
            new_name = entry.get().strip()
            if new_name:
                self.row_headers[row_idx] = new_name
                self.rebuild_table()
            dialog.destroy()
        
        tk.Button(dialog, text="OK", command=save_name).pack(pady=10)
        entry.bind("<Return>", lambda e: save_name())
    
    def rename_column(self, col_idx):
        """Rename column header"""
        current_name = self.col_headers.get(col_idx, f"Column{col_idx+1}")
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Rename Column")
        dialog.geometry("300x120")
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="Enter new column name:", 
                font=("Microsoft YaHei", 10)).pack(pady=10)
        
        entry = tk.Entry(dialog, font=("Microsoft YaHei", 10), width=20)
        entry.insert(0, current_name)
        entry.pack(pady=5)
        entry.focus_set()
        entry.select_range(0, tk.END)
        
        def save_name():
            new_name = entry.get().strip()
            if new_name and new_name != current_name:
                for i in range(self.num_rows):
                    if (i, col_idx) in self.table_data:
                        self.used_animals.discard(self.table_data[(i, col_idx)])
                        del self.table_data[(i, col_idx)]
                self.col_headers[col_idx] = new_name
                self.rebuild_table()
            dialog.destroy()
        
        tk.Button(dialog, text="OK", command=save_name).pack(pady=10)
        entry.bind("<Return>", lambda e: save_name())
    
    def show_animal_selector(self, event, row, col):
        """Show animal-session selection menu with drug names"""
        col_header = self.col_headers.get(col, f"Column{col+1}")
        is_custom_header = not col_header.startswith("Column")
        
        available_sessions = []
        
        # Load drug name config
        config_path = os.path.join(os.path.dirname(__file__), 'drug_name_config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                drug_name_config = json.load(f)
        else:
            drug_name_config = {}
        
        for animal_data in self.multi_animal_data:
            animal_id = animal_data.get('animal_single_channel_id', '')
            
            # Get drug sessions for this animal
            if 'fiber_events' not in animal_data:
                continue
            
            drug_sessions = identify_drug_sessions(animal_data['fiber_events'])
            
            if not drug_sessions:
                continue
            
            for session_idx, session_info in enumerate(drug_sessions):
                # Create session ID
                session_id = f"{animal_id}_Session{session_idx+1}"
                
                # Get drug name from config
                drug_info = drug_name_config.get(session_id, "Drug")
                # Handle both old format (string) and new format (dict)
                if isinstance(drug_info, dict):
                    drug_name = drug_info.get('name', 'Drug')
                else:
                    drug_name = drug_info
                
                # Create display ID with drug name - MODIFIED FORMAT
                display_id = f"{animal_id}_Session{session_idx+1}_{drug_name}"
                
                # Check if matches column header filter
                if is_custom_header:
                    ear_tag = animal_id.split('-')[-1] if '-' in animal_id else ''
                    if ear_tag != col_header:
                        continue
                
                # Check if not already used
                if display_id not in self.used_animals:
                    available_sessions.append({
                        'display_id': display_id,
                        'animal_id': animal_id,
                        'session_idx': session_idx,
                        'drug_name': drug_name,
                        'time': session_info['time'],
                        'event_name': session_info['event_name']
                    })
        
        if not available_sessions:
            return
        
        menu = tk.Menu(self.root, tearoff=0)
        
        if (row, col) in self.table_data:
            menu.add_command(label="Clear", command=lambda: self.clear_cell(row, col))
            menu.add_separator()
        
        for session in available_sessions:
            label = f"{session['display_id']} ({session['event_name']}, {session['time']:.1f}s)"
            menu.add_command(
                label=label,
                command=lambda s=session: self.select_session(row, col, s)
            )
        
        menu.post(event.x_root, event.y_root)
    
    def select_session(self, row, col, session):
        if (row, col) in self.table_data:
            self.used_animals.discard(self.table_data[(row, col)])
        display_id = session['display_id']
        self.table_data[(row, col)] = display_id
        self.used_animals.add(display_id)
        self.rebuild_table()
    
    def clear_cell(self, row, col):
        if (row, col) in self.table_data:
            self.used_animals.discard(self.table_data[(row, col)])
            del self.table_data[(row, col)]
            self.rebuild_table()
    
    def run_analysis(self, params):
        """Run drug-induced analysis with current table configuration"""
        # Group animals by day
        day_data = {}
        for i in range(self.num_rows):
            day_name = self.row_headers.get(i, f"Day{i+1}")
            day_animals = []
            
            for j in range(self.num_cols):
                if (i, j) in self.table_data:
                    display_id = self.table_data[(i, j)]
                    
                    # Parse display_id to get animal_id and drug_name
                    # Format: {animal_id}_Session{N}_{drug_name}
                    parts = display_id.rsplit('_', 1)
                    if len(parts) == 2:
                        session_part = parts[0]  # animal_id_SessionN
                        drug_name = parts[1]
                    else:
                        session_part = display_id
                        drug_name = "Drug"
                    
                    # Extract animal_id from session_part
                    session_parts = session_part.split('_Session')
                    if len(session_parts) == 2:
                        animal_id = session_parts[0]
                        session_idx = int(session_parts[1]) - 1
                    else:
                        continue
                    
                    for animal_data in self.multi_animal_data:
                        if animal_data.get('animal_single_channel_id') == animal_id:
                            # Add drug info to animal_data
                            animal_data_with_drug = animal_data.copy()
                            animal_data_with_drug['selected_session_idx'] = session_idx
                            animal_data_with_drug['selected_drug_name'] = drug_name
                            
                            # Load drug timing from config
                            session_id = f"{animal_id}_Session{session_idx+1}"
                            config_path = os.path.join(os.path.dirname(__file__), 'drug_name_config.json')
                            if os.path.exists(config_path):
                                with open(config_path, 'r') as f:
                                    drug_config = json.load(f)
                                
                                if session_id in drug_config:
                                    drug_info = drug_config[session_id]
                                    if isinstance(drug_info, dict):
                                        animal_data_with_drug['drug_onset_time'] = drug_info.get('onset_time')
                                        animal_data_with_drug['drug_offset_time'] = drug_info.get('offset_time')
                            
                            day_animals.append(animal_data_with_drug)
                            break
            
            if day_animals:
                day_data[day_name] = day_animals
        
        if not day_data:
            log_message("No valid data in table", "WARNING")
            return
        
        run_drug_induced_analysis(day_data, params)

def run_drug_induced_analysis(day_data, params):
    """Run drug-induced analysis for multiple days"""
    log_message(f"Starting drug-induced analysis for {len(day_data)} day(s)...")
    
    results = {}
    all_statistics = []
    
    for day_name, animals in day_data.items():
        log_message(f"Analyzing {day_name} with {len(animals)} animal(s)...")
        day_result, day_stats = analyze_day_drug_induced(day_name, animals, params)
        
        if day_result:
            results[day_name] = day_result
        if day_stats:
            all_statistics.extend(day_stats)
    
    if params['export_stats'] and all_statistics:
        export_statistics(all_statistics, "drug_induced")
    
    if results:
        plot_drug_induced_results(results, params)
        create_individual_day_windows(results, params)
        log_message("Analysis completed successfully")
    else:
        log_message("No valid results", "ERROR")

def calculate_episodes(events, fiber_timestamps, dff_data,
                       active_channels, target_wavelengths,
                       pre_time, post_time, baseline_start, baseline_end,
                       preprocessed_data=None, channel_data=None,
                       reference_signal="410", apply_baseline=False):
    """Calculate fiber episodes for drug/optogenetic analysis.
    
    DFF is computed from raw data using the event baseline window as F0:
      - reference_signal != 'baseline' and apply_baseline:
            dff = motion_corrected / F0
      - reference_signal != 'baseline' and not apply_baseline:
            dff = (raw_target - fitted_ref) / F0
      - reference_signal == 'baseline' and apply_baseline:
            dff = (raw_target - baseline_pred) / F0
      - reference_signal == 'baseline' and not apply_baseline:
            dff = (raw_target - F0) / F0
    where F0 = median of raw target in the event's baseline window.
    """
    time_array = np.linspace(-pre_time, post_time, int((pre_time + post_time) * 10))
    
    dff_episodes = {}
    zscore_episodes = {}
    
    for wavelength in target_wavelengths:
        dff_episodes[wavelength] = []
        zscore_episodes[wavelength] = []
    
    use_raw_dff = (preprocessed_data is not None and channel_data is not None)
    
    for channel in active_channels:
        for wavelength in target_wavelengths:
            if use_raw_dff and channel in channel_data:
                target_col = channel_data[channel].get(wavelength)
                if not target_col or target_col not in preprocessed_data.columns:
                    continue
                
                smoothed_col = f"CH{channel}_{wavelength}_smoothed"
                if smoothed_col in preprocessed_data.columns:
                    raw_target = preprocessed_data[smoothed_col].values
                else:
                    raw_target = preprocessed_data[target_col].values
                
                motion_corrected_col = f"CH{channel}_{wavelength}_motion_corrected"
                fitted_ref_col = f"CH{channel}_{wavelength}_fitted_ref"
                baseline_pred_col = f"CH{channel}_{wavelength}_baseline_pred"
                
                for event in events:
                    event_time = event if isinstance(event, (int, float)) else event[0]
                    
                    baseline_start_time = event_time + baseline_start
                    baseline_end_time = event_time + baseline_end
                    baseline_start_idx = np.argmin(np.abs(fiber_timestamps - baseline_start_time))
                    baseline_end_idx = np.argmin(np.abs(fiber_timestamps - baseline_end_time))
                    
                    if baseline_end_idx <= baseline_start_idx:
                        continue
                    
                    # F0 = median of raw target in baseline window
                    raw_baseline = raw_target[baseline_start_idx:baseline_end_idx]
                    F0 = np.nanmedian(raw_baseline)
                    if F0 == 0 or np.isnan(F0):
                        F0 = np.finfo(float).eps
                    
                    # Compute dff signal
                    if reference_signal != "baseline" and apply_baseline:
                        if motion_corrected_col in preprocessed_data.columns:
                            signal = preprocessed_data[motion_corrected_col].values
                            dff_signal = signal / F0
                            log_message(f"Using motion-corrected signal for dFF calculation for channel {channel} wavelength {wavelength}")
                        else:
                            dff_signal = (raw_target - F0) / F0
                            log_message(f"Motion-corrected signal not found, falling back to raw signal for dFF calculation for channel {channel} wavelength {wavelength}", "WARNING")
                    elif reference_signal != "baseline" and not apply_baseline:
                        if fitted_ref_col in preprocessed_data.columns:
                            fitted_ref = preprocessed_data[fitted_ref_col].values
                            dff_signal = (raw_target - fitted_ref) / F0
                            log_message(f"Using fitted reference signal for dFF calculation for channel {channel} wavelength {wavelength}")
                        else:
                            dff_signal = (raw_target - F0) / F0
                            log_message(f"Fitted reference signal not found, falling back to raw signal for dFF calculation for channel {channel} wavelength {wavelength}", "WARNING")
                    elif reference_signal == "baseline" and apply_baseline:
                        if baseline_pred_col in preprocessed_data.columns:
                            baseline_pred = preprocessed_data[baseline_pred_col].values
                            dff_signal = (raw_target - baseline_pred) / F0
                            log_message(f"Using baseline prediction signal for dFF calculation for channel {channel} wavelength {wavelength}")
                        else:
                            dff_signal = (raw_target - F0) / F0
                            log_message(f"Baseline prediction signal not found, falling back to raw signal for dFF calculation for channel {channel} wavelength {wavelength}", "WARNING")
                    else:
                        # reference_signal == "baseline" and not apply_baseline
                        dff_signal = (raw_target - F0) / F0
                        log_message(f"Using raw signal for dFF calculation for channel {channel} wavelength {wavelength}")
                    
                    # Extract plotting window
                    start_idx = np.argmin(np.abs(fiber_timestamps - (event_time - pre_time)))
                    end_idx = np.argmin(np.abs(fiber_timestamps - (event_time + post_time)))
                    
                    if end_idx > start_idx:
                        episode_data = dff_signal[start_idx:end_idx]
                        episode_times = fiber_timestamps[start_idx:end_idx] - event_time
                        
                        if len(episode_times) > 1:
                            interp_dff = np.interp(time_array, episode_times, episode_data)
                            dff_episodes[wavelength].append(interp_dff)
                            
                            # Z-score using baseline of computed dff
                            baseline_dff = dff_signal[baseline_start_idx:baseline_end_idx]
                            mean_dff = np.nanmean(baseline_dff)
                            std_dff = np.nanstd(baseline_dff)
                            if std_dff == 0:
                                std_dff = 1e-10
                            zscore_episode = (episode_data - mean_dff) / std_dff
                            interp_zscore = np.interp(time_array, episode_times, zscore_episode)
                            zscore_episodes[wavelength].append(interp_zscore)
            else:
                # Fallback: use pre-computed dff_data
                dff_key = f"{channel}_{wavelength}"
                if dff_key in dff_data:
                    data = dff_data[dff_key]
                    if isinstance(data, pd.Series):
                        data = data.values
                    
                    for event in events:
                        event_time = event if isinstance(event, (int, float)) else event[0]
                        
                        baseline_start_time = event_time + baseline_start
                        baseline_end_time = event_time + baseline_end
                        baseline_start_idx = np.argmin(np.abs(fiber_timestamps - baseline_start_time))
                        baseline_end_idx = np.argmin(np.abs(fiber_timestamps - baseline_end_time))
                        
                        if baseline_end_idx > baseline_start_idx:
                            baseline_data = data[baseline_start_idx:baseline_end_idx]
                            mean_dff = np.nanmean(baseline_data)
                            std_dff = np.nanstd(baseline_data)
                            if std_dff == 0:
                                std_dff = 1e-10
                            
                            start_idx = np.argmin(np.abs(fiber_timestamps - (event_time - pre_time)))
                            end_idx = np.argmin(np.abs(fiber_timestamps - (event_time + post_time)))
                            
                            if end_idx > start_idx:
                                episode_data = data[start_idx:end_idx]
                                episode_times = fiber_timestamps[start_idx:end_idx] - event_time
                                
                                if len(episode_times) > 1:
                                    interp_dff = np.interp(time_array, episode_times, episode_data)
                                    dff_episodes[wavelength].append(interp_dff)
                                    
                                    zscore_episode = (episode_data - mean_dff) / std_dff
                                    interp_zscore = np.interp(time_array, episode_times, zscore_episode)
                                    zscore_episodes[wavelength].append(interp_zscore)
    
    return {
        'time': time_array,
        'dff': dff_episodes,
        'zscore': zscore_episodes,
        'target_wavelengths': target_wavelengths
    }
    
def collect_statistics(day_name, animal_id, session_idx, drug_name, result,
                           time_array, params, target_wavelengths, active_channels):
    """Collect statistics for drug-induced fiber analysis"""
    rows = []
    pre_mask = (time_array >= -params['pre_time']) & (time_array <= 0)
    post_mask = (time_array >= 0) & (time_array <= params['post_time'])

    full_id = f"{animal_id}_Session{session_idx+1}_{drug_name}"

    # Fiber statistics
    for channel in active_channels:
        for wl in target_wavelengths:
            # dFF
            if wl in result['dff']:
                for trial_idx, episode_data in enumerate(result['dff'][wl]):
                    pre_data = episode_data[pre_mask]
                    post_data = episode_data[post_mask]

                    rows.append({
                        'day': day_name,
                        'animal_single_channel_id': full_id,
                        'analysis_type': 'drug_induced',
                        'channel': channel,
                        'wavelength': wl,
                        'trial': trial_idx + 1,
                        'drug_name': drug_name,
                        'pre_min': np.min(pre_data) if len(pre_data) > 0 else np.nan,
                        'pre_max': np.max(pre_data) if len(pre_data) > 0 else np.nan,
                        'pre_mean': np.mean(pre_data) if len(pre_data) > 0 else np.nan,
                        'pre_area': np.trapezoid(pre_data, time_array[pre_mask]) if len(pre_data) > 0 else np.nan,
                        'post_min': np.min(post_data) if len(post_data) > 0 else np.nan,
                        'post_max': np.max(post_data) if len(post_data) > 0 else np.nan,
                        'post_mean': np.mean(post_data) if len(post_data) > 0 else np.nan,
                        'post_area': np.trapezoid(post_data, time_array[post_mask]) if len(post_data) > 0 else np.nan,
                        'signal_type': 'fiber_dff',
                        'baseline_start': params['baseline_start'],
                        'baseline_end': params['baseline_end']
                    })

            # Z-score
            if wl in result['zscore']:
                for trial_idx, episode_data in enumerate(result['zscore'][wl]):
                    pre_data = episode_data[pre_mask]
                    post_data = episode_data[post_mask]

                    rows.append({
                        'day': day_name,
                        'animal_single_channel_id': full_id,
                        'analysis_type': 'drug_induced',
                        'channel': channel,
                        'wavelength': wl,
                        'trial': trial_idx + 1,
                        'drug_name': drug_name,
                        'pre_min': np.min(pre_data) if len(pre_data) > 0 else np.nan,
                        'pre_max': np.max(pre_data) if len(pre_data) > 0 else np.nan,
                        'pre_mean': np.mean(pre_data) if len(pre_data) > 0 else np.nan,
                        'pre_area': np.trapezoid(pre_data, time_array[pre_mask]) if len(pre_data) > 0 else np.nan,
                        'post_min': np.min(post_data) if len(post_data) > 0 else np.nan,
                        'post_max': np.max(post_data) if len(post_data) > 0 else np.nan,
                        'post_mean': np.mean(post_data) if len(post_data) > 0 else np.nan,
                        'post_area': np.trapezoid(post_data, time_array[post_mask]) if len(post_data) > 0 else np.nan,
                        'signal_type': 'fiber_zscore',
                        'baseline_start': params['baseline_start'],
                        'baseline_end': params['baseline_end']
                    })

    return rows

def analyze_day_drug_induced(day_name, animals, params):
    """Analyze drug-induced effects for one day (multiple animals combined)"""
    time_array = np.linspace(-params['pre_time'], params['post_time'], 
                            int((params['pre_time'] + params['post_time']) * 10))
    
    # Collect wavelengths
    target_wavelengths = []
    for animal_data in animals:
        if 'target_signal' in animal_data:
            signal = animal_data['target_signal']
            wls = signal.split('+') if '+' in signal else [signal]
            target_wavelengths.extend(wls)
    target_wavelengths = sorted(list(set(target_wavelengths)))
    
    if not target_wavelengths:
        target_wavelengths = ['470']
    
    # Initialize combined storage
    combined_dff = {wl: [] for wl in target_wavelengths}
    combined_zscore = {wl: [] for wl in target_wavelengths}
    statistics_rows = []
    
    for animal_data in animals:
        try:
            animal_id = animal_data.get('animal_single_channel_id', 'Unknown')
            session_idx = animal_data.get('selected_session_idx', 0)
            drug_name = animal_data.get('selected_drug_name', 'Drug')
            
            # Get drug timing
            drug_onset_time = animal_data.get('drug_onset_time')
            drug_offset_time = animal_data.get('drug_offset_time')
            
            log_message(f"Processing {animal_id} Session{session_idx+1} ({drug_name})")
            log_message(f"  Drug onset: {drug_onset_time}, offset: {drug_offset_time}")
            
            # Get data
            preprocessed_data = animal_data.get('preprocessed_data')
            if preprocessed_data is None or preprocessed_data.empty:
                log_message(f"No preprocessed data for {animal_id}", "WARNING")
                continue
            
            channels = animal_data.get('channels', {})
            time_col = channels.get('time')
            if not time_col or time_col not in preprocessed_data.columns:
                continue
            
            fiber_timestamps = preprocessed_data[time_col].values
            dff_data = animal_data.get('dff_data', {})
            active_channels = animal_data.get('active_channels', [])
            channel_data = animal_data.get('channel_data', {})
            reference_signal = animal_data.get('reference_signal', '410')
            apply_baseline = animal_data.get('apply_baseline', False)
            
            # Get drug events
            drug_sessions = identify_drug_sessions(animal_data['fiber_events'])
            
            if not drug_sessions or session_idx >= len(drug_sessions):
                log_message(f"Invalid session index for {animal_id}", "WARNING")
                continue
            
            selected_drug_session = drug_sessions[session_idx]
            drug_admin_time = selected_drug_session['time']
            
            # Use onset_time if available, otherwise use admin_time
            drug_event_time = drug_onset_time if drug_onset_time is not None else drug_admin_time
            
            # For drug-induced analysis, we only analyze one event per session
            events = [drug_event_time]
            
            result = calculate_episodes(
                events, fiber_timestamps, dff_data,
                active_channels, target_wavelengths,
                params['pre_time'], params['post_time'],
                params['baseline_start'], params['baseline_end'],
                preprocessed_data=preprocessed_data,
                channel_data=channel_data,
                reference_signal=reference_signal,
                apply_baseline=apply_baseline
            )
            
            # Combine results
            for wl in target_wavelengths:
                if wl in result['dff']:
                    combined_dff[wl].extend(result['dff'][wl])
                if wl in result['zscore']:
                    combined_zscore[wl].extend(result['zscore'][wl])
            
            # Collect statistics
            if params['export_stats']:
                statistics_rows.extend(collect_statistics(
                    day_name, animal_id, session_idx, drug_name, result,
                    time_array, params, target_wavelengths, active_channels
                ))
        
        except Exception as e:
            log_message(f"Error processing {animal_id}: {str(e)}", "ERROR")
            import traceback
            traceback.print_exc()
    
    if not any(combined_dff.values()):
        log_message(f"No valid episodes for {day_name}", "WARNING")
        return None, []
    
    result = {
        'time': time_array,
        'dff': combined_dff,
        'zscore': combined_zscore,
        'target_wavelengths': target_wavelengths
    }
    
    return result, statistics_rows

def plot_drug_induced_results(results, params):
    """Plot multi-animal drug-induced results with all days overlaid"""
    target_wavelengths = []
    for day_name, data in results.items():
        if 'target_wavelengths' in data:
            target_wavelengths = data['target_wavelengths']
            break
    
    if not target_wavelengths:
        target_wavelengths = ['470']
    
    result_window = tk.Toplevel()
    wavelength_label = '+'.join(target_wavelengths)
    result_window.title(f"Drug-Induced Activity - All Days ({wavelength_label}nm)")
    result_window.state('zoomed')
    result_window.configure(bg='#f8f8f8')
    
    num_wavelengths = len(target_wavelengths)
    num_cols = 2 * num_wavelengths
    
    fig = Figure(figsize=(4 * num_cols, 8), dpi=100)
    
    plot_idx = 1

    time_array = list(results.values())[0]['time']
    
    # Row 1: Traces
    for wl_idx, wavelength in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        
        # dFF trace
        ax_dff = fig.add_subplot(2, num_cols, plot_idx)
        for idx, (day_name, data) in enumerate(results.items()):
            day_color = DAY_COLORS[idx % len(DAY_COLORS)]
            episodes = data['dff'].get(wavelength, [])
            if episodes:
                episodes_array = np.array(episodes)
                mean_response = np.nanmean(episodes_array, axis=0)
                sem_response = np.nanstd(episodes_array, axis=0) / np.sqrt(len(episodes))
                
                ax_dff.plot(time_array, mean_response, color=day_color, linewidth=2, label=day_name)
                ax_dff.fill_between(time_array, mean_response - sem_response, 
                                   mean_response + sem_response, color=day_color, alpha=0.3)
        
        ax_dff.axvline(x=0, color='#808080', linestyle='--', alpha=0.8, label='Drug')
        ax_dff.set_xlim([time_array[0], time_array[-1]])
        ax_dff.set_xlabel('Time (s)')
        ax_dff.set_ylabel('ΔF/F')
        ax_dff.set_title(f'Fiber ΔF/F {wavelength}nm - All Days')
        ax_dff.legend()
        ax_dff.grid(False)
        plot_idx += 1
        
        # Z-score trace
        ax_zscore = fig.add_subplot(2, num_cols, plot_idx)
        for idx, (day_name, data) in enumerate(results.items()):
            day_color = DAY_COLORS[idx % len(DAY_COLORS)]
            episodes = data['zscore'].get(wavelength, [])
            if episodes:
                episodes_array = np.array(episodes)
                mean_response = np.nanmean(episodes_array, axis=0)
                sem_response = np.nanstd(episodes_array, axis=0) / np.sqrt(len(episodes))
                
                ax_zscore.plot(time_array, mean_response, color=day_color, linewidth=2, label=day_name)
                ax_zscore.fill_between(time_array, mean_response - sem_response, 
                                      mean_response + sem_response, color=day_color, alpha=0.3)
        
        ax_zscore.axvline(x=0, color='#808080', linestyle='--', alpha=0.8, label='Drug')
        ax_zscore.set_xlim([time_array[0], time_array[-1]])
        ax_zscore.set_xlabel('Time (s)')
        ax_zscore.set_ylabel('Z-score')
        ax_zscore.set_title(f'Fiber Z-score {wavelength}nm - All Days')
        ax_zscore.legend()
        ax_zscore.grid(False)
        plot_idx += 1
    
    # Row 2: Heatmaps
    for wl_idx, wavelength in enumerate(target_wavelengths):
        # dFF heatmap
        ax_dff_heat = fig.add_subplot(2, num_cols, plot_idx)
        all_episodes = []
        episodes_counts = []
        for day_name, data in results.items():
            episodes = data['dff'].get(wavelength, [])
            if episodes:
                all_episodes.extend(episodes)
                episodes_counts.append(len(episodes))

        if all_episodes:
            episodes_array = np.array(all_episodes)

            if len(episodes_array) == 1:
                episodes_array = np.vstack([episodes_array[0], episodes_array[0]])
                im = ax_dff_heat.imshow(episodes_array, aspect='auto', interpolation='nearest', 
                                extent=[time_array[0], time_array[-1], 0, 1],
                                cmap='coolwarm', origin='lower')
                ax_dff_heat.set_yticks(np.arange(0, 2, 1))
            else:
                im = ax_dff_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                    extent=[time_array[0], time_array[-1], 0, len(episodes_array)],
                                    cmap='coolwarm', origin='lower')
                if len(episodes_array) <= 10:
                    ax_dff_heat.set_yticks(np.arange(0, len(episodes_array)+1, 1))

            y_pos = 0
            for count in episodes_counts[:-1]:
                if count > 0:
                    y_pos += count
                    ax_dff_heat.axhline(y=y_pos, color='k', linestyle='--', linewidth=1)
                    
            ax_dff_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            ax_dff_heat.set_xlabel('Time (s)')
            ax_dff_heat.set_ylabel('Trials')
            ax_dff_heat.set_title(f'Fiber ΔF/F Heatmap {wavelength}nm')
            plt.colorbar(im, ax=ax_dff_heat, label='ΔF/F', orientation='horizontal')
        plot_idx += 1
        
        # Z-score heatmap
        ax_zscore_heat = fig.add_subplot(2, num_cols, plot_idx)
        all_episodes = []
        episodes_counts = []
        for day_name, data in results.items():
            episodes = data['zscore'].get(wavelength, [])
            if episodes:
                all_episodes.extend(episodes)
                episodes_counts.append(len(episodes))
        
        if all_episodes:
            episodes_array = np.array(all_episodes)
            if len(episodes_array) == 1:
                episodes_array = np.vstack([episodes_array[0], episodes_array[0]])
                im = ax_zscore_heat.imshow(episodes_array, aspect='auto', interpolation='nearest', 
                                        extent=[time_array[0], time_array[-1], 0, 1],
                                        cmap='coolwarm', origin='lower')
                ax_zscore_heat.set_yticks(np.arange(0, 2, 1))
            else:
                im = ax_zscore_heat.imshow(episodes_array, aspect='auto', interpolation='nearest', 
                                        extent=[time_array[0], time_array[-1], 0, len(episodes_array)],
                                        cmap='coolwarm', origin='lower')
                if len(episodes_array) <= 10:
                    ax_zscore_heat.set_yticks(np.arange(0, len(episodes_array)+1, 1))
            y_pos = 0
            for count in episodes_counts[:-1]:
                if count > 0:
                    y_pos += count
                    ax_zscore_heat.axhline(y=y_pos, color='k', linestyle='--', linewidth=1)
                    
            ax_zscore_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            ax_zscore_heat.set_xlabel('Time (s)')
            ax_zscore_heat.set_ylabel('Trials')
            ax_zscore_heat.set_title(f'Fiber Z-score Heatmap {wavelength}nm')
            plt.colorbar(im, ax=ax_zscore_heat, label='Z-score', orientation='horizontal')
        plot_idx += 1
    
    fig.tight_layout()
    
    canvas_frame = tk.Frame(result_window, bg='#f8f8f8')
    canvas_frame.pack(fill=tk.BOTH, expand=True)
    
    canvas = FigureCanvasTkAgg(fig, canvas_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    toolbar_frame = tk.Frame(canvas_frame, bg="#f5f5f5")
    toolbar_frame.pack(fill=tk.X, padx=2, pady=(0,2))
    toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
    
    log_message(f"Drug-induced results plotted for {len(results)} days")

def create_individual_day_windows(results, params):
    """Create individual windows for each day"""
    for day_name, data in results.items():
        create_single_day_window(day_name, data, params)

def create_single_day_window(day_name, data, params):
    """Create window for a single day"""
    day_window = tk.Toplevel()
    
    target_wavelengths = data.get('target_wavelengths', ['470'])
    wavelength_label = '+'.join(target_wavelengths)
    
    day_window.title(f"Drug-Induced Activity - {day_name} ({wavelength_label}nm)")
    day_window.state("zoomed")
    day_window.configure(bg='#f8f8f8')
    
    num_wavelengths = len(target_wavelengths)
    num_cols = 2 * num_wavelengths
    fig = Figure(figsize=(4 * num_cols, 8), dpi=100)
    
    plot_idx = 1
    time_array = data['time']
    
    # Row 1: Traces
    for wl_idx, wavelength in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        
        # dFF trace
        ax_dff = fig.add_subplot(2, num_cols, plot_idx)
        episodes = data['dff'].get(wavelength, [])
        if episodes:
            episodes_array = np.array(episodes)
            mean_response = np.nanmean(episodes_array, axis=0)
            sem_response = np.nanstd(episodes_array, axis=0) / np.sqrt(episodes_array.shape[0])
            
            ax_dff.plot(time_array, mean_response, color=color, linewidth=2, label='Mean')
            ax_dff.fill_between(time_array, mean_response - sem_response,
                              mean_response + sem_response, color=color, alpha=0.3)
            ax_dff.axvline(x=0, color='#808080', linestyle='--', alpha=0.8, label='Drug')
            ax_dff.set_xlim(time_array[0], time_array[-1])
            ax_dff.set_xlabel('Time (s)')
            ax_dff.set_ylabel('ΔF/F')
            ax_dff.set_title(f'{day_name} - Fiber ΔF/F {wavelength}nm')
            ax_dff.legend()
            ax_dff.grid(False)
        else:
            ax_dff.text(0.5, 0.5, f'No dFF data for {wavelength}nm',
                      ha='center', va='center', transform=ax_dff.transAxes,
                      fontsize=12, color='#666666')
            ax_dff.set_title(f'{day_name} - Fiber ΔF/F {wavelength}nm')
            ax_dff.axis('off')
        plot_idx += 1
        
        # Z-score trace
        ax_zscore = fig.add_subplot(2, num_cols, plot_idx)
        episodes = data['zscore'].get(wavelength, [])
        if episodes:
            episodes_array = np.array(episodes)
            mean_response = np.nanmean(episodes_array, axis=0)
            sem_response = np.nanstd(episodes_array, axis=0) / np.sqrt(episodes_array.shape[0])
            
            ax_zscore.plot(time_array, mean_response, color=color, linewidth=2, label='Mean')
            ax_zscore.fill_between(time_array, mean_response - sem_response,
                                 mean_response + sem_response, color=color, alpha=0.3)
            ax_zscore.axvline(x=0, color='#808080', linestyle='--', alpha=0.8, label='Drug')
            ax_zscore.set_xlim(time_array[0], time_array[-1])
            ax_zscore.set_xlabel('Time (s)')
            ax_zscore.set_ylabel('Z-score')
            ax_zscore.set_title(f'{day_name} - Fiber Z-score {wavelength}nm')
            ax_zscore.legend()
            ax_zscore.grid(False)
        else:
            ax_zscore.text(0.5, 0.5, f'No z-score data for {wavelength}nm',
                         ha='center', va='center', transform=ax_zscore.transAxes,
                         fontsize=12, color='#666666')
            ax_zscore.set_title(f'{day_name} - Fiber Z-score {wavelength}nm')
            ax_zscore.axis('off')
        plot_idx += 1
    
    # Row 2: Heatmaps
    for wl_idx, wavelength in enumerate(target_wavelengths):
        # dFF heatmap
        ax_dff_heat = fig.add_subplot(2, num_cols, plot_idx)
        episodes = data['dff'].get(wavelength, [])
        if episodes:
            episodes_array = np.array(episodes)
            if len(episodes_array) == 1:
                episodes_array = np.vstack([episodes_array[0], episodes_array[0]])
                im = ax_dff_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                    extent=[time_array[0], time_array[-1], 0, 1],
                                    cmap='coolwarm', origin='lower')
                ax_dff_heat.set_yticks(np.arange(0, 2, 1))
                ax_dff_heat.set_ylabel('Trials')
            else:
                im = ax_dff_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                    extent=[time_array[0], time_array[-1], 0, len(episodes)],
                                    cmap='coolwarm', origin='lower')
                if len(episodes_array) <= 10:
                    ax_dff_heat.set_yticks(np.arange(0, len(episodes)+1, 1))
                ax_dff_heat.set_ylabel('Trials')
            
            ax_dff_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            ax_dff_heat.set_xlabel('Time (s)')
            ax_dff_heat.set_title(f'{day_name} - Fiber ΔF/F Heatmap {wavelength}nm')
            
            if len(episodes_array) == 1:
                norm = colors.Normalize(vmin=episodes_array[0].min(), vmax=episodes_array[0].max())
                sm = plt.cm.ScalarMappable(cmap='coolwarm', norm=norm)
                sm.set_array([])
                cbar = plt.colorbar(sm, ax=ax_dff_heat, orientation='horizontal')
                cbar.set_label('ΔF/F')
            else:
                plt.colorbar(im, ax=ax_dff_heat, label='ΔF/F', orientation='horizontal')
        else:
            ax_dff_heat.text(0.5, 0.5, f'No dFF data for {wavelength}nm',
                           ha='center', va='center', transform=ax_dff_heat.transAxes,
                           fontsize=12, color='#666666')
            ax_dff_heat.set_title(f'{day_name} - Fiber ΔF/F Heatmap {wavelength}nm')
            ax_dff_heat.axis('off')
        plot_idx += 1
        
        # Z-score heatmap
        ax_zscore_heat = fig.add_subplot(2, num_cols, plot_idx)
        episodes = data['zscore'].get(wavelength, [])
        if episodes:
            episodes_array = np.array(episodes)
            
            if len(episodes_array) == 1:
                episodes_array = np.vstack([episodes_array[0], episodes_array[0]])
                im = ax_zscore_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                        extent=[time_array[0], time_array[-1], 0, 1],
                                        cmap='coolwarm', origin='lower')
                ax_zscore_heat.set_yticks(np.arange(0, 2, 1))
                ax_zscore_heat.set_ylabel('Trials')
            else:
                im = ax_zscore_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                        extent=[time_array[0], time_array[-1], 0, len(episodes)],
                                        cmap='coolwarm', origin='lower')
                if len(episodes) <= 10:
                    ax_zscore_heat.set_yticks(np.arange(0, len(episodes)+1, 1))
                ax_zscore_heat.set_ylabel('Trials')
            
            ax_zscore_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            ax_zscore_heat.set_xlabel('Time (s)')
            ax_zscore_heat.set_title(f'{day_name} - Fiber Z-score Heatmap {wavelength}nm')
            
            if len(episodes_array) == 1:
                norm = colors.Normalize(vmin=episodes_array[0].min(), vmax=episodes_array[0].max())
                sm = plt.cm.ScalarMappable(cmap='coolwarm', norm=norm)
                sm.set_array([])
                cbar = plt.colorbar(sm, ax=ax_zscore_heat, orientation='horizontal')
                cbar.set_label('Z-score')
            else:
                plt.colorbar(im, ax=ax_zscore_heat, label='Z-score', orientation='horizontal')
        else:
            ax_zscore_heat.text(0.5, 0.5, f'No z-score data for {wavelength}nm',
                              ha='center', va='center', transform=ax_zscore_heat.transAxes,
                              fontsize=12, color='#666666')
            ax_zscore_heat.set_title(f'{day_name} - Fiber Z-score Heatmap {wavelength}nm')
            ax_zscore_heat.axis('off')
        plot_idx += 1
    
    fig.tight_layout()
    
    canvas_frame = tk.Frame(day_window, bg='#f8f8f8')
    canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    canvas = FigureCanvasTkAgg(fig, canvas_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    toolbar_frame = tk.Frame(canvas_frame, bg="#f5f5f5")
    toolbar_frame.pack(fill=tk.X, padx=2, pady=(0,2))
    toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
    
    log_message(f"Individual day plot created for {day_name} with {len(target_wavelengths)} wavelength(s)")