"""
Drug-induced activity analysis with table configuration
Supports multi-animal drug event analysis
"""
import os
import json
import tkinter as tk
import numpy as np

from infrastructure.logger import log_message
from analysis_multimodal.Multimodal_analysis import (
    export_results, identify_drug_sessions, calculate_running_episodes,
    create_control_panel, create_table_window, initialize_table, create_parameter_panel,
    get_parameters_from_ui, FIBER_COLORS, ROW_COLORS,
    make_scrollable_window, make_figure, draw_heatmap, embed_figure
)

NUM_COLS = 3      # Drug: Running | dFF | Z-score

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
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'drug_name_config.json')
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
        # Group animals by row
        row_data = {}
        for i in range(self.num_rows):
            row_name = self.row_headers.get(i, f"Row{i+1}")
            row_animals = []
            
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
                            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'drug_name_config.json')
                            if os.path.exists(config_path):
                                with open(config_path, 'r') as f:
                                    drug_config = json.load(f)
                                
                                if session_id in drug_config:
                                    drug_info = drug_config[session_id]
                                    if isinstance(drug_info, dict):
                                        animal_data_with_drug['drug_onset_time'] = drug_info.get('onset_time')
                                        animal_data_with_drug['drug_offset_time'] = drug_info.get('offset_time')
                            
                            row_animals.append(animal_data_with_drug)
                            break
            
            if row_animals:
                row_data[row_name] = row_animals
        
        if not row_data:
            log_message("No valid data in table", "WARNING")
            return
        
        run_drug_induced_analysis(row_data, params)

def run_drug_induced_analysis(row_data, params):
    """Run drug-induced analysis for multiple rows"""
    log_message(f"Starting drug-induced analysis for {len(row_data)} row(s)...")
    
    results = {}
    all_statistics = []
    
    for row_name, animals in row_data.items():
        log_message(f"Analyzing {row_name} with {len(animals)} animal(s)...")
        row_result, row_stats = analyze_row_drug_induced(row_name, animals, params)
        
        if row_result:
            results[row_name] = row_result
        if row_stats:
            all_statistics.extend(row_stats)
    
    if params['export_stats'] and all_statistics:
        export_results(results, all_statistics, "drug_induced")
    
    if results:
        plot_drug_induced_results(results, params)
        create_individual_row_windows(results, params)
        log_message("Analysis completed successfully")
    else:
        log_message("No valid results", "ERROR")

