"""
Shared functions
"""
import tkinter as tk
from tkinter import filedialog, ttk
import numpy as np
import pandas as pd
from datetime import datetime
import os
import json

from logger import log_message

# Colors for different days and fiber channels
DAY_COLORS = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', 
              '#1abc9c', '#e67e22', '#34495e', '#f1c40f', '#95a5a6']
FIBER_COLORS = ['#008000', '#FFA500', '#FF0000']

def get_events_from_bouts(animal_data, event_type, duration = False):
    """Extract events from bouts data based on event type"""
    events = []
    
    if 'running_bouts' not in animal_data:
        return events
    
    bouts_data = animal_data['running_bouts']
    
    # Parse event type to get bout type and event kind
    if event_type.endswith('_onsets'):
        bout_type = event_type.replace('_onsets', '_bouts')
        event_kind = 'onset'
    elif event_type.endswith('_offsets'):
        bout_type = event_type.replace('_offsets', '_bouts')
        event_kind = 'offset'
    else:
        return events
    
    # Get bout data
    if bout_type in bouts_data:
        bouts = bouts_data[bout_type]
        
        # Get timestamps from AST2 data
        ast2_data = animal_data.get('ast2_data_adjusted')
        if ast2_data is None:
            return events
            
        timestamps = ast2_data['data']['timestamps']
        
        for bout in bouts:
            if len(bout) >= 2:
                start_idx, end_idx = bout[0], bout[1]
                
                if start_idx < len(timestamps) and end_idx < len(timestamps):
                    if event_kind == 'onset' and not duration:  # onset
                        events.append(timestamps[start_idx])
                    elif event_kind == 'offset' and not duration:  # offset
                        events.append(timestamps[end_idx])
                    elif duration:  # duration
                        events.append((timestamps[start_idx], timestamps[end_idx]))
    
    return events

