"""
Optogenetic-induced activity analysis with table configuration
Supports multi-animal optogenetic event analysis
"""
import os
import json
import tkinter as tk
import numpy as np

from infrastructure.logger import log_message
from analysis_multimodal.Multimodal_analysis import (
    export_results, identify_optogenetic_events, calculate_optogenetic_pulse_info,
    identify_drug_sessions, group_optogenetic_sessions, create_control_panel,
    create_parameter_panel, get_parameters_from_ui, calculate_running_episodes,
    create_table_window, initialize_table, FIBER_COLORS, ROW_COLORS,
    make_scrollable_window, make_figure, draw_heatmap, embed_figure
)

NUM_COLS = 3      # For optogenetic analysis: Running | dFF | Z-score

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
    all_drug_events = {}
    
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
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'opto_power_config.json')
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
    param_config = {
        'show_plot_window': True,
        'start_time': "-30",
        'end_time': "60",
        'show_baseline_window': True,
        'baseline_start': "-30",
        'baseline_end': "0"
    }
    param_frame = create_parameter_panel(container, param_config)
    param_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 5))
    
    # Right panel: Table
    table_frame = tk.Frame(container, bg="#f8f8f8")
    table_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
    
    btn_frame = tk.Frame(main_window, bg="#f8f8f8")
    btn_frame.pack(fill=tk.X, padx=10, pady=10)

    # Initialize table manager
    table_manager = TableManager(root, table_frame, btn_frame, multi_animal_data, 
                                    all_optogenetic_events, opto_config,
                                    all_drug_events, analysis_mode)

    def run_analysis():
        params = get_parameters_from_ui(param_frame, require_plot_window=True, require_baseline_window=True)
        if params:
            table_manager.run_analysis(params)

    tk.Button(btn_frame, text="Run Analysis", command=run_analysis,
             bg="#ffffff", fg="#000000", font=("Microsoft YaHei", 9, "bold"),
             relief=tk.FLAT, padx=10, pady=5).pack(side=tk.LEFT, padx=5)

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
                    if param_id.startswith(f"{animal_id}+Session{session_idx+1}+{freq:.1f}Hz+{pulse_width*1000:.0f}ms+{duration:.1f}s"):
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
                    parts = session_id.split('+')
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
                                    expected_id = f"{animal_id}+Session{session_idx+1}+{freq:.1f}Hz+{pulse_width*1000:.0f}ms+{duration:.1f}s"
                                    
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
        Uses drug onset and offset times from configuration
        Returns: 'baseline', '{drug_nameA}', '{drug_nameB} after {drug_nameA}', etc.
        """
        if animal_id not in self.all_drug_events:
            return 'baseline'
        
        drug_sessions = self.all_drug_events[animal_id]
        
        if not drug_sessions:
            return 'baseline'
        
        # Load drug config
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'drug_name_config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                drug_config = json.load(f)
        else:
            drug_config = {}
        
        # Get drug information with timing
        drug_info = []
        for idx, session_info in enumerate(drug_sessions):
            session_id = f"{animal_id}_Session{idx+1}"
            
            # Get config for this session
            if session_id in drug_config:
                config = drug_config[session_id]
                if isinstance(config, dict):
                    drug_name = config.get('name', f"Drug{idx+1}")
                    onset_time = config.get('onset_time', session_info['time'])
                    offset_time = config.get('offset_time')
                else:
                    # Old format compatibility
                    drug_name = config
                    onset_time = session_info['time']
                    offset_time = None
            else:
                drug_name = f"Drug{idx+1}"
                onset_time = session_info['time']
                offset_time = None
            
            # Calculate default offset if not specified
            if offset_time is None:
                if idx < len(drug_sessions) - 1:
                    # Next drug's onset time
                    next_session_id = f"{animal_id}_Session{idx+2}"
                    if next_session_id in drug_config and isinstance(drug_config[next_session_id], dict):
                        offset_time = drug_config[next_session_id].get('onset_time', drug_sessions[idx+1]['time'])
                    else:
                        offset_time = drug_sessions[idx+1]['time']
                else:
                    # Use running end time or very large number
                    ast2_data = animal_data.get('ast2_data_adjusted')
                    if ast2_data and 'data' in ast2_data and 'timestamps' in ast2_data['data']:
                        offset_time = ast2_data['data']['timestamps'][-1]
                    else:
                        offset_time = onset_time + 10000  # Large number
            
            drug_info.append({
                'name': drug_name, 
                'onset': onset_time,
                'offset': offset_time,
                'idx': idx
            })
        
        # Sort by onset time
        drug_info.sort(key=lambda x: x['onset'])
        
        # Get optogenetic session time window
        session_start = min([time for time, _ in session])
        session_end = max([time for time, _ in session])
        session_mid = (session_start + session_end) / 2
        
        # Classify based on session midpoint relative to drug onset/offset times
        if session_mid < drug_info[0]['onset']:
            return 'baseline'
        
        # Find which drug period this session belongs to
        for i in range(len(drug_info) - 1, -1, -1):
            if session_mid >= drug_info[i]['onset']:
                # Check if still within this drug's effect period
                if session_mid < drug_info[i]['offset']:
                    if i == 0:
                        # Within first drug period
                        return drug_info[0]['name']
                    else:
                        # Within later drug period
                        previous_drugs = ' + '.join([d['name'] for d in drug_info[:i]])
                        return f"{drug_info[i]['name']} after {previous_drugs}"
                # If past offset, continue checking previous drugs
        
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
        
        log_message(f"Found drug timing categories: {list(all_drug_timings)}")
        
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
        export_results(results, all_statistics, f"optogenetic_induced_{analysis_mode}")
    
    if results:
        plot_optogenetic_results(results, params, analysis_mode)
        create_individual_param_windows(results, params, analysis_mode)
        log_message("Analysis completed successfully")
    else:
        log_message("No valid results", "ERROR")

def collect_optogenetic_statistics(param_name, animal_id, result,
                                   time_array, params, target_wavelengths, 
                                   active_channels, power_mw):
    """
    Collect statistics for optogenetic-induced fiber analysis
    
    Args:
        param_name: Parameter/condition name (e.g., "5Hz_10ms" or "baseline")
        animal_id: Animal identifier
        result: Result dictionary from calculate_running_episodes
        time_array: Time array for the analysis
        params: Analysis parameters dict with 'plot_pre', 'plot_post', etc.
        target_wavelengths: List of wavelengths analyzed
        active_channels: List of active channels
        power_mw: Optogenetic stimulation power in mW
    
    Returns:
        List of dictionaries containing statistics for each trial/channel/wavelength
    """
    rows = []
    pre_mask = (time_array >= -params['plot_pre']) & (time_array <= 0)
    post_mask = (time_array >= 0) & (time_array <= params['plot_post'])

    # Running statistics
    for trial_idx, episode_data in enumerate(result['running']):
        pre_data = episode_data[pre_mask]
        post_data = episode_data[post_mask]

        rows.append({
            'parameter': param_name,
            'animal_single_channel_id': animal_id,
            'analysis_type': 'optogenetic_induced',
            'channel': 'running_speed',
            'wavelength': 'N/A',
            'trial': trial_idx + 1,
            'pre_min': np.min(pre_data) if len(pre_data) > 0 else np.nan,
            'pre_max': np.max(pre_data) if len(pre_data) > 0 else np.nan,
            'pre_mean': np.mean(pre_data) if len(pre_data) > 0 else np.nan,
            'pre_area': np.trapezoid(pre_data, time_array[pre_mask]) if len(pre_data) > 0 else np.nan,
            'post_min': np.min(post_data) if len(post_data) > 0 else np.nan,
            'post_max': np.max(post_data) if len(post_data) > 0 else np.nan,
            'post_mean': np.mean(post_data) if len(post_data) > 0 else np.nan,
            'post_area': np.trapezoid(post_data, time_array[post_mask]) if len(post_data) > 0 else np.nan,
            'signal_type': 'running_speed',
            'baseline_start': params['baseline_start'],
            'baseline_end': params['baseline_end'],
            'power_mw': power_mw
        })
    
    # Fiber statistics
    for channel in active_channels:
        for wl in target_wavelengths:
            # dFF statistics
            if wl in result['dff']:
                for trial_idx, episode_data in enumerate(result['dff'][wl]):
                    pre_data = episode_data[pre_mask]
                    post_data = episode_data[post_mask]
                    
                    rows.append({
                        'parameter': param_name,
                        'animal_single_channel_id': animal_id,
                        'analysis_type': 'optogenetic_induced',
                        'channel': channel,
                        'wavelength': wl,
                        'trial': trial_idx + 1,
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
                        'baseline_end': params['baseline_end'],
                        'power_mw': power_mw
                    })
            
            # Z-score statistics
            if wl in result['zscore']:
                for trial_idx, episode_data in enumerate(result['zscore'][wl]):
                    pre_data = episode_data[pre_mask]
                    post_data = episode_data[post_mask]
                    
                    rows.append({
                        'parameter': param_name,
                        'animal_single_channel_id': animal_id,
                        'analysis_type': 'optogenetic_induced',
                        'channel': channel,
                        'wavelength': wl,
                        'trial': trial_idx + 1,
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
                        'baseline_end': params['baseline_end'],
                        'power_mw': power_mw
                    })
    
    return rows

def analyze_param_optogenetic(param_name, sessions, params):
    """Analyze optogenetic effects for one parameter (multiple sessions combined)"""
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
    all_running_episodes = []
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

            ast2_data = animal_data.get('ast2_data_adjusted')
            if ast2_data is None or 'data' not in ast2_data:
                continue

            running_timestamps = ast2_data['data'].get('timestamps')
            running_speed_raw = ast2_data['data'].get('speed')
            if running_timestamps is None or running_speed_raw is None:
                continue

            processed_data = animal_data.get('running_processed_data')
            if processed_data and processed_data.get('filtered_speed') is not None:
                running_speed = processed_data['filtered_speed']
            else:
                running_speed = running_speed_raw
            
            preprocessed_data = animal_data.get('preprocessed_data')
            if preprocessed_data is None or preprocessed_data.empty:
                continue
            
            channels = animal_data.get('channels', {})
            time_col = channels['time']
            fiber_timestamps = preprocessed_data[time_col].values
            
            dff_data = animal_data.get('dff_data', {})
            active_channels = animal_data.get('active_channels', [])
            
            # Use first stimulation start as reference event for this session
            events = [stim_starts[0]]

            result = calculate_running_episodes(
                events, running_timestamps, running_speed,
                fiber_timestamps, dff_data,
                active_channels, target_wavelengths,
                params['plot_pre'], params['plot_post'],
                params['baseline_start'], params['baseline_end']
            )
            
            # Collect episodes
            if len(result['running']) > 0:
                all_running_episodes.extend(result['running'])

            for wl in target_wavelengths:
                if wl in result['dff']:
                    all_dff_episodes[wl].extend(result['dff'][wl])
                if wl in result['zscore']:
                    all_zscore_episodes[wl].extend(result['zscore'][wl])
            
            # Collect statistics if requested
            if params['export_stats']:
                statistics_rows.extend(collect_optogenetic_statistics(
                    param_name, animal_id, result,
                    result['time'], params,
                    target_wavelengths, active_channels,
                    session_info['power']
                ))
        
        except Exception as e:
            log_message(f"Error analyzing session for {animal_id}: {str(e)}", "ERROR")
            continue
    
    # Check if we have any data
    has_running = len(all_running_episodes) > 0
    has_dff = any(len(all_dff_episodes[wl]) > 0 for wl in target_wavelengths)
    has_zscore = any(len(all_zscore_episodes[wl]) > 0 for wl in target_wavelengths)
    has_data = has_running or has_dff or has_zscore
    
    if not has_data:
        return None, None
    
    # Calculate results
    time_array = np.linspace(-params['plot_pre'], params['plot_post'],
                            int((params['plot_pre'] + params['plot_post']) * 10))
    
    result = {
        'time': time_array,
        'running': all_running_episodes,
        'dff': all_dff_episodes,
        'zscore': all_zscore_episodes,
        'target_wavelengths': target_wavelengths
    }
    
    return result, statistics_rows if params['export_stats'] else None

def plot_optogenetic_results(results, params, analysis_mode="optogenetics"):
    """Plot optogenetic running and fiber results — all parameters overlaid."""
    target_wavelengths = []
    time_array = None
    for param_data in results.values():
        if analysis_mode == "optogenetics+drug":
            for data in param_data.values():
                if "target_wavelengths" in data and not target_wavelengths:
                    target_wavelengths = data["target_wavelengths"]
                if "time" in data and time_array is None:
                    time_array = data["time"]
        else:
            data = param_data.get("optogenetics", {})
            if "target_wavelengths" in data and not target_wavelengths:
                target_wavelengths = data["target_wavelengths"]
            if "time" in data and time_array is None:
                time_array = data["time"]
        if target_wavelengths and time_array is not None:
            break

    if not target_wavelengths:
        target_wavelengths = ["470"]

    wavelength_label = "+".join(target_wavelengths)
    title_suffix = " + Drug" if analysis_mode == "optogenetics+drug" else ""

    win, _, inner = make_scrollable_window(
        f"Optogenetic-Induced Activity{title_suffix} "
        f"- All Parameters ({wavelength_label}nm)"
    )

    for wl_idx, wavelength in enumerate(target_wavelengths):
        fig = make_figure(NUM_COLS)
        fig.suptitle(
            f"Wavelength {wavelength} nm — All Parameters{title_suffix}",
            fontsize=12, fontweight="bold")

        # Row 1: Traces
        ax_run = fig.add_subplot(2, NUM_COLS, 1)
        if analysis_mode == "optogenetics+drug":
            for param_idx, (param_name, param_data) in enumerate(results.items()):
                row_color = ROW_COLORS[param_idx % len(ROW_COLORS)]
                timing_names = list(param_data.keys())
                n = max(len(timing_names), 1)
                for timing_name in timing_names:
                    data = param_data[timing_name]
                    episodes = data.get("running", [])
                    if len(episodes) > 0:
                        arr = np.array(episodes)
                        if arr.ndim == 1:
                            arr = arr[np.newaxis, :]
                        mean = np.nanmean(arr, axis=0)
                        sem = np.nanstd(arr, axis=0) / np.sqrt(arr.shape[0])
                        timing_idx = timing_names.index(timing_name)
                        alpha = (1 / n) if timing_name == "baseline" else (1 / n) + (1 / n * timing_idx)
                        ax_run.plot(time_array, mean, color=row_color, linewidth=2,
                                    label=f"{param_name} {timing_name}", alpha=alpha)
                        ax_run.fill_between(time_array, mean - sem, mean + sem,
                                            color=row_color, alpha=alpha * 0.3)
        else:
            for param_idx, (param_name, param_data) in enumerate(results.items()):
                data = param_data.get("optogenetics", {})
                episodes = data.get("running", [])
                if len(episodes) > 0:
                    arr = np.array(episodes)
                    if arr.ndim == 1:
                        arr = arr[np.newaxis, :]
                    mean = np.nanmean(arr, axis=0)
                    sem = np.nanstd(arr, axis=0) / np.sqrt(arr.shape[0])
                    row_color = ROW_COLORS[param_idx % len(ROW_COLORS)]
                    ax_run.plot(time_array, mean, color=row_color, linewidth=2,
                                label=param_name)
                    ax_run.fill_between(time_array, mean - sem, mean + sem,
                                        color=row_color, alpha=0.5)
        ax_run.axvline(x=0, color="#808080", linestyle="--", alpha=0.8, label="Opto Stim")
        ax_run.set_xlim(time_array[0], time_array[-1])
        ax_run.set_xlabel("Time (s)")
        ax_run.set_ylabel("Speed (cm/s)")
        ax_run.set_title("Running Speed - All Parameters")
        ax_run.legend(fontsize=6, ncol=2)
        ax_run.grid(False)

        ax_dff = fig.add_subplot(2, NUM_COLS, 2)
        if analysis_mode == "optogenetics+drug":
            for param_idx, (param_name, param_data) in enumerate(results.items()):
                row_color = ROW_COLORS[param_idx % len(ROW_COLORS)]
                timing_names = list(param_data.keys())
                n = max(len(timing_names), 1)
                for timing_name in timing_names:
                    data = param_data[timing_name]
                    episodes = data["dff"].get(wavelength, [])
                    if len(episodes) > 0:
                        arr = np.array(episodes)
                        if arr.ndim == 1:
                            arr = arr[np.newaxis, :]
                        mean = np.nanmean(arr, axis=0)
                        sem = np.nanstd(arr, axis=0) / np.sqrt(arr.shape[0])
                        timing_idx = timing_names.index(timing_name)
                        alpha = (1 / n) if timing_name == "baseline" else (1 / n) + (1 / n * timing_idx)
                        ax_dff.plot(time_array, mean, color=row_color, linewidth=2,
                                    label=f"{param_name} {timing_name}", alpha=alpha)
                        ax_dff.fill_between(time_array, mean - sem, mean + sem,
                                            color=row_color, alpha=alpha * 0.3)
        else:
            for param_idx, (param_name, param_data) in enumerate(results.items()):
                data = param_data.get("optogenetics", {})
                episodes = data.get("dff", {}).get(wavelength, [])
                if len(episodes) > 0:
                    arr = np.array(episodes)
                    if arr.ndim == 1:
                        arr = arr[np.newaxis, :]
                    mean = np.nanmean(arr, axis=0)
                    sem = np.nanstd(arr, axis=0) / np.sqrt(arr.shape[0])
                    row_color = ROW_COLORS[param_idx % len(ROW_COLORS)]
                    ax_dff.plot(time_array, mean, color=row_color, linewidth=2,
                                label=param_name)
                    ax_dff.fill_between(time_array, mean - sem, mean + sem,
                                        color=row_color, alpha=0.5)
        ax_dff.axvline(x=0, color="#808080", linestyle="--", alpha=0.8, label="Opto Stim")
        ax_dff.set_xlim(time_array[0], time_array[-1])
        ax_dff.set_xlabel("Time (s)")
        ax_dff.set_ylabel("ΔF/F")
        ax_dff.set_title(f"Fiber ΔF/F {wavelength}nm - All Parameters")
        ax_dff.legend(fontsize=6, ncol=2)
        ax_dff.grid(False)

        ax_zs = fig.add_subplot(2, NUM_COLS, 3)
        if analysis_mode == "optogenetics+drug":
            for param_idx, (param_name, param_data) in enumerate(results.items()):
                row_color = ROW_COLORS[param_idx % len(ROW_COLORS)]
                timing_names = list(param_data.keys())
                n = max(len(timing_names), 1)
                for timing_name in timing_names:
                    data = param_data[timing_name]
                    episodes = data["zscore"].get(wavelength, [])
                    if len(episodes) > 0:
                        arr = np.array(episodes)
                        if arr.ndim == 1:
                            arr = arr[np.newaxis, :]
                        mean = np.nanmean(arr, axis=0)
                        sem = np.nanstd(arr, axis=0) / np.sqrt(arr.shape[0])
                        timing_idx = timing_names.index(timing_name)
                        alpha = (1 / n) if timing_name == "baseline" else (1 / n) + (1 / n * timing_idx)
                        ax_zs.plot(time_array, mean, color=row_color, linewidth=2,
                                   label=f"{param_name} {timing_name}", alpha=alpha)
                        ax_zs.fill_between(time_array, mean - sem, mean + sem,
                                           color=row_color, alpha=alpha * 0.3)
        else:
            for param_idx, (param_name, param_data) in enumerate(results.items()):
                data = param_data.get("optogenetics", {})
                episodes = data.get("zscore", {}).get(wavelength, [])
                if len(episodes) > 0:
                    arr = np.array(episodes)
                    if arr.ndim == 1:
                        arr = arr[np.newaxis, :]
                    mean = np.nanmean(arr, axis=0)
                    sem = np.nanstd(arr, axis=0) / np.sqrt(arr.shape[0])
                    row_color = ROW_COLORS[param_idx % len(ROW_COLORS)]
                    ax_zs.plot(time_array, mean, color=row_color, linewidth=2,
                               label=param_name)
                    ax_zs.fill_between(time_array, mean - sem, mean + sem,
                                       color=row_color, alpha=0.5)
        ax_zs.axvline(x=0, color="#808080", linestyle="--", alpha=0.8, label="Opto Stim")
        ax_zs.set_xlim(time_array[0], time_array[-1])
        ax_zs.set_xlabel("Time (s)")
        ax_zs.set_ylabel("Z-score")
        ax_zs.set_title(f"Fiber Z-score {wavelength}nm - All Parameters")
        ax_zs.legend(fontsize=6, ncol=2)
        ax_zs.grid(False)

        # Row 2: Heatmaps
        ax_run_heat = fig.add_subplot(2, NUM_COLS, 4)
        all_run = []
        if analysis_mode == "optogenetics+drug":
            for param_data in results.values():
                for data in param_data.values():
                    ep = data.get("running", [])
                    if len(ep) > 0:
                        all_run.extend(ep)
        else:
            for param_data in results.values():
                ep = param_data.get("optogenetics", {}).get("running", [])
                if len(ep) > 0:
                    all_run.extend(ep)
        if all_run:
            draw_heatmap(ax_run_heat, np.array(all_run),
                         time_array, "viridis", "Speed (cm/s)")
            ax_run_heat.set_title("Running Speed Heatmap")
        else:
            ax_run_heat.text(0.5, 0.5, "No running data",
                             ha="center", va="center",
                             transform=ax_run_heat.transAxes,
                             fontsize=12, color="#666666")
            ax_run_heat.set_title("Running Speed Heatmap")
            ax_run_heat.axis("off")

        ax_dff_heat = fig.add_subplot(2, NUM_COLS, 5)
        all_dff = []
        if analysis_mode == "optogenetics+drug":
            for param_data in results.values():
                for data in param_data.values():
                    ep = data["dff"].get(wavelength, [])
                    if len(ep) > 0:
                        all_dff.extend(ep)
        else:
            for param_data in results.values():
                ep = param_data.get("optogenetics", {}).get(
                    "dff", {}).get(wavelength, [])
                if len(ep) > 0:
                    all_dff.extend(ep)
        if all_dff:
            draw_heatmap(ax_dff_heat, np.array(all_dff),
                         time_array, "coolwarm", "ΔF/F")
            ax_dff_heat.set_title(f"Fiber ΔF/F Heatmap {wavelength}nm")
        else:
            ax_dff_heat.text(0.5, 0.5, f"No dFF data for {wavelength}nm",
                             ha="center", va="center",
                             transform=ax_dff_heat.transAxes,
                             fontsize=12, color="#666666")
            ax_dff_heat.set_title(f"Fiber ΔF/F Heatmap {wavelength}nm")
            ax_dff_heat.axis("off")

        ax_zs_heat = fig.add_subplot(2, NUM_COLS, 6)
        all_zs = []
        if analysis_mode == "optogenetics+drug":
            for param_data in results.values():
                for data in param_data.values():
                    ep = data["zscore"].get(wavelength, [])
                    if len(ep) > 0:
                        all_zs.extend(ep)
        else:
            for param_data in results.values():
                ep = param_data.get("optogenetics", {}).get(
                    "zscore", {}).get(wavelength, [])
                if len(ep) > 0:
                    all_zs.extend(ep)
        if all_zs:
            draw_heatmap(ax_zs_heat, np.array(all_zs),
                         time_array, "coolwarm", "Z-score")
            ax_zs_heat.set_title(f"Fiber Z-score Heatmap {wavelength}nm")
        else:
            ax_zs_heat.text(0.5, 0.5, f"No z-score data for {wavelength}nm",
                            ha="center", va="center",
                            transform=ax_zs_heat.transAxes,
                            fontsize=12, color="#666666")
            ax_zs_heat.set_title(f"Fiber Z-score Heatmap {wavelength}nm")
            ax_zs_heat.axis("off")

        fig.tight_layout(rect=[0, 0, 1, 0.96])
        embed_figure(inner, fig, row_in_frame=wl_idx)

    log_message(
        f"Optogenetic results plotted for {len(results)} parameters "
        f"({analysis_mode} mode)"
    )

def create_single_param_window(param_name, param_data, params,
                               analysis_mode="optogenetics"):
    """Create window for a single parameter with running and fiber plots."""
    target_wavelengths = []
    time_array = None
    if analysis_mode == "optogenetics+drug":
        for data in param_data.values():
            if "target_wavelengths" in data and not target_wavelengths:
                target_wavelengths = data["target_wavelengths"]
            if "time" in data and time_array is None:
                time_array = data["time"]
    else:
        data = param_data.get("optogenetics", {})
        if "target_wavelengths" in data:
            target_wavelengths = data["target_wavelengths"]
        if "time" in data:
            time_array = data["time"]
 
    if not target_wavelengths:
        target_wavelengths = ["470"]
 
    wavelength_label = "+".join(target_wavelengths)
    title_suffix = " + Drug" if analysis_mode == "optogenetics+drug" else ""
 
    win, _, inner = make_scrollable_window(
        f"Optogenetic-Induced Activity{title_suffix} "
        f"- {param_name} ({wavelength_label}nm)"
    )
 
    for wl_idx, wavelength in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        fig = make_figure(NUM_COLS)
        fig.suptitle(
            f"{param_name} — Wavelength {wavelength} nm{title_suffix}",
            fontsize=12, fontweight="bold")

        # Row 1: Traces
        ax_run = fig.add_subplot(2, NUM_COLS, 1)
        if analysis_mode == "optogenetics+drug":
            drug_timings = list(param_data.keys())
            n = max(len(drug_timings), 1)
            for timing_name in drug_timings:
                data = param_data[timing_name]
                episodes = data.get("running", [])
                if len(episodes) > 0:
                    arr = np.array(episodes)
                    if arr.ndim == 1:
                        arr = arr[np.newaxis, :]
                    mean = np.nanmean(arr, axis=0)
                    sem = np.nanstd(arr, axis=0) / np.sqrt(arr.shape[0])
                    timing_idx = drug_timings.index(timing_name)
                    alpha = (1 / n) if timing_name == "baseline" else (1 / n) + (1 / n * timing_idx)
                    ax_run.plot(time_array, mean, color="#000000", linewidth=2,
                                label=timing_name, alpha=alpha)
                    ax_run.fill_between(time_array, mean - sem, mean + sem,
                                        color="#000000", alpha=alpha * 0.5)
            ax_run.axvline(x=0, color="#808080", linestyle="--",
                           alpha=0.8, label="Opto Stim")
            ax_run.set_title(f"{param_name} - Running Speed (Multi-Drug)")
            ax_run.legend(fontsize=8)
        else:
            data = param_data.get("optogenetics", {})
            episodes = data.get("running", [])
            if len(episodes) > 0:
                arr = np.array(episodes)
                if arr.ndim == 1:
                    arr = arr[np.newaxis, :]
                mean = np.nanmean(arr, axis=0)
                sem = np.nanstd(arr, axis=0) / np.sqrt(arr.shape[0])
                ax_run.plot(time_array, mean, color="#000000",
                            linewidth=2, label="Mean")
                ax_run.fill_between(time_array, mean - sem, mean + sem,
                                    color="#000000", alpha=0.5)
                ax_run.axvline(x=0, color="#808080", linestyle="--",
                               alpha=0.8, label="Opto Stim")
                ax_run.legend()
            else:
                ax_run.text(0.5, 0.5, "No running data",
                            ha="center", va="center",
                            transform=ax_run.transAxes,
                            fontsize=12, color="#666666")
                ax_run.axis("off")
            ax_run.set_title(f"{param_name} - Running Speed")
        ax_run.set_xlim(time_array[0], time_array[-1])
        ax_run.set_xlabel("Time (s)")
        ax_run.set_ylabel("Speed (cm/s)")
        ax_run.grid(False)

        ax_dff = fig.add_subplot(2, NUM_COLS, 2)
        if analysis_mode == "optogenetics+drug":
            drug_timings = list(param_data.keys())
            n = max(len(drug_timings), 1)
            for timing_name in drug_timings:
                data = param_data[timing_name]
                episodes = data["dff"].get(wavelength, [])
                if len(episodes) > 0:
                    arr = np.array(episodes)
                    if arr.ndim == 1:
                        arr = arr[np.newaxis, :]
                    mean = np.nanmean(arr, axis=0)
                    sem  = np.nanstd(arr, axis=0) / np.sqrt(arr.shape[0])
                    timing_idx = drug_timings.index(timing_name)
                    alpha = (1 / n) if timing_name == "baseline" else (1 / n) + (1 / n * timing_idx)
                    ax_dff.plot(time_array, mean, color=color, linewidth=2,
                                label=timing_name, alpha=alpha)
                    ax_dff.fill_between(time_array, mean - sem, mean + sem,
                                        color=color, alpha=alpha * 0.5)
            ax_dff.axvline(x=0, color="#808080", linestyle="--",
                           alpha=0.8, label="Opto Stim")
            ax_dff.set_title(
                f"{param_name} - Fiber ΔF/F {wavelength}nm (Multi-Drug)")
            ax_dff.legend(fontsize=8)
        else:
            data = param_data.get("optogenetics", {})
            episodes = data.get("dff", {}).get(wavelength, [])
            if len(episodes) > 0:
                arr = np.array(episodes)
                if arr.ndim == 1:
                    arr = arr[np.newaxis, :]
                mean = np.nanmean(arr, axis=0)
                sem  = np.nanstd(arr, axis=0) / np.sqrt(arr.shape[0])
                ax_dff.plot(time_array, mean, color=color,
                            linewidth=2, label="Mean")
                ax_dff.fill_between(time_array, mean - sem, mean + sem,
                                    color=color, alpha=0.5)
                ax_dff.axvline(x=0, color="#808080", linestyle="--",
                               alpha=0.8, label="Opto Stim")
                ax_dff.legend()
            else:
                ax_dff.text(0.5, 0.5, f"No dFF data for {wavelength}nm",
                            ha="center", va="center",
                            transform=ax_dff.transAxes,
                            fontsize=12, color="#666666")
                ax_dff.axis("off")
            ax_dff.set_title(f"{param_name} - Fiber ΔF/F {wavelength}nm")
        ax_dff.set_xlim(time_array[0], time_array[-1])
        ax_dff.set_xlabel("Time (s)")
        ax_dff.set_ylabel("ΔF/F")
        ax_dff.grid(False)

        ax_zs = fig.add_subplot(2, NUM_COLS, 3)
        if analysis_mode == "optogenetics+drug":
            drug_timings = list(param_data.keys())
            n = max(len(drug_timings), 1)
            for timing_name in drug_timings:
                data = param_data[timing_name]
                episodes = data["zscore"].get(wavelength, [])
                if len(episodes) > 0:
                    arr = np.array(episodes)
                    if arr.ndim == 1:
                        arr = arr[np.newaxis, :]
                    mean = np.nanmean(arr, axis=0)
                    sem  = np.nanstd(arr, axis=0) / np.sqrt(arr.shape[0])
                    timing_idx = drug_timings.index(timing_name)
                    alpha = (1 / n) if timing_name == "baseline" else (1 / n) + (1 / n * timing_idx)
                    ax_zs.plot(time_array, mean, color=color, linewidth=2,
                               label=timing_name, alpha=alpha)
                    ax_zs.fill_between(time_array, mean - sem, mean + sem,
                                       color=color, alpha=alpha * 0.5)
            ax_zs.axvline(x=0, color="#808080", linestyle="--",
                          alpha=0.8, label="Opto Stim")
            ax_zs.set_title(
                f"{param_name} - Fiber Z-score {wavelength}nm (Multi-Drug)")
            ax_zs.legend(fontsize=8)
        else:
            data = param_data.get("optogenetics", {})
            episodes = data.get("zscore", {}).get(wavelength, [])
            if len(episodes) > 0:
                arr = np.array(episodes)
                if arr.ndim == 1:
                    arr = arr[np.newaxis, :]
                mean = np.nanmean(arr, axis=0)
                sem  = np.nanstd(arr, axis=0) / np.sqrt(arr.shape[0])
                ax_zs.plot(time_array, mean, color=color,
                           linewidth=2, label="Mean")
                ax_zs.fill_between(time_array, mean - sem, mean + sem,
                                   color=color, alpha=0.5)
                ax_zs.axvline(x=0, color="#808080", linestyle="--",
                              alpha=0.8, label="Opto Stim")
                ax_zs.legend()
            else:
                ax_zs.text(0.5, 0.5, f"No z-score data for {wavelength}nm",
                           ha="center", va="center",
                           transform=ax_zs.transAxes,
                           fontsize=12, color="#666666")
                ax_zs.axis("off")
            ax_zs.set_title(f"{param_name} - Fiber Z-score {wavelength}nm")
        ax_zs.set_xlim(time_array[0], time_array[-1])
        ax_zs.set_xlabel("Time (s)")
        ax_zs.set_ylabel("Z-score")
        ax_zs.grid(False)

        # Row 2: Heatmaps
        ax_run_heat = fig.add_subplot(2, NUM_COLS, 4)
        if analysis_mode == "optogenetics+drug":
            all_run, boundaries = [], []
            for timing_name, data in param_data.items():
                ep = data.get("running", [])
                if len(ep) > 0:
                    all_run.extend(ep)
                    boundaries.append(len(all_run))
        else:
            all_run = param_data.get("optogenetics", {}).get("running", [])
            boundaries = []
        if all_run:
            draw_heatmap(ax_run_heat, np.array(all_run), time_array,
                         "viridis", "Speed (cm/s)",
                         extra_lines=boundaries[:-1] if boundaries else None)
            ax_run_heat.set_title(f"{param_name} - Running Speed Heatmap")
        else:
            ax_run_heat.text(0.5, 0.5, "No running data",
                             ha="center", va="center",
                             transform=ax_run_heat.transAxes,
                             fontsize=12, color="#666666")
            ax_run_heat.set_title(f"{param_name} - Running Speed Heatmap")
            ax_run_heat.axis("off")

        ax_dff_heat = fig.add_subplot(2, NUM_COLS, 5)
        if analysis_mode == "optogenetics+drug":
            all_dff, boundaries = [], []
            for timing_name, data in param_data.items():
                ep = data["dff"].get(wavelength, [])
                if len(ep) > 0:
                    all_dff.extend(ep)
                    boundaries.append(len(all_dff))
        else:
            all_dff = param_data.get("optogenetics", {}).get(
                "dff", {}).get(wavelength, [])
            boundaries = []
        if all_dff:
            draw_heatmap(ax_dff_heat, np.array(all_dff), time_array,
                          "coolwarm", "ΔF/F",
                          extra_lines=boundaries[:-1] if boundaries else None)
            ax_dff_heat.set_title(
                f"{param_name} - Fiber ΔF/F Heatmap {wavelength}nm")
        else:
            ax_dff_heat.text(0.5, 0.5, f"No dFF data for {wavelength}nm",
                             ha="center", va="center",
                             transform=ax_dff_heat.transAxes,
                             fontsize=12, color="#666666")
            ax_dff_heat.set_title(
                f"{param_name} - Fiber ΔF/F Heatmap {wavelength}nm")
            ax_dff_heat.axis("off")

        ax_zs_heat = fig.add_subplot(2, NUM_COLS, 6)
        if analysis_mode == "optogenetics+drug":
            all_zs, boundaries = [], []
            for timing_name, data in param_data.items():
                ep = data["zscore"].get(wavelength, [])
                if len(ep) > 0:
                    all_zs.extend(ep)
                    boundaries.append(len(all_zs))
        else:
            all_zs = param_data.get("optogenetics", {}).get(
                "zscore", {}).get(wavelength, [])
            boundaries = []
        if all_zs:
            draw_heatmap(ax_zs_heat, np.array(all_zs), time_array,
                          "coolwarm", "Z-score",
                          extra_lines=boundaries[:-1] if boundaries else None)
            ax_zs_heat.set_title(
                f"{param_name} - Fiber Z-score Heatmap {wavelength}nm")
        else:
            ax_zs_heat.text(0.5, 0.5, f"No z-score data for {wavelength}nm",
                            ha="center", va="center",
                            transform=ax_zs_heat.transAxes,
                            fontsize=12, color="#666666")
            ax_zs_heat.set_title(
                f"{param_name} - Fiber Z-score Heatmap {wavelength}nm")
            ax_zs_heat.axis("off")
 
        fig.tight_layout(rect=[0, 0, 1, 0.96])
        embed_figure(inner, fig, row_in_frame=wl_idx)
 
    log_message(
        f"Individual parameter plot created for {param_name} "
        f"with {len(target_wavelengths)} wavelength(s) ({analysis_mode} mode)"
    )
 
def create_individual_param_windows(results, params, analysis_mode="optogenetics"):
    """Create individual windows for each parameter"""
    for param_name, param_data in results.items():
        create_single_param_window(param_name, param_data, params, analysis_mode)
