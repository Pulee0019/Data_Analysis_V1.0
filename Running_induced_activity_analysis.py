"""
Running-induced activity analysis with table configuration
Supports both running-only and running+drug analysis
"""
import os
import json
import tkinter as tk
from tkinter import ttk
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from logger import log_message
from Multimodal_analysis import (
    get_events_from_bouts, calculate_running_episodes, export_statistics,
    create_table_window, initialize_table, create_control_panel, identify_optogenetic_events, 
    identify_drug_sessions, calculate_optogenetic_pulse_info, get_events_within_optogenetic, 
    create_opto_parameter_string, group_optogenetic_sessions, create_parameter_panel, 
    get_parameters_from_ui, FIBER_COLORS, DAY_COLORS
)

def show_running_induced_analysis(root, multi_animal_data, analysis_mode="running"):
    """
    Show running-induced analysis configuration window
    analysis_mode: "running", "running+drug", or "running+optogenetics"
    """
    if not multi_animal_data:
        log_message("No animal data available", "ERROR")
        return
    
    # For optogenetics mode, identify optogenetic events first
    if analysis_mode == "running+optogenetics" or analysis_mode == "running+optogenetics+drug":
        log_message("Identifying optogenetic events for running+optogenetics analysis...")
        
        # Initialize event dictionaries
    all_optogenetic_events = {}
    all_drug_events = {}
    
    # For optogenetics modes, identify optogenetic events
    if "optogenetics" in analysis_mode:
        log_message("Identifying optogenetic events...")
        
        for animal_data in multi_animal_data:
            animal_id = animal_data.get('animal_single_channel_id', 'Unknown')
            events_data = animal_data.get('fiber_events')
            
            if events_data is None:
                continue
        
            # Identify optogenetic events
            events = identify_optogenetic_events(events_data)
            log_message(f"Found {len(events)} optogenetic events for {animal_id}")
            
            if events:
                # Group events into stimulation sessions
                sessions = group_optogenetic_sessions(events)
                all_optogenetic_events[animal_id] = sessions
                log_message(f"Found {len(sessions)} optogenetic sessions for {animal_id}")

        if not all_optogenetic_events:
            log_message("No optogenetic events found", "ERROR")
            return
    
    # For drug modes, identify drug events
    if "drug" in analysis_mode:
        log_message("Identifying drug events...")
        
        for animal_data in multi_animal_data:
            animal_id = animal_data.get('animal_single_channel_id', 'Unknown')
            events_data = animal_data.get('fiber_events')
            
            if events_data is None:
                continue
            
            # Get drug events
            drug_sessions = identify_drug_sessions(events_data)
            log_message(f"Found {len(drug_sessions)} drug sessions for {animal_id}")
            
            if drug_sessions:
                all_drug_events[animal_id] = drug_sessions

        if not all_drug_events:
            log_message("No drug events found", "ERROR")
            return
    
    # Get available bout types
    for animal_data in multi_animal_data:
        if 'running_bouts' in animal_data and animal_data['running_bouts']:
            bouts_data = animal_data['running_bouts']
            available_bout_types = list(bouts_data.keys())
    
    if not available_bout_types:
        log_message("No bout types found in animal data", "ERROR")
        return
    
    # Create main window with parameter panel and table
    main_window = tk.Toplevel(root)
    if analysis_mode == "running":
        title = "Running-Induced Activity Analysis"
    elif analysis_mode == "running+drug":
        title = "Running+Drug-Induced Activity Analysis"
    elif analysis_mode == "running+optogenetics":
        title = "Running+Optogenetics-Induced Activity Analysis"
    elif analysis_mode == "running+optogenetics+drug":
        title = "Running+Optogenetics+Drug-Induced Activity Analysis"
    
    main_window.title(title)
    main_window.geometry("900x700")
    main_window.transient(root)
    main_window.grab_set()
    
    # Main container with two sections
    container = tk.Frame(main_window, bg="#f8f8f8")
    container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # Left panel: Parameters
    param_config = {
        'start_time': "-5",
        'end_time': "15",
        'baseline_start': "-5",
        'baseline_end': "0",
        'show_bout_type': True,
        'bout_types': available_bout_types,
        'show_event_type': True,
    }
    param_frame = create_parameter_panel(container, param_config)
    param_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 5))
    
    # Right panel: Table
    table_frame = tk.Frame(container, bg="#f8f8f8")
    table_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
    
    btn_frame = tk.Frame(main_window, bg="#f8f8f8")
    btn_frame.pack(fill=tk.X, padx=10, pady=10)

    # Initialize table manager
    if analysis_mode == "running+optogenetics" or analysis_mode == "running+optogenetics+drug":
        config_path = os.path.join(os.path.dirname(__file__), 'opto_power_config.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            opto_config = json.load(f)
            
        table_manager = OptogeneticTableManager(root, table_frame, btn_frame, 
                                              multi_animal_data, analysis_mode,
                                              all_optogenetic_events, opto_config, all_drug_events)
    else:
        table_manager = TableManager(root, table_frame, btn_frame, multi_animal_data, analysis_mode)

    def run_analysis():
        params = get_parameters_from_ui(param_frame, require_bout_type=True, require_event_type=True)
        if params:
            # Add full_event_type
            params['full_event_type'] = f"{params['bout_type'].replace('_bouts', '')}_{params['event_type']}s"
            table_manager.run_analysis(params, analysis_mode)

    tk.Button(btn_frame, text="Run Analysis", command=run_analysis,
             bg="#ffffff", fg="#000000", font=("Microsoft YaHei", 9, "bold"),
             relief=tk.FLAT, padx=10, pady=5).pack(side=tk.LEFT, padx=5)

class TableManager:
    """Manage table for multi-animal configuration"""
    def __init__(self, root, table_frame, btn_frame, multi_animal_data, analysis_mode):
        self.root = root
        self.table_frame = table_frame
        self.btn_frame = btn_frame
        self.multi_animal_data = multi_animal_data
        self.analysis_mode = analysis_mode
        
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
        """Show animal selection menu"""
        col_header = self.col_headers.get(col, f"Column{col+1}")
        is_custom_header = not col_header.startswith("Column")
        
        available_animals = []
        for animal_data in self.multi_animal_data:
            animal_id = animal_data.get('animal_single_channel_id', '')
            
            if is_custom_header:
                ear_tag = animal_id.split('-')[-1] if '-' in animal_id else ''
                if ear_tag == col_header and animal_id not in self.used_animals:
                    available_animals.append(animal_id)
            else:
                if animal_id not in self.used_animals:
                    available_animals.append(animal_id)
        
        if not available_animals:
            return
        
        menu = tk.Menu(self.root, tearoff=0)
        
        if (row, col) in self.table_data:
            menu.add_command(label="Clear", command=lambda: self.clear_cell(row, col))
            menu.add_separator()
        
        for animal_id in available_animals:
            menu.add_command(label=animal_id,
                           command=lambda aid=animal_id: self.select_animal(row, col, aid))
        
        menu.post(event.x_root, event.y_root)
    
    def select_animal(self, row, col, animal_id):
        if (row, col) in self.table_data:
            self.used_animals.discard(self.table_data[(row, col)])
        self.table_data[(row, col)] = animal_id
        self.used_animals.add(animal_id)
        self.rebuild_table()
    
    def clear_cell(self, row, col):
        if (row, col) in self.table_data:
            self.used_animals.discard(self.table_data[(row, col)])
            del self.table_data[(row, col)]
            self.rebuild_table()
    
    def run_analysis(self, params, analysis_mode):
        """Run analysis with current table configuration"""
        # Group animals by day
        day_data = {}
        for i in range(self.num_rows):
            day_name = self.row_headers.get(i, f"Day{i+1}")
            day_animals = []
            
            for j in range(self.num_cols):
                if (i, j) in self.table_data:
                    animal_id = self.table_data[(i, j)]
                    for animal_data in self.multi_animal_data:
                        if animal_data.get('animal_single_channel_id') == animal_id:
                            day_animals.append(animal_data)
                            break
            
            if day_animals:
                day_data[day_name] = day_animals
        
        if not day_data:
            log_message("No valid data in table", "WARNING")
            return
        
        if analysis_mode == "running":
            run_running_only_analysis(day_data, params)
        elif analysis_mode == "running+drug":
            run_running_drug_analysis(day_data, params)
        elif analysis_mode == "running+optogenetics":
            run_running_optogenetics_analysis(day_data, params)

class OptogeneticTableManager:
    """Manage table for running+optogenetics configuration"""
    def __init__(self, root, table_frame, btn_frame, multi_animal_data, 
                 analysis_mode, all_optogenetic_events, power_values, all_drug_events):
        self.root = root
        self.table_frame = table_frame
        self.btn_frame = btn_frame
        self.multi_animal_data = multi_animal_data
        self.analysis_mode = analysis_mode
        self.all_optogenetic_events = all_optogenetic_events
        self.power_values = power_values
        self.all_drug_events = all_drug_events
        
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
                        self.rename_row, self.rename_column, self.show_animal_selector_opto)
    
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

    def show_animal_selector_opto(self, event, row, col):
        """Show animal selection menu for optogenetics"""
        col_header = self.col_headers.get(col, f"Column{col+1}")
        is_custom_header = not col_header.startswith("Column")
        
        available_animals = []
        for animal_data in self.multi_animal_data:
            animal_id = animal_data.get('animal_single_channel_id', '')
            
            if is_custom_header:
                ear_tag = animal_id.split('-')[-1] if '-' in animal_id else ''
                if ear_tag == col_header and animal_id not in self.used_animals:
                    # Check if animal has optogenetic events
                    if animal_id in self.all_optogenetic_events:
                        available_animals.append(animal_id)
            else:
                if animal_id not in self.used_animals and animal_id in self.all_optogenetic_events:
                    available_animals.append(animal_id)
        
        if not available_animals:
            return
        
        menu = tk.Menu(self.root, tearoff=0)
        
        if (row, col) in self.table_data:
            menu.add_command(label="Clear", command=lambda: self.clear_cell(row, col))
            menu.add_separator()
        
        for animal_id in available_animals:
            menu.add_command(label=animal_id,
                           command=lambda aid=animal_id: self.select_animal(row, col, aid))
        
        menu.post(event.x_root, event.y_root)
    
    def select_animal(self, row, col, animal_id):
        """Select animal for cell"""
        if (row, col) in self.table_data:
            self.used_animals.discard(self.table_data[(row, col)])
        
        self.table_data[(row, col)] = animal_id
        self.used_animals.add(animal_id)
        self.rebuild_table()
    
    def clear_cell(self, row, col):
        """Clear cell content"""
        if (row, col) in self.table_data:
            self.used_animals.discard(self.table_data[(row, col)])
            del self.table_data[(row, col)]
            self.rebuild_table()
    
    # Other methods (add_row, remove_row, etc.) same as TableManager
    
    def run_analysis(self, params, analysis_mode):
        """Run running+optogenetics analysis"""
        # Group animals by day
        day_data = {}
        for i in range(self.num_rows):
            day_name = self.row_headers.get(i, f"Row{i+1}")
            day_animals = []
            
            for j in range(self.num_cols):
                if (i, j) in self.table_data:
                    animal_id = self.table_data[(i, j)]
                    for animal_data in self.multi_animal_data:
                        if animal_data.get('animal_single_channel_id') == animal_id:
                            day_animals.append(animal_data)
                            break
            
            if day_animals:
                day_data[day_name] = day_animals
        
        if not day_data:
            log_message("No valid data in table", "WARNING")
            return
        
        run_running_optogenetics_analysis(day_data, params, 
                                         self.all_optogenetic_events, 
                                         self.power_values, self.all_drug_events, self.analysis_mode)

def run_running_only_analysis(day_data, params):
    """Run running-only analysis"""
    log_message(f"Starting running-induced analysis for {len(day_data)} day(s)...")
    
    results = {}
    all_statistics = []
    
    for day_name, animals in day_data.items():
        log_message(f"Analyzing {day_name} with {len(animals)} animal(s)...")
        day_result, day_stats = analyze_day_running(day_name, animals, params)
        
        if day_result:
            results[day_name] = day_result
        if day_stats:
            all_statistics.extend(day_stats)
    
    if params['export_stats'] and all_statistics:
        export_statistics(all_statistics, "running_induced", params['full_event_type'])
    
    if results:
        plot_running_results(results, params)
        log_message("Analysis completed successfully")
    else:
        log_message("No valid results", "ERROR")

def run_running_drug_analysis(day_data, params):
    """Run running+drug analysis"""
    log_message(f"Starting running+drug analysis for {len(day_data)} day(s)...")
    
    results = {}
    all_statistics = []
    
    for day_name, animals in day_data.items():
        log_message(f"Analyzing {day_name} with {len(animals)} animal(s)...")
        day_result, day_stats = analyze_day_running_drug(day_name, animals, params)
        
        if day_result:
            results[day_name] = day_result
        if day_stats:
            all_statistics.extend(day_stats)
    
    if params['export_stats'] and all_statistics:
        export_statistics(all_statistics, "running_drug_induced", params['full_event_type'])
    
    if results:
        plot_running_drug_results(results, params)
        log_message("Analysis completed successfully")
    else:
        log_message("No valid results", "ERROR")
        