def collect_statistics(row_name, animal_id, session_idx, drug_name, result,
                           time_array, params, target_wavelengths, active_channels):
    """Collect statistics for drug-induced running and fiber analysis"""
    rows = []
    pre_mask = (time_array >= -params['pre_time']) & (time_array <= 0)
    post_mask = (time_array >= 0) & (time_array <= params['post_time'])

    full_id = f"{animal_id}_Session{session_idx+1}_{drug_name}"

    # Running statistics
    for trial_idx, episode_data in enumerate(result['running']):
        pre_data = episode_data[pre_mask]
        post_data = episode_data[post_mask]

        rows.append({
            'row': row_name,
            'animal_single_channel_id': full_id,
            'analysis_type': 'drug_induced',
            'channel': 'running_speed',
            'wavelength': 'N/A',
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
            'signal_type': 'running_speed',
            'baseline_start': params['baseline_start'],
            'baseline_end': params['baseline_end']
        })

    # Fiber statistics
    for channel in active_channels:
        for wl in target_wavelengths:
            # dFF
            if wl in result['dff']:
                for trial_idx, episode_data in enumerate(result['dff'][wl]):
                    pre_data = episode_data[pre_mask]
                    post_data = episode_data[post_mask]

                    rows.append({
                        'row': row_name,
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
                        'row': row_name,
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

def analyze_row_drug_induced(row_name, animals, params):
    """Analyze drug-induced effects for one row (multiple animals combined)"""
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
    combined_running = []
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
            log_message(f"Drug onset: {drug_onset_time}, offset: {drug_offset_time}")

            ast2_data = animal_data.get('ast2_data_adjusted')
            if ast2_data is None or 'data' not in ast2_data:
                log_message(f"No running data for {animal_id}", "WARNING")
                continue

            running_timestamps = ast2_data['data'].get('timestamps')
            running_speed_raw = ast2_data['data'].get('speed')
            if running_timestamps is None or running_speed_raw is None:
                log_message(f"Incomplete running data for {animal_id}", "WARNING")
                continue

            processed_data = animal_data.get('running_processed_data')
            if processed_data and processed_data.get('filtered_speed') is not None:
                running_speed = processed_data['filtered_speed']
            else:
                running_speed = running_speed_raw
            
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
            
            result = calculate_running_episodes(
                events, running_timestamps, running_speed,
                fiber_timestamps, dff_data,
                active_channels, target_wavelengths,
                params['pre_time'], params['post_time'],
                params['baseline_start'], params['baseline_end']
            )
            
            # Combine results
            if len(result['running']) > 0:
                combined_running.extend(result['running'])

            for wl in target_wavelengths:
                if wl in result['dff']:
                    combined_dff[wl].extend(result['dff'][wl])
                if wl in result['zscore']:
                    combined_zscore[wl].extend(result['zscore'][wl])
            
            # Collect statistics
            if params['export_stats']:
                statistics_rows.extend(collect_statistics(
                    row_name, animal_id, session_idx, drug_name, result,
                    time_array, params, target_wavelengths, active_channels
                ))
        
        except Exception as e:
            log_message(f"Error processing {animal_id}: {str(e)}", "ERROR")
            import traceback
            traceback.print_exc()
    
    if not combined_running and not any(combined_dff.values()) and not any(combined_zscore.values()):
        log_message(f"No valid episodes for {row_name}", "WARNING")
        return None, []
    
    result = {
        'time': time_array,
        'running': combined_running,
        'dff': combined_dff,
        'zscore': combined_zscore,
        'target_wavelengths': target_wavelengths
    }
    
    return result, statistics_rows

def plot_drug_induced_results(results, params):
    """Plot multi-animal drug-induced running and fiber results with all rows overlaid."""
    target_wavelengths = []
    for data in results.values():
        if "target_wavelengths" in data:
            target_wavelengths = data["target_wavelengths"]
            break
    if not target_wavelengths:
        target_wavelengths = ["470"]

    wavelength_label = "+".join(target_wavelengths)
    time_array = list(results.values())[0]["time"]

    win, _, inner = make_scrollable_window(
        f"Drug-Induced Activity - All Rows ({wavelength_label}nm)"
    )

    for wl_idx, wavelength in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        fig = make_figure(NUM_COLS)
        fig.suptitle(f"Wavelength {wavelength} nm — All Rows",
                     fontsize=12, fontweight="bold")

        # Row 1: Traces
        ax_run = fig.add_subplot(2, NUM_COLS, 1)
        for idx, (row_name, data) in enumerate(results.items()):
            row_color = ROW_COLORS[idx % len(ROW_COLORS)]
            episodes = data.get("running", [])
            if len(episodes) > 0:
                arr = np.array(episodes)
                if arr.ndim == 1:
                    arr = arr[np.newaxis, :]
                mean = np.nanmean(arr, axis=0)
                sem = np.nanstd(arr, axis=0) / np.sqrt(arr.shape[0])
                ax_run.plot(time_array, mean, color=row_color,
                            linewidth=2, label=row_name)
                ax_run.fill_between(time_array, mean - sem, mean + sem,
                                    color=row_color, alpha=0.3)
        ax_run.axvline(x=0, color="#808080", linestyle="--",
                       alpha=0.8, label="Drug")
        ax_run.set_xlim(time_array[0], time_array[-1])
        ax_run.set_xlabel("Time (s)")
        ax_run.set_ylabel("Speed (cm/s)")
        ax_run.set_title("Running Speed - All Rows")
        ax_run.legend(fontsize=7)
        ax_run.grid(False)

        ax_dff = fig.add_subplot(2, NUM_COLS, 2)
        for idx, (row_name, data) in enumerate(results.items()):
            row_color = ROW_COLORS[idx % len(ROW_COLORS)]
            episodes = data["dff"].get(wavelength, [])
            if len(episodes) > 0:
                arr = np.array(episodes)
                if arr.ndim == 1:
                    arr = arr[np.newaxis, :]
                mean = np.nanmean(arr, axis=0)
                sem = np.nanstd(arr, axis=0) / np.sqrt(arr.shape[0])
                ax_dff.plot(time_array, mean, color=row_color,
                            linewidth=2, label=row_name)
                ax_dff.fill_between(time_array, mean - sem, mean + sem,
                                    color=row_color, alpha=0.3)
        ax_dff.axvline(x=0, color="#808080", linestyle="--",
                       alpha=0.8, label="Drug")
        ax_dff.set_xlim(time_array[0], time_array[-1])
        ax_dff.set_xlabel("Time (s)")
        ax_dff.set_ylabel("ΔF/F")
        ax_dff.set_title(f"Fiber ΔF/F {wavelength}nm - All Rows")
        ax_dff.legend(fontsize=7)
        ax_dff.grid(False)

        ax_zs = fig.add_subplot(2, NUM_COLS, 3)
        for idx, (row_name, data) in enumerate(results.items()):
            row_color = ROW_COLORS[idx % len(ROW_COLORS)]
            episodes = data["zscore"].get(wavelength, [])
            if len(episodes) > 0:
                arr = np.array(episodes)
                if arr.ndim == 1:
                    arr = arr[np.newaxis, :]
                mean = np.nanmean(arr, axis=0)
                sem = np.nanstd(arr, axis=0) / np.sqrt(arr.shape[0])
                ax_zs.plot(time_array, mean, color=row_color,
                           linewidth=2, label=row_name)
                ax_zs.fill_between(time_array, mean - sem, mean + sem,
                                   color=row_color, alpha=0.3)
        ax_zs.axvline(x=0, color="#808080", linestyle="--",
                      alpha=0.8, label="Drug")
        ax_zs.set_xlim(time_array[0], time_array[-1])
        ax_zs.set_xlabel("Time (s)")
        ax_zs.set_ylabel("Z-score")
        ax_zs.set_title(f"Fiber Z-score {wavelength}nm - All Rows")
        ax_zs.legend(fontsize=7)
        ax_zs.grid(False)

        # Row 2: Heatmaps
        ax_run_heat = fig.add_subplot(2, NUM_COLS, 4)
        all_run, counts = [], []
        for data in results.values():
            ep = data.get("running", [])
            if len(ep) > 0:
                all_run.extend(ep)
                counts.append(len(ep))
        if all_run:
            boundaries = []
            acc = 0
            for c in counts[:-1]:
                acc += c
                boundaries.append(acc)
            draw_heatmap(ax_run_heat, np.array(all_run), time_array,
                         "viridis", "Speed (cm/s)",
                         extra_lines=boundaries if boundaries else None)
            ax_run_heat.set_title("Running Speed Heatmap")
        else:
            ax_run_heat.text(0.5, 0.5, "No running data",
                             ha="center", va="center",
                             transform=ax_run_heat.transAxes,
                             fontsize=12, color="#666666")
            ax_run_heat.set_title("Running Speed Heatmap")
            ax_run_heat.axis("off")

        ax_dff_heat = fig.add_subplot(2, NUM_COLS, 5)
        all_dff, counts = [], []
        for data in results.values():
            ep = data["dff"].get(wavelength, [])
            if len(ep) > 0:
                all_dff.extend(ep)
                counts.append(len(ep))
        if all_dff:
            boundaries = []
            acc = 0
            for c in counts[:-1]:
                acc += c
                boundaries.append(acc)
            draw_heatmap(ax_dff_heat, np.array(all_dff), time_array,
                         "coolwarm", "ΔF/F",
                         extra_lines=boundaries if boundaries else None)
            ax_dff_heat.set_title(f"Fiber ΔF/F Heatmap {wavelength}nm")
        else:
            ax_dff_heat.text(0.5, 0.5, f"No dFF data for {wavelength}nm",
                             ha="center", va="center",
                             transform=ax_dff_heat.transAxes,
                             fontsize=12, color="#666666")
            ax_dff_heat.set_title(f"Fiber ΔF/F Heatmap {wavelength}nm")
            ax_dff_heat.axis("off")

        ax_zs_heat = fig.add_subplot(2, NUM_COLS, 6)
        all_zs, counts = [], []
        for data in results.values():
            ep = data["zscore"].get(wavelength, [])
            if len(ep) > 0:
                all_zs.extend(ep)
                counts.append(len(ep))
        if all_zs:
            boundaries = []
            acc = 0
            for c in counts[:-1]:
                acc += c
                boundaries.append(acc)
            draw_heatmap(ax_zs_heat, np.array(all_zs), time_array,
                         "coolwarm", "Z-score",
                         extra_lines=boundaries if boundaries else None)
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

    log_message(f"Drug-induced results plotted for {len(results)} rows")

def create_single_row_window(row_name, data, params):
    """Create window for a single row with running and fiber plots."""
    target_wavelengths = data.get("target_wavelengths", ["470"])
    wavelength_label = "+".join(target_wavelengths)
    time_array = data["time"]

    win, _, inner = make_scrollable_window(
        f"Drug-Induced Activity - {row_name} ({wavelength_label}nm)"
    )

    for wl_idx, wavelength in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        fig = make_figure(NUM_COLS)
        fig.suptitle(f"{row_name} — Wavelength {wavelength} nm",
                     fontsize=12, fontweight="bold")

        # Row 1: Traces
        ax_run = fig.add_subplot(2, NUM_COLS, 1)
        run_episodes = data.get("running", [])
        if len(run_episodes) > 0:
            run_arr = np.array(run_episodes)
            if run_arr.ndim == 1:
                run_arr = run_arr[np.newaxis, :]
            mean = np.nanmean(run_arr, axis=0)
            sem = np.nanstd(run_arr, axis=0) / np.sqrt(run_arr.shape[0])
            ax_run.plot(time_array, mean, color="#000000", linewidth=2, label="Mean")
            ax_run.fill_between(time_array, mean - sem, mean + sem,
                                color="#000000", alpha=0.3)
            ax_run.axvline(x=0, color="#808080", linestyle="--",
                           alpha=0.8, label="Drug")
            ax_run.set_xlim(time_array[0], time_array[-1])
            ax_run.set_xlabel("Time (s)")
            ax_run.set_ylabel("Speed (cm/s)")
            ax_run.legend()
            ax_run.grid(False)
        else:
            ax_run.text(0.5, 0.5, "No running data",
                        ha="center", va="center",
                        transform=ax_run.transAxes,
                        fontsize=12, color="#666666")
            ax_run.axis("off")
        ax_run.set_title(f"{row_name} - Running Speed")

        ax_dff = fig.add_subplot(2, NUM_COLS, 2)
        episodes = data["dff"].get(wavelength, [])
        if len(episodes) > 0:
            arr = np.array(episodes)
            if arr.ndim == 1:
                arr = arr[np.newaxis, :]
            mean = np.nanmean(arr, axis=0)
            sem  = np.nanstd(arr, axis=0) / np.sqrt(arr.shape[0])
            ax_dff.plot(time_array, mean, color=color, linewidth=2, label="Mean")
            ax_dff.fill_between(time_array, mean - sem, mean + sem,
                                color=color, alpha=0.3)
            ax_dff.axvline(x=0, color="#808080", linestyle="--",
                           alpha=0.8, label="Drug")
            ax_dff.set_xlim(time_array[0], time_array[-1])
            ax_dff.set_xlabel("Time (s)")
            ax_dff.set_ylabel("ΔF/F")
            ax_dff.legend()
            ax_dff.grid(False)
        else:
            ax_dff.text(0.5, 0.5, f"No dFF data for {wavelength}nm",
                        ha="center", va="center",
                        transform=ax_dff.transAxes,
                        fontsize=12, color="#666666")
            ax_dff.axis("off")
        ax_dff.set_title(f"{row_name} - Fiber ΔF/F {wavelength}nm")

        ax_zs = fig.add_subplot(2, NUM_COLS, 3)
        episodes = data["zscore"].get(wavelength, [])
        if len(episodes) > 0:
            arr = np.array(episodes)
            if arr.ndim == 1:
                arr = arr[np.newaxis, :]
            mean = np.nanmean(arr, axis=0)
            sem  = np.nanstd(arr, axis=0) / np.sqrt(arr.shape[0])
            ax_zs.plot(time_array, mean, color=color, linewidth=2, label="Mean")
            ax_zs.fill_between(time_array, mean - sem, mean + sem,
                               color=color, alpha=0.3)
            ax_zs.axvline(x=0, color="#808080", linestyle="--",
                          alpha=0.8, label="Drug")
            ax_zs.set_xlim(time_array[0], time_array[-1])
            ax_zs.set_xlabel("Time (s)")
            ax_zs.set_ylabel("Z-score")
            ax_zs.legend()
            ax_zs.grid(False)
        else:
            ax_zs.text(0.5, 0.5, f"No z-score data for {wavelength}nm",
                       ha="center", va="center",
                       transform=ax_zs.transAxes,
                       fontsize=12, color="#666666")
            ax_zs.axis("off")
        ax_zs.set_title(f"{row_name} - Fiber Z-score {wavelength}nm")

        # Row 2: Heatmaps
        ax_run_heat = fig.add_subplot(2, NUM_COLS, 4)
        if len(run_episodes) > 0:
            draw_heatmap(ax_run_heat, np.array(run_episodes),
                         time_array, "viridis", "Speed (cm/s)")
            ax_run_heat.set_title(f"{row_name} - Running Speed Heatmap")
        else:
            ax_run_heat.text(0.5, 0.5, "No running data",
                             ha="center", va="center",
                             transform=ax_run_heat.transAxes,
                             fontsize=12, color="#666666")
            ax_run_heat.set_title(f"{row_name} - Running Speed Heatmap")
            ax_run_heat.axis("off")

        ax_dff_heat = fig.add_subplot(2, NUM_COLS, 5)
        episodes = data["dff"].get(wavelength, [])
        if len(episodes) > 0:
            draw_heatmap(ax_dff_heat, np.array(episodes),
                          time_array, "coolwarm", "ΔF/F")
            ax_dff_heat.set_title(
                f"{row_name} - Fiber ΔF/F Heatmap {wavelength}nm")
        else:
            ax_dff_heat.text(0.5, 0.5, f"No dFF data for {wavelength}nm",
                             ha="center", va="center",
                             transform=ax_dff_heat.transAxes,
                             fontsize=12, color="#666666")
            ax_dff_heat.set_title(
                f"{row_name} - Fiber ΔF/F Heatmap {wavelength}nm")
            ax_dff_heat.axis("off")

        ax_zs_heat = fig.add_subplot(2, NUM_COLS, 6)
        episodes = data["zscore"].get(wavelength, [])
        if len(episodes) > 0:
            draw_heatmap(ax_zs_heat, np.array(episodes),
                          time_array, "coolwarm", "Z-score")
            ax_zs_heat.set_title(
                f"{row_name} - Fiber Z-score Heatmap {wavelength}nm")
        else:
            ax_zs_heat.text(0.5, 0.5, f"No z-score data for {wavelength}nm",
                            ha="center", va="center",
                            transform=ax_zs_heat.transAxes,
                            fontsize=12, color="#666666")
            ax_zs_heat.set_title(
                f"{row_name} - Fiber Z-score Heatmap {wavelength}nm")
            ax_zs_heat.axis("off")
 
        fig.tight_layout(rect=[0, 0, 1, 0.96])
        embed_figure(inner, fig, row_in_frame=wl_idx)
 
    log_message(
        f"Individual row plot created for {row_name} "
        f"with {len(target_wavelengths)} wavelength(s)"
    )
 
def create_individual_row_windows(results, params):
    """Create individual windows for each row"""
    for row_name, data in results.items():
        create_single_row_window(row_name, data, params)