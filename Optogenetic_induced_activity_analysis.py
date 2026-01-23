"""
Optogenetic-induced activity analysis with table configuration
Supports multi-animal optogenetic event analysis
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
    export_statistics,
    create_table_window, initialize_table, create_control_panel,
    identify_optogenetic_events, calculate_optogenetic_pulse_info,
    identify_drug_sessions, group_optogenetic_sessions
)

# Colors for different days
DAY_COLORS = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', 
              '#1abc9c', '#e67e22', '#34495e', '#f1c40f', '#95a5a6']
FIBER_COLORS = ['#008000', "#FF0000", '#FFA500']

def show_optogenetic_induced_analysis(root, multi_animal_data, analysis_mode="optogenetics"):
    """
    Show optogenetic-induced analysis configuration window with parameters and table
    Supports 'optogenetics' and 'optogenetics+drug' modes
    """
    if not multi_animal_data:
        log_message("No animal data available", "ERROR")
        return
    
    # First, identify all optogenetic events across all animals
    log_message("Identifying optogenetic events across all animals...")
    
    # Collect all optogenetic events for all animals
    all_optogenetic_events = {}
    all_drug_events = {}  # ADD THIS for drug mode
    
    for animal_data in multi_animal_data:
        animal_id = animal_data.get('animal_single_channel_id', 'Unknown')
        events_data = animal_data.get('fiber_events')
    
        # Identify optogenetic events
        events = identify_optogenetic_events(events_data)
        log_message(f"Found {len(events)} optogenetic events for {animal_id}")
        
        if events:
            # Group events into stimulation sessions based on frequency threshold
            sessions = group_optogenetic_sessions(events)
            all_optogenetic_events[animal_id] = sessions
            log_message(f"Found {len(sessions)} optogenetic sessions for {animal_id}")
        
        # Identify drug events if in drug mode
        if analysis_mode == "optogenetics+drug":
            drug_sessions = identify_drug_sessions(events_data)
            if drug_sessions:
                all_drug_events[animal_id] = drug_sessions
                log_message(f"Found {len(drug_sessions)} drug sessions for {animal_id}")
    
    if not all_optogenetic_events:
        log_message("No optogenetic events found in any animal", "ERROR")
        return
    
    # Check drug events in drug mode
    if analysis_mode == "optogenetics+drug" and not all_drug_events:
        log_message("No drug events found in any animal for optogenetics+drug mode", "ERROR")
        return
    
    config_path = os.path.join(os.path.dirname(__file__), 'opto_power_config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        opto_config = json.load(f)
    
    # Create main window with parameter panel and table
    main_window = tk.Toplevel(root)
    title_suffix = " + Drug" if analysis_mode == "optogenetics+drug" else ""
    main_window.title(f"Optogenetic-Induced Activity Analysis{title_suffix}")
    main_window.geometry("900x700")
    main_window.transient(root)
    main_window.grab_set()
    
    # Main container with two sections
    container = tk.Frame(main_window, bg="#f8f8f8")
    container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # Left panel: Parameters
    param_frame = create_parameter_panel(container)
    param_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 5))
    
    # Right panel: Table
    table_frame = tk.Frame(container, bg="#f8f8f8")
    table_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
    
    btn_frame = tk.Frame(main_window, bg="#f8f8f8")
    btn_frame.pack(fill=tk.X, padx=10, pady=10)

    # Initialize table manager (MODIFIED to pass drug events and mode)
    table_manager = TableManager(root, table_frame, btn_frame, multi_animal_data, 
                                all_optogenetic_events, opto_config,
                                all_drug_events, analysis_mode)

    def run_analysis():
        params = get_parameters_from_ui(param_frame)
        if params:
            table_manager.run_analysis(params)

    tk.Button(btn_frame, text="Run Analysis", command=run_analysis,
             bg="#ffffff", fg="#000000", font=("Microsoft YaHei", 9, "bold"),
             relief=tk.FLAT, padx=10, pady=5).pack(side=tk.LEFT, padx=5)

def create_parameter_panel(parent):
    """Create parameter configuration panel"""
    param_frame = tk.LabelFrame(parent, text="Analysis Parameters", 
                               font=("Microsoft YaHei", 11, "bold"), 
                               bg="#f8f8f8", width=350)
    param_frame.pack_propagate(False)
    
    # Plot window settings
    time_frame = tk.LabelFrame(param_frame, text="Plot Window (seconds)", 
                              font=("Microsoft YaHei", 9, "bold"), bg="#f8f8f8")
    time_frame.pack(fill=tk.X, padx=10, pady=10)
    
    start_frame = tk.Frame(time_frame, bg="#f8f8f8")
    start_frame.pack(fill=tk.X, pady=5)
    tk.Label(start_frame, text="Start:", bg="#f8f8f8", 
            font=("Microsoft YaHei", 8), width=8, anchor='w').pack(side=tk.LEFT, padx=10)
    start_time_var = tk.StringVar(value="-30")
    tk.Entry(start_frame, textvariable=start_time_var, width=8, 
            font=("Microsoft YaHei", 8)).pack(side=tk.LEFT, padx=5)
    
    end_frame = tk.Frame(time_frame, bg="#f8f8f8")
    end_frame.pack(fill=tk.X, pady=5)
    tk.Label(end_frame, text="End:", bg="#f8f8f8", 
            font=("Microsoft YaHei", 8), width=8, anchor='w').pack(side=tk.LEFT, padx=10)
    end_time_var = tk.StringVar(value="60")
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
    baseline_start_var = tk.StringVar(value="-30")
    tk.Entry(baseline_start_frame, textvariable=baseline_start_var, width=8, 
            font=("Microsoft YaHei", 8)).pack(side=tk.LEFT, padx=5)
    
    baseline_end_frame = tk.Frame(baseline_frame, bg="#f8f8f8")
    baseline_end_frame.pack(fill=tk.X, pady=5)
    tk.Label(baseline_end_frame, text="End:", bg="#f8f8f8", 
            font=("Microsoft YaHei", 8), width=8, anchor='w').pack(side=tk.LEFT, padx=10)
    baseline_end_var = tk.StringVar(value="0")
    tk.Entry(baseline_end_frame, textvariable=baseline_end_var, width=8, 
            font=("Microsoft YaHei", 8)).pack(side=tk.LEFT, padx=5)
    
    param_frame.baseline_start_var = baseline_start_var
    param_frame.baseline_end_var = baseline_end_var
    
    # Export option
    export_frame = tk.LabelFrame(param_frame, text="Export Options", 
                                font=("Microsoft YaHei", 9, "bold"), bg="#f8f8f8")
    export_frame.pack(fill=tk.X, padx=10, pady=10)
    
    export_var = tk.BooleanVar(value=False)
    tk.Checkbutton(export_frame, text="Export statistics to CSV", 
                  variable=export_var, bg="#f8f8f8",
                  font=("Microsoft YaHei", 8)).pack(anchor=tk.W, padx=10, pady=5)
    
    param_frame.export_var = export_var
    
    return param_frame

def get_parameters_from_ui(param_frame):
    """Extract parameters from UI"""
    try:
        start_time = float(param_frame.start_time_var.get())
        end_time = float(param_frame.end_time_var.get())
        baseline_start = float(param_frame.baseline_start_var.get())
        baseline_end = float(param_frame.baseline_end_var.get())
        export_stats = param_frame.export_var.get()
        
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
            'export_stats': export_stats
        }
        
        return params
        
    except ValueError:
        log_message("Please enter valid parameter values", "WARNING")
        return None

class TableManager:
    """Manage table for optogenetic parameter configuration"""
    def __init__(self, root, table_frame, btn_frame, multi_animal_data, 
                 all_optogenetic_events, power_values, 
                 all_drug_events=None, analysis_mode="optogenetics"):  # ADD THESE PARAMETERS
        self.root = root
        self.table_frame = table_frame
        self.btn_frame = btn_frame
        self.multi_animal_data = multi_animal_data
        self.all_optogenetic_events = all_optogenetic_events
        self.power_values = power_values
        self.all_drug_events = all_drug_events
        self.analysis_mode = analysis_mode
        
        self.table_data = {}
        self.row_headers = {}
        self.col_headers = {}
        self.used_sessions = set()
        
        self.num_rows = 6
        self.num_cols = 6
        
        # Initialize headers
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
                        self.rename_row, self.rename_column, self.show_session_selector)
    
    def add_row(self):
        self.num_rows += 1
        self.row_headers[self.num_rows - 1] = f"Row{self.num_rows}"
        self.rebuild_table()
    
    def remove_row(self):
        """Remove last parameter row"""
        if self.num_rows <= 1:
            return
        last_row = self.num_rows - 1
        
        # Remove sessions from this row
        for j in range(self.num_cols):
            key = (last_row, j)
            if key in self.table_data:
                session_id = self.table_data[key]
                self.used_sessions.discard(session_id)
                del self.table_data[key]
        
        # Remove parameter
        del self.row_headers[last_row]
        self.num_rows -= 1
        self.rebuild_table()
    
    def add_column(self):
        """Add a new repetition column"""
        self.num_cols += 1
        self.col_headers[self.num_cols - 1] = f"Column{self.num_cols}"
        self.rebuild_table()
    
    def remove_column(self):
        """Remove last repetition column"""
        if self.num_cols <= 1:
            return
        last_col = self.num_cols - 1
        
        # Remove sessions from this column
        for i in range(self.num_rows):
            key = (i, last_col)
            if key in self.table_data:
                session_id = self.table_data[key]
                self.used_sessions.discard(session_id)
                del self.table_data[key]
        
        del self.col_headers[last_col]
        self.num_cols -= 1
        self.rebuild_table()
    
    def rename_row(self, row_idx):
        """Rename parameter row header"""
        current_name = self.row_headers.get(row_idx, f"Row{row_idx+1}")
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Rename Row")
        dialog.geometry("300x120")
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="Enter new row name:", 
                font=("Microsoft YaHei", 10)).pack(pady=10)
        
        entry = tk.Entry(dialog, font=("Microsoft YaHei", 10), width=25)
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
                # Clear all cells in this column
                for i in range(self.num_rows):
                    key = (i, col_idx)
                    if key in self.table_data:
                        session_id = self.table_data[key]
                        self.used_sessions.discard(session_id)
                        del self.table_data[key]
                
                self.col_headers[col_idx] = new_name
                self.rebuild_table()
            dialog.destroy()
        
        tk.Button(dialog, text="OK", command=save_name).pack(pady=10)
        entry.bind("<Return>", lambda e: save_name())
    
    def show_session_selector(self, event, row, col):
        """Show session selection menu based on row parameter"""
        available_sessions = []
        for animal_id, sessions in self.all_optogenetic_events.items():
            for session_idx, session in enumerate(sessions):
                # Calculate session info
                freq, pulse_width, duration = calculate_optogenetic_pulse_info(session, animal_id)
                
                # Get power for this parameter
                for param_id, power in self.power_values.items():
                    if param_id.startswith(f"{animal_id}_Session{session_idx+1}_{freq:.1f}Hz_{pulse_width*1000:.0f}ms_{duration:.1f}s"):
                        session_id = param_id
                        
                        # Check if this session matches the row parameter
                        if session_id not in self.used_sessions:
                            available_sessions.append((session_id, animal_id, session_idx))
                        break
        
        if not available_sessions:
            return
        
        menu = tk.Menu(self.root, tearoff=0)
        
        if (row, col) in self.table_data:
            menu.add_command(label="Clear", command=lambda: self.clear_cell(row, col))
            menu.add_separator()
        
        for session_id, animal_id, session_idx in available_sessions:
            display_text = f"{session_id}"
            menu.add_command(label=display_text,
                           command=lambda sid=session_id: self.select_session(row, col, sid))
        
        menu.post(event.x_root, event.y_root)
    
    def select_session(self, row, col, session_id):
        """Select a session for the cell"""
        if (row, col) in self.table_data:
            self.used_sessions.discard(self.table_data[(row, col)])
        
        self.table_data[(row, col)] = session_id
        self.used_sessions.add(session_id)
        self.rebuild_table()
    
    def clear_cell(self, row, col):
        """Clear cell content"""
        if (row, col) in self.table_data:
            session_id = self.table_data[(row, col)]
            self.used_sessions.discard(session_id)
            del self.table_data[(row, col)]
            self.rebuild_table()
    
    def run_analysis(self, params):
        """Run optogenetic-induced analysis with current table configuration"""
        # Group sessions by parameter (row)
        row_data = {}
        for i in range(self.num_rows):
            row_name = self.row_headers.get(i, f"Row{i+1}")
            row_sessions = []
            
            for j in range(self.num_cols):
                if (i, j) in self.table_data:
                    session_id = self.table_data[(i, j)]
                    
                    # Parse session ID to get animal info
                    parts = session_id.split('_')
                    animal_id = parts[0]
                    
                    # Find animal data
                    for animal_data in self.multi_animal_data:
                        if animal_data.get('animal_single_channel_id') == animal_id:
                            # Find the specific session
                            if animal_id in self.all_optogenetic_events:
                                sessions = self.all_optogenetic_events[animal_id]
                                
                                # Find session index from ID
                                for session_idx, session in enumerate(sessions):
                                    freq, pulse_width, duration = calculate_optogenetic_pulse_info(session, animal_id)
                                    expected_id = f"{animal_id}_Session{session_idx+1}_{freq:.1f}Hz_{pulse_width*1000:.0f}ms_{duration:.1f}s"
                                    
                                    # Check if this matches the session ID (without power)
                                    if session_id.startswith(expected_id):
                                        session_info = {
                                            'animal_data': animal_data,
                                            'session': session,
                                            'session_idx': session_idx,
                                            'power': self.power_values.get(session_id, 0)
                                        }
                                        
                                        # Classify as pre/post drug if in drug mode
                                        if self.analysis_mode == "optogenetics+drug":
                                            drug_time_category = self._classify_session_drug_timing_multi(
                                                animal_id, session, animal_data
                                            )
                                            session_info['drug_timing'] = drug_time_category
                                        
                                        row_sessions.append(session_info)
                                        break
                            break
            
            if row_sessions:
                row_data[row_name] = row_sessions
        
        if not row_data:
            log_message("No valid data in table", "WARNING")
            return
        
        run_optogenetic_induced_analysis(row_data, params, self.analysis_mode)

    def _classify_session_drug_timing_multi(self, animal_id, session, animal_data):
        """
        Classify optogenetic session based on multiple drug administration times
        Returns: 'baseline', '{drug_nameA}', '{drug_nameB} after {drug_nameA}', etc.
        """
        if animal_id not in self.all_drug_events:
            return 'baseline'
        
        drug_sessions = self.all_drug_events[animal_id]
        
        if not drug_sessions:
            return 'baseline'
        
        # Load drug name config
        config_path = os.path.join(os.path.dirname(__file__), 'drug_name_config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                drug_name_config = json.load(f)
        else:
            drug_name_config = {}
        
        # Get drug names and times
        drug_info = []
        for idx, session_info in enumerate(drug_sessions):
            session_id = f"{animal_id}_Session{idx+1}"
            drug_name = drug_name_config.get(session_id, f"Drug{idx+1}")
            drug_time = session_info['time']
            drug_info.append({'name': drug_name, 'time': drug_time, 'idx': idx})
        
        # Sort by time
        drug_info.sort(key=lambda x: x['time'])
        
        # Get optogenetic session time window
        session_start = min([time for time, _ in session])
        session_end = max([time for time, _ in session])
        session_mid = (session_start + session_end) / 2
        
        # Classify based on session midpoint relative to drug times
        if session_mid < drug_info[0]['time']:
            return 'baseline'
        
        # Find which drug period this session belongs to
        for i in range(len(drug_info) - 1, -1, -1):
            if session_mid >= drug_info[i]['time']:
                if i == 0:
                    # After first drug only
                    return drug_info[0]['name']
                else:
                    # After multiple drugs
                    previous_drugs = ' + '.join([d['name'] for d in drug_info[:i]])
                    return f"{drug_info[i]['name']} after {previous_drugs}"
        
        return 'baseline'

def run_optogenetic_induced_analysis(row_data, params, analysis_mode="optogenetics"):
    """Run optogenetic-induced analysis for multiple parameters"""
    log_message(f"Starting optogenetic-induced analysis ({analysis_mode} mode) for {len(row_data)} parameter(s)...")
    
    results = {}
    all_statistics = []
    
    # Handle drug mode differently
    if analysis_mode == "optogenetics+drug":
        # Collect all unique drug timing categories
        all_drug_timings = set()
        for row_name, sessions in row_data.items():
            for session in sessions:
                drug_timing = session.get('drug_timing', 'baseline')
                all_drug_timings.add(drug_timing)
        
        log_message(f"Found drug timing categories: {sorted(all_drug_timings)}")
        
        # Separate sessions by drug timing
        for row_name, sessions in row_data.items():
            log_message(f"Analyzing {row_name} with {len(sessions)} session(s)...")
            
            # Group sessions by drug timing
            timing_groups = {}
            for session in sessions:
                timing = session.get('drug_timing', 'baseline')
                if timing not in timing_groups:
                    timing_groups[timing] = []
                timing_groups[timing].append(session)
            
            log_message(f"Drug timing distribution: {[(k, len(v)) for k, v in timing_groups.items()]}")
            
            row_results = {}
            
            for timing_name, timing_sessions in timing_groups.items():
                timing_result, timing_stats = analyze_param_optogenetic(
                    f"{row_name}_{timing_name}", timing_sessions, params
                )
                if timing_result:
                    row_results[timing_name] = timing_result
                if timing_stats:
                    all_statistics.extend(timing_stats)
            
            if row_results:
                results[row_name] = row_results
    
    else:
        # Original optogenetics-only mode
        for row_name, sessions in row_data.items():
            log_message(f"Analyzing {row_name} with {len(sessions)} session(s)...")
            row_result, row_stats = analyze_param_optogenetic(row_name, sessions, params)
            
            if row_result:
                results[row_name] = {'optogenetics': row_result}
            if row_stats:
                all_statistics.extend(row_stats)
    
    if params['export_stats'] and all_statistics:
        export_statistics(all_statistics, f"optogenetic_induced_{analysis_mode}")
    
    if results:
        plot_optogenetic_results(results, params, analysis_mode)
        create_individual_param_windows(results, params, analysis_mode)
        log_message("Analysis completed successfully")
    else:
        log_message("No valid results", "ERROR")

def analyze_param_optogenetic(param_name, sessions, params):
    """Analyze optogenetic effects for one parameter (multiple sessions combined)"""
    time_array = np.linspace(-params['pre_time'], params['post_time'], 
                            int((params['pre_time'] + params['post_time']) * 10))
    
    # Collect all wavelengths from sessions
    target_wavelengths = []
    for session_info in sessions:
        animal_data = session_info['animal_data']
        if 'target_signal' in animal_data:
            signal = animal_data['target_signal']
            wls = signal.split('+') if '+' in signal else [signal]
            target_wavelengths.extend(wls)
    
    target_wavelengths = sorted(list(set(target_wavelengths)))
    if not target_wavelengths:
        target_wavelengths = ['470']
    
    # Initialize storage
    all_dff_episodes = {wl: [] for wl in target_wavelengths}
    all_zscore_episodes = {wl: [] for wl in target_wavelengths}
    statistics_rows = []
    
    # Process each session
    for session_info in sessions:
        animal_data = session_info['animal_data']
        session_events = session_info['session']
        
        try:
            animal_id = animal_data.get('animal_single_channel_id', 'Unknown')
            
            # Find optogenetic stimulation start times
            stim_starts = [time for time, event_type in session_events if event_type == 'start']
            
            if not stim_starts:
                continue
            
            # Use first stimulation start as reference
            stim_start_time = stim_starts[0]
            
            preprocessed_data = animal_data.get('preprocessed_data')
            if preprocessed_data is None:
                continue
            
            channels = animal_data.get('channels', {})
            time_col = channels['time']
            fiber_timestamps = preprocessed_data[time_col].values
            
            dff_data = animal_data.get('dff_data', {})
            active_channels = animal_data.get('active_channels', [])
            
            # Extract episodes for each channel and wavelength
            for channel in active_channels:
                for wavelength in target_wavelengths:
                    dff_key = f"{channel}_{wavelength}"
                    if dff_key in dff_data:
                        data = dff_data[dff_key]
                        if isinstance(data, pd.Series):
                            data = data.values
                        
                        # Calculate baseline statistics
                        baseline_start_time = stim_start_time + params['baseline_start']
                        baseline_end_time = stim_start_time + params['baseline_end']
                        
                        baseline_start_idx = np.argmin(np.abs(fiber_timestamps - baseline_start_time))
                        baseline_end_idx = np.argmin(np.abs(fiber_timestamps - baseline_end_time))
                        
                        if baseline_end_idx > baseline_start_idx:
                            baseline_data = data[baseline_start_idx:baseline_end_idx]
                            mean_baseline = np.nanmean(baseline_data)
                            std_baseline = np.nanstd(baseline_data)
                            
                            if std_baseline == 0:
                                std_baseline = 1e-10
                            
                            # Extract plotting window
                            start_idx = np.argmin(np.abs(fiber_timestamps - (stim_start_time - params['pre_time'])))
                            end_idx = np.argmin(np.abs(fiber_timestamps - (stim_start_time + params['post_time'])))
                            
                            if end_idx > start_idx:
                                episode_data = data[start_idx:end_idx]
                                episode_times = fiber_timestamps[start_idx:end_idx] - stim_start_time
                                
                                if len(episode_times) > 1:
                                    # Store dFF data
                                    interp_dff = np.interp(time_array, episode_times, episode_data)
                                    all_dff_episodes[wavelength].append(interp_dff)
                                    
                                    # Calculate z-score
                                    zscore_episode = (episode_data - mean_baseline) / std_baseline
                                    interp_zscore = np.interp(time_array, episode_times, zscore_episode)
                                    all_zscore_episodes[wavelength].append(interp_zscore)
                                    
                                    # Collect statistics
                                    if params['export_stats']:
                                        pre_mask = (time_array >= -params['pre_time']) & (time_array <= 0)
                                        post_mask = (time_array >= 0) & (time_array <= params['post_time'])
                                        
                                        pre_data = interp_dff[pre_mask]
                                        post_data = interp_dff[post_mask]
                                        
                                        statistics_rows.append({
                                            'parameter': param_name,
                                            'animal_single_channel_id': animal_id,
                                            'analysis_type': 'optogenetic_induced',
                                            'channel': channel,
                                            'wavelength': wavelength,
                                            'trial': 1,
                                            'pre_min': np.min(pre_data) if len(pre_data) > 0 else np.nan,
                                            'pre_max': np.max(pre_data) if len(pre_data) > 0 else np.nan,
                                            'pre_mean': np.mean(pre_data) if len(pre_data) > 0 else np.nan,
                                            'pre_area': np.trapz(pre_data, time_array[pre_mask]) if len(pre_data) > 0 else np.nan,
                                            'post_min': np.min(post_data) if len(post_data) > 0 else np.nan,
                                            'post_max': np.max(post_data) if len(post_data) > 0 else np.nan,
                                            'post_mean': np.mean(post_data) if len(post_data) > 0 else np.nan,
                                            'post_area': np.trapz(post_data, time_array[post_mask]) if len(post_data) > 0 else np.nan,
                                            'signal_type': 'fiber_dff',
                                            'baseline_start': params['baseline_start'],
                                            'baseline_end': params['baseline_end'],
                                            'power_mw': session_info['power']
                                        })
        
        except Exception as e:
            log_message(f"Error analyzing session for {animal_id}: {str(e)}", "ERROR")
            continue
    
    # Calculate results
    result = {
        'time': time_array,
        'dff': all_dff_episodes,
        'zscore': all_zscore_episodes,
        'target_wavelengths': target_wavelengths
    }
    
    return result, statistics_rows if params['export_stats'] else None

def plot_optogenetic_results(results, params, analysis_mode="optogenetics"):
    """Plot multi-parameter optogenetic results"""
    # Extract wavelengths
    target_wavelengths = []
    for param_name, param_data in results.items():
        if analysis_mode == "optogenetics+drug":
            for timing_key, data in param_data.items():
                if 'target_wavelengths' in data:
                    target_wavelengths = data['target_wavelengths']
                    break
        else:
            data = param_data.get('optogenetics', {})
            if 'target_wavelengths' in data:
                target_wavelengths = data['target_wavelengths']
                break
        if target_wavelengths:
            break
    
    if not target_wavelengths:
        target_wavelengths = ['470']
    
    result_window = tk.Toplevel()
    wavelength_label = '+'.join(target_wavelengths)
    title_suffix = " + Drug" if analysis_mode == "optogenetics+drug" else ""
    result_window.title(f"Optogenetic-Induced Activity{title_suffix} - All Parameters ({wavelength_label}nm)")
    result_window.state('zoomed')
    result_window.configure(bg='#f8f8f8')
    
    num_wavelengths = len(target_wavelengths)
    num_cols = 2 * num_wavelengths
    
    fig = Figure(figsize=(4 * num_cols, 8), dpi=100)
    
    plot_idx = 1
    
    # Get time array from first available result
    time_array = None
    for param_data in results.values():
        if analysis_mode == "optogenetics+drug":
            for data in param_data.values():
                if 'time' in data:
                    time_array = data['time']
                    break
        else:
            data = param_data.get('optogenetics', {})
            if 'time' in data:
                time_array = data['time']
                break
        if time_array is not None:
            break
    
    # Row 1: Traces
    for wl_idx, wavelength in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        
        # dFF trace
        ax_dff = fig.add_subplot(2, num_cols, plot_idx)
        
        if analysis_mode == "optogenetics+drug":
            # Plot all drug timing categories with different styles
            color_idx = 0
            for param_name, param_data in results.items():
                for timing_name in sorted(param_data.keys()):
                    data = param_data[timing_name]
                    episodes = data['dff'].get(wavelength, [])
                    if episodes:
                        episodes_array = np.array(episodes)
                        mean_response = np.nanmean(episodes_array, axis=0)
                        sem_response = np.nanstd(episodes_array, axis=0) / np.sqrt(len(episodes))
                        
                        day_color = DAY_COLORS[color_idx % len(DAY_COLORS)]
                        
                        # Use different alpha for different timing
                        if timing_name == 'baseline':
                            alpha = 1/len(param_data)
                            linestyle = '-'
                        else:
                            alpha = 1/len(param_data) + (1/len(param_data) * (sorted(param_data.keys()).index(timing_name) + 1))
                            linestyle = '-'
                        
                        ax_dff.plot(time_array, mean_response, color=day_color, 
                                   linewidth=2, linestyle=linestyle, 
                                   label=f'{param_name} {timing_name}', alpha=alpha)
                        ax_dff.fill_between(time_array, mean_response - sem_response, 
                                           mean_response + sem_response, color=day_color, alpha=alpha*0.3)
                    
                    color_idx += 1
        else:
            # optogenetics-only mode
            for idx, (param_name, param_data) in enumerate(results.items()):
                data = param_data.get('optogenetics', {})
                episodes = data.get('dff', {}).get(wavelength, [])
                if episodes:
                    episodes_array = np.array(episodes)
                    mean_response = np.nanmean(episodes_array, axis=0)
                    sem_response = np.nanstd(episodes_array, axis=0) / np.sqrt(len(episodes))
                    
                    day_color = DAY_COLORS[idx % len(DAY_COLORS)]
                    ax_dff.plot(time_array, mean_response, color=day_color, linewidth=2, label=param_name, alpha=1)
                    ax_dff.fill_between(time_array, mean_response - sem_response, 
                                       mean_response + sem_response, color=day_color, alpha=0.5)
        
        ax_dff.axvline(x=0, color='#808080', linestyle='--', alpha=0.8, label='Opto Stim')
        ax_dff.set_xlim([time_array[0], time_array[-1]])
        ax_dff.set_xlabel('Time (s)')
        ax_dff.set_ylabel('ΔF/F')
        ax_dff.set_title(f'Fiber ΔF/F {wavelength}nm - All Parameters')
        ax_dff.legend(fontsize=6, ncol=2)
        ax_dff.grid(False)
        plot_idx += 1
        
        # Z-score trace (similar structure)
        ax_zscore = fig.add_subplot(2, num_cols, plot_idx)
        
        if analysis_mode == "optogenetics+drug":
            color_idx = 0
            for param_name, param_data in results.items():
                for timing_name in sorted(param_data.keys()):
                    data = param_data[timing_name]
                    episodes = data['zscore'].get(wavelength, [])
                    if episodes:
                        episodes_array = np.array(episodes)
                        mean_response = np.nanmean(episodes_array, axis=0)
                        sem_response = np.nanstd(episodes_array, axis=0) / np.sqrt(len(episodes))
                        
                        day_color = DAY_COLORS[color_idx % len(DAY_COLORS)]
                        
                        if timing_name == 'baseline':
                            alpha = 1/len(param_data)
                            linestyle = '-'
                        else:
                            alpha = 1/len(param_data) + (1/len(param_data) * (sorted(param_data.keys()).index(timing_name) + 1))
                            linestyle = '-'
                        
                        ax_zscore.plot(time_array, mean_response, color=day_color, 
                                      linewidth=2, linestyle=linestyle, 
                                      label=f'{param_name} {timing_name}', alpha=alpha)
                        ax_zscore.fill_between(time_array, mean_response - sem_response, 
                                              mean_response + sem_response, color=day_color, alpha=alpha*0.3)
                    
                    color_idx += 1
        else:
            for idx, (param_name, param_data) in enumerate(results.items()):
                data = param_data.get('optogenetics', {})
                episodes = data.get('zscore', {}).get(wavelength, [])
                if episodes:
                    episodes_array = np.array(episodes)
                    mean_response = np.nanmean(episodes_array, axis=0)
                    sem_response = np.nanstd(episodes_array, axis=0) / np.sqrt(len(episodes))
                    
                    day_color = DAY_COLORS[idx % len(DAY_COLORS)]
                    ax_zscore.plot(time_array, mean_response, color=day_color, linewidth=2, label=param_name, alpha=1)
                    ax_zscore.fill_between(time_array, mean_response - sem_response, 
                                          mean_response + sem_response, color=day_color, alpha=0.5)
        
        ax_zscore.axvline(x=0, color='#808080', linestyle='--', alpha=0.8, label='Opto Stim')
        ax_zscore.set_xlim([time_array[0], time_array[-1]])
        ax_zscore.set_xlabel('Time (s)')
        ax_zscore.set_ylabel('Z-score')
        ax_zscore.set_title(f'Fiber Z-score {wavelength}nm - All Parameters')
        ax_zscore.legend(fontsize=6, ncol=2)
        ax_zscore.grid(False)
        plot_idx += 1
    
    # Row 2: Heatmaps (combine all timing categories)
    for wl_idx, wavelength in enumerate(target_wavelengths):
        # dFF heatmap
        ax_dff_heat = fig.add_subplot(2, num_cols, plot_idx)
        all_episodes = []
        
        if analysis_mode == "optogenetics+drug":
            for param_data in results.values():
                for timing_key in sorted(param_data.keys()):
                    data = param_data[timing_key]
                    episodes = data['dff'].get(wavelength, [])
                    if episodes:
                        all_episodes.extend(episodes)
        else:
            for param_data in results.values():
                data = param_data.get('optogenetics', {})
                episodes = data.get('dff', {}).get(wavelength, [])
                if episodes:
                    all_episodes.extend(episodes)
        
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

            ax_dff_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            ax_dff_heat.set_xlabel('Time (s)')
            ax_dff_heat.set_ylabel('Trials')
            ax_dff_heat.set_title(f'Fiber ΔF/F Heatmap {wavelength}nm')
            plt.colorbar(im, ax=ax_dff_heat, label='ΔF/F', orientation='horizontal')
        plot_idx += 1
        
        # Z-score heatmap (similar structure)
        ax_zscore_heat = fig.add_subplot(2, num_cols, plot_idx)
        all_episodes = []
        
        if analysis_mode == "optogenetics+drug":
            for param_data in results.values():
                for timing_key in sorted(param_data.keys()):
                    data = param_data[timing_key]
                    episodes = data['zscore'].get(wavelength, [])
                    if episodes:
                        all_episodes.extend(episodes)
        else:
            for param_data in results.values():
                data = param_data.get('optogenetics', {})
                episodes = data.get('zscore', {}).get(wavelength, [])
                if episodes:
                    all_episodes.extend(episodes)
        
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
    
    log_message(f"Optogenetic results plotted for {len(results)} parameters ({analysis_mode} mode)")

def create_individual_param_windows(results, params, analysis_mode="optogenetics"):
    """Create individual windows for each parameter"""
    for param_name, param_data in results.items():
        create_single_param_window(param_name, param_data, params, analysis_mode)

def create_single_param_window(param_name, param_data, params, analysis_mode="optogenetics"):
    """Create window for a single parameter"""
    param_window = tk.Toplevel()
    
    # Extract wavelengths
    target_wavelengths = []
    if analysis_mode == "optogenetics+drug":
        for data in param_data.values():
            if 'target_wavelengths' in data:
                target_wavelengths = data['target_wavelengths']
                break
    else:
        data = param_data.get('optogenetics', {})
        if 'target_wavelengths' in data:
            target_wavelengths = data['target_wavelengths']
    
    if not target_wavelengths:
        target_wavelengths = ['470']
    
    wavelength_label = '+'.join(target_wavelengths)
    title_suffix = " + Drug" if analysis_mode == "optogenetics+drug" else ""
    
    param_window.title(f"Optogenetic-Induced Activity{title_suffix} - {param_name} ({wavelength_label}nm)")
    param_window.state("zoomed")
    param_window.configure(bg='#f8f8f8')
    
    num_wavelengths = len(target_wavelengths)
    num_cols = 2 * num_wavelengths
    fig = Figure(figsize=(4 * num_cols, 8), dpi=100)
    
    plot_idx = 1
    
    # Get time array
    time_array = None
    if analysis_mode == "optogenetics+drug":
        for data in param_data.values():
            if 'time' in data:
                time_array = data['time']
                break
    else:
        data = param_data.get('optogenetics', {})
        if 'time' in data:
            time_array = data['time']
    
    # Row 1: Traces
    for wl_idx, wavelength in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        
        # dFF trace
        ax_dff = fig.add_subplot(2, num_cols, plot_idx)
        
        if analysis_mode == "optogenetics+drug":
            # Get all drug timing categories
            drug_timings = sorted(param_data.keys())
            
            for timing_idx, timing_name in enumerate(drug_timings):
                data = param_data[timing_name]
                episodes = data['dff'].get(wavelength, [])
                
                if episodes:
                    episodes_array = np.array(episodes)
                    mean_response = np.nanmean(episodes_array, axis=0)
                    sem_response = np.nanstd(episodes_array, axis=0) / np.sqrt(episodes_array.shape[0])
                    
                    # Different styles for different timings
                    if timing_name == 'baseline':
                        alpha = 1/len(param_data)
                        linestyle = '-'
                    else:
                        alpha = 1/len(param_data) + (1/len(param_data) * (sorted(param_data.keys()).index(timing_name) + 1))
                        linestyle = '-'
                    
                    ax_dff.plot(time_array, mean_response, color=color, linewidth=2, 
                               linestyle=linestyle, label=timing_name, alpha=alpha)
                    ax_dff.fill_between(time_array, mean_response - sem_response,
                                      mean_response + sem_response, color=color, alpha=alpha*0.5)
            
            ax_dff.axvline(x=0, color='#808080', linestyle='--', alpha=0.8, label='Opto Stim')
            ax_dff.set_xlim(time_array[0], time_array[-1])
            ax_dff.set_xlabel('Time (s)')
            ax_dff.set_ylabel('ΔF/F')
            ax_dff.set_title(f'{param_name} - Fiber ΔF/F {wavelength}nm (Multi-Drug)')
            ax_dff.legend(fontsize=8)
            ax_dff.grid(False)
        else:
            # Original optogenetics-only mode
            data = param_data.get('optogenetics', {})
            episodes = data.get('dff', {}).get(wavelength, [])
            if episodes:
                episodes_array = np.array(episodes)
                mean_response = np.nanmean(episodes_array, axis=0)
                sem_response = np.nanstd(episodes_array, axis=0) / np.sqrt(episodes_array.shape[0])
                
                ax_dff.plot(time_array, mean_response, color=color, linewidth=2, label='Mean', alpha=1)
                ax_dff.fill_between(time_array, mean_response - sem_response,
                                  mean_response + sem_response, color=color, alpha=0.5)
                ax_dff.axvline(x=0, color='#808080', linestyle='--', alpha=0.8, label='Opto Stim')
                ax_dff.set_xlim(time_array[0], time_array[-1])
                ax_dff.set_xlabel('Time (s)')
                ax_dff.set_ylabel('ΔF/F')
                ax_dff.set_title(f'{param_name} - Fiber ΔF/F {wavelength}nm')
                ax_dff.legend()
                ax_dff.grid(False)
            else:
                ax_dff.text(0.5, 0.5, f'No dFF data for {wavelength}nm',
                          ha='center', va='center', transform=ax_dff.transAxes,
                          fontsize=12, color='#666666')
                ax_dff.set_title(f'{param_name} - Fiber ΔF/F {wavelength}nm')
                ax_dff.axis('off')
        plot_idx += 1
        
        # Z-score trace
        ax_zscore = fig.add_subplot(2, num_cols, plot_idx)
        
        if analysis_mode == "optogenetics+drug":
            drug_timings = sorted(param_data.keys())
            
            for timing_idx, timing_name in enumerate(drug_timings):
                data = param_data[timing_name]
                episodes = data['zscore'].get(wavelength, [])
                
                if episodes:
                    episodes_array = np.array(episodes)
                    mean_response = np.nanmean(episodes_array, axis=0)
                    sem_response = np.nanstd(episodes_array, axis=0) / np.sqrt(episodes_array.shape[0])
                    
                    if timing_name == 'baseline':
                        alpha = 1/len(param_data)
                        linestyle = '-'
                    else:
                        alpha = 1/len(param_data) + (1/len(param_data) * (sorted(param_data.keys()).index(timing_name) + 1))
                        linestyle = '-'
                    
                    ax_zscore.plot(time_array, mean_response, color=color, linewidth=2, 
                                  linestyle=linestyle, label=timing_name, alpha=alpha)
                    ax_zscore.fill_between(time_array, mean_response - sem_response,
                                         mean_response + sem_response, color=color, alpha=alpha*0.5)
            
            ax_zscore.axvline(x=0, color='#808080', linestyle='--', alpha=0.8, label='Opto Stim')
            ax_zscore.set_xlim(time_array[0], time_array[-1])
            ax_zscore.set_xlabel('Time (s)')
            ax_zscore.set_ylabel('Z-score')
            ax_zscore.set_title(f'{param_name} - Fiber Z-score {wavelength}nm (Multi-Drug)')
            ax_zscore.legend(fontsize=8)
            ax_zscore.grid(False)
        else:
            data = param_data.get('optogenetics', {})
            episodes = data.get('zscore', {}).get(wavelength, [])
            if episodes:
                episodes_array = np.array(episodes)
                mean_response = np.nanmean(episodes_array, axis=0)
                sem_response = np.nanstd(episodes_array, axis=0) / np.sqrt(episodes_array.shape[0])
                
                ax_zscore.plot(time_array, mean_response, color=color, linewidth=2, label='Mean', alpha=1)
                ax_zscore.fill_between(time_array, mean_response - sem_response,
                                     mean_response + sem_response, color=color, alpha=0.5)
                ax_zscore.axvline(x=0, color='#808080', linestyle='--', alpha=0.8, label='Opto Stim')
                ax_zscore.set_xlim(time_array[0], time_array[-1])
                ax_zscore.set_xlabel('Time (s)')
                ax_zscore.set_ylabel('Z-score')
                ax_zscore.set_title(f'{param_name} - Fiber Z-score {wavelength}nm')
                ax_zscore.legend()
                ax_zscore.grid(False)
            else:
                ax_zscore.text(0.5, 0.5, f'No z-score data for {wavelength}nm',
                             ha='center', va='center', transform=ax_zscore.transAxes,
                             fontsize=12, color='#666666')
                ax_zscore.set_title(f'{param_name} - Fiber Z-score {wavelength}nm')
                ax_zscore.axis('off')
        plot_idx += 1
    
    # Row 2: Heatmaps
    for wl_idx, wavelength in enumerate(target_wavelengths):
        # dFF heatmap
        ax_dff_heat = fig.add_subplot(2, num_cols, plot_idx)
        
        if analysis_mode == "optogenetics+drug":
            # Combine all drug timing episodes
            all_episodes = []
            category_boundaries = []
            drug_timings = sorted(param_data.keys())
            
            for timing_name in drug_timings:
                data = param_data[timing_name]
                episodes = data['dff'].get(wavelength, [])
                if episodes:
                    all_episodes.extend(episodes)
                    if all_episodes:
                        category_boundaries.append(len(all_episodes))
        else:
            data = param_data.get('optogenetics', {})
            all_episodes = data.get('dff', {}).get(wavelength, [])
            category_boundaries = []
        
        if all_episodes:
            episodes_array = np.array(all_episodes)
            if len(episodes_array) == 1:
                episodes_array = np.vstack([episodes_array[0], episodes_array[0]])
                im = ax_dff_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                    extent=[time_array[0], time_array[-1], 0, 1],
                                    cmap='coolwarm', origin='lower')
                ax_dff_heat.set_yticks(np.arange(0, 2, 1))
                ax_dff_heat.set_ylabel('Trials')
            else:
                im = ax_dff_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                    extent=[time_array[0], time_array[-1], 0, len(all_episodes)],
                                    cmap='coolwarm', origin='lower')
                if len(episodes_array) <= 10:
                    ax_dff_heat.set_yticks(np.arange(0, len(all_episodes)+1, 1))
                ax_dff_heat.set_ylabel('Trials')
            
            # Draw category boundaries for multi-drug
            if analysis_mode == "optogenetics+drug" and category_boundaries:
                for boundary in category_boundaries[:-1]:
                    ax_dff_heat.axhline(y=boundary, color="#000000", linestyle='--', alpha=0.5, linewidth=1)
            
            ax_dff_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            ax_dff_heat.set_xlabel('Time (s)')
            ax_dff_heat.set_title(f'{param_name} - Fiber ΔF/F Heatmap {wavelength}nm')
            
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
            ax_dff_heat.set_title(f'{param_name} - Fiber ΔF/F Heatmap {wavelength}nm')
            ax_dff_heat.axis('off')
        plot_idx += 1
        
        # Z-score heatmap
        ax_zscore_heat = fig.add_subplot(2, num_cols, plot_idx)
        
        if analysis_mode == "optogenetics+drug":
            all_episodes = []
            category_boundaries = []
            drug_timings = sorted(param_data.keys())
            
            for timing_name in drug_timings:
                data = param_data[timing_name]
                episodes = data['zscore'].get(wavelength, [])
                if episodes:
                    all_episodes.extend(episodes)
                    if all_episodes:
                        category_boundaries.append(len(all_episodes))
        else:
            data = param_data.get('optogenetics', {})
            all_episodes = data.get('zscore', {}).get(wavelength, [])
            category_boundaries = []
        
        if all_episodes:
            episodes_array = np.array(all_episodes)
            
            if len(episodes_array) == 1:
                episodes_array = np.vstack([episodes_array[0], episodes_array[0]])
                im = ax_zscore_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                        extent=[time_array[0], time_array[-1], 0, 1],
                                        cmap='coolwarm', origin='lower')
                ax_zscore_heat.set_yticks(np.arange(0, 2, 1))
                ax_zscore_heat.set_ylabel('Trials')
            else:
                im = ax_zscore_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                        extent=[time_array[0], time_array[-1], 0, len(all_episodes)],
                                        cmap='coolwarm', origin='lower')
                if len(all_episodes) <= 10:
                    ax_zscore_heat.set_yticks(np.arange(0, len(all_episodes)+1, 1))
                ax_zscore_heat.set_ylabel('Trials')
            
            # Draw category boundaries
            if analysis_mode == "optogenetics+drug" and category_boundaries:
                for boundary in category_boundaries[:-1]:
                    ax_zscore_heat.axhline(y=boundary, color="#000000", linestyle='--', alpha=0.5, linewidth=1)
            
            ax_zscore_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            ax_zscore_heat.set_xlabel('Time (s)')
            ax_zscore_heat.set_title(f'{param_name} - Fiber Z-score Heatmap {wavelength}nm')
            
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
            ax_zscore_heat.set_title(f'{param_name} - Fiber Z-score Heatmap {wavelength}nm')
            ax_zscore_heat.axis('off')
        plot_idx += 1
    
    fig.tight_layout()
    
    canvas_frame = tk.Frame(param_window, bg='#f8f8f8')
    canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    canvas = FigureCanvasTkAgg(fig, canvas_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    toolbar_frame = tk.Frame(canvas_frame, bg="#f5f5f5")
    toolbar_frame.pack(fill=tk.X, padx=2, pady=(0,2))
    toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
    
    log_message(f"Individual parameter plot created for {param_name} with {len(target_wavelengths)} wavelength(s) ({analysis_mode} mode)")