def analyze_day_running(day_name, animals, params):
    """Analyze one day for running-only mode"""
    time_array = np.linspace(-params['pre_time'], params['post_time'], 
                            int((params['pre_time'] + params['post_time']) * 10))
    
    # Collect all wavelengths
    target_wavelengths = []
    for animal_data in animals:
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
    
    # Process each animal
    for animal_data in animals:
        try:
            animal_id = animal_data.get('animal_single_channel_id', 'Unknown')

            # Get events
            events = get_events_from_bouts(animal_data, params['full_event_type'], duration = False)
            if not events:
                log_message(f"No events for {animal_id}", "WARNING")
                continue
                        # Get data
            ast2_data = animal_data.get('ast2_data_adjusted')
            if not ast2_data:
                continue

            running_timestamps = ast2_data['data']['timestamps']
            processed_data = animal_data.get('running_processed_data')
            running_speed = processed_data['filtered_speed'] if processed_data else ast2_data['data']['speed']
            
            preprocessed_data = animal_data.get('preprocessed_data')
            if preprocessed_data is None or preprocessed_data.empty:
                continue
                
            channels = animal_data.get('channels', {})
            time_col = channels['time']
            fiber_timestamps = preprocessed_data[time_col].values
            
            dff_data = animal_data.get('dff_data', {})
            active_channels = animal_data.get('active_channels', [])

            # Calculate episodes
            result = calculate_running_episodes(
                events, running_timestamps, running_speed,
                fiber_timestamps, dff_data,
                active_channels, target_wavelengths,
                params['pre_time'], params['post_time'],
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
                statistics_rows.extend(collect_statistics(
                    day_name, animal_id, params['full_event_type'],
                    result, time_array, params, target_wavelengths, active_channels
                ))
                
        except Exception as e:
            log_message(f"Error analyzing {animal_data.get('animal_single_channel_id', 'Unknown')}: {str(e)}", "ERROR")
            continue
    
    if not all_running_episodes:
        return None, None
    
    # Calculate results
    result = {
        'time': time_array,
        'running': {
            'episodes': np.array(all_running_episodes),
            'mean': np.nanmean(all_running_episodes, axis=0),
            'sem': np.nanstd(all_running_episodes, axis=0) / np.sqrt(len(all_running_episodes))
        },
        'dff': {},
        'zscore': {},
        'target_wavelengths': target_wavelengths
    }
    
    for wl in target_wavelengths:
        if all_dff_episodes[wl]:
            episodes_array = np.array(all_dff_episodes[wl])
            result['dff'][wl] = {
                'episodes': episodes_array,
                'mean': np.nanmean(episodes_array, axis=0),
                'sem': np.nanstd(episodes_array, axis=0) / np.sqrt(len(all_dff_episodes[wl]))
            }
        
        if all_zscore_episodes[wl]:
            episodes_array = np.array(all_zscore_episodes[wl])
            result['zscore'][wl] = {
                'episodes': episodes_array,
                'mean': np.nanmean(episodes_array, axis=0),
                'sem': np.nanstd(episodes_array, axis=0) / np.sqrt(len(all_zscore_episodes[wl]))
            }
    
    return result, statistics_rows if params['export_stats'] else None

def analyze_day_running_drug(day_name, animals, params):
    """Analyze one day for running+drug mode with multiple drugs"""
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
    
    # Load drug name config
    config_path = os.path.join(os.path.dirname(__file__), 'drug_name_config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            drug_name_config = json.load(f)
    else:
        drug_name_config = {}
    
    # Collect all unique drug timing categories across all animals
    all_drug_categories = set()
    
    # Initialize storage with dynamic categories
    category_data = {}
    statistics_rows = []
    
    # Process each animal
    for animal_data in animals:
        try:
            animal_id = animal_data.get('animal_single_channel_id', 'Unknown')
            
            # Find drug events
            fiber_data = animal_data.get('fiber_data_trimmed')
            if fiber_data is None or fiber_data.empty:
                fiber_data = animal_data.get('fiber_data')
                
            channels = animal_data.get('channels', {})
            events_col = channels.get('events')
            
            if not events_col or events_col not in fiber_data.columns:
                continue
            
            # Get drug sessions
            drug_sessions = identify_drug_sessions(animal_data['fiber_events'])
            
            if not drug_sessions:
                log_message(f"No drug events for {animal_id}", "WARNING")
                continue
            
            # Get drug names and times
            drug_info = []
            for idx, session_info in enumerate(drug_sessions):
                session_id = f"{animal_id}_Session{idx+1}"
                drug_name = drug_name_config.get(session_id, f"Drug{idx+1}")
                drug_time = session_info['time']
                drug_info.append({'name': drug_name, 'time': drug_time, 'idx': idx})
            
            # Sort by time
            drug_info.sort(key=lambda x: x['time'])
            
            # Get running events
            events = get_events_from_bouts(animal_data, params['full_event_type'], duration=False)
            if not events:
                continue
            
            # Classify running events into drug categories
            event_categories = {}
            
            for event_time in events:
                # Determine which drug category this event belongs to
                if event_time < drug_info[0]['time']:
                    category = 'baseline'
                else:
                    # Find which drug period
                    for i in range(len(drug_info) - 1, -1, -1):
                        if event_time >= drug_info[i]['time']:
                            if i == 0:
                                category = drug_info[0]['name']
                            else:
                                previous_drugs = ' + '.join([d['name'] for d in drug_info[:i]])
                                category = f"{drug_info[i]['name']} after {previous_drugs}"
                            break
                
                if category not in event_categories:
                    event_categories[category] = []
                event_categories[category].append(event_time)
                all_drug_categories.add(category)
            
            # Get data
            ast2_data = animal_data.get('ast2_data_adjusted')
            if not ast2_data:
                continue
                
            running_timestamps = ast2_data['data']['timestamps']
            processed_data = animal_data.get('running_processed_data')
            running_speed = processed_data['filtered_speed'] if processed_data else ast2_data['data']['speed']
            
            preprocessed_data = animal_data.get('preprocessed_data')
            if preprocessed_data is None or preprocessed_data.empty:
                continue
            
            time_col = channels['time']
            fiber_timestamps = preprocessed_data[time_col].values
            dff_data = animal_data.get('dff_data', {})
            active_channels = animal_data.get('active_channels', [])
            
            # Process each drug category
            for category, category_events in event_categories.items():
                if category not in category_data:
                    category_data[category] = {
                        'running': [],
                        'dff': {wl: [] for wl in target_wavelengths},
                        'zscore': {wl: [] for wl in target_wavelengths}
                    }
                
                category_result = calculate_running_episodes(
                    category_events, running_timestamps, running_speed,
                    fiber_timestamps, dff_data,
                    active_channels, target_wavelengths,
                    params['pre_time'], params['post_time'],
                    params['baseline_start'], params['baseline_end']
                )
                
                if len(category_result['running']) > 0:
                    category_data[category]['running'].extend(category_result['running'])
                
                for wl in target_wavelengths:
                    if wl in category_result['dff']:
                        category_data[category]['dff'][wl].extend(category_result['dff'][wl])
                    if wl in category_result['zscore']:
                        category_data[category]['zscore'][wl].extend(category_result['zscore'][wl])
                
                # Collect statistics
                if params['export_stats']:
                    statistics_rows.extend(collect_statistics(
                        day_name, f"{animal_id}_{category}", params['full_event_type'],
                        category_result, time_array, params, target_wavelengths, active_channels
                    ))
                        
        except Exception as e:
            log_message(f"Error analyzing {animal_data.get('animal_single_channel_id', 'Unknown')}: {str(e)}", "ERROR")
            continue
    
    # Build result structure
    result = {
        'time': time_array,
        'target_wavelengths': target_wavelengths,
        'drug_categories': list(all_drug_categories)
    }
    
    # Add data for each category
    for category in list(all_drug_categories):
        if category in category_data:
            result[category] = {
                'running': {
                    'episodes': np.array(category_data[category]['running']) if category_data[category]['running'] else np.array([]),
                    'mean': np.nanmean(category_data[category]['running'], axis=0) if category_data[category]['running'] else None,
                    'sem': np.nanstd(category_data[category]['running'], axis=0) / np.sqrt(len(category_data[category]['running'])) if category_data[category]['running'] else None
                },
                'dff': {},
                'zscore': {}
            }
            
            for wl in target_wavelengths:
                if category_data[category]['dff'][wl]:
                    episodes_array = np.array(category_data[category]['dff'][wl])
                    result[category]['dff'][wl] = {
                        'episodes': episodes_array,
                        'mean': np.nanmean(episodes_array, axis=0),
                        'sem': np.nanstd(episodes_array, axis=0) / np.sqrt(len(category_data[category]['dff'][wl]))
                    }
                
                if category_data[category]['zscore'][wl]:
                    episodes_array = np.array(category_data[category]['zscore'][wl])
                    result[category]['zscore'][wl] = {
                        'episodes': episodes_array,
                        'mean': np.nanmean(episodes_array, axis=0),
                        'sem': np.nanstd(episodes_array, axis=0) / np.sqrt(len(category_data[category]['zscore'][wl]))
                    }
    
    return result, statistics_rows if params['export_stats'] else None

def analyze_day_running_optogenetics(day_name, animals, params, all_optogenetic_events, power_values):
    """Analyze one day for running+optogenetics mode"""
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
    
    # Initialize storage for with/without optogenetics
    with_opto = {
        'running': [],
        'dff': {wl: [] for wl in target_wavelengths},
        'zscore': {wl: [] for wl in target_wavelengths}
    }
    
    without_opto = {
        'running': [],
        'dff': {wl: [] for wl in target_wavelengths},
        'zscore': {wl: [] for wl in target_wavelengths}
    }
    
    statistics_rows = []
    
    # Process each animal
    for animal_data in animals:
        try:
            animal_id = animal_data.get('animal_single_channel_id', 'Unknown')
            
            # Check if animal has optogenetic events
            if animal_id not in all_optogenetic_events:
                log_message(f"No optogenetic events for {animal_id}", "WARNING")
                continue
            
            # Get optogenetic sessions for this animal
            opto_sessions = all_optogenetic_events[animal_id]
            if not opto_sessions:
                continue
            
            # Use first session (assuming one session per animal for simplicity)
            opto_session = opto_sessions[0]
            
            # Get running events
            running_events = get_events_from_bouts(animal_data, params['full_event_type'], duration = True)
            if not running_events:
                log_message(f"No running events for {animal_id}", "WARNING")
                continue
            
            # Categorize running events
            with_opto_events, without_opto_events = get_events_within_optogenetic(
                opto_session, running_events, params['full_event_type']
            )
            
            # Get session parameters for unique ID
            freq, pulse_width, duration = calculate_optogenetic_pulse_info(opto_session, animal_id)
            power = 0
            for param_id, pwr in power_values.items():
                if param_id.startswith(f"{animal_id}_{freq:.1f}Hz_{pulse_width*1000:.0f}ms_{duration:.1f}s"):
                    power = pwr
                    break
            
            # Create unique IDs
            base_param = create_opto_parameter_string(freq, pulse_width, duration, power)
            with_opto_id = f"{animal_id}_{base_param}_with_{params['full_event_type']}"
            without_opto_id = f"{animal_id}_{base_param}_without_{params['full_event_type']}"
            
            # Get data
            ast2_data = animal_data.get('ast2_data_adjusted')
            if not ast2_data:
                continue
                
            running_timestamps = ast2_data['data']['timestamps']
            processed_data = animal_data.get('running_processed_data')
            running_speed = processed_data['filtered_speed'] if processed_data else ast2_data['data']['speed']
            
            preprocessed_data = animal_data.get('preprocessed_data')
            if preprocessed_data is None or preprocessed_data.empty:
                continue
                
            channels = animal_data.get('channels', {})
            time_col = channels['time']
            fiber_timestamps = preprocessed_data[time_col].values
            
            dff_data = animal_data.get('dff_data', {})
            active_channels = animal_data.get('active_channels', [])
            
            # Process events with optogenetics
            if with_opto_events:
                with_result = calculate_running_episodes(
                    with_opto_events, running_timestamps, running_speed,
                    fiber_timestamps, dff_data,
                    active_channels, target_wavelengths,
                    params['pre_time'], params['post_time'],
                    params['baseline_start'], params['baseline_end']
                )
                
                if len(with_result['running']) > 0:
                    with_opto['running'].extend(with_result['running'])
                
                for wl in target_wavelengths:
                    if wl in with_result['dff']:
                        with_opto['dff'][wl].extend(with_result['dff'][wl])
                    if wl in with_result['zscore']:
                        with_opto['zscore'][wl].extend(with_result['zscore'][wl])
                
                # Collect statistics
                if params['export_stats'] and len(with_result['running']) > 0:
                    for episode_idx in range(len(with_result['running'])):
                        for channel in active_channels:
                            for wl in target_wavelengths:
                                if wl in with_result['dff'] and episode_idx < len(with_result['dff'][wl]):
                                    # Add statistics for with-opto events
                                    statistics_rows.append({
                                        'day': day_name,
                                        'animal_single_channel_id': with_opto_id,
                                        'event_type': params['full_event_type'],
                                        'channel': channel,
                                        'wavelength': wl,
                                        'trial': episode_idx + 1,
                                        'condition': 'with_opto',
                                        'signal_type': 'fiber_dff'
                                    })
            
            # Process events without optogenetics
            if without_opto_events:
                without_result = calculate_running_episodes(
                    without_opto_events, running_timestamps, running_speed,
                    fiber_timestamps, dff_data,
                    active_channels, target_wavelengths,
                    params['pre_time'], params['post_time'],
                    params['baseline_start'], params['baseline_end']
                )
                
                if len(without_result['running']) > 0:
                    without_opto['running'].extend(without_result['running'])
                
                for wl in target_wavelengths:
                    if wl in without_result['dff']:
                        without_opto['dff'][wl].extend(without_result['dff'][wl])
                    if wl in without_result['zscore']:
                        without_opto['zscore'][wl].extend(without_result['zscore'][wl])
                
                # Collect statistics
                if params['export_stats'] and len(without_result['running']) > 0:
                    for episode_idx in range(len(without_result['running'])):
                        for channel in active_channels:
                            for wl in target_wavelengths:
                                if wl in without_result['dff'] and episode_idx < len(without_result['dff'][wl]):
                                    # Add statistics for without-opto events
                                    statistics_rows.append({
                                        'day': day_name,
                                        'animal_single_channel_id': without_opto_id,
                                        'event_type': params['full_event_type'],
                                        'channel': channel,
                                        'wavelength': wl,
                                        'trial': episode_idx + 1,
                                        'condition': 'without_opto',
                                        'signal_type': 'fiber_dff'
                                    })
                        
        except Exception as e:
            log_message(f"Error analyzing {animal_id}: {str(e)}", "ERROR")
            continue
    
    # Combine results
    result = {
        'time': time_array,
        'with_opto': {
            'running': {
                'episodes': np.array(with_opto['running']) if with_opto['running'] else np.array([]),
                'mean': np.nanmean(with_opto['running'], axis=0) if with_opto['running'] else None,
                'sem': np.nanstd(with_opto['running'], axis=0) / np.sqrt(len(with_opto['running'])) if with_opto['running'] else None
            },
            'dff': {},
            'zscore': {}
        },
        'without_opto': {
            'running': {
                'episodes': np.array(without_opto['running']) if without_opto['running'] else np.array([]),
                'mean': np.nanmean(without_opto['running'], axis=0) if without_opto['running'] else None,
                'sem': np.nanstd(without_opto['running'], axis=0) / np.sqrt(len(without_opto['running'])) if without_opto['running'] else None
            },
            'dff': {},
            'zscore': {}
        },
        'target_wavelengths': target_wavelengths
    }
    
    for wl in target_wavelengths:
        if with_opto['dff'][wl]:
            episodes_array = np.array(with_opto['dff'][wl])
            result['with_opto']['dff'][wl] = {
                'episodes': episodes_array,
                'mean': np.nanmean(episodes_array, axis=0),
                'sem': np.nanstd(episodes_array, axis=0) / np.sqrt(len(with_opto['dff'][wl]))
            }
        
        if with_opto['zscore'][wl]:
            episodes_array = np.array(with_opto['zscore'][wl])
            result['with_opto']['zscore'][wl] = {
                'episodes': episodes_array,
                'mean': np.nanmean(episodes_array, axis=0),
                'sem': np.nanstd(episodes_array, axis=0) / np.sqrt(len(with_opto['zscore'][wl]))
            }
        
        if without_opto['dff'][wl]:
            episodes_array = np.array(without_opto['dff'][wl])
            result['without_opto']['dff'][wl] = {
                'episodes': episodes_array,
                'mean': np.nanmean(episodes_array, axis=0),
                'sem': np.nanstd(episodes_array, axis=0) / np.sqrt(len(without_opto['dff'][wl]))
            }
        
        if without_opto['zscore'][wl]:
            episodes_array = np.array(without_opto['zscore'][wl])
            result['without_opto']['zscore'][wl] = {
                'episodes': episodes_array,
                'mean': np.nanmean(episodes_array, axis=0),
                'sem': np.nanstd(episodes_array, axis=0) / np.sqrt(len(without_opto['zscore'][wl]))
            }
    
    return result, statistics_rows if params['export_stats'] else None

def collect_statistics(day_name, animal_id, event_type, result, time_array, params, 
                       target_wavelengths, active_channels):
    """Collect statistics for export"""
    rows = []
    pre_mask = (time_array >= -params['pre_time']) & (time_array <= 0)
    post_mask = (time_array >= 0) & (time_array <= params['post_time'])
    
    # Running statistics
    for trial_idx, episode_data in enumerate(result['running']):
        pre_data = episode_data[pre_mask]
        post_data = episode_data[post_mask]
        
        rows.append({
            'day': day_name,
            'animal_single_channel_id': animal_id,
            'event_type': event_type,
            'trial': trial_idx + 1,
            'pre_min': np.min(pre_data) if len(pre_data) > 0 else np.nan,
            'pre_max': np.max(pre_data) if len(pre_data) > 0 else np.nan,
            'pre_mean': np.mean(pre_data) if len(pre_data) > 0 else np.nan,
            'pre_area': np.trapz(pre_data, time_array[pre_mask]) if len(pre_data) > 0 else np.nan,
            'post_min': np.min(post_data) if len(post_data) > 0 else np.nan,
            'post_max': np.max(post_data) if len(post_data) > 0 else np.nan,
            'post_mean': np.mean(post_data) if len(post_data) > 0 else np.nan,
            'post_area': np.trapz(post_data, time_array[post_mask]) if len(post_data) > 0 else np.nan,
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
                        'day': day_name,
                        'animal_single_channel_id': animal_id,
                        'event_type': event_type,
                        'channel': channel,
                        'wavelength': wl,
                        'trial': trial_idx + 1,
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
                        'baseline_end': params['baseline_end']
                    })
            
            # Z-score
            if wl in result['zscore']:
                for trial_idx, episode_data in enumerate(result['zscore'][wl]):
                    pre_data = episode_data[pre_mask]
                    post_data = episode_data[post_mask]
                    
                    rows.append({
                        'day': day_name,
                        'animal_single_channel_id': animal_id,
                        'event_type': event_type,
                        'channel': channel,
                        'wavelength': wl,
                        'trial': trial_idx + 1,
                        'pre_min': np.min(pre_data) if len(pre_data) > 0 else np.nan,
                        'pre_max': np.max(pre_data) if len(pre_data) > 0 else np.nan,
                        'pre_mean': np.mean(pre_data) if len(pre_data) > 0 else np.nan,
                        'pre_area': np.trapz(pre_data, time_array[pre_mask]) if len(pre_data) > 0 else np.nan,
                        'post_min': np.min(post_data) if len(post_data) > 0 else np.nan,
                        'post_max': np.max(post_data) if len(post_data) > 0 else np.nan,
                        'post_mean': np.mean(post_data) if len(post_data) > 0 else np.nan,
                        'post_area': np.trapz(post_data, time_array[post_mask]) if len(post_data) > 0 else np.nan,
                        'signal_type': 'fiber_zscore',
                        'baseline_start': params['baseline_start'],
                        'baseline_end': params['baseline_end']
                    })
    
    return rows

def plot_running_results(results, params):
    """Plot running-only results"""
    target_wavelengths = []
    for day_name, data in results.items():
        if 'target_wavelengths' in data:
            target_wavelengths = data['target_wavelengths']
            break
    
    if not target_wavelengths:
        target_wavelengths = ['470']
    
    result_window = tk.Toplevel()
    wavelength_label = '+'.join(target_wavelengths)
    result_window.title(f"Running-Induced Activity - All Days ({wavelength_label}nm)")
    result_window.state('zoomed')
    result_window.configure(bg='#f8f8f8')
    
    num_wavelengths = len(target_wavelengths)
    num_cols = 1 + 2 * num_wavelengths
    
    fig = Figure(figsize=(4 * num_cols, 10), dpi=100)
    
    plot_idx = 1
    
    # Row 1: Traces
    # Running trace
    ax_running = fig.add_subplot(2, num_cols, plot_idx)
    for idx, (day_name, data) in enumerate(results.items()):
        day_color = DAY_COLORS[idx % len(DAY_COLORS)]
        if 'running' in data and data['running']['mean'] is not None:
            ax_running.plot(data['time'], data['running']['mean'],
                          color=day_color, linewidth=2, label=day_name)
            ax_running.fill_between(data['time'],
                                   data['running']['mean'] - data['running']['sem'],
                                   data['running']['mean'] + data['running']['sem'],
                                   color=day_color, alpha=0.3)
    
    ax_running.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
    ax_running.set_xlim([data['time'][0], data['time'][-1]])
    ax_running.set_xlabel('Time (s)')
    ax_running.set_ylabel('Speed (cm/s)')
    ax_running.set_title('Running Speed - All Days')
    ax_running.legend()
    ax_running.grid(False)
    plot_idx += 1
    
    # Fiber traces
    for wl_idx, wl in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        
        # dFF trace
        ax_dff = fig.add_subplot(2, num_cols, plot_idx)
        for idx, (day_name, data) in enumerate(results.items()):
            day_color = DAY_COLORS[idx % len(DAY_COLORS)]
            if wl in data['dff']:
                ax_dff.plot(data['time'], data['dff'][wl]['mean'],
                          color=day_color, linewidth=2, label=day_name)
                ax_dff.fill_between(data['time'],
                                   data['dff'][wl]['mean'] - data['dff'][wl]['sem'],
                                   data['dff'][wl]['mean'] + data['dff'][wl]['sem'],
                                   color=day_color, alpha=0.3)
        
        ax_dff.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_dff.set_xlim([data['time'][0], data['time'][-1]])
        ax_dff.set_xlabel('Time (s)')
        ax_dff.set_ylabel('ΔF/F')
        ax_dff.set_title(f'Fiber ΔF/F {wl}nm - All Days')
        ax_dff.legend()
        ax_dff.grid(False)
        plot_idx += 1
        
        # Z-score trace
        ax_zscore = fig.add_subplot(2, num_cols, plot_idx)
        for idx, (day_name, data) in enumerate(results.items()):
            day_color = DAY_COLORS[idx % len(DAY_COLORS)]
            if wl in data['zscore']:
                ax_zscore.plot(data['time'], data['zscore'][wl]['mean'],
                             color=day_color, linewidth=2, label=day_name)
                ax_zscore.fill_between(data['time'],
                                      data['zscore'][wl]['mean'] - data['zscore'][wl]['sem'],
                                      data['zscore'][wl]['mean'] + data['zscore'][wl]['sem'],
                                      color=day_color, alpha=0.3)
        
        ax_zscore.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_zscore.set_xlim([data['time'][0], data['time'][-1]])
        ax_zscore.set_xlabel('Time (s)')
        ax_zscore.set_ylabel('Z-score')
        ax_zscore.set_title(f'Fiber Z-score {wl}nm - All Days')
        ax_zscore.legend()
        ax_zscore.grid(False)
        plot_idx += 1
    
    # Row 2: Heatmaps
    # Running heatmap
    ax_running_heat = fig.add_subplot(2, num_cols, plot_idx)
    all_running = []
    for day_name, data in results.items():
        if 'running' in data and len(data['running']['episodes']) > 0:
            all_running.extend(data['running']['episodes'])
    
    if all_running:
        time_array = list(results.values())[0]['time']
        all_running = np.array(all_running)

        if len(all_running) == 1:
            all_running = np.vstack([all_running[0], all_running[0]])
            im = ax_running_heat.imshow(all_running, aspect='auto', interpolation='nearest',
                                        extent=[time_array[0], time_array[-1], 0, 1],
                                        cmap='viridis', origin='lower')
            ax_running_heat.set_yticks(np.arange(0, 2, 1))
        else:
            im = ax_running_heat.imshow(all_running, aspect='auto', interpolation='nearest',
                                        extent=[time_array[0], time_array[-1], 0, len(all_running)],
                                        cmap='viridis', origin='lower')
            if len(all_running) <= 10:
                ax_running_heat.set_yticks(np.arange(0, len(all_running)+1, 1))

        ax_running_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
        ax_running_heat.set_xlabel('Time (s)')
        ax_running_heat.set_ylabel('Trials')
        ax_running_heat.set_title('Running Speed Heatmap')
        plt.colorbar(im, ax=ax_running_heat, label='Speed (cm/s)', orientation='horizontal')
    plot_idx += 1
    
    # Fiber heatmaps
    for wl_idx, wl in enumerate(target_wavelengths):
        # dFF heatmap
        ax_dff_heat = fig.add_subplot(2, num_cols, plot_idx)
        all_dff = []
        for day_name, data in results.items():
            if wl in data['dff']:
                all_dff.extend(data['dff'][wl]['episodes'])
        
        if all_dff:
            time_array = list(results.values())[0]['time']
            all_dff = np.array(all_dff)
            if len(all_dff) == 1:
                all_dff = np.vstack([all_dff[0], all_dff[0]])
                im = ax_dff_heat.imshow(all_dff, aspect='auto', interpolation='nearest',
                                    extent=[time_array[0], time_array[-1], 0, 1],
                                    cmap='coolwarm', origin='lower')
                ax_dff_heat.set_yticks(np.arange(0, 2, 1))
            else:
                im = ax_dff_heat.imshow(all_dff, aspect='auto', interpolation='nearest',
                                    extent=[time_array[0], time_array[-1], 0, len(all_dff)],
                                    cmap='coolwarm', origin='lower')
                if len(all_dff) <= 10:
                    ax_dff_heat.set_yticks(np.arange(0, len(all_dff)+1, 1))

            ax_dff_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            ax_dff_heat.set_xlabel('Time (s)')
            ax_dff_heat.set_ylabel('Trials')
            ax_dff_heat.set_title(f'Fiber ΔF/F Heatmap {wl}nm')
            plt.colorbar(im, ax=ax_dff_heat, label='ΔF/F', orientation='horizontal')
        plot_idx += 1
        
        # Z-score heatmap
        ax_zscore_heat = fig.add_subplot(2, num_cols, plot_idx)
        all_zscore = []
        for day_name, data in results.items():
            if wl in data['zscore']:
                all_zscore.extend(data['zscore'][wl]['episodes'])
        
        if all_zscore:
            time_array = list(results.values())[0]['time']
            all_zscore = np.array(all_zscore)

            if len(all_zscore) == 1:
                all_zscore = np.vstack([all_zscore[0], all_zscore[0]])
                im = ax_zscore_heat.imshow(all_zscore, aspect='auto', interpolation='nearest',
                                        extent=[time_array[0], time_array[-1], 0, 1],
                                        cmap='coolwarm', origin='lower')
                ax_zscore_heat.set_yticks(np.arange(0, 2, 1))
            else:
                im = ax_zscore_heat.imshow(all_zscore, aspect='auto', interpolation='nearest',
                                        extent=[time_array[0], time_array[-1], 0, len(all_zscore)],
                                        cmap='coolwarm', origin='lower')
                if len(all_zscore) <= 10:
                    ax_zscore_heat.set_yticks(np.arange(0, len(all_zscore)+1, 1))

            ax_zscore_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            ax_zscore_heat.set_xlabel('Time (s)')
            ax_zscore_heat.set_ylabel('Trials')
            ax_zscore_heat.set_title(f'Fiber Z-score Heatmap {wl}nm')
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

    # Create individual day windows
    create_individual_day_windows_running(results, params)

def create_individual_day_windows_running(results, params):
    """Create individual windows for each day - running only"""
    for day_name, data in results.items():
        create_single_day_window_running(day_name, data, params)

def create_single_day_window_running(day_name, data, params):
    """Create window for a single day - running only"""
    day_window = tk.Toplevel()
    
    target_wavelengths = data.get('target_wavelengths', ['470'])
    wavelength_label = '+'.join(target_wavelengths)
    
    day_window.title(f"Running-Induced Activity - {day_name} - {params['full_event_type']}")
    day_window.state("zoomed")
    day_window.configure(bg='#f8f8f8')
    
    num_wavelengths = len(target_wavelengths)
    num_cols = 1 + 2 * num_wavelengths
    fig = Figure(figsize=(4 * num_cols, 8), dpi=100)
    
    plot_idx = 1
    time_array = data['time']
    
    # Row 1: Traces
    # Running trace
    ax_running = fig.add_subplot(2, num_cols, plot_idx)
    if 'running' in data and data['running']['mean'] is not None:
        ax_running.plot(time_array, data['running']['mean'], 
                       color="#000000", linewidth=2, label='Mean')
        ax_running.fill_between(time_array,
                               data['running']['mean'] - data['running']['sem'],
                               data['running']['mean'] + data['running']['sem'],
                               color="#000000", alpha=0.3)
        ax_running.axvline(x=0, color='#808080', linestyle='--', alpha=0.8, label='Event')
        ax_running.set_xlim(time_array[0], time_array[-1])
        ax_running.set_xlabel('Time (s)')
        ax_running.set_ylabel('Speed (cm/s)')
        ax_running.set_title(f'{day_name} - Running Speed - {params["full_event_type"]}')
        ax_running.legend()
        ax_running.grid(False)
    plot_idx += 1
    
    # Fiber traces
    for wl_idx, wl in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        
        # dFF trace
        ax_dff = fig.add_subplot(2, num_cols, plot_idx)
        if wl in data['dff']:
            ax_dff.plot(time_array, data['dff'][wl]['mean'],
                       color=color, linewidth=2, label='Mean')
            ax_dff.fill_between(time_array,
                               data['dff'][wl]['mean'] - data['dff'][wl]['sem'],
                               data['dff'][wl]['mean'] + data['dff'][wl]['sem'],
                               color=color, alpha=0.3)
            ax_dff.axvline(x=0, color='#808080', linestyle='--', alpha=0.8, label='Event')
            ax_dff.set_xlim(time_array[0], time_array[-1])
            ax_dff.set_xlabel('Time (s)')
            ax_dff.set_ylabel('ΔF/F')
            ax_dff.set_title(f'{day_name} - Fiber ΔF/F {wl}nm')
            ax_dff.legend()
            ax_dff.grid(False)
        plot_idx += 1
        
        # Z-score trace
        ax_zscore = fig.add_subplot(2, num_cols, plot_idx)
        if wl in data['zscore']:
            ax_zscore.plot(time_array, data['zscore'][wl]['mean'],
                          color=color, linewidth=2, label='Mean')
            ax_zscore.fill_between(time_array,
                                  data['zscore'][wl]['mean'] - data['zscore'][wl]['sem'],
                                  data['zscore'][wl]['mean'] + data['zscore'][wl]['sem'],
                                  color=color, alpha=0.3)
            ax_zscore.axvline(x=0, color='#808080', linestyle='--', alpha=0.8, label='Event')
            ax_zscore.set_xlim(time_array[0], time_array[-1])
            ax_zscore.set_xlabel('Time (s)')
            ax_zscore.set_ylabel('Z-score')
            ax_zscore.set_title(f'{day_name} - Fiber Z-score {wl}nm')
            ax_zscore.legend()
            ax_zscore.grid(False)
        plot_idx += 1
    
    # Row 2: Heatmaps
    # Running heatmap
    ax_running_heat = fig.add_subplot(2, num_cols, plot_idx)
    if 'running' in data and len(data['running']['episodes']) > 0:
        episodes_array = data['running']['episodes']

        if len(episodes_array) == 1:
            episodes_array = np.vstack([episodes_array[0], episodes_array[0]])
            im = ax_running_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                        extent=[time_array[0], time_array[-1], 0, 1],
                                        cmap='viridis', origin='lower')
            ax_running_heat.set_yticks(np.arange(0, 2, 1))
        else:
            im = ax_running_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                        extent=[time_array[0], time_array[-1], 0, len(episodes_array)],
                                        cmap='viridis', origin='lower')
            if len(episodes_array) <= 10:
                ax_running_heat.set_yticks(np.arange(0, len(episodes_array)+1, 1))

        ax_running_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
        ax_running_heat.set_xlabel('Time (s)')
        ax_running_heat.set_ylabel('Trials')
        ax_running_heat.set_title(f'{day_name} - Running Speed Heatmap')
        plt.colorbar(im, ax=ax_running_heat, label='Speed (cm/s)', orientation='horizontal')
    plot_idx += 1
    
    # Fiber heatmaps
    for wl_idx, wl in enumerate(target_wavelengths):
        # dFF heatmap
        ax_dff_heat = fig.add_subplot(2, num_cols, plot_idx)
        if wl in data['dff']:
            episodes_array = data['dff'][wl]['episodes']

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
            ax_dff_heat.set_title(f'{day_name} - Fiber ΔF/F Heatmap {wl}nm')
            plt.colorbar(im, ax=ax_dff_heat, label='ΔF/F', orientation='horizontal')
        plot_idx += 1
        
        # Z-score heatmap
        ax_zscore_heat = fig.add_subplot(2, num_cols, plot_idx)
        if wl in data['zscore']:
            episodes_array = data['zscore'][wl]['episodes']

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
            ax_zscore_heat.set_title(f'{day_name} - Fiber Z-score Heatmap {wl}nm')
            plt.colorbar(im, ax=ax_zscore_heat, label='Z-score', orientation='horizontal')
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
    
    log_message(f"Individual day plot created for {day_name}")