def identify_optogenetic_events(fiber_events):
    """
    Identify optogenetic events from fiber data
    """
    config_path = os.path.join(os.path.dirname(__file__), 'event_config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        event_config = json.load(f)
        
    opto_event_name = event_config.get('opto_event', 'Input3')
    running_start_name = event_config.get('running_start', 'Input2')
    events = []

    # Find optogenetic events using configured name
    opto_start_mask = (fiber_events['Name'] == opto_event_name) & (fiber_events['State'] == 0)
    opto_end_mask = (fiber_events['Name'] == opto_event_name) & (fiber_events['State'] == 1)
    
    running_start_time = fiber_events.loc[
        (fiber_events['Name'] == running_start_name) & (fiber_events['State'] == 0), 
        'TimeStamp'
    ].values

    # Extract start events
    start_times = (fiber_events.loc[opto_start_mask, 'TimeStamp'].values - running_start_time) / 1000
    for time in start_times:
        events.append((float(time), 'start'))
    
    # Extract end events
    end_times = (fiber_events.loc[opto_end_mask, 'TimeStamp'].values - running_start_time) / 1000
    for time in end_times:
        events.append((float(time), 'end'))
    
    # Sort by time
    events.sort(key=lambda x: x[0])
    return events

def group_optogenetic_sessions(events):
    """
    Group optogenetic events into sessions based on frequency threshold
    Returns list of sessions, each session is a list of (time, event_type) tuples
    """
    if not events:
        return []
    
    # Sort events by time
    events.sort(key=lambda x: x[0])
    
    sessions = []
    current_session = []
    
    for time, event_type in events:
        if not current_session:
            current_session.append((time, event_type))
        else:
            # Calculate time difference from last event
            last_time = current_session[-1][0]
            time_diff = time - last_time
            
            # If time difference > 20 seconds, start new session (frequency < 0.05 Hz)
            if time_diff > 20.0:
                if len(current_session) >= 2:  # Need at least one complete pulse
                    sessions.append(current_session)
                current_session = [(time, event_type)]
            else:
                current_session.append((time, event_type))
    
    # Add the last session
    if len(current_session) >= 2:
        sessions.append(current_session)
    
    return sessions

def identify_drug_sessions(fiber_events):
    """
    Identify multiple drug administration sessions from fiber data
    Returns list of dict with {time, event_name}
    """
    config_path = os.path.join(os.path.dirname(__file__), 'event_config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        event_config = json.load(f)
    
    drug_event_names = event_config.get('drug_event', 'Event1')
    # Support multiple drug events separated by comma
    if isinstance(drug_event_names, str):
        drug_event_names = [name.strip() for name in drug_event_names.split(',')]
    elif not isinstance(drug_event_names, list):
        drug_event_names = [str(drug_event_names)]
    
    running_start_name = event_config.get('running_start', 'Input2')
    
    drug_sessions = []
    
    running_start_time = fiber_events.loc[
        (fiber_events['Name'] == running_start_name) & (fiber_events['State'] == 0), 
        'TimeStamp'
    ].values
    
    if len(running_start_time) == 0:
        return drug_sessions
    
    running_start_time = running_start_time[0]
    
    # Find all drug events with their event names
    for drug_event_name in drug_event_names:
        drug_start_mask = (fiber_events['Name'] == drug_event_name) & (fiber_events['State'] == 0)
        start_times = (fiber_events.loc[drug_start_mask, 'TimeStamp'].values - running_start_time) / 1000
        
        for time in start_times:
            drug_sessions.append({
                'time': float(time),
                'event_name': drug_event_name
            })
    
    # Sort by time
    drug_sessions.sort(key=lambda x: x['time'])
    return drug_sessions

def get_drug_session_info(animal_id):
    """
    Get drug session information for an animal from config
    Returns list of {'session_id', 'drug_name', 'event_name'}
    """
    # Load drug name config
    config_path = os.path.join(os.path.dirname(__file__), 'drug_name_config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            drug_name_config = json.load(f)
    else:
        drug_name_config = {}
    
    session_info = []
    session_idx = 1
    
    # Find all sessions for this animal
    while True:
        session_id = f"{animal_id}_Session{session_idx}"
        if session_id in drug_name_config:
            session_info.append({
                'session_id': session_id,
                'drug_name': drug_name_config[session_id]
            })
            session_idx += 1
        else:
            break
    
    return session_info

def classify_events_by_drug_sessions(events, drug_sessions, drug_name_config, animal_id):
    """
    Classify events based on drug sessions
    Returns dict with keys: 'baseline', '{drug_name1}', '{drug_name2} after {drug_name1}', etc.
    """
    if not drug_sessions:
        return {'baseline': events}
    
    classified = {}
    
    # Get drug names for sessions
    drug_names = []
    for idx, session in enumerate(drug_sessions):
        session_id = f"{animal_id}_Session{idx+1}"
        drug_name = drug_name_config.get(session_id, 'Drug')
        drug_names.append(drug_name)
    
    # Classify events
    for event in events:
        # Find which period this event belongs to
        event_time = event if isinstance(event, (int, float)) else event[0]
        
        classified_key = None
        
        # Check if before first drug
        if event_time < drug_sessions[0]['time']:
            classified_key = 'baseline'
        else:
            # Find the period
            for idx in range(len(drug_sessions) - 1, -1, -1):
                if event_time >= drug_sessions[idx]['time']:
                    if idx == 0:
                        classified_key = drug_names[0]
                    else:
                        # Build compound name
                        classified_key = f"{drug_names[idx]} after {' + '.join(drug_names[:idx])}"
                    break
        
        if classified_key:
            if classified_key not in classified:
                classified[classified_key] = []
            classified[classified_key].append(event)
    
    return classified

def calculate_optogenetic_pulse_info(session_events, animal_id):
    """
    Calculate frequency, pulse width, and duration from a session of events
    """
    if len(session_events) < 2:
        return 0, 0, 0
    
    # Separate start and end times
    start_times = [time for time, event_type in session_events if event_type == 'start']
    end_times = [time for time, event_type in session_events if event_type == 'end']
    
    if not start_times or not end_times:
        return 0, 0, 0
    
    # Calculate pulse widths
    pulse_widths = []
    for start, end in zip(start_times, end_times):
        if end > start:
            pulse_widths.append(end - start)
    
    if not pulse_widths:
        return 0, 0, 0
    
    avg_pulse_width = np.mean(pulse_widths)
    
    # Calculate frequency (based on start times)
    if len(start_times) > 1:
        intervals = np.diff(start_times)
        frequency = 1.0 / np.mean(intervals)
    else:
        frequency = 0
    
    # Calculate total duration
    duration = max(start_times + end_times) - min(start_times + end_times)
    
    return frequency, avg_pulse_width, duration

def get_events_within_optogenetic(session_events, running_events, event_type):
    """
    Categorize running events as 'with' or 'without' optogenetic stimulation
    Returns two lists: with_opto_events, without_opto_events
    """
    with_opto = []
    without_opto = []
    
    # Extract optogenetic stimulation periods
    opto_periods = []
    start_time = None
    
    for time, ev_type in session_events:
        if ev_type == 'start' and start_time is None:
            start_time = time
        elif ev_type == 'end' and start_time is not None:
            opto_periods.append((start_time, time))
            start_time = None
    
    # Parse event type to get bout type and event kind
    if event_type.endswith('_onsets'):
        bout_type = event_type.replace('_onsets', '_bouts')
        event_kind = 'onset'
    elif event_type.endswith('_offsets'):
        bout_type = event_type.replace('_offsets', '_bouts')
        event_kind = 'offset'

    # Check each running event
    for start, end in running_events:
        event_within_opto = False
        
        for opto_start, opto_end in opto_periods:
            if start <= opto_start <= end and event_kind == 'onset' or start <= opto_end <= end and event_kind == 'offset':
                event_within_opto = True
                break
        
        if event_within_opto:
            if event_kind == 'onset':
                with_opto.append(start)
            elif event_kind == 'offset':
                with_opto.append(end)
        else:
            if event_kind == 'onset':
                without_opto.append(start)
            elif event_kind == 'offset':
                without_opto.append(end)
    
    return with_opto, without_opto

def create_opto_parameter_string(freq, pulse_width, duration, power):
    """Create a standardized parameter string"""
    return f"{freq:.1f}Hz_{pulse_width*1000:.0f}ms_{duration:.1f}s_{power:.1f}mW"

def calculate_running_episodes(events, running_timestamps, running_speed,
                               fiber_timestamps, dff_data,
                               active_channels, target_wavelengths,
                               pre_time, post_time, baseline_start, baseline_end):
    """Calculate episodes around running events with custom baseline"""
    time_array = np.linspace(-pre_time, post_time, int((pre_time + post_time) * 10))
    
    # Running episodes
    running_episodes = []
    for event in events:
        start_idx = np.argmin(np.abs(running_timestamps - (event - pre_time)))
        end_idx = np.argmin(np.abs(running_timestamps - (event + post_time)))
        
        if end_idx > start_idx:
            episode_data = running_speed[start_idx:end_idx]
            episode_times = running_timestamps[start_idx:end_idx] - event
            
            if len(episode_times) > 1:
                interp_data = np.interp(time_array, episode_times, episode_data)
                running_episodes.append(interp_data)
    
    # Fiber episodes
    dff_episodes = {}
    zscore_episodes = {}
    
    for wavelength in target_wavelengths:
        dff_episodes[wavelength] = []
        zscore_episodes[wavelength] = []
    
    for channel in active_channels:
        for wavelength in target_wavelengths:
            dff_key = f"{channel}_{wavelength}"
            if dff_key in dff_data:
                data = dff_data[dff_key]
                if isinstance(data, pd.Series):
                    data = data.values
                
                for event in events:
                    # Calculate baseline statistics from custom window
                    baseline_start_time = event + baseline_start
                    baseline_end_time = event + baseline_end
                    
                    baseline_start_idx = np.argmin(np.abs(fiber_timestamps - baseline_start_time))
                    baseline_end_idx = np.argmin(np.abs(fiber_timestamps - baseline_end_time))
                    
                    if baseline_end_idx > baseline_start_idx:
                        baseline_data = data[baseline_start_idx:baseline_end_idx]
                        mean_dff = np.nanmean(baseline_data)
                        std_dff = np.nanstd(baseline_data)
                        
                        if std_dff == 0:
                            std_dff = 1e-10
                        
                        # Extract plotting window
                        start_idx = np.argmin(np.abs(fiber_timestamps - (event - pre_time)))
                        end_idx = np.argmin(np.abs(fiber_timestamps - (event + post_time)))
                        
                        if end_idx > start_idx:
                            episode_data = data[start_idx:end_idx]
                            episode_times = fiber_timestamps[start_idx:end_idx] - event
                            
                            if len(episode_times) > 1:
                                # Store dFF data
                                interp_dff = np.interp(time_array, episode_times, episode_data)
                                dff_episodes[wavelength].append(interp_dff)
                                
                                # Calculate z-score using custom baseline
                                zscore_episode = (episode_data - mean_dff) / std_dff
                                interp_zscore = np.interp(time_array, episode_times, zscore_episode)
                                zscore_episodes[wavelength].append(interp_zscore)
    
    return {
        'time': time_array,
        'running': np.array(running_episodes) if running_episodes else np.array([]),
        'dff': dff_episodes,
        'zscore': zscore_episodes
    }

def export_statistics(statistics_rows, analysis_type, event_type=None):
    """Export statistics to CSV"""
    if not statistics_rows:
        log_message("No statistics data to export", "WARNING")
        return
    
    df = pd.DataFrame(statistics_rows)
    
    save_dir = filedialog.askdirectory(title='Select directory to save statistics CSV')
    
    if save_dir:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if event_type:
            filename = f"{analysis_type}_{event_type}_statistics_{timestamp}.csv"
        else:
            filename = f"{analysis_type}_statistics_{timestamp}.csv"
        save_path = os.path.join(save_dir, filename)
        df.to_csv(save_path, index=False)
        
        log_message(f"Statistics exported to {save_path} ({len(df)} rows)")
    else:
        log_message("Save directory not selected", "WARNING")

def create_parameter_panel(parent, param_config):
    """
    Create parameter configuration panel with flexible configuration
    
    param_config: dict with keys:
        - 'title': Panel title (default: "Analysis Parameters")
        - 'width': Panel width (default: 350)
        - 'start_time': Default start time (default: "-30")
        - 'end_time': Default end time (default: "60")
        - 'baseline_start': Default baseline start (default: "-30")
        - 'baseline_end': Default baseline end (default: "0")
        - 'show_bout_type': Whether to show bout type selection (default: False)
        - 'bout_types': List of available bout types (default: [])
        - 'show_event_type': Whether to show event type selection (default: False)
        - 'show_export': Whether to show export option (default: True)
    """
    config = {
        'title': "Analysis Parameters",
        'width': 350,
        'start_time': "-30",
        'end_time': "60",
        'baseline_start': "-30",
        'baseline_end': "0",
        'show_bout_type': False,
        'bout_types': [],
        'show_event_type': False,
        'show_export': True,
    }
    config.update(param_config)
    
    param_frame = tk.LabelFrame(parent, text=config['title'], 
                               font=("Microsoft YaHei", 11, "bold"), 
                               bg="#f8f8f8", width=config['width'])
    param_frame.pack_propagate(False)
    
    # Bout type selection (if needed)
    if config['show_bout_type'] and config['bout_types']:
        bout_frame = tk.LabelFrame(param_frame, text="Bout Type", 
                                  font=("Microsoft YaHei", 9, "bold"), bg="#f8f8f8")
        bout_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(bout_frame, text="Select Type:", bg="#f8f8f8", 
                font=("Microsoft YaHei", 8)).pack(anchor=tk.W, padx=10, pady=(5,2))
        
        bout_type_var = tk.StringVar()
        bout_type_combo = ttk.Combobox(bout_frame, textvariable=bout_type_var,
                                      values=config['bout_types'], state="readonly",
                                      font=("Microsoft YaHei", 8))
        bout_type_combo.pack(padx=10, pady=5, fill=tk.X)
        if config['bout_types']:
            bout_type_combo.set(config['bout_types'][0])
        
        param_frame.bout_type_var = bout_type_var
    
    # Event type selection (if needed)
    if config['show_event_type']:
        event_frame = tk.LabelFrame(param_frame, text="Event Type", 
                                   font=("Microsoft YaHei", 9, "bold"), bg="#f8f8f8")
        event_frame.pack(fill=tk.X, padx=10, pady=10)
        
        event_type_var = tk.StringVar(value="onset")
        tk.Radiobutton(event_frame, text="Onset", variable=event_type_var, 
                      value="onset", bg="#f8f8f8", font=("Microsoft YaHei", 8)).pack(anchor=tk.W, padx=20)
        tk.Radiobutton(event_frame, text="Offset", variable=event_type_var, 
                      value="offset", bg="#f8f8f8", font=("Microsoft YaHei", 8)).pack(anchor=tk.W, padx=20)
        
        param_frame.event_type_var = event_type_var
    
    # Plot window settings
    time_frame = tk.LabelFrame(param_frame, text="Plot Window (seconds)", 
                              font=("Microsoft YaHei", 9, "bold"), bg="#f8f8f8")
    time_frame.pack(fill=tk.X, padx=10, pady=10)
    
    start_frame = tk.Frame(time_frame, bg="#f8f8f8")
    start_frame.pack(fill=tk.X, pady=5)
    tk.Label(start_frame, text="Start:", bg="#f8f8f8", 
            font=("Microsoft YaHei", 8), width=8, anchor='w').pack(side=tk.LEFT, padx=10)
    start_time_var = tk.StringVar(value=config['start_time'])
    tk.Entry(start_frame, textvariable=start_time_var, width=8, 
            font=("Microsoft YaHei", 8)).pack(side=tk.LEFT, padx=5)
    
    end_frame = tk.Frame(time_frame, bg="#f8f8f8")
    end_frame.pack(fill=tk.X, pady=5)
    tk.Label(end_frame, text="End:", bg="#f8f8f8", 
            font=("Microsoft YaHei", 8), width=8, anchor='w').pack(side=tk.LEFT, padx=10)
    end_time_var = tk.StringVar(value=config['end_time'])
    tk.Entry(end_frame, textvariable=end_time_var, width=8, 
            font=("Microsoft YaHei", 8)).pack(side=tk.LEFT, padx=5)
    
    param_frame.start_time_var = start_time_var
    param_frame.end_time_var = end_time_var
    
    # Baseline window settings
    baseline_frame = tk.LabelFrame(param_frame, text="Baseline Window (seconds)", 
                                  font=("Microsoft YaHei", 9, "bold"), bg="#f8f8f8")
    baseline_frame.pack(fill=tk.X, padx=10, pady=10)
    
    baseline_start_frame = tk.Frame(baseline_frame, bg="#f8f8f8")
    baseline_start_frame.pack(fill=tk.X, pady=5)
    tk.Label(baseline_start_frame, text="Start:", bg="#f8f8f8", 
            font=("Microsoft YaHei", 8), width=8, anchor='w').pack(side=tk.LEFT, padx=10)
    baseline_start_var = tk.StringVar(value=config['baseline_start'])
    tk.Entry(baseline_start_frame, textvariable=baseline_start_var, width=8, 
            font=("Microsoft YaHei", 8)).pack(side=tk.LEFT, padx=5)
    
    baseline_end_frame = tk.Frame(baseline_frame, bg="#f8f8f8")
    baseline_end_frame.pack(fill=tk.X, pady=5)
    tk.Label(baseline_end_frame, text="End:", bg="#f8f8f8", 
            font=("Microsoft YaHei", 8), width=8, anchor='w').pack(side=tk.LEFT, padx=10)
    baseline_end_var = tk.StringVar(value=config['baseline_end'])
    tk.Entry(baseline_end_frame, textvariable=baseline_end_var, width=8, 
            font=("Microsoft YaHei", 8)).pack(side=tk.LEFT, padx=5)
    
    param_frame.baseline_start_var = baseline_start_var
    param_frame.baseline_end_var = baseline_end_var
    
    # Export option
    if config['show_export']:
        export_frame = tk.LabelFrame(param_frame, text="Export Options", 
                                    font=("Microsoft YaHei", 9, "bold"), bg="#f8f8f8")
        export_frame.pack(fill=tk.X, padx=10, pady=10)
        
        export_var = tk.BooleanVar(value=False)
        tk.Checkbutton(export_frame, text="Export statistics to CSV", 
                      variable=export_var, bg="#f8f8f8",
                      font=("Microsoft YaHei", 8)).pack(anchor=tk.W, padx=10, pady=5)
        
        param_frame.export_var = export_var
    
    return param_frame

def get_parameters_from_ui(param_frame, require_bout_type=False, require_event_type=False):
    """Extract parameters from UI"""
    try:
        start_time = float(param_frame.start_time_var.get())
        end_time = float(param_frame.end_time_var.get())
        baseline_start = float(param_frame.baseline_start_var.get())
        baseline_end = float(param_frame.baseline_end_var.get())
        
        if start_time >= end_time:
            log_message("Start time must be less than end time", "WARNING")
            return None
        
        if baseline_start >= baseline_end:
            log_message("Baseline start must be less than baseline end", "WARNING")
            return None
        
        pre_time = abs(min(0, start_time))
        post_time = max(0, end_time)
        
        params = {
            'start_time': start_time,
            'end_time': end_time,
            'pre_time': pre_time,
            'post_time': post_time,
            'baseline_start': baseline_start,
            'baseline_end': baseline_end,
        }
        
        # Add optional parameters
        if hasattr(param_frame, 'bout_type_var') and require_bout_type:
            params['bout_type'] = param_frame.bout_type_var.get()
        
        if hasattr(param_frame, 'event_type_var') and require_event_type:
            params['event_type'] = param_frame.event_type_var.get()
        
        if hasattr(param_frame, 'export_var'):
            params['export_stats'] = param_frame.export_var.get()
        else:
            params['export_stats'] = False
        
        return params
        
    except ValueError:
        log_message("Please enter valid parameter values", "WARNING")
        return None
    
def create_table_window(main_frame):
    """Create a generic table configuration window"""
    # Table container
    table_container = tk.Frame(main_frame, bg="#ffffff")
    table_container.pack(fill=tk.BOTH, expand=True)
    
    canvas = tk.Canvas(table_container, bg="#ffffff")
    v_scrollbar = tk.Scrollbar(table_container, orient=tk.VERTICAL, command=canvas.yview)
    h_scrollbar = tk.Scrollbar(table_container, orient=tk.HORIZONTAL, command=canvas.xview)
    
    table_frame = tk.Frame(canvas, bg="#ffffff")
    
    canvas.create_window((0, 0), window=table_frame, anchor="nw")
    canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
    
    def configure_scroll_region(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
    
    table_frame.bind("<Configure>", configure_scroll_region)
    
    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

def initialize_table(table_frame, num_rows, num_cols, row_headers, col_headers, table_data, rename_row_callback, rename_column_callback, show_animal_selector_callback):
    """Initialize table with default values"""
    # Clear existing widgets
    for widget in table_frame.winfo_children():
        widget.destroy()
    
    # Create corner cell
    corner = tk.Label(table_frame, text="", bg="#bdc3c7", 
                     relief=tk.RAISED, bd=2, width=12, height=2)
    corner.grid(row=0, column=0, sticky="nsew")
    
    # Create column headers
    for j in range(num_cols):
        header_text = col_headers.get(j, f"Animal{j+1}")
        header = tk.Label(table_frame, text=header_text, 
                        bg="#ffffff", fg="#000000",
                        font=("Microsoft YaHei", 10, "bold"),
                        relief=tk.RAISED, bd=2, width=12, height=2)
        header.grid(row=0, column=j+1, sticky="nsew")
        header.bind("<Double-Button-1>", lambda e, col=j: rename_column_callback(col))
    
    # Create row headers and cells
    for i in range(num_rows):
        # Row header
        header_text = row_headers.get(i, f"Day{i+1}")
        header = tk.Label(table_frame, text=header_text,
                        bg="#ffffff", fg="#000000",
                        font=("Microsoft YaHei", 10, "bold"),
                        relief=tk.RAISED, bd=2, width=12, height=2)
        header.grid(row=i+1, column=0, sticky="nsew")
        header.bind("<Double-Button-1>", lambda e, row=i: rename_row_callback(row))
        
        # Data cells
        for j in range(num_cols):
            cell_value = table_data.get((i, j), "")
            cell = tk.Label(table_frame, text=cell_value,
                          bg="#ecf0f1", relief=tk.SUNKEN, bd=2,
                          width=15, height=3, anchor="center",
                          font=("Microsoft YaHei", 9))
            cell.grid(row=i+1, column=j+1, sticky="nsew", padx=1, pady=1)
            cell.bind("<Button-3>", lambda e, row=i, col=j: show_animal_selector_callback(e, row, col))
    
    # Configure grid weights
    for i in range(num_rows + 1):
        table_frame.grid_rowconfigure(i, weight=1)
    for j in range(num_cols + 1):
        table_frame.grid_columnconfigure(j, weight=1)

def create_control_panel(btn_frame, add_row_callback, remove_row_callback, add_column_callback, remove_column_callback):
    """Create control panel for table operations"""
    
    tk.Button(btn_frame, text="+ Add Row", command=add_row_callback,
             bg="#fefefe", fg="#000000", font=("Microsoft YaHei", 9, "bold"),
             relief=tk.FLAT, padx=10, pady=5).pack(side=tk.LEFT, padx=5)
    
    tk.Button(btn_frame, text="- Remove Row", command=remove_row_callback,
             bg="#ffffff", fg="#000000", font=("Microsoft YaHei", 9, "bold"),
             relief=tk.FLAT, padx=10, pady=5).pack(side=tk.LEFT, padx=5)
    
    tk.Button(btn_frame, text="+ Add Column", command=add_column_callback,
             bg="#ffffff", fg="#000000", font=("Microsoft YaHei", 9, "bold"),
             relief=tk.FLAT, padx=10, pady=5).pack(side=tk.LEFT, padx=5)
    
    tk.Button(btn_frame, text="- Remove Column", command=remove_column_callback,
             bg="#ffffff", fg="#000000", font=("Microsoft YaHei", 9, "bold"),
             relief=tk.FLAT, padx=10, pady=5).pack(side=tk.LEFT, padx=5)