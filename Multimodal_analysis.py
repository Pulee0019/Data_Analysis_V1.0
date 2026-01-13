"""
Shared functions for multimodal analysis
Used by both Running_induced_activity_analysis.py and Drug_induced_activity_analysis.py
"""
import tkinter as tk
from tkinter import filedialog
import numpy as np
import pandas as pd
from datetime import datetime
import os

from logger import log_message

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
    
def identify_optogenetic_events(fiber_events):
    """
    Identify optogenetic events from fiber data
    Input3: Laser events
    0: Laser start
    1: Laser end
    Returns list of (time, event_type) tuples
    """
    events = []

    # Find optogenetic events
    opto_start_mask = (fiber_events['Name'] == 'Input3') & (fiber_events['State'] == 0)
    opto_end_mask = (fiber_events['Name'] == 'Input3') & (fiber_events['State'] == 1)
    
    running_start_time = fiber_events.loc[(fiber_events['Name'] == 'Input2') & (fiber_events['State'] == 0), 'TimeStamp'].values

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

def identify_drug_events(fiber_events):
    """
    Identify drug administration events from fiber data
    Event2: Drug administration
    State 0: Drug administered
    State 1: Drug administration ended
    Returns list of (time, event_type) tuples
    """
    events = []

    # Find drug administration events
    drug_start_mask = (fiber_events['Name'] == 'Event2') & (fiber_events['State'] == 0)
    drug_end_mask = (fiber_events['Name'] == 'Event2') & (fiber_events['State'] == 1)
    
    running_start_time = fiber_events.loc[(fiber_events['Name'] == 'Input2') & (fiber_events['State'] == 0), 'TimeStamp'].values

    # Extract start events
    start_times = (fiber_events.loc[drug_start_mask, 'TimeStamp'].values - running_start_time) / 1000
    for time in start_times:
        events.append((float(time), 'start'))
    
    # Extract end events
    end_times = (fiber_events.loc[drug_end_mask, 'TimeStamp'].values - running_start_time) / 1000
    for time in end_times:
        events.append((float(time), 'end'))
    
    # Sort by time
    events.sort(key=lambda x: x[0])
    return events

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