def create_individual_day_windows_running_drug(results, params):
    """Create individual windows for each day - running+drug"""
    for day_name, data in results.items():
        create_single_day_window_running_drug(day_name, data, params)

def create_single_day_window_running_drug(day_name, data, params):
    """Create window for a single day - running+drug"""
    day_window = tk.Toplevel()
    
    target_wavelengths = data.get('target_wavelengths', ['470'])
    wavelength_label = '+'.join(target_wavelengths)
    drug_name = params.get('drug_name', 'Drug')
    
    day_window.title(f"Running+Drug Analysis - {day_name} - {params['full_event_type']}")
    day_window.state("zoomed")
    day_window.configure(bg='#f8f8f8')
    
    num_wavelengths = len(target_wavelengths)
    num_cols = 1 + 2 * num_wavelengths
    fig = Figure(figsize=(4 * num_cols, 8), dpi=100)
    
    plot_idx = 1
    time_array = data['time']
    
    # Row 1: Traces
    # Running trace
    ax_running = fig.add_subplot(2, num_cols, plot_idx)
    
    if data['pre_drug']['running']['mean'] is not None:
        ax_running.plot(time_array, data['pre_drug']['running']['mean'],
                      color="#000000", linewidth=2, linestyle='-', alpha=0.5, label=f'Pre {drug_name}')
        ax_running.fill_between(time_array,
                               data['pre_drug']['running']['mean'] - data['pre_drug']['running']['sem'],
                               data['pre_drug']['running']['mean'] + data['pre_drug']['running']['sem'],
                               color="#000000", alpha=0.2)
    
    if data['post_drug']['running']['mean'] is not None:
        ax_running.plot(time_array, data['post_drug']['running']['mean'],
                      color="#000000", linewidth=2, linestyle='-', alpha=1, label=f'Post {drug_name}')
        ax_running.fill_between(time_array,
                               data['post_drug']['running']['mean'] - data['post_drug']['running']['sem'],
                               data['post_drug']['running']['mean'] + data['post_drug']['running']['sem'],
                               color="#000000", alpha=0.5)
    
    ax_running.axvline(x=0, color='#808080', linestyle='--', alpha=0.8, label='Event')
    ax_running.set_xlim(time_array[0], time_array[-1])
    ax_running.set_xlabel('Time (s)')
    ax_running.set_ylabel('Speed (cm/s)')
    ax_running.set_title(f'{day_name} - Running Speed - {params["full_event_type"]}')
    ax_running.legend()
    ax_running.grid(False)
    plot_idx += 1
    
    # Fiber traces
    for wl_idx, wl in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        
        # dFF trace
        ax_dff = fig.add_subplot(2, num_cols, plot_idx)
        
        if wl in data['pre_drug']['dff']:
            ax_dff.plot(time_array, data['pre_drug']['dff'][wl]['mean'],
                      color=color, linewidth=2, linestyle='-', alpha=0.5, label=f'Pre {drug_name}')
            ax_dff.fill_between(time_array,
                               data['pre_drug']['dff'][wl]['mean'] - data['pre_drug']['dff'][wl]['sem'],
                               data['pre_drug']['dff'][wl]['mean'] + data['pre_drug']['dff'][wl]['sem'],
                               color=color, alpha=0.2)
        
        if wl in data['post_drug']['dff']:
            ax_dff.plot(time_array, data['post_drug']['dff'][wl]['mean'],
                      color=color, linewidth=2, linestyle='-', alpha=1, label=f'Post {drug_name}')
            ax_dff.fill_between(time_array,
                               data['post_drug']['dff'][wl]['mean'] - data['post_drug']['dff'][wl]['sem'],
                               data['post_drug']['dff'][wl]['mean'] + data['post_drug']['dff'][wl]['sem'],
                               color=color, alpha=0.5)
        
        ax_dff.axvline(x=0, color='#808080', linestyle='--', alpha=0.8, label='Event')
        ax_dff.set_xlim(time_array[0], time_array[-1])
        ax_dff.set_xlabel('Time (s)')
        ax_dff.set_ylabel('ΔF/F')
        ax_dff.set_title(f'{day_name} - Fiber ΔF/F {wl}nm')
        ax_dff.legend()
        ax_dff.grid(False)
        plot_idx += 1
        
        # Z-score trace
        ax_zscore = fig.add_subplot(2, num_cols, plot_idx)
        
        if wl in data['pre_drug']['zscore']:
            ax_zscore.plot(time_array, data['pre_drug']['zscore'][wl]['mean'],
                         color=color, linewidth=2, linestyle='-', alpha=0.5, label=f'Pre {drug_name}')
            ax_zscore.fill_between(time_array,
                                  data['pre_drug']['zscore'][wl]['mean'] - data['pre_drug']['zscore'][wl]['sem'],
                                  data['pre_drug']['zscore'][wl]['mean'] + data['pre_drug']['zscore'][wl]['sem'],
                                  color=color, alpha=0.2)
        
        if wl in data['post_drug']['zscore']:
            ax_zscore.plot(time_array, data['post_drug']['zscore'][wl]['mean'],
                         color=color, linewidth=2, linestyle='-', alpha=1, label=f'Post {drug_name}')
            ax_zscore.fill_between(time_array,
                                  data['post_drug']['zscore'][wl]['mean'] - data['post_drug']['zscore'][wl]['sem'],
                                  data['post_drug']['zscore'][wl]['mean'] + data['post_drug']['zscore'][wl]['sem'],
                                  color=color, alpha=0.5)
        
        ax_zscore.axvline(x=0, color='#808080', linestyle='--', alpha=0.8, label='Event')
        ax_zscore.set_xlim(time_array[0], time_array[-1])
        ax_zscore.set_xlabel('Time (s)')
        ax_zscore.set_ylabel('Z-score')
        ax_zscore.set_title(f'{day_name} - Fiber Z-score {wl}nm')
        ax_zscore.legend()
        ax_zscore.grid(False)
        plot_idx += 1
    
    # Row 2: Heatmaps
    # Running heatmap
    ax_running_heat = fig.add_subplot(2, num_cols, plot_idx)
    
    if len(data['pre_drug']['running']['episodes']) > 0 and len(data['post_drug']['running']['episodes']) > 0:
        combined = np.vstack([data['pre_drug']['running']['episodes'], data['post_drug']['running']['episodes']])
        n_pre = len(data['pre_drug']['running']['episodes'])
        
        if len(combined) == 1:
            combined = np.vstack([combined[0], combined[0]])
            im = ax_running_heat.imshow(combined, aspect='auto', interpolation='nearest',
                                       extent=[time_array[0], time_array[-1], 0, 1],
                                       cmap='viridis', origin='lower')
            ax_running_heat.set_yticks(np.arange(0, 2, 1))
        else:
            im = ax_running_heat.imshow(combined, aspect='auto', interpolation='nearest',
                                    extent=[time_array[0], time_array[-1], 0, len(combined)],
                                    cmap='viridis', origin='lower')
            if len(combined) <= 10:
                ax_running_heat.set_yticks(np.arange(0, len(combined)+1, 1))

        ax_running_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
        ax_running_heat.axhline(y=n_pre, color='k', linestyle='--', linewidth=1)
        ax_running_heat.set_xlabel('Time (s)')
        ax_running_heat.set_ylabel('Trials')
        ax_running_heat.set_title(f'{day_name} - Running Speed Heatmap')
        plt.colorbar(im, ax=ax_running_heat, label='Speed (cm/s)', orientation='horizontal')
    plot_idx += 1
    
    # Fiber heatmaps
    for wl_idx, wl in enumerate(target_wavelengths):
        # dFF heatmap
        ax_dff_heat = fig.add_subplot(2, num_cols, plot_idx)
        
        if wl in data['pre_drug']['dff'] and wl in data['post_drug']['dff']:
            combined = np.vstack([data['pre_drug']['dff'][wl]['episodes'], 
                                 data['post_drug']['dff'][wl]['episodes']])
            n_pre = len(data['pre_drug']['dff'][wl]['episodes'])
            
            if len(combined) == 1:
                combined = np.vstack([combined[0], combined[0]])
                im = ax_dff_heat.imshow(combined, aspect='auto', interpolation='nearest',
                                    extent=[time_array[0], time_array[-1], 0, 1],
                                    cmap='coolwarm', origin='lower')
                ax_dff_heat.set_yticks(np.arange(0, 2, 1))
            else:
                im = ax_dff_heat.imshow(combined, aspect='auto', interpolation='nearest',
                                    extent=[time_array[0], time_array[-1], 0, len(combined)],
                                    cmap='coolwarm', origin='lower')
                if len(combined) <= 10:
                    ax_dff_heat.set_yticks(np.arange(0, len(combined)+1, 1))

            ax_dff_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            ax_dff_heat.axhline(y=n_pre, color='k', linestyle='--', linewidth=1)
            ax_dff_heat.set_xlabel('Time (s)')
            ax_dff_heat.set_ylabel('Trials')
            ax_dff_heat.set_title(f'{day_name} - Fiber ΔF/F Heatmap {wl}nm')
            plt.colorbar(im, ax=ax_dff_heat, label='ΔF/F', orientation='horizontal')
        plot_idx += 1
        
        # Z-score heatmap
        ax_zscore_heat = fig.add_subplot(2, num_cols, plot_idx)
        
        if wl in data['pre_drug']['zscore'] and wl in data['post_drug']['zscore']:
            combined = np.vstack([data['pre_drug']['zscore'][wl]['episodes'],
                                 data['post_drug']['zscore'][wl]['episodes']])
            n_pre = len(data['pre_drug']['zscore'][wl]['episodes'])
            
            if len(combined) == 1:
                combined = np.vstack([combined[0], combined[0]])
                im = ax_zscore_heat.imshow(combined, aspect='auto', interpolation='nearest',
                                       extent=[time_array[0], time_array[-1], 0, 1],
                                       cmap='coolwarm', origin='lower')
                ax_zscore_heat.set_yticks(np.arange(0, 2, 1))
            else:
                im = ax_zscore_heat.imshow(combined, aspect='auto', interpolation='nearest',
                                        extent=[time_array[0], time_array[-1], 0, len(combined)],
                                        cmap='coolwarm', origin='lower')
                if len(combined) <= 10:
                    ax_zscore_heat.set_yticks(np.arange(0, len(combined)+1, 1))

            ax_zscore_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            ax_zscore_heat.axhline(y=n_pre, color='k', linestyle='--', linewidth=1)
            ax_zscore_heat.set_xlabel('Time (s)')
            ax_zscore_heat.set_ylabel('Trials')
            ax_zscore_heat.set_title(f'{day_name} - Fiber Z-score Heatmap {wl}nm')
            plt.colorbar(im, ax=ax_zscore_heat, label='Z-score', orientation='horizontal')
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
    
    log_message(f"Individual day plot created for {day_name}")

def plot_running_drug_results(results, params):
    """Plot running+drug results with multiple drug categories"""
    target_wavelengths = []
    for day_name, data in results.items():
        if 'target_wavelengths' in data:
            target_wavelengths = data['target_wavelengths']
            break
    
    if not target_wavelengths:
        target_wavelengths = ['470']
    
    result_window = tk.Toplevel()
    wavelength_label = '+'.join(target_wavelengths)
    result_window.title(f"Running+Drug Analysis - {params['full_event_type']}")
    result_window.state('zoomed')
    result_window.configure(bg='#f8f8f8')
    
    num_wavelengths = len(target_wavelengths)
    num_cols = 1 + 2 * num_wavelengths
    
    fig = Figure(figsize=(4 * num_cols, 8), dpi=100)
    
    plot_idx = 1
    time_array = list(results.values())[0]['time']
    
    # Get all drug categories
    all_categories = set()
    for data in results.values():
        if 'drug_categories' in data:
            all_categories.update(data['drug_categories'])
    all_categories = list(all_categories)
    
    # Row 1: Traces
    # Running trace
    ax_running = fig.add_subplot(2, num_cols, plot_idx)
    for idx, (day_name, data) in enumerate(results.items()):
        day_color = DAY_COLORS[idx % len(DAY_COLORS)]
        
        for cat_idx, category in enumerate(all_categories):
            if category in data and data[category]['running']['mean'] is not None:
                # Use different alpha/linestyle for different categories
                if category == 'baseline':
                    alpha = 1/len(all_categories)
                    linestyle = '-'
                else:
                    alpha = 1/len(all_categories) + (1/len(all_categories) * cat_idx)
                    linestyle = '-'
                
                log_message(f"Plotting {day_name} - {category} running trace with alpha {alpha:.2f}")
                ax_running.plot(time_array, data[category]['running']['mean'],
                              color=day_color, linestyle=linestyle, linewidth=2, alpha=alpha,
                              label=f"{day_name} {category}")
                ax_running.fill_between(time_array,
                                       data[category]['running']['mean'] - data[category]['running']['sem'],
                                       data[category]['running']['mean'] + data[category]['running']['sem'],
                                       color=day_color, alpha=alpha*0.3)

    ax_running.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
    ax_running.set_xlim(time_array[0], time_array[-1])
    ax_running.set_xlabel('Time (s)')
    ax_running.set_ylabel('Speed (cm/s)')
    ax_running.set_title(f'Running Speed - {params["full_event_type"]}')
    ax_running.legend(fontsize=7, ncol=2)
    ax_running.grid(False)
    plot_idx += 1

    # Fiber traces (similar structure for dFF and z-score)
    for wl_idx, wl in enumerate(target_wavelengths):
        # dFF trace
        ax_dff = fig.add_subplot(2, num_cols, plot_idx)
        for idx, (day_name, data) in enumerate(results.items()):
            day_color = DAY_COLORS[idx % len(DAY_COLORS)]
            
            for cat_idx, category in enumerate(all_categories):
                if category in data and wl in data[category]['dff']:
                    if category == 'baseline':
                        alpha = 1/len(all_categories)
                        linestyle = '-'
                    else:
                        alpha = 1/len(all_categories) + (1/len(all_categories) * cat_idx)
                        linestyle = '-'
                    
                    log_message(f"Plotting {day_name} - {category} dFF trace at {wl}nm with alpha {alpha:.2f}")
                    ax_dff.plot(time_array, data[category]['dff'][wl]['mean'],
                              color=day_color, linewidth=2, linestyle=linestyle, alpha=alpha,
                              label=f'{day_name} {category}')
                    ax_dff.fill_between(time_array,
                                       data[category]['dff'][wl]['mean'] - data[category]['dff'][wl]['sem'],
                                       data[category]['dff'][wl]['mean'] + data[category]['dff'][wl]['sem'],
                                       color=day_color, alpha=alpha*0.3)
        
        ax_dff.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_dff.set_xlim(time_array[0], time_array[-1])
        ax_dff.set_xlabel('Time (s)')
        ax_dff.set_ylabel('ΔF/F')
        ax_dff.set_title(f'Fiber ΔF/F {wl}nm')
        ax_dff.legend(fontsize=7, ncol=2)
        ax_dff.grid(False)
        plot_idx += 1
        
        # Z-score trace
        ax_zscore = fig.add_subplot(2, num_cols, plot_idx)
        for idx, (day_name, data) in enumerate(results.items()):
            day_color = DAY_COLORS[idx % len(DAY_COLORS)]
            
            for cat_idx, category in enumerate(all_categories):
                if category in data and wl in data[category]['zscore']:
                    if category == 'baseline':
                        alpha = 1/len(all_categories)
                        linestyle = '-'
                    else:
                        alpha = 1/len(all_categories) + (1/len(all_categories) * cat_idx)
                        linestyle = '-'
                    
                    log_message(f"Plotting {day_name} - {category} z-score trace at {wl}nm with alpha {alpha:.2f}")
                    ax_zscore.plot(time_array, data[category]['zscore'][wl]['mean'],
                                  color=day_color, linewidth=2, linestyle=linestyle, alpha=alpha,
                                  label=f'{day_name} {category}')
                    ax_zscore.fill_between(time_array,
                                          data[category]['zscore'][wl]['mean'] - data[category]['zscore'][wl]['sem'],
                                          data[category]['zscore'][wl]['mean'] + data[category]['zscore'][wl]['sem'],
                                          color=day_color, alpha=alpha*0.3)
        
        ax_zscore.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_zscore.set_xlim(time_array[0], time_array[-1])
        ax_zscore.set_xlabel('Time (s)')
        ax_zscore.set_ylabel('Z-score')
        ax_zscore.set_title(f'Fiber Z-score {wl}nm')
        ax_zscore.legend(fontsize=7, ncol=2)
        ax_zscore.grid(False)
        plot_idx += 1

    # Row 2: Heatmaps (combine all categories with dividing lines)
    # Running heatmap
    ax_running_heat = fig.add_subplot(2, num_cols, plot_idx)
    all_running_episodes = []
    category_boundaries = []
    
    for category in all_categories:
        category_episodes = []
        for day_name, data in results.items():
            if category in data and len(data[category]['running']['episodes']) > 0:
                category_episodes.extend(data[category]['running']['episodes'])
        
        if category_episodes:
            all_running_episodes.extend(category_episodes)
            if all_running_episodes:
                category_boundaries.append(len(all_running_episodes))

    if all_running_episodes:
        episodes_array = np.array(all_running_episodes)
        if len(episodes_array) == 1:
            episodes_array = np.vstack([episodes_array[0], episodes_array[0]])
            im = ax_running_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                        extent=[time_array[0], time_array[-1], 0, 1],
                                        cmap='viridis', origin='lower')
        else:
            im = ax_running_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                        extent=[time_array[0], time_array[-1], 0, len(episodes_array)],
                                        cmap='viridis', origin='lower')
            if len(episodes_array) <= 10:
                ax_running_heat.set_yticks(np.arange(0, len(episodes_array)+1, 1))

        ax_running_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
        
        # Draw category boundaries
        for boundary in category_boundaries[:-1]:
            ax_running_heat.axhline(y=boundary, color='k', linestyle='--', linewidth=1)
        
        ax_running_heat.set_xlabel('Time (s)')
        ax_running_heat.set_ylabel('Trials')
        ax_running_heat.set_title('Running Speed Heatmap')
        plt.colorbar(im, ax=ax_running_heat, label='Speed (cm/s)', orientation='horizontal')
    plot_idx += 1

    # Fiber heatmaps (similar for dFF and z-score)
    for wl_idx, wl in enumerate(target_wavelengths):
        # dFF heatmap
        ax_dff_heat = fig.add_subplot(2, num_cols, plot_idx)
        all_dff_episodes = []
        category_boundaries = []
        
        for category in all_categories:
            category_episodes = []
            for day_name, data in results.items():
                if category in data and wl in data[category]['dff']:
                    category_episodes.extend(data[category]['dff'][wl]['episodes'])
            
            if category_episodes:
                all_dff_episodes.extend(category_episodes)
                if all_dff_episodes:
                    category_boundaries.append(len(all_dff_episodes))
        
        if all_dff_episodes:
            episodes_array = np.array(all_dff_episodes)
            if len(episodes_array) == 1:
                episodes_array = np.vstack([episodes_array[0], episodes_array[0]])
                im = ax_dff_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                    extent=[time_array[0], time_array[-1], 0, 1],
                                    cmap='coolwarm', origin='lower')
            else:
                im = ax_dff_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                    extent=[time_array[0], time_array[-1], 0, len(episodes_array)],
                                    cmap='coolwarm', origin='lower')
                if len(episodes_array) <= 10:
                    ax_dff_heat.set_yticks(np.arange(0, len(episodes_array)+1, 1))
            
            ax_dff_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            for boundary in category_boundaries[:-1]:
                ax_dff_heat.axhline(y=boundary, color='k', linestyle='--', linewidth=1)
            
            ax_dff_heat.set_xlabel('Time (s)')
            ax_dff_heat.set_ylabel('Trials')
            ax_dff_heat.set_title(f'Fiber ΔF/F Heatmap {wl}nm')
            plt.colorbar(im, ax=ax_dff_heat, label='ΔF/F', orientation='horizontal')
        plot_idx += 1
        
        # Z-score heatmap (similar structure)
        ax_zscore_heat = fig.add_subplot(2, num_cols, plot_idx)
        all_zscore_episodes = []
        category_boundaries = []
        
        for category in all_categories:
            category_episodes = []
            for day_name, data in results.items():
                if category in data and wl in data[category]['zscore']:
                    category_episodes.extend(data[category]['zscore'][wl]['episodes'])
            
            if category_episodes:
                all_zscore_episodes.extend(category_episodes)
                if all_zscore_episodes:
                    category_boundaries.append(len(all_zscore_episodes))
        
        if all_zscore_episodes:
            episodes_array = np.array(all_zscore_episodes)
            if len(episodes_array) == 1:
                episodes_array = np.vstack([episodes_array[0], episodes_array[0]])
                im = ax_zscore_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                        extent=[time_array[0], time_array[-1], 0, 1],
                                        cmap='coolwarm', origin='lower')
            else:
                im = ax_zscore_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                        extent=[time_array[0], time_array[-1], 0, len(episodes_array)],
                                        cmap='coolwarm', origin='lower')
                if len(episodes_array) <= 10:
                    ax_zscore_heat.set_yticks(np.arange(0, len(episodes_array)+1, 1))

            ax_zscore_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            for boundary in category_boundaries[:-1]:
                ax_zscore_heat.axhline(y=boundary, color='k', linestyle='--', linewidth=1)
            
            ax_zscore_heat.set_xlabel('Time (s)')
            ax_zscore_heat.set_ylabel('Trials')
            ax_zscore_heat.set_title(f'Fiber Z-score Heatmap {wl}nm')
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

    # Create individual day windows
    create_individual_day_windows_running_drug(results, params)

def create_individual_day_windows_running_drug(results, params):
    """Create individual windows for each day - running+drug"""
    for day_name, data in results.items():
        create_single_day_window_running_drug(day_name, data, params)

def create_single_day_window_running_drug(day_name, data, params):
    """Create window for a single day - running+drug with multiple categories"""
    day_window = tk.Toplevel()
    
    target_wavelengths = data.get('target_wavelengths', ['470'])
    wavelength_label = '+'.join(target_wavelengths)
    
    # Get all drug categories
    drug_categories = data.get('drug_categories', [])
    
    day_window.title(f"Running+Drug Analysis - {day_name} - {params['full_event_type']}")
    day_window.state("zoomed")
    day_window.configure(bg='#f8f8f8')
    
    num_wavelengths = len(target_wavelengths)
    num_cols = 1 + 2 * num_wavelengths
    fig = Figure(figsize=(4 * num_cols, 8), dpi=100)
    
    plot_idx = 1
    time_array = data['time']
    
    # Row 1: Traces
    # Running trace
    ax_running = fig.add_subplot(2, num_cols, plot_idx)
    
    for cat_idx, category in enumerate(drug_categories):
        if category in data and data[category]['running']['mean'] is not None:
            # Different styles for different categories
            if category == 'baseline':
                alpha = 1/len(drug_categories)
                linestyle = '-'
            else:
                alpha = 1/len(drug_categories) + (1/len(drug_categories) * cat_idx)
                linestyle = '-'
            
            log_message(f"Plotting {day_name} - {category} running trace with alpha {alpha:.2f}")
            ax_running.plot(time_array, data[category]['running']['mean'],
                          color="#000000", linewidth=2, linestyle=linestyle, 
                          alpha=alpha, label=category)
            ax_running.fill_between(time_array,
                                   data[category]['running']['mean'] - data[category]['running']['sem'],
                                   data[category]['running']['mean'] + data[category]['running']['sem'],
                                   color="#000000", alpha=alpha*0.5)
    
    ax_running.axvline(x=0, color='#808080', linestyle='--', alpha=0.8, label='Event')
    ax_running.set_xlim(time_array[0], time_array[-1])
    ax_running.set_xlabel('Time (s)')
    ax_running.set_ylabel('Speed (cm/s)')
    ax_running.set_title(f'{day_name} - Running Speed (Multi-Drug)')
    ax_running.legend(fontsize=8)
    ax_running.grid(False)
    plot_idx += 1
    
    # Fiber traces
    for wl_idx, wl in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        
        # dFF trace
        ax_dff = fig.add_subplot(2, num_cols, plot_idx)
        
        for cat_idx, category in enumerate(drug_categories):
            if category in data and wl in data[category]['dff']:
                if category == 'baseline':
                    alpha = 1/len(drug_categories)
                    linestyle = '-'
                else:
                    alpha = 1/len(drug_categories) + (1/len(drug_categories) * cat_idx)
                    linestyle = '-'
                
                log_message(f"Plotting {day_name} - {category} dFF trace at {wl}nm with alpha {alpha:.2f}")
                ax_dff.plot(time_array, data[category]['dff'][wl]['mean'],
                          color=color, linewidth=2, linestyle=linestyle, 
                          alpha=alpha, label=category)
                ax_dff.fill_between(time_array,
                                   data[category]['dff'][wl]['mean'] - data[category]['dff'][wl]['sem'],
                                   data[category]['dff'][wl]['mean'] + data[category]['dff'][wl]['sem'],
                                   color=color, alpha=alpha*0.5)
        
        ax_dff.axvline(x=0, color='#808080', linestyle='--', alpha=0.8, label='Event')
        ax_dff.set_xlim(time_array[0], time_array[-1])
        ax_dff.set_xlabel('Time (s)')
        ax_dff.set_ylabel('ΔF/F')
        ax_dff.set_title(f'{day_name} - Fiber ΔF/F {wl}nm (Multi-Drug)')
        ax_dff.legend(fontsize=8)
        ax_dff.grid(False)
        plot_idx += 1
        
        # Z-score trace
        ax_zscore = fig.add_subplot(2, num_cols, plot_idx)
        
        for cat_idx, category in enumerate(drug_categories):
            if category in data and wl in data[category]['zscore']:
                if category == 'baseline':
                    alpha = 1/len(drug_categories)
                    linestyle = '-'
                else:
                    alpha = 1/len(drug_categories) + (1/len(drug_categories) * cat_idx)
                    linestyle = '-'
                
                log_message(f"Plotting {day_name} - {category} z-score trace at {wl}nm with alpha {alpha:.2f}")
                ax_zscore.plot(time_array, data[category]['zscore'][wl]['mean'],
                             color=color, linewidth=2, linestyle=linestyle, 
                             alpha=alpha, label=category)
                ax_zscore.fill_between(time_array,
                                      data[category]['zscore'][wl]['mean'] - data[category]['zscore'][wl]['sem'],
                                      data[category]['zscore'][wl]['mean'] + data[category]['zscore'][wl]['sem'],
                                      color=color, alpha=alpha*0.5)
        
        ax_zscore.axvline(x=0, color='#808080', linestyle='--', alpha=0.8, label='Event')
        ax_zscore.set_xlim(time_array[0], time_array[-1])
        ax_zscore.set_xlabel('Time (s)')
        ax_zscore.set_ylabel('Z-score')
        ax_zscore.set_title(f'{day_name} - Fiber Z-score {wl}nm (Multi-Drug)')
        ax_zscore.legend(fontsize=8)
        ax_zscore.grid(False)
        plot_idx += 1
    
    # Row 2: Heatmaps
    # Running heatmap
    ax_running_heat = fig.add_subplot(2, num_cols, plot_idx)
    
    all_running_episodes = []
    category_boundaries = []
    
    for category in drug_categories:
        if category in data and len(data[category]['running']['episodes']) > 0:
            all_running_episodes.extend(data[category]['running']['episodes'])
            if all_running_episodes:
                category_boundaries.append(len(all_running_episodes))
    
    if all_running_episodes:
        episodes_array = np.array(all_running_episodes)
        
        if len(episodes_array) == 1:
            episodes_array = np.vstack([episodes_array[0], episodes_array[0]])
            im = ax_running_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                       extent=[time_array[0], time_array[-1], 0, 1],
                                       cmap='viridis', origin='lower')
            ax_running_heat.set_yticks(np.arange(0, 2, 1))
        else:
            im = ax_running_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                    extent=[time_array[0], time_array[-1], 0, len(episodes_array)],
                                    cmap='viridis', origin='lower')
            if len(episodes_array) <= 10:
                ax_running_heat.set_yticks(np.arange(0, len(episodes_array)+1, 1))

        ax_running_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
        
        # Draw category boundaries
        for boundary in category_boundaries[:-1]:
            ax_running_heat.axhline(y=boundary, color='k', linestyle='--', linewidth=1)
        
        ax_running_heat.set_xlabel('Time (s)')
        ax_running_heat.set_ylabel('Trials')
        ax_running_heat.set_title(f'{day_name} - Running Speed Heatmap (Multi-Drug)')
        plt.colorbar(im, ax=ax_running_heat, label='Speed (cm/s)', orientation='horizontal')
    plot_idx += 1
    
    # Fiber heatmaps
    for wl_idx, wl in enumerate(target_wavelengths):
        # dFF heatmap
        ax_dff_heat = fig.add_subplot(2, num_cols, plot_idx)
        
        all_dff_episodes = []
        category_boundaries = []
        
        for category in drug_categories:
            if category in data and wl in data[category]['dff']:
                all_dff_episodes.extend(data[category]['dff'][wl]['episodes'])
                if all_dff_episodes:
                    category_boundaries.append(len(all_dff_episodes))
        
        if all_dff_episodes:
            episodes_array = np.array(all_dff_episodes)
            
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
            
            # Draw category boundaries
            for boundary in category_boundaries[:-1]:
                ax_dff_heat.axhline(y=boundary, color='k', linestyle='--', linewidth=1)
            
            ax_dff_heat.set_xlabel('Time (s)')
            ax_dff_heat.set_ylabel('Trials')
            ax_dff_heat.set_title(f'{day_name} - Fiber ΔF/F Heatmap {wl}nm (Multi-Drug)')
            plt.colorbar(im, ax=ax_dff_heat, label='ΔF/F', orientation='horizontal')
        plot_idx += 1
        
        # Z-score heatmap
        ax_zscore_heat = fig.add_subplot(2, num_cols, plot_idx)
        
        all_zscore_episodes = []
        category_boundaries = []
        
        for category in drug_categories:
            if category in data and wl in data[category]['zscore']:
                all_zscore_episodes.extend(data[category]['zscore'][wl]['episodes'])
                if all_zscore_episodes:
                    category_boundaries.append(len(all_zscore_episodes))
        
        if all_zscore_episodes:
            episodes_array = np.array(all_zscore_episodes)
            
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
            
            # Draw category boundaries
            for boundary in category_boundaries[:-1]:
                ax_zscore_heat.axhline(y=boundary, color='k', linestyle='--', linewidth=1)
            
            ax_zscore_heat.set_xlabel('Time (s)')
            ax_zscore_heat.set_ylabel('Trials')
            ax_zscore_heat.set_title(f'{day_name} - Fiber Z-score Heatmap {wl}nm (Multi-Drug)')
            plt.colorbar(im, ax=ax_zscore_heat, label='Z-score', orientation='horizontal')
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
    
    log_message(f"Individual day plot created for {day_name} with {len(drug_categories)} drug categories")

def plot_running_optogenetics_results(results, params):
    """Plot running+optogenetics results with with/without comparison"""
    target_wavelengths = []
    for day_name, data in results.items():
        if 'target_wavelengths' in data:
            target_wavelengths = data['target_wavelengths']
            break
    
    if not target_wavelengths:
        target_wavelengths = ['470']
    
    result_window = tk.Toplevel()
    wavelength_label = '+'.join(target_wavelengths)
    result_window.title(f"Running+Optogenetics Analysis - {params['full_event_type']}")
    result_window.state('zoomed')
    result_window.configure(bg='#f8f8f8')
    
    num_wavelengths = len(target_wavelengths)
    num_cols = 1 + 2 * num_wavelengths
    
    fig = Figure(figsize=(4 * num_cols, 8), dpi=100)
    
    plot_idx = 1
    time_array = list(results.values())[0]['time']
    
    # Row 1: Traces
    # Running trace
    ax_running = fig.add_subplot(2, num_cols, plot_idx)
    for idx, (day_name, data) in enumerate(results.items()):
        day_color = DAY_COLORS[idx % len(DAY_COLORS)]
        
        # Plot with optogenetics
        if data['with_opto']['running']['mean'] is not None:
            ax_running.plot(time_array, data['with_opto']['running']['mean'],
                          color=day_color, linestyle='-', linewidth=2, alpha=1,
                          label=f"{day_name} With Opto")
            ax_running.fill_between(time_array,
                                   data['with_opto']['running']['mean'] - data['with_opto']['running']['sem'],
                                   data['with_opto']['running']['mean'] + data['with_opto']['running']['sem'],
                                   color=day_color, alpha=0.5)
        
        # Plot without optogenetics
        if data['without_opto']['running']['mean'] is not None:
            ax_running.plot(time_array, data['without_opto']['running']['mean'],
                          color=day_color, linestyle='-', linewidth=2, alpha=0.5,
                          label=f"{day_name} Without Opto")
            ax_running.fill_between(time_array,
                                   data['without_opto']['running']['mean'] - data['without_opto']['running']['sem'],
                                   data['without_opto']['running']['mean'] + data['without_opto']['running']['sem'],
                                   color=day_color, alpha=0.2)
    
    ax_running.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
    ax_running.set_xlim(time_array[0], time_array[-1])
    ax_running.set_xlabel('Time (s)')
    ax_running.set_ylabel('Speed (cm/s)')
    ax_running.set_title(f'Running Speed - {params["full_event_type"]}')
    ax_running.legend(fontsize=8)
    ax_running.grid(False)
    plot_idx += 1
    
    # Fiber traces
    for wl_idx, wl in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        
        # dFF trace
        ax_dff = fig.add_subplot(2, num_cols, plot_idx)
        for idx, (day_name, data) in enumerate(results.items()):
            day_color = DAY_COLORS[idx % len(DAY_COLORS)]
            
            # With optogenetics
            if wl in data['with_opto']['dff']:
                ax_dff.plot(time_array, data['with_opto']['dff'][wl]['mean'],
                          color=day_color, linewidth=2, linestyle='-', alpha=1,
                          label=f'{day_name} With Opto')
                ax_dff.fill_between(time_array,
                                   data['with_opto']['dff'][wl]['mean'] - data['with_opto']['dff'][wl]['sem'],
                                   data['with_opto']['dff'][wl]['mean'] + data['with_opto']['dff'][wl]['sem'],
                                   color=day_color, alpha=0.5)
            
            # Without optogenetics
            if wl in data['without_opto']['dff']:
                ax_dff.plot(time_array, data['without_opto']['dff'][wl]['mean'],
                          color=day_color, linewidth=2, linestyle='-', alpha=0.5,
                          label=f'{day_name} Without Opto')
                ax_dff.fill_between(time_array,
                                   data['without_opto']['dff'][wl]['mean'] - data['without_opto']['dff'][wl]['sem'],
                                   data['without_opto']['dff'][wl]['mean'] + data['without_opto']['dff'][wl]['sem'],
                                   color=day_color, alpha=0.2)
        
        ax_dff.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_dff.set_xlim(time_array[0], time_array[-1])
        ax_dff.set_xlabel('Time (s)')
        ax_dff.set_ylabel('ΔF/F')
        ax_dff.set_title(f'Fiber ΔF/F {wl}nm')
        ax_dff.legend(fontsize=8)
        ax_dff.grid(False)
        plot_idx += 1
        
        # Z-score trace
        ax_zscore = fig.add_subplot(2, num_cols, plot_idx)
        for idx, (day_name, data) in enumerate(results.items()):
            day_color = DAY_COLORS[idx % len(DAY_COLORS)]
            
            # With optogenetics
            if wl in data['with_opto']['zscore']:
                ax_zscore.plot(time_array, data['with_opto']['zscore'][wl]['mean'],
                             color=day_color, linewidth=2, linestyle='-', alpha=1,
                             label=f'{day_name} With Opto')
                ax_zscore.fill_between(time_array,
                                      data['with_opto']['zscore'][wl]['mean'] - data['with_opto']['zscore'][wl]['sem'],
                                      data['with_opto']['zscore'][wl]['mean'] + data['with_opto']['zscore'][wl]['sem'],
                                      color=day_color, alpha=0.5)
            
            # Without optogenetics
            if wl in data['without_opto']['zscore']:
                ax_zscore.plot(time_array, data['without_opto']['zscore'][wl]['mean'],
                             color=day_color, linewidth=2, linestyle='-', alpha=0.5,
                             label=f'{day_name} Without Opto')
                ax_zscore.fill_between(time_array,
                                      data['without_opto']['zscore'][wl]['mean'] - data['without_opto']['zscore'][wl]['sem'],
                                      data['without_opto']['zscore'][wl]['mean'] + data['without_opto']['zscore'][wl]['sem'],
                                      color=day_color, alpha=0.2)
        
        ax_zscore.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_zscore.set_xlim(time_array[0], time_array[-1])
        ax_zscore.set_xlabel('Time (s)')
        ax_zscore.set_ylabel('Z-score')
        ax_zscore.set_title(f'Fiber Z-score {wl}nm')
        ax_zscore.legend(fontsize=8)
        ax_zscore.grid(False)
        plot_idx += 1
    
    # Row 2: Heatmaps
    # Running heatmap
    ax_running_heat = fig.add_subplot(2, num_cols, plot_idx)
    all_with_opto = []
    all_without_opto = []
    
    for day_name, data in results.items():
        if len(data['with_opto']['running']['episodes']) > 0:
            all_with_opto.extend(data['with_opto']['running']['episodes'])
        if len(data['without_opto']['running']['episodes']) > 0:
            all_without_opto.extend(data['without_opto']['running']['episodes'])
    
    if all_with_opto and all_without_opto:
        combined = np.vstack([np.array(all_with_opto), np.array(all_without_opto)])
        n_with = len(all_with_opto)
        
        if len(combined) == 1:
            combined = np.vstack([combined[0], combined[0]])
            im = ax_running_heat.imshow(combined, aspect='auto', interpolation='nearest',
                                        extent=[time_array[0], time_array[-1], 0, 1],
                                        cmap='viridis', origin='lower')
            ax_running_heat.set_yticks(np.arange(0, 2, 1))
        else:
            im = ax_running_heat.imshow(combined, aspect='auto', interpolation='nearest',
                                        extent=[time_array[0], time_array[-1], 0, len(combined)],
                                        cmap='viridis', origin='lower')
            if len(combined) <= 10:
                ax_running_heat.set_yticks(np.arange(0, len(combined)+1, 1))
        
        ax_running_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
        ax_running_heat.axhline(y=n_with, color='k', linestyle='--', linewidth=1)
        ax_running_heat.set_xlabel('Time (s)')
        ax_running_heat.set_ylabel('Trials')
        ax_running_heat.set_title('Running Speed Heatmap')
        plt.colorbar(im, ax=ax_running_heat, label='Speed (cm/s)', orientation='horizontal')
    plot_idx += 1
    
    # Fiber heatmaps (similar structure for dFF and z-score)
    for wl_idx, wl in enumerate(target_wavelengths):
        # dFF heatmap
        ax_dff_heat = fig.add_subplot(2, num_cols, plot_idx)
        all_with_opto_dff = []
        all_without_opto_dff = []
        for day_name, data in results.items():
            if wl in data['with_opto']['dff']:
                all_with_opto_dff.extend(data['with_opto']['dff'][wl]['episodes'])
            if wl in data['without_opto']['dff']:
                all_without_opto_dff.extend(data['without_opto']['dff'][wl]['episodes'])
        
        if all_with_opto_dff and all_without_opto_dff:
            combined_dff = np.vstack([np.array(all_with_opto_dff), np.array(all_without_opto_dff)])
            n_with = len(all_with_opto_dff)
            if len(combined_dff) == 1:
                combined_dff = np.vstack([combined_dff[0], combined_dff[0]])
                im = ax_dff_heat.imshow(combined_dff, aspect='auto', interpolation='nearest',
                                    extent=[time_array[0], time_array[-1], 0, 1],
                                    cmap='coolwarm', origin='lower')
                ax_dff_heat.set_yticks(np.arange(0, 2, 1))
            else:
                im = ax_dff_heat.imshow(combined_dff, aspect='auto', interpolation='nearest',
                                    extent=[time_array[0], time_array[-1], 0, len(combined_dff)],
                                    cmap='coolwarm', origin='lower')
                if len(combined_dff) <= 10:
                    ax_dff_heat.set_yticks(np.arange(0, len(combined_dff)+1, 1))
            
            ax_dff_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            ax_dff_heat.axhline(y=n_with, color='k', linestyle='--', linewidth=1)
            ax_dff_heat.set_xlabel('Time (s)')
            ax_dff_heat.set_ylabel('Trials')
            ax_dff_heat.set_title(f'Fiber ΔF/F Heatmap {wl}nm')
            plt.colorbar(im, ax=ax_dff_heat, label='ΔF/F', orientation='horizontal')
        plot_idx += 1

        # Z-score heatmap
        ax_zscore_heat = fig.add_subplot(2, num_cols, plot_idx)
        all_with_opto_zscore = []
        all_without_opto_zscore = []
        for day_name, data in results.items():
            if wl in data['with_opto']['zscore']:
                all_with_opto_zscore.extend(data['with_opto']['zscore'][wl]['episodes'])
            if wl in data['without_opto']['zscore']:
                all_without_opto_zscore.extend(data['without_opto']['zscore'][wl]['episodes'])
        if all_with_opto_zscore and all_without_opto_zscore:
            combined_zscore = np.vstack([np.array(all_with_opto_zscore), np.array(all_without_opto_zscore)])
            n_with = len(all_with_opto_zscore)
            if len(combined_zscore) == 1:
                combined_zscore = np.vstack([combined_zscore[0], combined_zscore[0]])
                im = ax_zscore_heat.imshow(combined_zscore, aspect='auto', interpolation='nearest',
                                        extent=[time_array[0], time_array[-1], 0, 1],
                                        cmap='coolwarm', origin='lower')
                ax_zscore_heat.set_yticks(np.arange(0, 2, 1))
            else:
                im = ax_zscore_heat.imshow(combined_zscore, aspect='auto', interpolation='nearest',
                                        extent=[time_array[0], time_array[-1], 0, len(combined_zscore)],
                                        cmap='coolwarm', origin='lower')
                if len(combined_zscore) <= 10:
                    ax_zscore_heat.set_yticks(np.arange(0, len(combined_zscore)+1, 1))

            ax_zscore_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            ax_zscore_heat.axhline(y=n_with, color='k', linestyle='--', linewidth=1)
            ax_zscore_heat.set_xlabel('Time (s)')
            ax_zscore_heat.set_ylabel('Trials')
            ax_zscore_heat.set_title(f'Fiber Z-score Heatmap {wl}nm')
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
    
    # Create individual day windows
    create_individual_day_windows_running_optogenetics(results, params)

def create_individual_day_windows_running_optogenetics(results, params):
    """Create individual windows for each day - running+optogenetics"""
    for day_name, data in results.items():
        create_single_day_window_running_optogenetics(day_name, data, params)

def create_single_day_window_running_optogenetics(day_name, data, params):
    """Create window for a single day - running+optogenetics"""
    day_window = tk.Toplevel()
    
    target_wavelengths = data.get('target_wavelengths', ['470'])
    wavelength_label = '+'.join(target_wavelengths)
    
    day_window.title(f"Running+Optogenetics Analysis - {day_name} - {params['full_event_type']}")
    day_window.state("zoomed")
    day_window.configure(bg='#f8f8f8')
    
    num_wavelengths = len(target_wavelengths)
    num_cols = 1 + 2 * num_wavelengths
    fig = Figure(figsize=(4 * num_cols, 8), dpi=100)
    
    plot_idx = 1
    time_array = data['time']
    
    # Row 1: Traces
    # Running trace
    ax_running = fig.add_subplot(2, num_cols, plot_idx)
    
    # Plot with optogenetics
    if data['with_opto']['running']['mean'] is not None:
        ax_running.plot(time_array, data['with_opto']['running']['mean'],
                      color="#000000", linewidth=2, linestyle='-', alpha=1, label='With Opto')
        ax_running.fill_between(time_array,
                               data['with_opto']['running']['mean'] - data['with_opto']['running']['sem'],
                               data['with_opto']['running']['mean'] + data['with_opto']['running']['sem'],
                               color="#000000", alpha=0.5)
    
    # Plot without optogenetics
    if data['without_opto']['running']['mean'] is not None:
        ax_running.plot(time_array, data['without_opto']['running']['mean'],
                      color="#000000", linewidth=2, linestyle='-', alpha=0.5, label='Without Opto')
        ax_running.fill_between(time_array,
                               data['without_opto']['running']['mean'] - data['without_opto']['running']['sem'],
                               data['without_opto']['running']['mean'] + data['without_opto']['running']['sem'],
                               color="#000000", alpha=0.2)
    
    ax_running.axvline(x=0, color='#808080', linestyle='--', alpha=0.8, label='Event')
    ax_running.set_xlim(time_array[0], time_array[-1])
    ax_running.set_xlabel('Time (s)')
    ax_running.set_ylabel('Speed (cm/s)')
    ax_running.set_title(f'{day_name} - Running Speed')
    ax_running.legend()
    ax_running.grid(False)
    plot_idx += 1
    
    # Fiber traces
    for wl_idx, wl in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        
        # dFF trace
        ax_dff = fig.add_subplot(2, num_cols, plot_idx)
        
        # With optogenetics
        if wl in data['with_opto']['dff']:
            ax_dff.plot(time_array, data['with_opto']['dff'][wl]['mean'],
                      color=color, linewidth=2, linestyle='-', alpha=1, label='With Opto')
            ax_dff.fill_between(time_array,
                               data['with_opto']['dff'][wl]['mean'] - data['with_opto']['dff'][wl]['sem'],
                               data['with_opto']['dff'][wl]['mean'] + data['with_opto']['dff'][wl]['sem'],
                               color=color, alpha=0.5)
        
        # Without optogenetics
        if wl in data['without_opto']['dff']:
            ax_dff.plot(time_array, data['without_opto']['dff'][wl]['mean'],
                      color=color, linewidth=2, linestyle='-', alpha=0.5, label='Without Opto')
            ax_dff.fill_between(time_array,
                               data['without_opto']['dff'][wl]['mean'] - data['without_opto']['dff'][wl]['sem'],
                               data['without_opto']['dff'][wl]['mean'] + data['without_opto']['dff'][wl]['sem'],
                               color=color, alpha=0.2)
        
        ax_dff.axvline(x=0, color='#808080', linestyle='--', alpha=0.8, label='Event')
        ax_dff.set_xlim(time_array[0], time_array[-1])
        ax_dff.set_xlabel('Time (s)')
        ax_dff.set_ylabel('ΔF/F')
        ax_dff.set_title(f'{day_name} - Fiber ΔF/F {wl}nm')
        ax_dff.legend()
        ax_dff.grid(False)
        plot_idx += 1
        
        # Z-score trace
        ax_zscore = fig.add_subplot(2, num_cols, plot_idx)
        
        # With optogenetics
        if wl in data['with_opto']['zscore']:
            ax_zscore.plot(time_array, data['with_opto']['zscore'][wl]['mean'],
                         color=color, linewidth=2, linestyle='-', alpha=1, label='With Opto')
            ax_zscore.fill_between(time_array,
                                  data['with_opto']['zscore'][wl]['mean'] - data['with_opto']['zscore'][wl]['sem'],
                                  data['with_opto']['zscore'][wl]['mean'] + data['with_opto']['zscore'][wl]['sem'],
                                  color=color, alpha=0.5)
        
        # Without optogenetics
        if wl in data['without_opto']['zscore']:
            ax_zscore.plot(time_array, data['without_opto']['zscore'][wl]['mean'],
                         color=color, linewidth=2, linestyle='-', alpha=0.5, label='Without Opto')
            ax_zscore.fill_between(time_array,
                                  data['without_opto']['zscore'][wl]['mean'] - data['without_opto']['zscore'][wl]['sem'],
                                  data['without_opto']['zscore'][wl]['mean'] + data['without_opto']['zscore'][wl]['sem'],
                                  color=color, alpha=0.2)
        
        ax_zscore.axvline(x=0, color='#808080', linestyle='--', alpha=0.8, label='Event')
        ax_zscore.set_xlim(time_array[0], time_array[-1])
        ax_zscore.set_xlabel('Time (s)')
        ax_zscore.set_ylabel('Z-score')
        ax_zscore.set_title(f'{day_name} - Fiber Z-score {wl}nm')
        ax_zscore.legend()
        ax_zscore.grid(False)
        plot_idx += 1
    
    # Row 2: Heatmaps
    # Running heatmap
    ax_running_heat = fig.add_subplot(2, num_cols, plot_idx)
    
    if (len(data['with_opto']['running']['episodes']) > 0 and 
        len(data['without_opto']['running']['episodes']) > 0):
        
        # Combine with and without opto episodes
        combined = np.vstack([
            data['with_opto']['running']['episodes'], 
            data['without_opto']['running']['episodes']
        ])
        n_with_opto = len(data['with_opto']['running']['episodes'])
        
        if len(combined) == 1:
            combined = np.vstack([combined[0], combined[0]])
            im = ax_running_heat.imshow(combined, aspect='auto', interpolation='nearest',
                                    extent=[time_array[0], time_array[-1], 0, 1],
                                    cmap='viridis', origin='lower')
            ax_running_heat.set_yticks(np.arange(0, 2, 1))
        else:
            im = ax_running_heat.imshow(combined, aspect='auto', interpolation='nearest',
                                    extent=[time_array[0], time_array[-1], 0, len(combined)],
                                    cmap='viridis', origin='lower')
            if len(combined) <= 10:
                ax_running_heat.set_yticks(np.arange(0, len(combined)+1, 1))
        
        ax_running_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
        ax_running_heat.axhline(y=n_with_opto, color='k', linestyle='--', linewidth=1)
        ax_running_heat.set_xlabel('Time (s)')
        ax_running_heat.set_ylabel('Trials')
        ax_running_heat.set_title(f'{day_name} - Running Speed Heatmap')
        plt.colorbar(im, ax=ax_running_heat, label='Speed (cm/s)', orientation='horizontal')
    else:
        # Show message if no data
        ax_running_heat.text(0.5, 0.5, 'No running data available',
                           ha='center', va='center', transform=ax_running_heat.transAxes,
                           fontsize=12, color='#666666')
        ax_running_heat.set_title(f'{day_name} - Running Speed Heatmap')
        ax_running_heat.axis('off')
    
    plot_idx += 1
    
    # Fiber heatmaps
    for wl_idx, wl in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        
        # dFF heatmap
        ax_dff_heat = fig.add_subplot(2, num_cols, plot_idx)
        
        if (wl in data['with_opto']['dff'] and wl in data['without_opto']['dff'] and
            len(data['with_opto']['dff'][wl]['episodes']) > 0 and 
            len(data['without_opto']['dff'][wl]['episodes']) > 0):
            
            # Combine with and without opto episodes
            combined = np.vstack([
                data['with_opto']['dff'][wl]['episodes'], 
                data['without_opto']['dff'][wl]['episodes']
            ])
            n_with_opto = len(data['with_opto']['dff'][wl]['episodes'])
            
            if len(combined) == 1:
                combined = np.vstack([combined[0], combined[0]])
                im = ax_dff_heat.imshow(combined, aspect='auto', interpolation='nearest',
                                    extent=[time_array[0], time_array[-1], 0, 1],
                                    cmap='coolwarm', origin='lower')
                ax_dff_heat.set_yticks(np.arange(0, 2, 1))
            else:
                im = ax_dff_heat.imshow(combined, aspect='auto', interpolation='nearest',
                                    extent=[time_array[0], time_array[-1], 0, len(combined)],
                                    cmap='coolwarm', origin='lower')
                if len(combined) <= 10:
                    ax_dff_heat.set_yticks(np.arange(0, len(combined)+1, 1))
            
            ax_dff_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            ax_dff_heat.axhline(y=n_with_opto, color='k', linestyle='--', linewidth=1)
            ax_dff_heat.set_xlabel('Time (s)')
            ax_dff_heat.set_ylabel('Trials')
            ax_dff_heat.set_title(f'{day_name} - Fiber ΔF/F Heatmap {wl}nm')
            plt.colorbar(im, ax=ax_dff_heat, label='ΔF/F', orientation='horizontal')
        else:
            # Show message if no data
            ax_dff_heat.text(0.5, 0.5, f'No dFF data for {wl}nm',
                           ha='center', va='center', transform=ax_dff_heat.transAxes,
                           fontsize=12, color='#666666')
            ax_dff_heat.set_title(f'{day_name} - Fiber ΔF/F Heatmap {wl}nm')
            ax_dff_heat.axis('off')
        
        plot_idx += 1
        
        # Z-score heatmap
        ax_zscore_heat = fig.add_subplot(2, num_cols, plot_idx)
        
        if (wl in data['with_opto']['zscore'] and wl in data['without_opto']['zscore'] and
            len(data['with_opto']['zscore'][wl]['episodes']) > 0 and 
            len(data['without_opto']['zscore'][wl]['episodes']) > 0):
            
            # Combine with and without opto episodes
            combined = np.vstack([
                data['with_opto']['zscore'][wl]['episodes'], 
                data['without_opto']['zscore'][wl]['episodes']
            ])
            n_with_opto = len(data['with_opto']['zscore'][wl]['episodes'])
            
            if len(combined) == 1:
                combined = np.vstack([combined[0], combined[0]])
                im = ax_zscore_heat.imshow(combined, aspect='auto', interpolation='nearest',
                                        extent=[time_array[0], time_array[-1], 0, 1],
                                        cmap='coolwarm', origin='lower')
                ax_zscore_heat.set_yticks(np.arange(0, 2, 1))
            else:
                im = ax_zscore_heat.imshow(combined, aspect='auto', interpolation='nearest',
                                        extent=[time_array[0], time_array[-1], 0, len(combined)],
                                        cmap='coolwarm', origin='lower')
                if len(combined) <= 10:
                    ax_zscore_heat.set_yticks(np.arange(0, len(combined)+1, 1))
            
            ax_zscore_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            ax_zscore_heat.axhline(y=n_with_opto, color='k', linestyle='--', linewidth=1)
            ax_zscore_heat.set_xlabel('Time (s)')
            ax_zscore_heat.set_ylabel('Trials')
            ax_zscore_heat.set_title(f'{day_name} - Fiber Z-score Heatmap {wl}nm')
            plt.colorbar(im, ax=ax_zscore_heat, label='Z-score', orientation='horizontal')
        else:
            # Show message if no data
            ax_zscore_heat.text(0.5, 0.5, f'No z-score data for {wl}nm',
                              ha='center', va='center', transform=ax_zscore_heat.transAxes,
                              fontsize=12, color='#666666')
            ax_zscore_heat.set_title(f'{day_name} - Fiber Z-score Heatmap {wl}nm')
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
    
    log_message(f"Individual day plot created for {day_name} (with/without optogenetics)")

def run_running_optogenetics_analysis(day_data, params, all_optogenetic_events, 
                                     power_values, all_drug_events, analysis_mode):
    """Run running+optogenetics analysis"""
    log_message(f"Starting running+optogenetics analysis for {len(day_data)} day(s)...")
    
    results = {}
    all_statistics = []
    
    for day_name, animals in day_data.items():
        log_message(f"Analyzing {day_name} with {len(animals)} animal(s)...")
        
        if analysis_mode == "running+optogenetics+drug":
            # Drug mode
            day_result, day_stats = analyze_day_running_optogenetics_drug(
                day_name, animals, params, all_optogenetic_events, 
                power_values, all_drug_events
            )
        else:
            # No drug mode
            day_result, day_stats = analyze_day_running_optogenetics(
                day_name, animals, params, all_optogenetic_events, power_values
            )
        
        if day_result:
            results[day_name] = day_result
        if day_stats:
            all_statistics.extend(day_stats)
    
    if params['export_stats'] and all_statistics:
        export_type = "running_opto_drug_induced" if analysis_mode == "running+optogenetics+drug" else "running_opto_induced"
        export_statistics(all_statistics, export_type, params['full_event_type'])
    
    if results:
        if analysis_mode == "running+optogenetics+drug":
            plot_running_optogenetics_drug_results(results, params)
        else:
            plot_running_optogenetics_results(results, params)
        log_message("Analysis completed successfully")
    else:
        log_message("No valid results", "ERROR")

def analyze_day_running_optogenetics_drug(day_name, animals, params, 
                                          all_optogenetic_events, power_values, all_drug_events):
    """Analyze one day for running+optogenetics+drug mode with multiple drugs"""
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
    
    # Load drug name config
    config_path = os.path.join(os.path.dirname(__file__), 'drug_name_config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            drug_name_config = json.load(f)
    else:
        drug_name_config = {}
    
    # Collect all unique drug categories
    all_drug_categories = set()
    
    # Initialize dynamic storage for conditions
    # Format: {category: {with_opto: {...}, without_opto: {...}}}
    conditions = {}
    
    statistics_rows = []
    
    # Process each animal
    for animal_data in animals:
        try:
            animal_id = animal_data.get('animal_single_channel_id', 'Unknown')
            
            # Check if animal has optogenetic events
            if animal_id not in all_optogenetic_events:
                log_message(f"No optogenetic events for {animal_id}", "WARNING")
                continue
            
            # Get optogenetic sessions
            opto_sessions = all_optogenetic_events[animal_id]
            if not opto_sessions:
                continue
            
            # Use first session
            opto_session = opto_sessions[0]
            
            # Get drug sessions
            drug_sessions = identify_drug_sessions(animal_data['fiber_events'])
            
            if not drug_sessions:
                log_message(f"No drug events for {animal_id}", "WARNING")
                continue
            
            # Get drug names and times
            drug_info = []
            for idx, session_info in enumerate(drug_sessions):
                session_id = f"{animal_id}_Session{idx+1}"
                drug_name = drug_name_config.get(session_id, f"Drug{idx+1}")
                drug_time = session_info['time']
                drug_info.append({'name': drug_name, 'time': drug_time, 'idx': idx})
            
            # Sort by time
            drug_info.sort(key=lambda x: x['time'])
            
            # Get running events
            running_events = get_events_from_bouts(animal_data, params['full_event_type'], duration=True)
            if not running_events:
                log_message(f"No running events for {animal_id}", "WARNING")
                continue
            
            # Classify running events by drug category
            event_categories = {}
            
            for start, end in running_events:
                # Determine drug category
                if start < drug_info[0]['time']:
                    category = 'baseline'
                else:
                    # Find which drug period
                    for i in range(len(drug_info) - 1, -1, -1):
                        if start >= drug_info[i]['time']:
                            if i == 0:
                                category = drug_info[0]['name']
                            else:
                                previous_drugs = ' + '.join([d['name'] for d in drug_info[:i]])
                                category = f"{drug_info[i]['name']} after {previous_drugs}"
                            break
                
                if category not in event_categories:
                    event_categories[category] = []
                event_categories[category].append((start, end))
                all_drug_categories.add(category)
            
            # For each category, further divide by with/without opto
            for category, category_events in event_categories.items():
                with_opto, without_opto = get_events_within_optogenetic(
                    opto_session, category_events, params['full_event_type']
                )
                
                # Initialize category storage if needed
                if category not in conditions:
                    conditions[category] = {
                        'with_opto': {
                            'running': [],
                            'dff': {wl: [] for wl in target_wavelengths},
                            'zscore': {wl: [] for wl in target_wavelengths}
                        },
                        'without_opto': {
                            'running': [],
                            'dff': {wl: [] for wl in target_wavelengths},
                            'zscore': {wl: [] for wl in target_wavelengths}
                        }
                    }
                
                # Get data
                ast2_data = animal_data.get('ast2_data_adjusted')
                if not ast2_data:
                    continue
                
                running_timestamps = ast2_data['data']['timestamps']
                processed_data = animal_data.get('running_processed_data')
                running_speed = processed_data['filtered_speed'] if processed_data else ast2_data['data']['speed']
                
                preprocessed_data = animal_data.get('preprocessed_data')
                if preprocessed_data is None or preprocessed_data.empty:
                    continue
                
                channels = animal_data.get('channels', {})
                time_col = channels['time']
                fiber_timestamps = preprocessed_data[time_col].values
                dff_data = animal_data.get('dff_data', {})
                active_channels = animal_data.get('active_channels', [])
                
                # Process with opto events
                if with_opto:
                    with_result = calculate_running_episodes(
                        with_opto, running_timestamps, running_speed,
                        fiber_timestamps, dff_data,
                        active_channels, target_wavelengths,
                        params['pre_time'], params['post_time'],
                        params['baseline_start'], params['baseline_end']
                    )
                    
                    if len(with_result['running']) > 0:
                        conditions[category]['with_opto']['running'].extend(with_result['running'])
                    
                    for wl in target_wavelengths:
                        if wl in with_result['dff']:
                            conditions[category]['with_opto']['dff'][wl].extend(with_result['dff'][wl])
                        if wl in with_result['zscore']:
                            conditions[category]['with_opto']['zscore'][wl].extend(with_result['zscore'][wl])
                    
                    # Collect statistics
                    if params['export_stats'] and len(with_result['running']) > 0:
                        stats = collect_statistics_with_condition(
                            day_name, f"{animal_id}_{category}_with_opto", 
                            params['full_event_type'],
                            with_result, time_array, params, target_wavelengths, 
                            active_channels, f"{category}_with_opto"
                        )
                        statistics_rows.extend(stats)
                
                # Process without opto events
                if without_opto:
                    without_result = calculate_running_episodes(
                        without_opto, running_timestamps, running_speed,
                        fiber_timestamps, dff_data,
                        active_channels, target_wavelengths,
                        params['pre_time'], params['post_time'],
                        params['baseline_start'], params['baseline_end']
                    )
                    
                    if len(without_result['running']) > 0:
                        conditions[category]['without_opto']['running'].extend(without_result['running'])
                    
                    for wl in target_wavelengths:
                        if wl in without_result['dff']:
                            conditions[category]['without_opto']['dff'][wl].extend(without_result['dff'][wl])
                        if wl in without_result['zscore']:
                            conditions[category]['without_opto']['zscore'][wl].extend(without_result['zscore'][wl])
                    
                    # Collect statistics
                    if params['export_stats'] and len(without_result['running']) > 0:
                        stats = collect_statistics_with_condition(
                            day_name, f"{animal_id}_{category}_without_opto",
                            params['full_event_type'],
                            without_result, time_array, params, target_wavelengths, 
                            active_channels, f"{category}_without_opto"
                        )
                        statistics_rows.extend(stats)
        
        except Exception as e:
            log_message(f"Error analyzing {animal_id}: {str(e)}", "ERROR")
            continue
    
    # Build result structure
    result = {
        'time': time_array,
        'target_wavelengths': target_wavelengths,
        'drug_categories': list(all_drug_categories)
    }
    
    # Process each category
    for category in list(all_drug_categories):
        if category in conditions:
            result[category] = {}
            
            for opto_condition in ['with_opto', 'without_opto']:
                condition_data = conditions[category][opto_condition]
                
                result[category][opto_condition] = {
                    'running': {
                        'episodes': np.array(condition_data['running']) if condition_data['running'] else np.array([]),
                        'mean': np.nanmean(condition_data['running'], axis=0) if condition_data['running'] else None,
                        'sem': np.nanstd(condition_data['running'], axis=0) / np.sqrt(len(condition_data['running'])) if condition_data['running'] else None
                    },
                    'dff': {},
                    'zscore': {}
                }
                
                for wl in target_wavelengths:
                    if condition_data['dff'][wl]:
                        episodes_array = np.array(condition_data['dff'][wl])
                        result[category][opto_condition]['dff'][wl] = {
                            'episodes': episodes_array,
                            'mean': np.nanmean(episodes_array, axis=0),
                            'sem': np.nanstd(episodes_array, axis=0) / np.sqrt(len(condition_data['dff'][wl]))
                        }
                    
                    if condition_data['zscore'][wl]:
                        episodes_array = np.array(condition_data['zscore'][wl])
                        result[category][opto_condition]['zscore'][wl] = {
                            'episodes': episodes_array,
                            'mean': np.nanmean(episodes_array, axis=0),
                            'sem': np.nanstd(episodes_array, axis=0) / np.sqrt(len(condition_data['zscore'][wl]))
                        }
    
    return result, statistics_rows if params['export_stats'] else None

def collect_statistics_with_condition(day_name, animal_id, event_type, result, 
                                      time_array, params, target_wavelengths, 
                                      active_channels, condition):
    """Collect statistics with condition label"""
    rows = []
    pre_mask = (time_array >= -params['pre_time']) & (time_array <= 0)
    post_mask = (time_array >= 0) & (time_array <= params['post_time'])
    
    # Running statistics
    for trial_idx, episode_data in enumerate(result['running']):
        pre_data = episode_data[pre_mask]
        post_data = episode_data[post_mask]
        
        rows.append({
            'day': day_name,
            'animal_single_channel_id': animal_id,
            'event_type': event_type,
            'channel': 'running_speed',
            'wavelength': 'N/A',
            'trial': trial_idx + 1,
            'condition': condition,
            'pre_min': np.min(pre_data) if len(pre_data) > 0 else np.nan,
            'pre_max': np.max(pre_data) if len(pre_data) > 0 else np.nan,
            'pre_mean': np.mean(pre_data) if len(pre_data) > 0 else np.nan,
            'pre_area': np.trapz(pre_data, time_array[pre_mask]) if len(pre_data) > 0 else np.nan,
            'post_min': np.min(post_data) if len(post_data) > 0 else np.nan,
            'post_max': np.max(post_data) if len(post_data) > 0 else np.nan,
            'post_mean': np.mean(post_data) if len(post_data) > 0 else np.nan,
            'post_area': np.trapz(post_data, time_array[post_mask]) if len(post_data) > 0 else np.nan,
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
                        'day': day_name,
                        'animal_single_channel_id': animal_id,
                        'event_type': event_type,
                        'channel': channel,
                        'wavelength': wl,
                        'trial': trial_idx + 1,
                        'condition': condition,
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
                        'baseline_end': params['baseline_end']
                    })
            # Z-score
            if wl in result['zscore']:
                for trial_idx, episode_data in enumerate(result['zscore'][wl]):
                    pre_data = episode_data[pre_mask]
                    post_data = episode_data[post_mask]
                    
                    rows.append({
                        'day': day_name,
                        'animal_single_channel_id': animal_id,
                        'event_type': event_type,
                        'channel': channel,
                        'wavelength': wl,
                        'trial': trial_idx + 1,
                        'condition': condition,
                        'pre_min': np.min(pre_data) if len(pre_data) > 0 else np.nan,
                        'pre_max': np.max(pre_data) if len(pre_data) > 0 else np.nan,
                        'pre_mean': np.mean(pre_data) if len(pre_data) > 0 else np.nan,
                        'pre_area': np.trapz(pre_data, time_array[pre_mask]) if len(pre_data) > 0 else np.nan,
                        'post_min': np.min(post_data) if len(post_data) > 0 else np.nan,
                        'post_max': np.max(post_data) if len(post_data) > 0 else np.nan,
                        'post_mean': np.mean(post_data) if len(post_data) > 0 else np.nan,
                        'post_area': np.trapz(post_data, time_array[post_mask]) if len(post_data) > 0 else np.nan,
                        'signal_type': 'fiber_zscore',
                        'baseline_start': params['baseline_start'],
                        'baseline_end': params['baseline_end']
                    })
                    
    return rows

def plot_running_optogenetics_drug_results(results, params):
    """Plot running+optogenetics+drug results with multiple drug categories"""
    
    # Get all drug categories
    all_categories = set()
    for day_name, data in results.items():
        if 'drug_categories' in data:
            all_categories.update(data['drug_categories'])
    all_categories = list(all_categories)
    
    # Create comparison windows for each meaningful comparison
    # 1. Within each category: with vs without opto
    for category in all_categories:
        plot_comparison_window_multi_drug(
            results, params,
            category, 'with_opto', 'without_opto',
            f'{category}: With vs Without Optogenetics',
            'With Opto', 'Without Opto'
        )
    
    # 2. With opto across categories
    plot_comparison_window_multi_drug_categories(
        results, params, 'with_opto',
        all_categories,
        'With Optogenetics: Across Drug Categories'
    )
    
    # 3. Without opto across categories
    plot_comparison_window_multi_drug_categories(
        results, params, 'without_opto',
        all_categories,
        'Without Optogenetics: Across Drug Categories'
    )
    
    # Create individual day windows
    create_individual_day_windows_running_optogenetics_drug_multi(results, params)

def plot_comparison_window_multi_drug(results, params, category, condition1_key, condition2_key, 
                                      window_title, label1, label2):
    target_wavelengths = []
    for day_name, data in results.items():
        if 'target_wavelengths' in data:
            target_wavelengths = data['target_wavelengths']
            break
    
    if not target_wavelengths:
        target_wavelengths = ['470']
    
    result_window = tk.Toplevel()
    result_window.title(f"{window_title} - All Days")
    result_window.state('zoomed')
    result_window.configure(bg='#f8f8f8')
    
    num_wavelengths = len(target_wavelengths)
    num_cols = 1 + 2 * num_wavelengths
    
    fig = Figure(figsize=(4 * num_cols, 8), dpi=100)
    
    plot_idx = 1
    time_array = list(results.values())[0]['time']
    
    ax_running = fig.add_subplot(2, num_cols, plot_idx)
    
    for idx, (day_name, data) in enumerate(results.items()):
        if category not in data:
            continue
            
        day_color = DAY_COLORS[idx % len(DAY_COLORS)]
        category_data = data[category]
        
        if condition1_key in category_data and category_data[condition1_key]['running']['mean'] is not None:
            ax_running.plot(time_array, category_data[condition1_key]['running']['mean'],
                          color=day_color, linestyle='-', linewidth=2, alpha=1,
                          label=f"{day_name} {label1}")
            ax_running.fill_between(time_array,
                                   category_data[condition1_key]['running']['mean'] - category_data[condition1_key]['running']['sem'],
                                   category_data[condition1_key]['running']['mean'] + category_data[condition1_key]['running']['sem'],
                                   color=day_color, alpha=0.5)
        
        if condition2_key in category_data and category_data[condition2_key]['running']['mean'] is not None:
            ax_running.plot(time_array, category_data[condition2_key]['running']['mean'],
                          color=day_color, linestyle='-', linewidth=2, alpha=0.5,
                          label=f"{day_name} {label2}")
            ax_running.fill_between(time_array,
                                   category_data[condition2_key]['running']['mean'] - category_data[condition2_key]['running']['sem'],
                                   category_data[condition2_key]['running']['mean'] + category_data[condition2_key]['running']['sem'],
                                   color=day_color, alpha=0.2)
    
    ax_running.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
    ax_running.set_xlim(time_array[0], time_array[-1])
    ax_running.set_xlabel('Time (s)')
    ax_running.set_ylabel('Speed (cm/s)')
    ax_running.set_title(f'{category} - Running Speed Comparison')
    ax_running.legend(fontsize=8, ncol=2)
    ax_running.grid(False)
    plot_idx += 1
    
    for wl_idx, wl in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        
        # dFF
        ax_dff = fig.add_subplot(2, num_cols, plot_idx)
        
        for idx, (day_name, data) in enumerate(results.items()):
            if category not in data:
                continue
                
            day_color = DAY_COLORS[idx % len(DAY_COLORS)]
            category_data = data[category]
            
            if condition1_key in category_data and wl in category_data[condition1_key]['dff']:
                ax_dff.plot(time_array, category_data[condition1_key]['dff'][wl]['mean'],
                          color=day_color, linewidth=2, linestyle='-', alpha=1,
                          label=f'{day_name} {label1}')
                ax_dff.fill_between(time_array,
                                   category_data[condition1_key]['dff'][wl]['mean'] - category_data[condition1_key]['dff'][wl]['sem'],
                                   category_data[condition1_key]['dff'][wl]['mean'] + category_data[condition1_key]['dff'][wl]['sem'],
                                   color=day_color, alpha=0.5)
            
            if condition2_key in category_data and wl in category_data[condition2_key]['dff']:
                ax_dff.plot(time_array, category_data[condition2_key]['dff'][wl]['mean'],
                          color=day_color, linewidth=2, linestyle='-', alpha=0.5,
                          label=f'{day_name} {label2}')
                ax_dff.fill_between(time_array,
                                   category_data[condition2_key]['dff'][wl]['mean'] - category_data[condition2_key]['dff'][wl]['sem'],
                                   category_data[condition2_key]['dff'][wl]['mean'] + category_data[condition2_key]['dff'][wl]['sem'],
                                   color=day_color, alpha=0.2)
        
        ax_dff.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_dff.set_xlim(time_array[0], time_array[-1])
        ax_dff.set_xlabel('Time (s)')
        ax_dff.set_ylabel('ΔF/F')
        ax_dff.set_title(f'{category} - Fiber ΔF/F {wl}nm Comparison')
        ax_dff.legend(fontsize=8, ncol=2)
        ax_dff.grid(False)
        plot_idx += 1
        
        # Z-score
        ax_zscore = fig.add_subplot(2, num_cols, plot_idx)
        
        for idx, (day_name, data) in enumerate(results.items()):
            if category not in data:
                continue
                
            day_color = DAY_COLORS[idx % len(DAY_COLORS)]
            category_data = data[category]
            
            if condition1_key in category_data and wl in category_data[condition1_key]['zscore']:
                ax_zscore.plot(time_array, category_data[condition1_key]['zscore'][wl]['mean'],
                             color=day_color, linewidth=2, linestyle='-', alpha=1,
                             label=f'{day_name} {label1}')
                ax_zscore.fill_between(time_array,
                                      category_data[condition1_key]['zscore'][wl]['mean'] - category_data[condition1_key]['zscore'][wl]['sem'],
                                      category_data[condition1_key]['zscore'][wl]['mean'] + category_data[condition1_key]['zscore'][wl]['sem'],
                                      color=day_color, alpha=0.5)
            
            if condition2_key in category_data and wl in category_data[condition2_key]['zscore']:
                ax_zscore.plot(time_array, category_data[condition2_key]['zscore'][wl]['mean'],
                             color=day_color, linewidth=2, linestyle='-', alpha=0.5,
                             label=f'{day_name} {label2}')
                ax_zscore.fill_between(time_array,
                                      category_data[condition2_key]['zscore'][wl]['mean'] - category_data[condition2_key]['zscore'][wl]['sem'],
                                      category_data[condition2_key]['zscore'][wl]['mean'] + category_data[condition2_key]['zscore'][wl]['sem'],
                                      color=day_color, alpha=0.2)
        
        ax_zscore.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_zscore.set_xlim(time_array[0], time_array[-1])
        ax_zscore.set_xlabel('Time (s)')
        ax_zscore.set_ylabel('Z-score')
        ax_zscore.set_title(f'{category} - Fiber Z-score {wl}nm Comparison')
        ax_zscore.legend(fontsize=8, ncol=2)
        ax_zscore.grid(False)
        plot_idx += 1
    
    ax_running_heat = fig.add_subplot(2, num_cols, plot_idx)
    
    all_cond1 = []
    all_cond2 = []
    
    for day_name, data in results.items():
        if category not in data:
            continue
            
        category_data = data[category]
        
        if condition1_key in category_data and len(category_data[condition1_key]['running']['episodes']) > 0:
            all_cond1.extend(category_data[condition1_key]['running']['episodes'])
        
        if condition2_key in category_data and len(category_data[condition2_key]['running']['episodes']) > 0:
            all_cond2.extend(category_data[condition2_key]['running']['episodes'])
    
    if all_cond1 or all_cond2:
        combined = []
        if all_cond1:
            combined.extend(all_cond1)
        if all_cond2:
            combined.extend(all_cond2)
        
        if combined:
            combined = np.array(combined)
            n_cond1 = len(all_cond1)
            
            if len(combined) == 1:
                combined = np.vstack([combined[0], combined[0]])
                im = ax_running_heat.imshow(combined, aspect='auto', interpolation='nearest',
                                          extent=[time_array[0], time_array[-1], 0, 1],
                                          cmap='viridis', origin='lower')
            else:
                im = ax_running_heat.imshow(combined, aspect='auto', interpolation='nearest',
                                          extent=[time_array[0], time_array[-1], 0, len(combined)],
                                          cmap='viridis', origin='lower')
                if len(combined) <= 10:
                    ax_running_heat.set_yticks(np.arange(0, len(combined)+1, 1))
            
            ax_running_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            if n_cond1 > 0 and len(combined) > n_cond1:
                ax_running_heat.axhline(y=n_cond1, color='k', linestyle='--', linewidth=1)
            
            ax_running_heat.set_xlabel('Time (s)')
            ax_running_heat.set_ylabel('Trials')
            ax_running_heat.set_title(f'{category} - Running Speed Heatmap')
            plt.colorbar(im, ax=ax_running_heat, label='Speed (cm/s)', orientation='horizontal')
        else:
            ax_running_heat.text(0.5, 0.5, 'No data available', 
                               ha='center', va='center', fontsize=12, color='gray')
            ax_running_heat.set_title(f'{category} - Running Speed Heatmap')
            ax_running_heat.axis('off')
    else:
        ax_running_heat.text(0.5, 0.5, 'No data available', 
                           ha='center', va='center', fontsize=12, color='gray')
        ax_running_heat.set_title(f'{category} - Running Speed Heatmap')
        ax_running_heat.axis('off')
    
    plot_idx += 1
    
    for wl_idx, wl in enumerate(target_wavelengths):
        # dFF
        ax_dff_heat = fig.add_subplot(2, num_cols, plot_idx)
        
        all_cond1_dff = []
        all_cond2_dff = []
        
        for day_name, data in results.items():
            if category not in data:
                continue
                
            category_data = data[category]
            
            if condition1_key in category_data and wl in category_data[condition1_key]['dff']:
                all_cond1_dff.extend(category_data[condition1_key]['dff'][wl]['episodes'])
            
            if condition2_key in category_data and wl in category_data[condition2_key]['dff']:
                all_cond2_dff.extend(category_data[condition2_key]['dff'][wl]['episodes'])
        
        if all_cond1_dff or all_cond2_dff:
            combined_dff = []
            if all_cond1_dff:
                combined_dff.extend(all_cond1_dff)
            if all_cond2_dff:
                combined_dff.extend(all_cond2_dff)
            
            if combined_dff:
                combined_dff = np.array(combined_dff)
                n_cond1 = len(all_cond1_dff)
                
                if len(combined_dff) == 1:
                    combined_dff = np.vstack([combined_dff[0], combined_dff[0]])
                    im = ax_dff_heat.imshow(combined_dff, aspect='auto', interpolation='nearest',
                                          extent=[time_array[0], time_array[-1], 0, 1],
                                          cmap='coolwarm', origin='lower')
                else:
                    im = ax_dff_heat.imshow(combined_dff, aspect='auto', interpolation='nearest',
                                          extent=[time_array[0], time_array[-1], 0, len(combined_dff)],
                                          cmap='coolwarm', origin='lower')
                    if len(combined_dff) <= 10:
                        ax_dff_heat.set_yticks(np.arange(0, len(combined_dff)+1, 1))
                
                ax_dff_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
                if n_cond1 > 0 and len(combined_dff) > n_cond1:
                    ax_dff_heat.axhline(y=n_cond1, color='k', linestyle='--', linewidth=1)
                
                ax_dff_heat.set_xlabel('Time (s)')
                ax_dff_heat.set_ylabel('Trials')
                ax_dff_heat.set_title(f'{category} - Fiber ΔF/F Heatmap {wl}nm')
                plt.colorbar(im, ax=ax_dff_heat, label='ΔF/F', orientation='horizontal')
            else:
                ax_dff_heat.text(0.5, 0.5, 'No data available', 
                               ha='center', va='center', fontsize=12, color='gray')
                ax_dff_heat.set_title(f'{category} - Fiber ΔF/F Heatmap {wl}nm')
                ax_dff_heat.axis('off')
        else:
            ax_dff_heat.text(0.5, 0.5, 'No data available', 
                           ha='center', va='center', fontsize=12, color='gray')
            ax_dff_heat.set_title(f'{category} - Fiber ΔF/F Heatmap {wl}nm')
            ax_dff_heat.axis('off')
        
        plot_idx += 1
        
        ax_zscore_heat = fig.add_subplot(2, num_cols, plot_idx)
        
        all_cond1_zscore = []
        all_cond2_zscore = []
        
        for day_name, data in results.items():
            if category not in data:
                continue
                
            category_data = data[category]
            
            if condition1_key in category_data and wl in category_data[condition1_key]['zscore']:
                all_cond1_zscore.extend(category_data[condition1_key]['zscore'][wl]['episodes'])
            
            if condition2_key in category_data and wl in category_data[condition2_key]['zscore']:
                all_cond2_zscore.extend(category_data[condition2_key]['zscore'][wl]['episodes'])
        
        if all_cond1_zscore or all_cond2_zscore:
            combined_zscore = []
            if all_cond1_zscore:
                combined_zscore.extend(all_cond1_zscore)
            if all_cond2_zscore:
                combined_zscore.extend(all_cond2_zscore)
            
            if combined_zscore:
                combined_zscore = np.array(combined_zscore)
                n_cond1 = len(all_cond1_zscore)
                
                if len(combined_zscore) == 1:
                    combined_zscore = np.vstack([combined_zscore[0], combined_zscore[0]])
                    im = ax_zscore_heat.imshow(combined_zscore, aspect='auto', interpolation='nearest',
                                             extent=[time_array[0], time_array[-1], 0, 1],
                                             cmap='coolwarm', origin='lower')
                else:
                    im = ax_zscore_heat.imshow(combined_zscore, aspect='auto', interpolation='nearest',
                                             extent=[time_array[0], time_array[-1], 0, len(combined_zscore)],
                                             cmap='coolwarm', origin='lower')
                    if len(combined_zscore) <= 10:
                        ax_zscore_heat.set_yticks(np.arange(0, len(combined_zscore)+1, 1))
                
                ax_zscore_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
                if n_cond1 > 0 and len(combined_zscore) > n_cond1:
                    ax_zscore_heat.axhline(y=n_cond1, color='k', linestyle='--', linewidth=1)
                
                ax_zscore_heat.set_xlabel('Time (s)')
                ax_zscore_heat.set_ylabel('Trials')
                ax_zscore_heat.set_title(f'{category} - Fiber Z-score Heatmap {wl}nm')
                plt.colorbar(im, ax=ax_zscore_heat, label='Z-score', orientation='horizontal')
            else:
                ax_zscore_heat.text(0.5, 0.5, 'No data available', 
                                  ha='center', va='center', fontsize=12, color='gray')
                ax_zscore_heat.set_title(f'{category} - Fiber Z-score Heatmap {wl}nm')
                ax_zscore_heat.axis('off')
        else:
            ax_zscore_heat.text(0.5, 0.5, 'No data available', 
                              ha='center', va='center', fontsize=12, color='gray')
            ax_zscore_heat.set_title(f'{category} - Fiber Z-score Heatmap {wl}nm')
            ax_zscore_heat.axis('off')
        
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

def plot_comparison_window_multi_drug_categories(results, params, condition_key, 
                                                 categories, window_title):
    target_wavelengths = []
    for day_name, data in results.items():
        if 'target_wavelengths' in data:
            target_wavelengths = data['target_wavelengths']
            break
    
    if not target_wavelengths:
        target_wavelengths = ['470']
    
    result_window = tk.Toplevel()
    result_window.title(f"{window_title} - All Days")
    result_window.state('zoomed')
    result_window.configure(bg='#f8f8f8')
    
    num_wavelengths = len(target_wavelengths)
    num_cols = 1 + 2 * num_wavelengths
    
    fig = Figure(figsize=(4 * num_cols, 8), dpi=100)
    
    plot_idx = 1
    time_array = list(results.values())[0]['time']
    
    ax_running = fig.add_subplot(2, num_cols, plot_idx)
    
    for idx, (day_name, data) in enumerate(results.items()):
        day_color = DAY_COLORS[idx % len(DAY_COLORS)]
        
        for cat_idx, category in enumerate(categories):
            if category not in data:
                continue
                
            category_data = data[category]
            
            if condition_key in category_data and category_data[condition_key]['running']['mean'] is not None:
                alpha = 1/len(categories) + (1/len(categories) * cat_idx)
                
                log_message(f"Plotting {day_name} - {category} with alpha {alpha}")
                ax_running.plot(time_array, category_data[condition_key]['running']['mean'],
                              color=day_color, linestyle='-', linewidth=2, 
                              alpha=alpha, label=f"{day_name} {category}")
                ax_running.fill_between(time_array,
                                       category_data[condition_key]['running']['mean'] - category_data[condition_key]['running']['sem'],
                                       category_data[condition_key]['running']['mean'] + category_data[condition_key]['running']['sem'],
                                       color=day_color, alpha=alpha*0.5)
    
    ax_running.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
    ax_running.set_xlim(time_array[0], time_array[-1])
    ax_running.set_xlabel('Time (s)')
    ax_running.set_ylabel('Speed (cm/s)')
    ax_running.set_title(f'{window_title} - Running Speed')
    ax_running.legend(fontsize=7, ncol=2)
    ax_running.grid(False)
    plot_idx += 1
    
    for wl_idx, wl in enumerate(target_wavelengths):
        # dFF
        ax_dff = fig.add_subplot(2, num_cols, plot_idx)
        
        for idx, (day_name, data) in enumerate(results.items()):
            day_color = DAY_COLORS[idx % len(DAY_COLORS)]
            
            for cat_idx, category in enumerate(categories):
                if category not in data:
                    continue
                    
                category_data = data[category]
                
                if condition_key in category_data and wl in category_data[condition_key]['dff']:
                    alpha = 1/len(categories) + (1/len(categories) * cat_idx)
                    
                    log_message(f"Plotting {day_name} - {category} with alpha {alpha}")
                    ax_dff.plot(time_array, category_data[condition_key]['dff'][wl]['mean'],
                              color=day_color, linewidth=2, linestyle='-', 
                              alpha=alpha, label=f'{day_name} {category}')
                    ax_dff.fill_between(time_array,
                                       category_data[condition_key]['dff'][wl]['mean'] - category_data[condition_key]['dff'][wl]['sem'],
                                       category_data[condition_key]['dff'][wl]['mean'] + category_data[condition_key]['dff'][wl]['sem'],
                                       color=day_color, alpha=alpha*0.5)
        
        ax_dff.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_dff.set_xlim(time_array[0], time_array[-1])
        ax_dff.set_xlabel('Time (s)')
        ax_dff.set_ylabel('ΔF/F')
        ax_dff.set_title(f'{window_title} - Fiber ΔF/F {wl}nm')
        ax_dff.legend(fontsize=7, ncol=2)
        ax_dff.grid(False)
        plot_idx += 1
        
        # Z-score
        ax_zscore = fig.add_subplot(2, num_cols, plot_idx)
        
        for idx, (day_name, data) in enumerate(results.items()):
            day_color = DAY_COLORS[idx % len(DAY_COLORS)]
            
            for cat_idx, category in enumerate(categories):
                if category not in data:
                    continue
                    
                category_data = data[category]
                
                if condition_key in category_data and wl in category_data[condition_key]['zscore']:
                    alpha = 1/len(categories) + (1/len(categories) * cat_idx)
                    
                    log_message(f"Plotting {day_name} - {category} with alpha {alpha}")
                    ax_zscore.plot(time_array, category_data[condition_key]['zscore'][wl]['mean'],
                                 color=day_color, linewidth=2, linestyle='-', 
                                 alpha=alpha, label=f'{day_name} {category}')
                    ax_zscore.fill_between(time_array,
                                          category_data[condition_key]['zscore'][wl]['mean'] - category_data[condition_key]['zscore'][wl]['sem'],
                                          category_data[condition_key]['zscore'][wl]['mean'] + category_data[condition_key]['zscore'][wl]['sem'],
                                          color=day_color, alpha=alpha*0.5)
        
        ax_zscore.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_zscore.set_xlim(time_array[0], time_array[-1])
        ax_zscore.set_xlabel('Time (s)')
        ax_zscore.set_ylabel('Z-score')
        ax_zscore.set_title(f'{window_title} - Fiber Z-score {wl}nm')
        ax_zscore.legend(fontsize=7, ncol=2)
        ax_zscore.grid(False)
        plot_idx += 1
    
    ax_running_heat = fig.add_subplot(2, num_cols, plot_idx)
    
    all_episodes = []
    category_boundaries = []
    
    for category in categories:
        category_episodes = []
        
        for day_name, data in results.items():
            if category not in data:
                continue
                
            category_data = data[category]
            
            if condition_key in category_data and len(category_data[condition_key]['running']['episodes']) > 0:
                category_episodes.extend(category_data[condition_key]['running']['episodes'])
        
        if category_episodes:
            all_episodes.extend(category_episodes)
            if all_episodes:
                category_boundaries.append(len(all_episodes))
    
    if all_episodes:
        episodes_array = np.array(all_episodes)
        
        if len(episodes_array) == 1:
            episodes_array = np.vstack([episodes_array[0], episodes_array[0]])
            im = ax_running_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                      extent=[time_array[0], time_array[-1], 0, 1],
                                      cmap='viridis', origin='lower')
        else:
            im = ax_running_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                      extent=[time_array[0], time_array[-1], 0, len(episodes_array)],
                                      cmap='viridis', origin='lower')
            if len(episodes_array) <= 10:
                ax_running_heat.set_yticks(np.arange(0, len(episodes_array)+1, 1))
        
        ax_running_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
        
        for boundary in category_boundaries[:-1]:
            ax_running_heat.axhline(y=boundary, color='k', linestyle='--', linewidth=1)
        
        ax_running_heat.set_xlabel('Time (s)')
        ax_running_heat.set_ylabel('Trials')
        ax_running_heat.set_title(f'{window_title} - Running Speed Heatmap')
        plt.colorbar(im, ax=ax_running_heat, label='Speed (cm/s)', orientation='horizontal')
    else:
        ax_running_heat.text(0.5, 0.5, 'No data available', 
                           ha='center', va='center', fontsize=12, color='gray')
        ax_running_heat.set_title(f'{window_title} - Running Speed Heatmap')
        ax_running_heat.axis('off')
    
    plot_idx += 1
    
    for wl_idx, wl in enumerate(target_wavelengths):
        # dFF
        ax_dff_heat = fig.add_subplot(2, num_cols, plot_idx)
        
        all_episodes = []
        category_boundaries = []
        
        for category in categories:
            category_episodes = []
            
            for day_name, data in results.items():
                if category not in data:
                    continue
                    
                category_data = data[category]
                
                if condition_key in category_data and wl in category_data[condition_key]['dff']:
                    category_episodes.extend(category_data[condition_key]['dff'][wl]['episodes'])
            
            if category_episodes:
                all_episodes.extend(category_episodes)
                if all_episodes:
                    category_boundaries.append(len(all_episodes))
        
        if all_episodes:
            episodes_array = np.array(all_episodes)
            
            if len(episodes_array) == 1:
                episodes_array = np.vstack([episodes_array[0], episodes_array[0]])
                im = ax_dff_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                      extent=[time_array[0], time_array[-1], 0, 1],
                                      cmap='coolwarm', origin='lower')
            else:
                im = ax_dff_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                      extent=[time_array[0], time_array[-1], 0, len(episodes_array)],
                                      cmap='coolwarm', origin='lower')
                if len(episodes_array) <= 10:
                    ax_dff_heat.set_yticks(np.arange(0, len(episodes_array)+1, 1))
            
            ax_dff_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            
            for boundary in category_boundaries[:-1]:
                ax_dff_heat.axhline(y=boundary, color='k', linestyle='--', linewidth=1)
            
            ax_dff_heat.set_xlabel('Time (s)')
            ax_dff_heat.set_ylabel('Trials')
            ax_dff_heat.set_title(f'{window_title} - Fiber ΔF/F Heatmap {wl}nm')
            plt.colorbar(im, ax=ax_dff_heat, label='ΔF/F', orientation='horizontal')
        else:
            ax_dff_heat.text(0.5, 0.5, 'No data available', 
                           ha='center', va='center', fontsize=12, color='gray')
            ax_dff_heat.set_title(f'{window_title} - Fiber ΔF/F Heatmap {wl}nm')
            ax_dff_heat.axis('off')
        
        plot_idx += 1
        
        # Z-score
        ax_zscore_heat = fig.add_subplot(2, num_cols, plot_idx)
        
        all_episodes = []
        category_boundaries = []
        
        for category in categories:
            category_episodes = []
            
            for day_name, data in results.items():
                if category not in data:
                    continue
                    
                category_data = data[category]
                
                if condition_key in category_data and wl in category_data[condition_key]['zscore']:
                    category_episodes.extend(category_data[condition_key]['zscore'][wl]['episodes'])
            
            if category_episodes:
                all_episodes.extend(category_episodes)
                if all_episodes:
                    category_boundaries.append(len(all_episodes))
        
        if all_episodes:
            episodes_array = np.array(all_episodes)
            
            if len(episodes_array) == 1:
                episodes_array = np.vstack([episodes_array[0], episodes_array[0]])
                im = ax_zscore_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                         extent=[time_array[0], time_array[-1], 0, 1],
                                         cmap='coolwarm', origin='lower')
            else:
                im = ax_zscore_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                         extent=[time_array[0], time_array[-1], 0, len(episodes_array)],
                                         cmap='coolwarm', origin='lower')
                if len(episodes_array) <= 10:
                    ax_zscore_heat.set_yticks(np.arange(0, len(episodes_array)+1, 1))
            
            ax_zscore_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            
            for boundary in category_boundaries[:-1]:
                ax_zscore_heat.axhline(y=boundary, color='k', linestyle='--', linewidth=1)
            
            ax_zscore_heat.set_xlabel('Time (s)')
            ax_zscore_heat.set_ylabel('Trials')
            ax_zscore_heat.set_title(f'{window_title} - Fiber Z-score Heatmap {wl}nm')
            plt.colorbar(im, ax=ax_zscore_heat, label='Z-score', orientation='horizontal')
        else:
            ax_zscore_heat.text(0.5, 0.5, 'No data available', 
                              ha='center', va='center', fontsize=12, color='gray')
            ax_zscore_heat.set_title(f'{window_title} - Fiber Z-score Heatmap {wl}nm')
            ax_zscore_heat.axis('off')
        
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

def create_individual_day_windows_running_optogenetics_drug_multi(results, params):
    """Create individual windows for each day - running+optogenetics+drug with multiple drugs"""
    for day_name, data in results.items():
        # Get all drug categories
        drug_categories = data.get('drug_categories', [])
        
        # Create multiple comparison windows for this day
        # 1. For each category: with vs without opto
        for category in drug_categories:
            create_single_day_category_window(
                day_name, data, params, category,
                f'Running+Optogenetics+Drug - {day_name} - {category}: With vs Without Opto'
            )
        
        # 2. Overall comparison across categories
        create_single_day_all_categories_window(
            day_name, data, params,
            f'Running+Optogenetics+Drug - {day_name} - All Categories'
        )

def create_single_day_category_window(day_name, data, params, category, window_title):
    """Create window for one drug category showing with/without opto comparison"""
    if category not in data:
        return
    
    category_window = tk.Toplevel()
    
    target_wavelengths = data.get('target_wavelengths', ['470'])
    
    category_window.title(window_title)
    category_window.state("zoomed")
    category_window.configure(bg='#f8f8f8')
    
    num_wavelengths = len(target_wavelengths)
    num_cols = 1 + 2 * num_wavelengths
    fig = Figure(figsize=(4 * num_cols, 8), dpi=100)
    
    plot_idx = 1
    time_array = data['time']
    
    category_data = data[category]
    
    # Row 1: Traces
    # Running trace
    ax_running = fig.add_subplot(2, num_cols, plot_idx)
    
    # With opto
    if 'with_opto' in category_data and category_data['with_opto']['running']['mean'] is not None:
        ax_running.plot(time_array, category_data['with_opto']['running']['mean'],
                      color="#000000", linewidth=2, linestyle='-', alpha=1, label='With Opto')
        ax_running.fill_between(time_array,
                               category_data['with_opto']['running']['mean'] - category_data['with_opto']['running']['sem'],
                               category_data['with_opto']['running']['mean'] + category_data['with_opto']['running']['sem'],
                               color="#000000", alpha=0.5)
    
    # Without opto
    if 'without_opto' in category_data and category_data['without_opto']['running']['mean'] is not None:
        ax_running.plot(time_array, category_data['without_opto']['running']['mean'],
                      color="#000000", linewidth=2, linestyle='-', alpha=0.5, label='Without Opto')
        ax_running.fill_between(time_array,
                               category_data['without_opto']['running']['mean'] - category_data['without_opto']['running']['sem'],
                               category_data['without_opto']['running']['mean'] + category_data['without_opto']['running']['sem'],
                               color="#000000", alpha=0.3)
    
    ax_running.axvline(x=0, color='#808080', linestyle='--', alpha=0.8, label='Event')
    ax_running.set_xlim(time_array[0], time_array[-1])
    ax_running.set_xlabel('Time (s)')
    ax_running.set_ylabel('Speed (cm/s)')
    ax_running.set_title(f'{category} - Running Speed')
    ax_running.legend()
    ax_running.grid(False)
    plot_idx += 1
    
    # Fiber traces
    for wl_idx, wl in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        
        # dFF trace
        ax_dff = fig.add_subplot(2, num_cols, plot_idx)
        
        # With opto
        if 'with_opto' in category_data and wl in category_data['with_opto']['dff']:
            ax_dff.plot(time_array, category_data['with_opto']['dff'][wl]['mean'],
                      color=color, linewidth=2, linestyle='-', alpha=1, label='With Opto')
            ax_dff.fill_between(time_array,
                               category_data['with_opto']['dff'][wl]['mean'] - category_data['with_opto']['dff'][wl]['sem'],
                               category_data['with_opto']['dff'][wl]['mean'] + category_data['with_opto']['dff'][wl]['sem'],
                               color=color, alpha=0.5)
        
        # Without opto
        if 'without_opto' in category_data and wl in category_data['without_opto']['dff']:
            ax_dff.plot(time_array, category_data['without_opto']['dff'][wl]['mean'],
                      color=color, linewidth=2, linestyle='-', alpha=0.5, label='Without Opto')
            ax_dff.fill_between(time_array,
                               category_data['without_opto']['dff'][wl]['mean'] - category_data['without_opto']['dff'][wl]['sem'],
                               category_data['without_opto']['dff'][wl]['mean'] + category_data['without_opto']['dff'][wl]['sem'],
                               color=color, alpha=0.3)
        
        ax_dff.axvline(x=0, color='#808080', linestyle='--', alpha=0.8, label='Event')
        ax_dff.set_xlim(time_array[0], time_array[-1])
        ax_dff.set_xlabel('Time (s)')
        ax_dff.set_ylabel('ΔF/F')
        ax_dff.set_title(f'{category} - Fiber ΔF/F {wl}nm')
        ax_dff.legend()
        ax_dff.grid(False)
        plot_idx += 1
        
        # Z-score trace
        ax_zscore = fig.add_subplot(2, num_cols, plot_idx)
        
        # With opto
        if 'with_opto' in category_data and wl in category_data['with_opto']['zscore']:
            ax_zscore.plot(time_array, category_data['with_opto']['zscore'][wl]['mean'],
                         color=color, linewidth=2, linestyle='-', alpha=1, label='With Opto')
            ax_zscore.fill_between(time_array,
                                  category_data['with_opto']['zscore'][wl]['mean'] - category_data['with_opto']['zscore'][wl]['sem'],
                                  category_data['with_opto']['zscore'][wl]['mean'] + category_data['with_opto']['zscore'][wl]['sem'],
                                  color=color, alpha=0.5)
        
        # Without opto
        if 'without_opto' in category_data and wl in category_data['without_opto']['zscore']:
            ax_zscore.plot(time_array, category_data['without_opto']['zscore'][wl]['mean'],
                         color=color, linewidth=2, linestyle='-', alpha=0.5, label='Without Opto')
            ax_zscore.fill_between(time_array,
                                  category_data['without_opto']['zscore'][wl]['mean'] - category_data['without_opto']['zscore'][wl]['sem'],
                                  category_data['without_opto']['zscore'][wl]['mean'] + category_data['without_opto']['zscore'][wl]['sem'],
                                  color=color, alpha=0.3)
        
        ax_zscore.axvline(x=0, color='#808080', linestyle='--', alpha=0.8, label='Event')
        ax_zscore.set_xlim(time_array[0], time_array[-1])
        ax_zscore.set_xlabel('Time (s)')
        ax_zscore.set_ylabel('Z-score')
        ax_zscore.set_title(f'{category} - Fiber Z-score {wl}nm')
        ax_zscore.legend()
        ax_zscore.grid(False)
        plot_idx += 1
    
    # Row 2: Heatmaps
    # Running heatmap
    ax_running_heat = fig.add_subplot(2, num_cols, plot_idx)
    
    with_episodes = []
    without_episodes = []
    
    if 'with_opto' in category_data and len(category_data['with_opto']['running']['episodes']) > 0:
        with_episodes = category_data['with_opto']['running']['episodes']
    
    if 'without_opto' in category_data and len(category_data['without_opto']['running']['episodes']) > 0:
        without_episodes = category_data['without_opto']['running']['episodes']
    
    if with_episodes is not None or without_episodes is not None:
        all_episodes = []
        if with_episodes is not None:
            all_episodes.extend(with_episodes)
        if without_episodes is not None:
            all_episodes.extend(without_episodes)
        
        all_episodes = np.array(all_episodes)
        n_with = len(with_episodes) if with_episodes is not None else 0
        
        if len(all_episodes) == 1:
            all_episodes = np.vstack([all_episodes[0], all_episodes[0]])
            im = ax_running_heat.imshow(all_episodes, aspect='auto', interpolation='nearest',
                                      extent=[time_array[0], time_array[-1], 0, 1],
                                      cmap='viridis', origin='lower')
        else:
            im = ax_running_heat.imshow(all_episodes, aspect='auto', interpolation='nearest',
                                      extent=[time_array[0], time_array[-1], 0, len(all_episodes)],
                                      cmap='viridis', origin='lower')
            if len(all_episodes) <= 10:
                ax_running_heat.set_yticks(np.arange(0, len(all_episodes)+1, 1))
        
        ax_running_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
        if n_with > 0 and len(all_episodes) > n_with:
            ax_running_heat.axhline(y=n_with, color='k', linestyle='--', linewidth=1, 
                                    label='With/Without boundary')
        
        ax_running_heat.set_xlabel('Time (s)')
        ax_running_heat.set_ylabel('Trials')
        ax_running_heat.set_title(f'{category} - Running Speed Heatmap')
        ax_running_heat.legend(loc='upper right', fontsize=8)
        plt.colorbar(im, ax=ax_running_heat, label='Speed (cm/s)', orientation='horizontal')
    plot_idx += 1
    
    # Fiber heatmaps
    for wl_idx, wl in enumerate(target_wavelengths):
        # dFF heatmap
        ax_dff_heat = fig.add_subplot(2, num_cols, plot_idx)
        
        with_dff = []
        without_dff = []
        
        if 'with_opto' in category_data and wl in category_data['with_opto']['dff']:
            with_dff = category_data['with_opto']['dff'][wl]['episodes']
        
        if 'without_opto' in category_data and wl in category_data['without_opto']['dff']:
            without_dff = category_data['without_opto']['dff'][wl]['episodes']
        
        if with_dff is not None or without_dff is not None:
            all_dff = []
            if with_dff is not None:
                all_dff.extend(with_dff)
            if without_dff is not None:
                all_dff.extend(without_dff)
            
            all_dff = np.array(all_dff)
            n_with = len(with_dff) if with_dff is not None else 0
            
            if len(all_dff) == 1:
                all_dff = np.vstack([all_dff[0], all_dff[0]])
                im = ax_dff_heat.imshow(all_dff, aspect='auto', interpolation='nearest',
                                      extent=[time_array[0], time_array[-1], 0, 1],
                                      cmap='coolwarm', origin='lower')
            else:
                im = ax_dff_heat.imshow(all_dff, aspect='auto', interpolation='nearest',
                                      extent=[time_array[0], time_array[-1], 0, len(all_dff)],
                                      cmap='coolwarm', origin='lower')
                if len(all_dff) <= 10:
                    ax_dff_heat.set_yticks(np.arange(0, len(all_dff)+1, 1))
            
            ax_dff_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            if n_with > 0 and len(all_dff) > n_with:
                ax_dff_heat.axhline(y=n_with, color='k', linestyle='--', linewidth=1,
                                    label='With/Without boundary')
            
            ax_dff_heat.set_xlabel('Time (s)')
            ax_dff_heat.set_ylabel('Trials')
            ax_dff_heat.set_title(f'{category} - Fiber ΔF/F Heatmap {wl}nm')
            ax_dff_heat.legend(loc='upper right', fontsize=8)
            plt.colorbar(im, ax=ax_dff_heat, label='ΔF/F', orientation='horizontal')
        plot_idx += 1
        
        # Z-score heatmap
        ax_zscore_heat = fig.add_subplot(2, num_cols, plot_idx)
        
        with_zscore = []
        without_zscore = []
        
        if 'with_opto' in category_data and wl in category_data['with_opto']['zscore']:
            with_zscore = category_data['with_opto']['zscore'][wl]['episodes']
        
        if 'without_opto' in category_data and wl in category_data['without_opto']['zscore']:
            without_zscore = category_data['without_opto']['zscore'][wl]['episodes']
        
        if with_zscore is not None or without_zscore is not None:
            all_zscore = []
            if with_zscore is not None:
                all_zscore.extend(with_zscore)
            if without_zscore is not None:
                all_zscore.extend(without_zscore)
            
            all_zscore = np.array(all_zscore)
            n_with = len(with_zscore) if with_zscore is not None else 0
            
            if len(all_zscore) == 1:
                all_zscore = np.vstack([all_zscore[0], all_zscore[0]])
                im = ax_zscore_heat.imshow(all_zscore, aspect='auto', interpolation='nearest',
                                         extent=[time_array[0], time_array[-1], 0, 1],
                                         cmap='coolwarm', origin='lower')
            else:
                im = ax_zscore_heat.imshow(all_zscore, aspect='auto', interpolation='nearest',
                                         extent=[time_array[0], time_array[-1], 0, len(all_zscore)],
                                         cmap='coolwarm', origin='lower')
                if len(all_zscore) <= 10:
                    ax_zscore_heat.set_yticks(np.arange(0, len(all_zscore)+1, 1))
            
            ax_zscore_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            if n_with > 0 and len(all_zscore) > n_with:
                ax_zscore_heat.axhline(y=n_with, color='k', linestyle='--', linewidth=1,
                                        label='With/Without boundary')
            
            ax_zscore_heat.set_xlabel('Time (s)')
            ax_zscore_heat.set_ylabel('Trials')
            ax_zscore_heat.set_title(f'{category} - Fiber Z-score Heatmap {wl}nm')
            ax_zscore_heat.legend(loc='upper right', fontsize=8)
            plt.colorbar(im, ax=ax_zscore_heat, label='Z-score', orientation='horizontal')
        plot_idx += 1
    
    fig.tight_layout()
    
    canvas_frame = tk.Frame(category_window, bg='#f8f8f8')
    canvas_frame.pack(fill=tk.BOTH, expand=True)
    
    canvas = FigureCanvasTkAgg(fig, canvas_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    toolbar_frame = tk.Frame(canvas_frame, bg="#f5f5f5")
    toolbar_frame.pack(fill=tk.X, padx=2, pady=(0,2))
    toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
    
    log_message(f"Category window created: {window_title}")

def create_single_day_all_categories_window(day_name, data, params, window_title):
    """Create window showing all categories with opto condition comparison"""
    all_window = tk.Toplevel()
    
    target_wavelengths = data.get('target_wavelengths', ['470'])
    drug_categories = data.get('drug_categories', [])
    
    all_window.title(window_title)
    all_window.state("zoomed")
    all_window.configure(bg='#f8f8f8')
    
    num_wavelengths = len(target_wavelengths)
    num_cols = 1 + 2 * num_wavelengths
    fig = Figure(figsize=(4 * num_cols, 8), dpi=100)
    
    plot_idx = 1
    time_array = data['time']
    
    # Row 1: Traces showing all categories
    # Running trace
    ax_running = fig.add_subplot(2, num_cols, plot_idx)
    
    for cat_idx, category in enumerate(drug_categories):
        if category not in data:
            continue
        
        category_data = data[category]
        
        # Plot with opto
        if 'with_opto' in category_data and category_data['with_opto']['running']['mean'] is not None:
            alpha = 1/len(drug_categories) + (1/len(drug_categories) * cat_idx)
            log_message(f"Plotting {day_name} - {category} with alpha {alpha}")
            ax_running.plot(time_array, category_data['with_opto']['running']['mean'],
                          color=DAY_COLORS[cat_idx % len(DAY_COLORS)], 
                          linewidth=2, linestyle='-', alpha=alpha, 
                          label=f'{category} +Opto')
            ax_running.fill_between(time_array,
                                   category_data['with_opto']['running']['mean'] - category_data['with_opto']['running']['sem'],
                                   category_data['with_opto']['running']['mean'] + category_data['with_opto']['running']['sem'],
                                   color=DAY_COLORS[cat_idx % len(DAY_COLORS)], alpha=alpha*0.3)
        
        # Plot without opto
        if 'without_opto' in category_data and category_data['without_opto']['running']['mean'] is not None:
            alpha = 1/len(drug_categories) + (1/len(drug_categories) * cat_idx)
            log_message(f"Plotting {day_name} - {category} with alpha {alpha}")
            ax_running.plot(time_array, category_data['without_opto']['running']['mean'],
                          color=DAY_COLORS[cat_idx % len(DAY_COLORS)], 
                          linewidth=2, linestyle='-', alpha=alpha, 
                          label=f'{category} -Opto')
            ax_running.fill_between(time_array,
                                   category_data['without_opto']['running']['mean'] - category_data['without_opto']['running']['sem'],
                                   category_data['without_opto']['running']['mean'] + category_data['without_opto']['running']['sem'],
                                   color=DAY_COLORS[cat_idx % len(DAY_COLORS)], alpha=alpha*0.3)
    
    ax_running.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
    ax_running.set_xlim(time_array[0], time_array[-1])
    ax_running.set_xlabel('Time (s)')
    ax_running.set_ylabel('Speed (cm/s)')
    ax_running.set_title(f'{day_name} - Running Speed (All Categories)')
    ax_running.legend(fontsize=7, ncol=2)
    ax_running.grid(False)
    plot_idx += 1
    
    # Fiber traces
    for wl_idx, wl in enumerate(target_wavelengths):
        # dFF trace
        ax_dff = fig.add_subplot(2, num_cols, plot_idx)
        
        for cat_idx, category in enumerate(drug_categories):
            if category not in data:
                continue
            
            category_data = data[category]
            fiber_color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
            
            # With opto
            if 'with_opto' in category_data and wl in category_data['with_opto']['dff']:
                alpha = 1/len(drug_categories) + (1/len(drug_categories) * cat_idx)
                log_message(f"Plotting {day_name} - {category} with alpha {alpha}")
                ax_dff.plot(time_array, category_data['with_opto']['dff'][wl]['mean'],
                          color=DAY_COLORS[cat_idx % len(DAY_COLORS)], 
                          linewidth=2, linestyle='-', alpha=alpha,
                          label=f'{category} +Opto')
                ax_dff.fill_between(time_array,
                                   category_data['with_opto']['dff'][wl]['mean'] - category_data['with_opto']['dff'][wl]['sem'],
                                   category_data['with_opto']['dff'][wl]['mean'] + category_data['with_opto']['dff'][wl]['sem'],
                                   color=DAY_COLORS[cat_idx % len(DAY_COLORS)], alpha=alpha*0.3)
            
            # Without opto
            if 'without_opto' in category_data and wl in category_data['without_opto']['dff']:
                alpha = 1/len(drug_categories) + (1/len(drug_categories) * cat_idx)
                log_message(f"Plotting {day_name} - {category} with alpha {alpha}")
                ax_dff.plot(time_array, category_data['without_opto']['dff'][wl]['mean'],
                          color=DAY_COLORS[cat_idx % len(DAY_COLORS)], 
                          linewidth=2, linestyle='-', alpha=alpha,
                          label=f'{category} -Opto')
                ax_dff.fill_between(time_array,
                                   category_data['without_opto']['dff'][wl]['mean'] - category_data['without_opto']['dff'][wl]['sem'],
                                   category_data['without_opto']['dff'][wl]['mean'] + category_data['without_opto']['dff'][wl]['sem'],
                                   color=DAY_COLORS[cat_idx % len(DAY_COLORS)], alpha=alpha*0.3)
        
        ax_dff.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_dff.set_xlim(time_array[0], time_array[-1])
        ax_dff.set_xlabel('Time (s)')
        ax_dff.set_ylabel('ΔF/F')
        ax_dff.set_title(f'{day_name} - Fiber ΔF/F {wl}nm (All Categories)')
        ax_dff.legend(fontsize=6, ncol=2)
        ax_dff.grid(False)
        plot_idx += 1
        
        # Z-score trace (similar structure)
        ax_zscore = fig.add_subplot(2, num_cols, plot_idx)
        
        for cat_idx, category in enumerate(drug_categories):
            if category not in data:
                continue
            
            category_data = data[category]
            
            # With opto
            if 'with_opto' in category_data and wl in category_data['with_opto']['zscore']:
                alpha = 1/len(drug_categories) + (1/len(drug_categories) * cat_idx)
                log_message(f"Plotting {day_name} - {category} with alpha {alpha}")
                ax_zscore.plot(time_array, category_data['with_opto']['zscore'][wl]['mean'],
                             color=DAY_COLORS[cat_idx % len(DAY_COLORS)], 
                             linewidth=2, linestyle='-', alpha=alpha,
                             label=f'{category} +Opto')
                ax_zscore.fill_between(time_array,
                                      category_data['with_opto']['zscore'][wl]['mean'] - category_data['with_opto']['zscore'][wl]['sem'],
                                      category_data['with_opto']['zscore'][wl]['mean'] + category_data['with_opto']['zscore'][wl]['sem'],
                                      color=DAY_COLORS[cat_idx % len(DAY_COLORS)], alpha=alpha*0.3)
            
            # Without opto
            if 'without_opto' in category_data and wl in category_data['without_opto']['zscore']:
                alpha = 1/len(drug_categories) + (1/len(drug_categories) * cat_idx)
                log_message(f"Plotting {day_name} - {category} with alpha {alpha}")
                ax_zscore.plot(time_array, category_data['without_opto']['zscore'][wl]['mean'],
                             color=DAY_COLORS[cat_idx % len(DAY_COLORS)], 
                             linewidth=2, linestyle='-', alpha=alpha,
                             label=f'{category} -Opto')
                ax_zscore.fill_between(time_array,
                                      category_data['without_opto']['zscore'][wl]['mean'] - category_data['without_opto']['zscore'][wl]['sem'],
                                      category_data['without_opto']['zscore'][wl]['mean'] + category_data['without_opto']['zscore'][wl]['sem'],
                                      color=DAY_COLORS[cat_idx % len(DAY_COLORS)], alpha=alpha*0.3)
        
        ax_zscore.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_zscore.set_xlim(time_array[0], time_array[-1])
        ax_zscore.set_xlabel('Time (s)')
        ax_zscore.set_ylabel('Z-score')
        ax_zscore.set_title(f'{day_name} - Fiber Z-score {wl}nm (All Categories)')
        ax_zscore.legend(fontsize=6, ncol=2)
        ax_zscore.grid(False)
        plot_idx += 1
    
    # ############ Row 2: Heatmaps ############
    # Running speed heatmap
    ax_running_heat = fig.add_subplot(2, num_cols, plot_idx)
    
    all_running_episodes = []
    category_boundaries = []
    condition_boundaries = []
    
    for category in drug_categories:
        if category not in data:
            continue
        
        category_data = data[category]
        category_start = len(all_running_episodes)
        
        # Add with opto episodes first
        if 'with_opto' in category_data and len(category_data['with_opto']['running']['episodes']) > 0:
            with_episodes = category_data['with_opto']['running']['episodes']
            all_running_episodes.extend(with_episodes)
            if all_running_episodes:
                condition_boundaries.append(len(all_running_episodes))
        
        # Add without opto episodes next
        if 'without_opto' in category_data and len(category_data['without_opto']['running']['episodes']) > 0:
            without_episodes = category_data['without_opto']['running']['episodes']
            all_running_episodes.extend(without_episodes)
            if all_running_episodes:
                category_boundaries.append(len(all_running_episodes))
    
    if all_running_episodes:
        episodes_array = np.array(all_running_episodes)
        
        if len(episodes_array) == 1:
            episodes_array = np.vstack([episodes_array[0], episodes_array[0]])
            im = ax_running_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                      extent=[time_array[0], time_array[-1], 0, 1],
                                      cmap='viridis', origin='lower')
        else:
            im = ax_running_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                      extent=[time_array[0], time_array[-1], 0, len(episodes_array)],
                                      cmap='viridis', origin='lower')
            if len(episodes_array) <= 10:
                ax_running_heat.set_yticks(np.arange(0, len(episodes_array)+1, 1))
        
        # Draw vertical event line
        ax_running_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
        
        # Draw condition boundaries (light lines for with/without opto separation)
        for boundary in condition_boundaries[:-1]:
            ax_running_heat.axhline(y=boundary, color='gray', linestyle='-', linewidth=1, alpha=0.5)
        
        # Draw category boundaries (dark lines for category separation)
        for boundary in category_boundaries[:-1]:
            ax_running_heat.axhline(y=boundary, color='k', linestyle='--', linewidth=2, alpha=0.8)
        
        # Add labels for categories
        y_positions = []
        current_y = 0
        for i, category in enumerate(drug_categories):
            if category not in data:
                continue
            
            category_data = data[category]
            category_height = 0
            
            if 'with_opto' in category_data:
                category_height += len(category_data['with_opto']['running']['episodes'])
            if 'without_opto' in category_data:
                category_height += len(category_data['without_opto']['running']['episodes'])
            
            if category_height > 0:
                mid_y = current_y + category_height / 2
                y_positions.append((mid_y, category))
                current_y += category_height
        
        # Set y-tick labels for categories
        if y_positions:
            y_pos, y_labels = zip(*y_positions)
            ax_running_heat.set_yticks(y_pos)
            ax_running_heat.set_yticklabels(y_labels, fontsize=7)
        
        ax_running_heat.set_xlabel('Time (s)')
        ax_running_heat.set_ylabel('Trials')
        ax_running_heat.set_title(f'{day_name} - Running Speed Heatmap (All Categories)')
        plt.colorbar(im, ax=ax_running_heat, label='Speed (cm/s)', orientation='horizontal')
    else:
        # Show message if no data
        ax_running_heat.text(0.5, 0.5, 'No running data available',
                           ha='center', va='center', transform=ax_running_heat.transAxes,
                           fontsize=12, color='#666666')
        ax_running_heat.set_title(f'{day_name} - Running Speed Heatmap (All Categories)')
        ax_running_heat.axis('off')
    
    plot_idx += 1
    
    # Fiber heatmaps
    for wl_idx, wl in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        
        # dFF heatmap
        ax_dff_heat = fig.add_subplot(2, num_cols, plot_idx)
        
        all_dff_episodes = []
        category_boundaries_dff = []
        condition_boundaries_dff = []
        
        for category in drug_categories:
            if category not in data:
                continue
            
            category_data = data[category]
            category_start = len(all_dff_episodes)
            
            # Add with opto episodes first
            if 'with_opto' in category_data and wl in category_data['with_opto']['dff']:
                with_episodes = category_data['with_opto']['dff'][wl]['episodes']
                all_dff_episodes.extend(with_episodes)
                if all_dff_episodes:
                    condition_boundaries_dff.append(len(all_dff_episodes))
            
            # Add without opto episodes next
            if 'without_opto' in category_data and wl in category_data['without_opto']['dff']:
                without_episodes = category_data['without_opto']['dff'][wl]['episodes']
                all_dff_episodes.extend(without_episodes)
                if all_dff_episodes:
                    category_boundaries_dff.append(len(all_dff_episodes))
        
        if all_dff_episodes is not None and len(all_dff_episodes) > 0:
            episodes_array = np.array(all_dff_episodes)
            
            if len(episodes_array) == 1:
                episodes_array = np.vstack([episodes_array[0], episodes_array[0]])
                im = ax_dff_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                      extent=[time_array[0], time_array[-1], 0, 1],
                                      cmap='coolwarm', origin='lower')
            else:
                im = ax_dff_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                      extent=[time_array[0], time_array[-1], 0, len(episodes_array)],
                                      cmap='coolwarm', origin='lower')
                if len(episodes_array) <= 10:
                    ax_dff_heat.set_yticks(np.arange(0, len(episodes_array)+1, 1))
            
            # Draw vertical event line
            ax_dff_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            
            # Draw condition boundaries
            for boundary in condition_boundaries_dff[:-1]:
                ax_dff_heat.axhline(y=boundary, color='gray', linestyle='-', linewidth=1, alpha=0.5)
            
            # Draw category boundaries
            for boundary in category_boundaries_dff[:-1]:
                ax_dff_heat.axhline(y=boundary, color='k', linestyle='--', linewidth=2, alpha=0.8)
            
            # Add category labels
            y_positions = []
            current_y = 0
            for i, category in enumerate(drug_categories):
                if category not in data:
                    continue
                
                category_data = data[category]
                category_height = 0
                
                if 'with_opto' in category_data and wl in category_data['with_opto']['dff']:
                    category_height += len(category_data['with_opto']['dff'][wl]['episodes'])
                if 'without_opto' in category_data and wl in category_data['without_opto']['dff']:
                    category_height += len(category_data['without_opto']['dff'][wl]['episodes'])
                
                if category_height > 0:
                    mid_y = current_y + category_height / 2
                    y_positions.append((mid_y, category))
                    current_y += category_height
            
            # Set y-tick labels for categories
            if y_positions:
                y_pos, y_labels = zip(*y_positions)
                ax_dff_heat.set_yticks(y_pos)
                ax_dff_heat.set_yticklabels(y_labels, fontsize=7)
            
            ax_dff_heat.set_xlabel('Time (s)')
            ax_dff_heat.set_ylabel('Trials')
            ax_dff_heat.set_title(f'{day_name} - Fiber ΔF/F Heatmap {wl}nm (All Categories)')
            plt.colorbar(im, ax=ax_dff_heat, label='ΔF/F', orientation='horizontal')
        else:
            # Show message if no data
            ax_dff_heat.text(0.5, 0.5, f'No dFF data for {wl}nm',
                           ha='center', va='center', transform=ax_dff_heat.transAxes,
                           fontsize=12, color='#666666')
            ax_dff_heat.set_title(f'{day_name} - Fiber ΔF/F Heatmap {wl}nm (All Categories)')
            ax_dff_heat.axis('off')
        
        plot_idx += 1
        
        # Z-score heatmap
        ax_zscore_heat = fig.add_subplot(2, num_cols, plot_idx)
        
        all_zscore_episodes = []
        category_boundaries_zscore = []
        condition_boundaries_zscore = []
        
        for category in drug_categories:
            if category not in data:
                continue
            
            category_data = data[category]
            category_start = len(all_zscore_episodes)
            
            # Add with opto episodes first
            if 'with_opto' in category_data and wl in category_data['with_opto']['zscore']:
                with_episodes = category_data['with_opto']['zscore'][wl]['episodes']
                all_zscore_episodes.extend(with_episodes)
                if all_zscore_episodes:
                    condition_boundaries_zscore.append(len(all_zscore_episodes))
            
            # Add without opto episodes next
            if 'without_opto' in category_data and wl in category_data['without_opto']['zscore']:
                without_episodes = category_data['without_opto']['zscore'][wl]['episodes']
                all_zscore_episodes.extend(without_episodes)
                if all_zscore_episodes:
                    category_boundaries_zscore.append(len(all_zscore_episodes))
        
        if all_zscore_episodes:
            episodes_array = np.array(all_zscore_episodes)
            
            if len(episodes_array) == 1:
                episodes_array = np.vstack([episodes_array[0], episodes_array[0]])
                im = ax_zscore_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                         extent=[time_array[0], time_array[-1], 0, 1],
                                         cmap='coolwarm', origin='lower')
            else:
                im = ax_zscore_heat.imshow(episodes_array, aspect='auto', interpolation='nearest',
                                         extent=[time_array[0], time_array[-1], 0, len(episodes_array)],
                                         cmap='coolwarm', origin='lower')
                if len(episodes_array) <= 10:
                    ax_zscore_heat.set_yticks(np.arange(0, len(episodes_array)+1, 1))
            
            # Draw vertical event line
            ax_zscore_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            
            # Draw condition boundaries
            for boundary in condition_boundaries_zscore[:-1]:
                ax_zscore_heat.axhline(y=boundary, color='gray', linestyle='-', linewidth=1, alpha=0.5)
            
            # Draw category boundaries
            for boundary in category_boundaries_zscore[:-1]:
                ax_zscore_heat.axhline(y=boundary, color='k', linestyle='--', linewidth=2, alpha=0.8)
            
            # Add category labels
            y_positions = []
            current_y = 0
            for i, category in enumerate(drug_categories):
                if category not in data:
                    continue
                
                category_data = data[category]
                category_height = 0
                
                if 'with_opto' in category_data and wl in category_data['with_opto']['zscore']:
                    category_height += len(category_data['with_opto']['zscore'][wl]['episodes'])
                if 'without_opto' in category_data and wl in category_data['without_opto']['zscore']:
                    category_height += len(category_data['without_opto']['zscore'][wl]['episodes'])
                
                if category_height > 0:
                    mid_y = current_y + category_height / 2
                    y_positions.append((mid_y, category))
                    current_y += category_height
            
            # Set y-tick labels for categories
            if y_positions:
                y_pos, y_labels = zip(*y_positions)
                ax_zscore_heat.set_yticks(y_pos)
                ax_zscore_heat.set_yticklabels(y_labels, fontsize=7)
            
            ax_zscore_heat.set_xlabel('Time (s)')
            ax_zscore_heat.set_ylabel('Trials')
            ax_zscore_heat.set_title(f'{day_name} - Fiber Z-score Heatmap {wl}nm (All Categories)')
            plt.colorbar(im, ax=ax_zscore_heat, label='Z-score', orientation='horizontal')
        else:
            # Show message if no data
            ax_zscore_heat.text(0.5, 0.5, f'No z-score data for {wl}nm',
                              ha='center', va='center', transform=ax_zscore_heat.transAxes,
                              fontsize=12, color='#666666')
            ax_zscore_heat.set_title(f'{day_name} - Fiber Z-score Heatmap {wl}nm (All Categories)')
            ax_zscore_heat.axis('off')
        
        plot_idx += 1
    
    fig.tight_layout()
    
    canvas_frame = tk.Frame(all_window, bg='#f8f8f8')
    canvas_frame.pack(fill=tk.BOTH, expand=True)
    
    canvas = FigureCanvasTkAgg(fig, canvas_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    toolbar_frame = tk.Frame(canvas_frame, bg="#f5f5f5")
    toolbar_frame.pack(fill=tk.X, padx=2, pady=(0,2))
    toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
    
    log_message(f"All categories window created: {window_title}")