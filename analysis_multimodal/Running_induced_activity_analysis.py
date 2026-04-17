"""
Running-induced activity analysis with table configuration
Supports both running-only and running+drug analysis
"""
import os
import json
import tkinter as tk
import numpy as np

from infrastructure.logger import log_message
from analysis_multimodal.Multimodal_analysis import (
    get_events_from_bouts, calculate_running_episodes, export_results,
    create_table_window, initialize_table, create_control_panel, identify_optogenetic_events, 
    identify_drug_sessions, calculate_optogenetic_pulse_info, get_events_within_optogenetic, 
    create_opto_parameter_string, group_optogenetic_sessions, create_parameter_panel, 
    get_parameters_from_ui, FIBER_COLORS, ROW_COLORS,
    make_scrollable_window, make_figure, draw_heatmap, embed_figure
)

NUM_COLS = 3     # Running: speed | ΔF/F | Z-score

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
        
    available_bout_types = []
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
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'opto_power_config.json')
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
        # Group animals by row
        row_data = {}
        for i in range(self.num_rows):
            row_name = self.row_headers.get(i, f"Row{i+1}")
            row_animals = []
            
            for j in range(self.num_cols):
                if (i, j) in self.table_data:
                    animal_id = self.table_data[(i, j)]
                    for animal_data in self.multi_animal_data:
                        if animal_data.get('animal_single_channel_id') == animal_id:
                            row_animals.append(animal_data)
                            break
            
            if row_animals:
                row_data[row_name] = row_animals
        
        if not row_data:
            log_message("No valid data in table", "WARNING")
            return
        
        if analysis_mode == "running":
            run_running_only_analysis(row_data, params)
        elif analysis_mode == "running+drug":
            run_running_drug_analysis(row_data, params)
        elif analysis_mode == "running+optogenetics":
            run_running_optogenetics_analysis(row_data, params)

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
        # Group animals by row
        row_data = {}
        for i in range(self.num_rows):
            row_name = self.row_headers.get(i, f"Row{i+1}")
            row_animals = []
            
            for j in range(self.num_cols):
                if (i, j) in self.table_data:
                    animal_id = self.table_data[(i, j)]
                    for animal_data in self.multi_animal_data:
                        if animal_data.get('animal_single_channel_id') == animal_id:
                            row_animals.append(animal_data)
                            break
            
            if row_animals:
                row_data[row_name] = row_animals
        
        if not row_data:
            log_message("No valid data in table", "WARNING")
            return
        
        run_running_optogenetics_analysis(row_data, params, 
                                         self.all_optogenetic_events, 
                                         self.power_values, self.all_drug_events, self.analysis_mode)

def run_running_only_analysis(row_data, params):
    """Run running-only analysis"""
    log_message(f"Starting running-induced analysis for {len(row_data)} row(s)...")
    
    results = {}
    all_statistics = []
    
    for row_name, animals in row_data.items():
        log_message(f"Analyzing {row_name} with {len(animals)} animal(s)...")
        row_result, row_stats = analyze_row_running(row_name, animals, params)
        
        if row_result:
            results[row_name] = row_result
        if row_stats:
            all_statistics.extend(row_stats)
    
    if params['export_stats'] and all_statistics:
        export_results(results, all_statistics, "running_induced", params['full_event_type'])
    
    if results:
        plot_running_results(results, params)
        log_message("Analysis completed successfully")
    else:
        log_message("No valid results", "ERROR")

def run_running_drug_analysis(row_data, params):
    """Run running+drug analysis"""
    log_message(f"Starting running+drug analysis for {len(row_data)} row(s)...")
    
    results = {}
    all_statistics = []
    
    for row_name, animals in row_data.items():
        log_message(f"Analyzing {row_name} with {len(animals)} animal(s)...")
        row_result, row_stats = analyze_row_running_drug(row_name, animals, params)
        
        if row_result:
            results[row_name] = row_result
        if row_stats:
            all_statistics.extend(row_stats)
    
    if params['export_stats'] and all_statistics:
        export_results(results, all_statistics, "running_drug_induced", params['full_event_type'])
    
    if results:
        plot_running_drug_results(results, params)
        log_message("Analysis completed successfully")
    else:
        log_message("No valid results", "ERROR")
        
def analyze_row_running(row_name, animals, params):
    """Analyze one row for running-only mode"""
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
                    row_name, animal_id, params['full_event_type'],
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

def analyze_row_running_drug(row_name, animals, params):
    """Analyze one row for running+drug mode with multiple drugs
    Modified to use drug onset/offset times from configuration
    """
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
    
    # Load drug config
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'drug_name_config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            drug_config = json.load(f)
    else:
        drug_config = {}
    
    # Collect all unique drug timing categories across all animals
    all_drug_categories = []
    
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
            
            # Get running end time
            running_end_time = None
            ast2_data = animal_data.get('ast2_data_adjusted')
            if ast2_data and 'data' in ast2_data and 'timestamps' in ast2_data['data']:
                running_end_time = ast2_data['data']['timestamps'][-1]
            
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
                        # Use running end time
                        offset_time = running_end_time if running_end_time else onset_time + 10000
                
                drug_info.append({
                    'name': drug_name,
                    'onset': onset_time,
                    'offset': offset_time,
                    'idx': idx
                })
            
            # Sort by onset time
            drug_info.sort(key=lambda x: x['onset'])
            
            log_message(f"Animal {animal_id} drug timing:")
            for d in drug_info:
                log_message(f"{d['name']}: onset={d['onset']:.1f}s, offset={d['offset']:.1f}s")
            
            # Get running events
            events = get_events_from_bouts(animal_data, params['full_event_type'], duration=False)
            if not events:
                continue
            
            # Classify running events into drug categories
            # Now using onset/offset times instead of just onset
            event_categories = {}
            
            for event_time in events:
                category = 'baseline'
                
                # Check if event is before first drug onset
                if event_time < drug_info[0]['onset']:
                    category = 'baseline'
                else:
                    # Find which drug period this event belongs to
                    # Check from latest to earliest drug
                    for i in range(len(drug_info)):
                        # Event must be after onset AND before offset
                        if drug_info[i]['onset'] <= event_time < drug_info[i]['offset']:
                            if i == 0:
                                # Within first drug period
                                category = drug_info[0]['name']
                            else:
                                # Within later drug period
                                previous_drugs = ' + '.join([d['name'] for d in drug_info[:i]])
                                category = f"{drug_info[i]['name']} after {previous_drugs}"
                            break
                
                if category not in event_categories:
                    event_categories[category] = []
                event_categories[category].append(event_time)
                if category not in all_drug_categories:
                    all_drug_categories.append(category)
            
            log_message(f"Animal {animal_id} all drug categories: {', '.join(all_drug_categories)}")
            
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
                        row_name, animal_id, category, category_result,
                        time_array, params, target_wavelengths, active_channels
                    ))
        
        except Exception as e:
            log_message(f"Error processing {animal_id}: {str(e)}", "ERROR")
            import traceback
            traceback.print_exc()
    
    # Calculate means for each category
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

def analyze_row_running_optogenetics(row_name, animals, params, all_optogenetic_events, power_values):
    """Analyze one row for running+optogenetics mode"""
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
                                        'row': row_name,
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
                                        'row': row_name,
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

def collect_statistics(row_name, animal_id, event_type, result, time_array, params, 
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
            'row': row_name,
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
                        'row': row_name,
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
                        'row': row_name,
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
    """Plot running-only results — all rows overlaid."""
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
        f"Running-Induced Activity - All Rows ({wavelength_label}nm)"
    )
 
    for wl_idx, wl in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        fig = make_figure(NUM_COLS)
        fig.suptitle(f"Wavelength {wl} nm — All Rows",
                     fontsize=12, fontweight="bold")
 
        # Row 1: Traces
        ax_run = fig.add_subplot(2, NUM_COLS, 1)
        for idx, (row_name, data) in enumerate(results.items()):
            dc = ROW_COLORS[idx % len(ROW_COLORS)]
            if "running" in data and data["running"]["mean"] is not None:
                t = data["time"]
                ax_run.plot(t, data["running"]["mean"],
                            color=dc, linewidth=2, label=row_name)
                ax_run.fill_between(
                    t,
                    data["running"]["mean"] - data["running"]["sem"],
                    data["running"]["mean"] + data["running"]["sem"],
                    color=dc, alpha=0.3)
        ax_run.axvline(x=0, color="#808080", linestyle="--", alpha=0.8)
        ax_run.set_xlim(time_array[0], time_array[-1])
        ax_run.set_xlabel("Time (s)")
        ax_run.set_ylabel("Speed (cm/s)")
        ax_run.set_title("Running Speed - All Rows")
        ax_run.legend(fontsize=7)
        ax_run.grid(False)
 
        ax_dff = fig.add_subplot(2, NUM_COLS, 2)
        for idx, (row_name, data) in enumerate(results.items()):
            dc = ROW_COLORS[idx % len(ROW_COLORS)]
            if wl in data["dff"]:
                t = data["time"]
                ax_dff.plot(t, data["dff"][wl]["mean"],
                            color=dc, linewidth=2, label=row_name)
                ax_dff.fill_between(
                    t,
                    data["dff"][wl]["mean"] - data["dff"][wl]["sem"],
                    data["dff"][wl]["mean"] + data["dff"][wl]["sem"],
                    color=dc, alpha=0.3)
        ax_dff.axvline(x=0, color="#808080", linestyle="--", alpha=0.8)
        ax_dff.set_xlim(time_array[0], time_array[-1])
        ax_dff.set_xlabel("Time (s)")
        ax_dff.set_ylabel("ΔF/F")
        ax_dff.set_title(f"Fiber ΔF/F {wl}nm - All Rows")
        ax_dff.legend(fontsize=7)
        ax_dff.grid(False)
 
        ax_zs = fig.add_subplot(2, NUM_COLS, 3)
        for idx, (row_name, data) in enumerate(results.items()):
            dc = ROW_COLORS[idx % len(ROW_COLORS)]
            if wl in data["zscore"]:
                t = data["time"]
                ax_zs.plot(t, data["zscore"][wl]["mean"],
                           color=dc, linewidth=2, label=row_name)
                ax_zs.fill_between(
                    t,
                    data["zscore"][wl]["mean"] - data["zscore"][wl]["sem"],
                    data["zscore"][wl]["mean"] + data["zscore"][wl]["sem"],
                    color=dc, alpha=0.3)
        ax_zs.axvline(x=0, color="#808080", linestyle="--", alpha=0.8)
        ax_zs.set_xlim(time_array[0], time_array[-1])
        ax_zs.set_xlabel("Time (s)")
        ax_zs.set_ylabel("Z-score")
        ax_zs.set_title(f"Fiber Z-score {wl}nm - All Rows")
        ax_zs.legend(fontsize=7)
        ax_zs.grid(False)
 
        # Row 2: Heatmaps
        ax_run_heat = fig.add_subplot(2, NUM_COLS, 4)
        all_run, counts = [], []
        for data in results.values():
            if "running" in data and len(data["running"]["episodes"]) > 0:
                all_run.extend(data["running"]["episodes"])
                counts.append(len(data["running"]["episodes"]))
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
            ax_run_heat.axis("off")
            ax_run_heat.set_title("Running Speed Heatmap")
 
        ax_dff_heat = fig.add_subplot(2, NUM_COLS, 5)
        all_dff, counts = [], []
        for data in results.values():
            if wl in data["dff"]:
                ep = data["dff"][wl]["episodes"]
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
            ax_dff_heat.set_title(f"Fiber ΔF/F Heatmap {wl}nm")
        else:
            ax_dff_heat.axis("off")
            ax_dff_heat.set_title(f"Fiber ΔF/F Heatmap {wl}nm")
 
        ax_zs_heat = fig.add_subplot(2, NUM_COLS, 6)
        all_zs, counts = [], []
        for data in results.values():
            if wl in data["zscore"]:
                ep = data["zscore"][wl]["episodes"]
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
            ax_zs_heat.set_title(f"Fiber Z-score Heatmap {wl}nm")
        else:
            ax_zs_heat.axis("off")
            ax_zs_heat.set_title(f"Fiber Z-score Heatmap {wl}nm")
 
        fig.tight_layout(rect=[0, 0, 1, 0.96])
        embed_figure(inner, fig, row_in_frame=wl_idx)
 
    create_individual_row_windows_running(results, params)
    log_message("Running results plotted.")

def create_individual_row_windows_running(results, params):
    """Create individual windows for each row - running only"""
    for row_name, data in results.items():
        create_single_row_window_running(row_name, data, params)

def create_single_row_window_running(row_name, data, params):
    """Create window for a single row — running only."""
    from analysis_multimodal.Multimodal_analysis import FIBER_COLORS
    from infrastructure.logger import log_message
 
    target_wavelengths = data.get("target_wavelengths", ["470"])
    time_array = data["time"]
 
    win, _, inner = make_scrollable_window(
        f"Running-Induced Activity - {row_name} - {params['full_event_type']}"
    )
 
    for wl_idx, wl in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        fig = make_figure(NUM_COLS)
        fig.suptitle(f"{row_name} — Wavelength {wl} nm",
                     fontsize=12, fontweight="bold")
 
        # Row 1: Traces
        ax_run = fig.add_subplot(2, NUM_COLS, 1)
        if "running" in data and data["running"]["mean"] is not None:
            ax_run.plot(time_array, data["running"]["mean"],
                        color="#000000", linewidth=2, label="Mean")
            ax_run.fill_between(
                time_array,
                data["running"]["mean"] - data["running"]["sem"],
                data["running"]["mean"] + data["running"]["sem"],
                color="#000000", alpha=0.3)
            ax_run.axvline(x=0, color="#808080", linestyle="--",
                           alpha=0.8, label="Event")
            ax_run.set_xlim(time_array[0], time_array[-1])
            ax_run.set_xlabel("Time (s)")
            ax_run.set_ylabel("Speed (cm/s)")
            ax_run.legend()
            ax_run.grid(False)
        ax_run.set_title(
            f"{row_name} - Running Speed - {params['full_event_type']}")
 
        ax_dff = fig.add_subplot(2, NUM_COLS, 2)
        if wl in data["dff"]:
            ax_dff.plot(time_array, data["dff"][wl]["mean"],
                        color=color, linewidth=2, label="Mean")
            ax_dff.fill_between(
                time_array,
                data["dff"][wl]["mean"] - data["dff"][wl]["sem"],
                data["dff"][wl]["mean"] + data["dff"][wl]["sem"],
                color=color, alpha=0.3)
            ax_dff.axvline(x=0, color="#808080", linestyle="--",
                           alpha=0.8, label="Event")
            ax_dff.set_xlim(time_array[0], time_array[-1])
            ax_dff.set_xlabel("Time (s)")
            ax_dff.set_ylabel("ΔF/F")
            ax_dff.legend()
            ax_dff.grid(False)
        ax_dff.set_title(f"{row_name} - Fiber ΔF/F {wl}nm")
 
        ax_zs = fig.add_subplot(2, NUM_COLS, 3)
        if wl in data["zscore"]:
            ax_zs.plot(time_array, data["zscore"][wl]["mean"],
                       color=color, linewidth=2, label="Mean")
            ax_zs.fill_between(
                time_array,
                data["zscore"][wl]["mean"] - data["zscore"][wl]["sem"],
                data["zscore"][wl]["mean"] + data["zscore"][wl]["sem"],
                color=color, alpha=0.3)
            ax_zs.axvline(x=0, color="#808080", linestyle="--",
                          alpha=0.8, label="Event")
            ax_zs.set_xlim(time_array[0], time_array[-1])
            ax_zs.set_xlabel("Time (s)")
            ax_zs.set_ylabel("Z-score")
            ax_zs.legend()
            ax_zs.grid(False)
        ax_zs.set_title(f"{row_name} - Fiber Z-score {wl}nm")
 
        # Row 2: Heatmaps
        ax_run_heat = fig.add_subplot(2, NUM_COLS, 4)
        if "running" in data and len(data["running"]["episodes"]) > 0:
            draw_heatmap(ax_run_heat, data["running"]["episodes"],
                          time_array, "viridis", "Speed (cm/s)")
            ax_run_heat.set_title(f"{row_name} - Running Speed Heatmap")
        else:
            ax_run_heat.axis("off")
            ax_run_heat.set_title(f"{row_name} - Running Speed Heatmap")
 
        ax_dff_heat = fig.add_subplot(2, NUM_COLS, 5)
        if wl in data["dff"]:
            draw_heatmap(ax_dff_heat, data["dff"][wl]["episodes"],
                          time_array, "coolwarm", "ΔF/F")
            ax_dff_heat.set_title(f"{row_name} - Fiber ΔF/F Heatmap {wl}nm")
        else:
            ax_dff_heat.axis("off")
            ax_dff_heat.set_title(f"{row_name} - Fiber ΔF/F Heatmap {wl}nm")
 
        ax_zs_heat = fig.add_subplot(2, NUM_COLS, 6)
        if wl in data["zscore"]:
            draw_heatmap(ax_zs_heat, data["zscore"][wl]["episodes"],
                          time_array, "coolwarm", "Z-score")
            ax_zs_heat.set_title(f"{row_name} - Fiber Z-score Heatmap {wl}nm")
        else:
            ax_zs_heat.axis("off")
            ax_zs_heat.set_title(f"{row_name} - Fiber Z-score Heatmap {wl}nm")
 
        fig.tight_layout(rect=[0, 0, 1, 0.96])
        embed_figure(inner, fig, row_in_frame=wl_idx)
 
    log_message(f"Individual row plot created for {row_name}")

def plot_running_drug_results(results, params):
    """Plot running+drug results with multiple drug categories"""
    target_wavelengths = []
    for row_name, data in results.items():
        if 'target_wavelengths' in data:
            target_wavelengths = data['target_wavelengths']
            break
    if not target_wavelengths:
        target_wavelengths = ['470']
 
    wavelength_label = '+'.join(target_wavelengths)
    time_array = list(results.values())[0]['time']
 
    # Get all drug categories
    all_categories = []
    for data in results.values():
        if 'drug_categories' in data:
            for category in data['drug_categories']:
                if category not in all_categories:
                    all_categories.append(category)
 
    win, _, inner = make_scrollable_window(
        f"Running+Drug Analysis - {params['full_event_type']}"
    )
 
    for wl_idx, wl in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        fig = make_figure(NUM_COLS)
        fig.suptitle(f"Wavelength {wl} nm — Running+Drug", fontsize=12, fontweight="bold")
 
        # ── Row 1: Traces ──────────────────────────────────────────────
        ax_running = fig.add_subplot(2, NUM_COLS, 1)
        for idx, (row_name, data) in enumerate(results.items()):
            row_color = ROW_COLORS[idx % len(ROW_COLORS)]
            for cat_idx, category in enumerate(all_categories):
                if category in data and data[category]['running']['mean'] is not None:
                    if category == 'baseline':
                        alpha = 1/len(all_categories)
                        linestyle = '-'
                    else:
                        alpha = 1/len(all_categories) + (1/len(all_categories) * cat_idx)
                        linestyle = '-'
                    ax_running.plot(time_array, data[category]['running']['mean'],
                                  color=row_color, linestyle=linestyle, linewidth=2, alpha=alpha,
                                  label=f"{row_name} {category}")
                    ax_running.fill_between(time_array,
                                           data[category]['running']['mean'] - data[category]['running']['sem'],
                                           data[category]['running']['mean'] + data[category]['running']['sem'],
                                           color=row_color, alpha=alpha*0.3)
        ax_running.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_running.set_xlim(time_array[0], time_array[-1])
        ax_running.set_xlabel('Time (s)')
        ax_running.set_ylabel('Speed (cm/s)')
        ax_running.set_title(f'Running Speed - {params["full_event_type"]}')
        ax_running.legend(fontsize=7, ncol=2)
        ax_running.grid(False)
 
        ax_dff = fig.add_subplot(2, NUM_COLS, 2)
        for idx, (row_name, data) in enumerate(results.items()):
            row_color = ROW_COLORS[idx % len(ROW_COLORS)]
            for cat_idx, category in enumerate(all_categories):
                if category in data and wl in data[category]['dff']:
                    if category == 'baseline':
                        alpha = 1/len(all_categories)
                        linestyle = '-'
                    else:
                        alpha = 1/len(all_categories) + (1/len(all_categories) * cat_idx)
                        linestyle = '-'
                    ax_dff.plot(time_array, data[category]['dff'][wl]['mean'],
                              color=row_color, linewidth=2, linestyle=linestyle, alpha=alpha,
                              label=f'{row_name} {category}')
                    ax_dff.fill_between(time_array,
                                       data[category]['dff'][wl]['mean'] - data[category]['dff'][wl]['sem'],
                                       data[category]['dff'][wl]['mean'] + data[category]['dff'][wl]['sem'],
                                       color=row_color, alpha=alpha*0.3)
        ax_dff.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_dff.set_xlim(time_array[0], time_array[-1])
        ax_dff.set_xlabel('Time (s)')
        ax_dff.set_ylabel('ΔF/F')
        ax_dff.set_title(f'Fiber ΔF/F {wl}nm')
        ax_dff.legend(fontsize=7, ncol=2)
        ax_dff.grid(False)
 
        ax_zscore = fig.add_subplot(2, NUM_COLS, 3)
        for idx, (row_name, data) in enumerate(results.items()):
            row_color = ROW_COLORS[idx % len(ROW_COLORS)]
            for cat_idx, category in enumerate(all_categories):
                if category in data and wl in data[category]['zscore']:
                    if category == 'baseline':
                        alpha = 1/len(all_categories)
                        linestyle = '-'
                    else:
                        alpha = 1/len(all_categories) + (1/len(all_categories) * cat_idx)
                        linestyle = '-'
                    ax_zscore.plot(time_array, data[category]['zscore'][wl]['mean'],
                                 color=row_color, linewidth=2, linestyle=linestyle, alpha=alpha,
                                 label=f'{row_name} {category}')
                    ax_zscore.fill_between(time_array,
                                          data[category]['zscore'][wl]['mean'] - data[category]['zscore'][wl]['sem'],
                                          data[category]['zscore'][wl]['mean'] + data[category]['zscore'][wl]['sem'],
                                          color=row_color, alpha=alpha*0.3)
        ax_zscore.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_zscore.set_xlim(time_array[0], time_array[-1])
        ax_zscore.set_xlabel('Time (s)')
        ax_zscore.set_ylabel('Z-score')
        ax_zscore.set_title(f'Fiber Z-score {wl}nm')
        ax_zscore.legend(fontsize=7, ncol=2)
        ax_zscore.grid(False)
 
        # ── Row 2: Heatmaps ────────────────────────────────────────────
        ax_running_heat = fig.add_subplot(2, NUM_COLS, 4)
        all_running_episodes = []
        category_boundaries = []
        for category in all_categories:
            category_episodes = []
            for row_name, data in results.items():
                if category in data and len(data[category]['running']['episodes']) > 0:
                    category_episodes.extend(data[category]['running']['episodes'])
            if category_episodes:
                all_running_episodes.extend(category_episodes)
                if all_running_episodes:
                    category_boundaries.append(len(all_running_episodes))
        if all_running_episodes:
            draw_heatmap(ax_running_heat, np.array(all_running_episodes), time_array,
                         'viridis', 'Speed (cm/s)',
                         extra_lines=category_boundaries[:-1] if len(category_boundaries) > 1 else None)
            ax_running_heat.set_title('Running Speed Heatmap')
        else:
            ax_running_heat.axis('off')
            ax_running_heat.set_title('Running Speed Heatmap')
 
        ax_dff_heat = fig.add_subplot(2, NUM_COLS, 5)
        all_dff_episodes = []
        category_boundaries = []
        for category in all_categories:
            category_episodes = []
            for row_name, data in results.items():
                if category in data and wl in data[category]['dff']:
                    category_episodes.extend(data[category]['dff'][wl]['episodes'])
            if category_episodes:
                all_dff_episodes.extend(category_episodes)
                if all_dff_episodes:
                    category_boundaries.append(len(all_dff_episodes))
        if all_dff_episodes:
            draw_heatmap(ax_dff_heat, np.array(all_dff_episodes), time_array,
                         'coolwarm', 'ΔF/F',
                         extra_lines=category_boundaries[:-1] if len(category_boundaries) > 1 else None)
            ax_dff_heat.set_title(f'Fiber ΔF/F Heatmap {wl}nm')
        else:
            ax_dff_heat.axis('off')
            ax_dff_heat.set_title(f'Fiber ΔF/F Heatmap {wl}nm')
 
        ax_zscore_heat = fig.add_subplot(2, NUM_COLS, 6)
        all_zscore_episodes = []
        category_boundaries = []
        for category in all_categories:
            category_episodes = []
            for row_name, data in results.items():
                if category in data and wl in data[category]['zscore']:
                    category_episodes.extend(data[category]['zscore'][wl]['episodes'])
            if category_episodes:
                all_zscore_episodes.extend(category_episodes)
                if all_zscore_episodes:
                    category_boundaries.append(len(all_zscore_episodes))
        if all_zscore_episodes:
            draw_heatmap(ax_zscore_heat, np.array(all_zscore_episodes), time_array,
                         'coolwarm', 'Z-score',
                         extra_lines=category_boundaries[:-1] if len(category_boundaries) > 1 else None)
            ax_zscore_heat.set_title(f'Fiber Z-score Heatmap {wl}nm')
        else:
            ax_zscore_heat.axis('off')
            ax_zscore_heat.set_title(f'Fiber Z-score Heatmap {wl}nm')
 
        fig.tight_layout()
        embed_figure(inner, fig, row_in_frame=wl_idx)
 
    create_individual_row_windows_running_drug(results, params)

def create_individual_row_windows_running_drug(results, params):
    """Create individual windows for each row - running+drug"""
    for row_name, data in results.items():
        create_single_row_window_running_drug(row_name, data, params)

def create_single_row_window_running_drug(row_name, data, params):
    """Create window for a single row - running+drug with multiple categories"""
    target_wavelengths = data.get('target_wavelengths', ['470'])
    drug_categories = data.get('drug_categories', [])
    time_array = data['time']
 
    win, _, inner = make_scrollable_window(
        f"Running+Drug Analysis - {row_name} - {params['full_event_type']}"
    )
 
    for wl_idx, wl in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        fig = make_figure(NUM_COLS)
        fig.suptitle(f"{row_name} — Wavelength {wl} nm (Running+Drug)",
                     fontsize=12, fontweight="bold")
 
        # Row 1: Traces
        ax_running = fig.add_subplot(2, NUM_COLS, 1)
        for cat_idx, category in enumerate(drug_categories):
            if category in data and data[category]['running']['mean'] is not None:
                if category == 'baseline':
                    alpha = 1/len(drug_categories)
                    linestyle = '-'
                else:
                    alpha = 1/len(drug_categories) + (1/len(drug_categories) * cat_idx)
                    linestyle = '-'
                log_message(f"Plotting {row_name} - {category} - {cat_idx} running trace with alpha {alpha:.2f}")
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
        ax_running.set_title(f'{row_name} - Running Speed (Multi-Drug)')
        ax_running.legend(fontsize=8)
        ax_running.grid(False)
 
        ax_dff = fig.add_subplot(2, NUM_COLS, 2)
        for cat_idx, category in enumerate(drug_categories):
            if category in data and wl in data[category]['dff']:
                if category == 'baseline':
                    alpha = 1/len(drug_categories)
                    linestyle = '-'
                else:
                    alpha = 1/len(drug_categories) + (1/len(drug_categories) * cat_idx)
                    linestyle = '-'
                log_message(f"Plotting {row_name} - {category} - {cat_idx} dFF trace at {wl}nm with alpha {alpha:.2f}")
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
        ax_dff.set_title(f'{row_name} - Fiber ΔF/F {wl}nm (Multi-Drug)')
        ax_dff.legend(fontsize=8)
        ax_dff.grid(False)
 
        ax_zscore = fig.add_subplot(2, NUM_COLS, 3)
        for cat_idx, category in enumerate(drug_categories):
            if category in data and wl in data[category]['zscore']:
                if category == 'baseline':
                    alpha = 1/len(drug_categories)
                    linestyle = '-'
                else:
                    alpha = 1/len(drug_categories) + (1/len(drug_categories) * cat_idx)
                    linestyle = '-'
                log_message(f"Plotting {row_name} - {category} - {cat_idx} z-score trace at {wl}nm with alpha {alpha:.2f}")
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
        ax_zscore.set_title(f'{row_name} - Fiber Z-score {wl}nm (Multi-Drug)')
        ax_zscore.legend(fontsize=8)
        ax_zscore.grid(False)
 
        # Row 2: Heatmaps
        ax_running_heat = fig.add_subplot(2, NUM_COLS, 4)
        all_running_episodes = []
        category_boundaries = []
        for category in drug_categories:
            if category in data and len(data[category]['running']['episodes']) > 0:
                all_running_episodes.extend(data[category]['running']['episodes'])
                if all_running_episodes:
                    category_boundaries.append(len(all_running_episodes))
        if all_running_episodes:
            draw_heatmap(ax_running_heat, np.array(all_running_episodes), time_array,
                         'viridis', 'Speed (cm/s)',
                         extra_lines=category_boundaries[:-1] if len(category_boundaries) > 1 else None)
            ax_running_heat.set_title(f'{row_name} - Running Speed Heatmap (Multi-Drug)')
        else:
            ax_running_heat.axis('off')
            ax_running_heat.set_title(f'{row_name} - Running Speed Heatmap (Multi-Drug)')
 
        ax_dff_heat = fig.add_subplot(2, NUM_COLS, 5)
        all_dff_episodes = []
        category_boundaries = []
        for category in drug_categories:
            if category in data and wl in data[category]['dff']:
                all_dff_episodes.extend(data[category]['dff'][wl]['episodes'])
                if all_dff_episodes:
                    category_boundaries.append(len(all_dff_episodes))
        if all_dff_episodes:
            draw_heatmap(ax_dff_heat, np.array(all_dff_episodes), time_array,
                         'coolwarm', 'ΔF/F',
                         extra_lines=category_boundaries[:-1] if len(category_boundaries) > 1 else None)
            ax_dff_heat.set_title(f'{row_name} - Fiber ΔF/F Heatmap {wl}nm (Multi-Drug)')
        else:
            ax_dff_heat.axis('off')
            ax_dff_heat.set_title(f'{row_name} - Fiber ΔF/F Heatmap {wl}nm (Multi-Drug)')
 
        ax_zscore_heat = fig.add_subplot(2, NUM_COLS, 6)
        all_zscore_episodes = []
        category_boundaries = []
        for category in drug_categories:
            if category in data and wl in data[category]['zscore']:
                all_zscore_episodes.extend(data[category]['zscore'][wl]['episodes'])
                if all_zscore_episodes:
                    category_boundaries.append(len(all_zscore_episodes))
        if all_zscore_episodes:
            draw_heatmap(ax_zscore_heat, np.array(all_zscore_episodes), time_array,
                         'coolwarm', 'Z-score',
                         extra_lines=category_boundaries[:-1] if len(category_boundaries) > 1 else None)
            ax_zscore_heat.set_title(f'{row_name} - Fiber Z-score Heatmap {wl}nm (Multi-Drug)')
        else:
            ax_zscore_heat.axis('off')
            ax_zscore_heat.set_title(f'{row_name} - Fiber Z-score Heatmap {wl}nm (Multi-Drug)')
 
        fig.tight_layout()
        embed_figure(inner, fig, row_in_frame=wl_idx)
 
    log_message(f"Individual row plot created for {row_name} with {len(drug_categories)} drug categories")

def plot_running_optogenetics_results(results, params):
    """Plot running+optogenetics results with with/without comparison"""
    target_wavelengths = []
    for row_name, data in results.items():
        if 'target_wavelengths' in data:
            target_wavelengths = data['target_wavelengths']
            break
    if not target_wavelengths:
        target_wavelengths = ['470']
 
    wavelength_label = '+'.join(target_wavelengths)
    time_array = list(results.values())[0]['time']
 
    win, _, inner = make_scrollable_window(
        f"Running+Optogenetics Analysis - {params['full_event_type']}"
    )
 
    for wl_idx, wl in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        fig = make_figure(NUM_COLS)
        fig.suptitle(f"Wavelength {wl} nm — Running+Optogenetics",
                     fontsize=12, fontweight="bold")
 
        # ── Row 1: Traces ──────────────────────────────────────────────
        ax_running = fig.add_subplot(2, NUM_COLS, 1)
        for idx, (row_name, data) in enumerate(results.items()):
            row_color = ROW_COLORS[idx % len(ROW_COLORS)]
            if data['with_opto']['running']['mean'] is not None:
                ax_running.plot(time_array, data['with_opto']['running']['mean'],
                              color=row_color, linestyle='-', linewidth=2, alpha=1,
                              label=f"{row_name} With Opto")
                ax_running.fill_between(time_array,
                                       data['with_opto']['running']['mean'] - data['with_opto']['running']['sem'],
                                       data['with_opto']['running']['mean'] + data['with_opto']['running']['sem'],
                                       color=row_color, alpha=0.5)
            if data['without_opto']['running']['mean'] is not None:
                ax_running.plot(time_array, data['without_opto']['running']['mean'],
                              color=row_color, linestyle='-', linewidth=2, alpha=0.5,
                              label=f"{row_name} Without Opto")
                ax_running.fill_between(time_array,
                                       data['without_opto']['running']['mean'] - data['without_opto']['running']['sem'],
                                       data['without_opto']['running']['mean'] + data['without_opto']['running']['sem'],
                                       color=row_color, alpha=0.2)
        ax_running.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_running.set_xlim(time_array[0], time_array[-1])
        ax_running.set_xlabel('Time (s)')
        ax_running.set_ylabel('Speed (cm/s)')
        ax_running.set_title(f'Running Speed - {params["full_event_type"]}')
        ax_running.legend(fontsize=8)
        ax_running.grid(False)
 
        ax_dff = fig.add_subplot(2, NUM_COLS, 2)
        for idx, (row_name, data) in enumerate(results.items()):
            row_color = ROW_COLORS[idx % len(ROW_COLORS)]
            if wl in data['with_opto']['dff']:
                ax_dff.plot(time_array, data['with_opto']['dff'][wl]['mean'],
                          color=row_color, linewidth=2, linestyle='-', alpha=1,
                          label=f'{row_name} With Opto')
                ax_dff.fill_between(time_array,
                                   data['with_opto']['dff'][wl]['mean'] - data['with_opto']['dff'][wl]['sem'],
                                   data['with_opto']['dff'][wl]['mean'] + data['with_opto']['dff'][wl]['sem'],
                                   color=row_color, alpha=0.5)
            if wl in data['without_opto']['dff']:
                ax_dff.plot(time_array, data['without_opto']['dff'][wl]['mean'],
                          color=row_color, linewidth=2, linestyle='-', alpha=0.5,
                          label=f'{row_name} Without Opto')
                ax_dff.fill_between(time_array,
                                   data['without_opto']['dff'][wl]['mean'] - data['without_opto']['dff'][wl]['sem'],
                                   data['without_opto']['dff'][wl]['mean'] + data['without_opto']['dff'][wl]['sem'],
                                   color=row_color, alpha=0.2)
        ax_dff.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_dff.set_xlim(time_array[0], time_array[-1])
        ax_dff.set_xlabel('Time (s)')
        ax_dff.set_ylabel('ΔF/F')
        ax_dff.set_title(f'Fiber ΔF/F {wl}nm')
        ax_dff.legend(fontsize=8)
        ax_dff.grid(False)
 
        ax_zscore = fig.add_subplot(2, NUM_COLS, 3)
        for idx, (row_name, data) in enumerate(results.items()):
            row_color = ROW_COLORS[idx % len(ROW_COLORS)]
            if wl in data['with_opto']['zscore']:
                ax_zscore.plot(time_array, data['with_opto']['zscore'][wl]['mean'],
                             color=row_color, linewidth=2, linestyle='-', alpha=1,
                             label=f'{row_name} With Opto')
                ax_zscore.fill_between(time_array,
                                      data['with_opto']['zscore'][wl]['mean'] - data['with_opto']['zscore'][wl]['sem'],
                                      data['with_opto']['zscore'][wl]['mean'] + data['with_opto']['zscore'][wl]['sem'],
                                      color=row_color, alpha=0.5)
            if wl in data['without_opto']['zscore']:
                ax_zscore.plot(time_array, data['without_opto']['zscore'][wl]['mean'],
                             color=row_color, linewidth=2, linestyle='-', alpha=0.5,
                             label=f'{row_name} Without Opto')
                ax_zscore.fill_between(time_array,
                                      data['without_opto']['zscore'][wl]['mean'] - data['without_opto']['zscore'][wl]['sem'],
                                      data['without_opto']['zscore'][wl]['mean'] + data['without_opto']['zscore'][wl]['sem'],
                                      color=row_color, alpha=0.2)
        ax_zscore.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_zscore.set_xlim(time_array[0], time_array[-1])
        ax_zscore.set_xlabel('Time (s)')
        ax_zscore.set_ylabel('Z-score')
        ax_zscore.set_title(f'Fiber Z-score {wl}nm')
        ax_zscore.legend(fontsize=8)
        ax_zscore.grid(False)
 
        # ── Row 2: Heatmaps ────────────────────────────────────────────
        ax_running_heat = fig.add_subplot(2, NUM_COLS, 4)
        all_with_opto = []
        all_without_opto = []
        for row_name, data in results.items():
            if len(data['with_opto']['running']['episodes']) > 0:
                all_with_opto.extend(data['with_opto']['running']['episodes'])
            if len(data['without_opto']['running']['episodes']) > 0:
                all_without_opto.extend(data['without_opto']['running']['episodes'])
        if all_with_opto and all_without_opto:
            combined = np.vstack([np.array(all_with_opto), np.array(all_without_opto)])
            n_with = len(all_with_opto)
            draw_heatmap(ax_running_heat, combined, time_array,
                         'viridis', 'Speed (cm/s)',
                         extra_lines=[n_with] if n_with > 0 and len(combined) > n_with else None)
            ax_running_heat.set_title('Running Speed Heatmap')
        elif all_with_opto:
            draw_heatmap(ax_running_heat, np.array(all_with_opto), time_array,
                         'viridis', 'Speed (cm/s)')
            ax_running_heat.set_title('Running Speed Heatmap')
        elif all_without_opto:
            draw_heatmap(ax_running_heat, np.array(all_without_opto), time_array,
                         'viridis', 'Speed (cm/s)')
            ax_running_heat.set_title('Running Speed Heatmap')
        else:
            ax_running_heat.axis('off')
            ax_running_heat.set_title('Running Speed Heatmap')
 
        ax_dff_heat = fig.add_subplot(2, NUM_COLS, 5)
        all_with_opto_dff = []
        all_without_opto_dff = []
        for row_name, data in results.items():
            if wl in data['with_opto']['dff']:
                all_with_opto_dff.extend(data['with_opto']['dff'][wl]['episodes'])
            if wl in data['without_opto']['dff']:
                all_without_opto_dff.extend(data['without_opto']['dff'][wl]['episodes'])
        if all_with_opto_dff and all_without_opto_dff:
            combined_dff = np.vstack([np.array(all_with_opto_dff), np.array(all_without_opto_dff)])
            n_with = len(all_with_opto_dff)
            draw_heatmap(ax_dff_heat, combined_dff, time_array,
                         'coolwarm', 'ΔF/F',
                         extra_lines=[n_with] if n_with > 0 and len(combined_dff) > n_with else None)
            ax_dff_heat.set_title(f'Fiber ΔF/F Heatmap {wl}nm')
        elif all_with_opto_dff:
            draw_heatmap(ax_dff_heat, np.array(all_with_opto_dff), time_array,
                         'coolwarm', 'ΔF/F')
            ax_dff_heat.set_title(f'Fiber ΔF/F Heatmap {wl}nm')
        elif all_without_opto_dff:
            draw_heatmap(ax_dff_heat, np.array(all_without_opto_dff), time_array,
                         'coolwarm', 'ΔF/F')
            ax_dff_heat.set_title(f'Fiber ΔF/F Heatmap {wl}nm')
        else:
            ax_dff_heat.axis('off')
            ax_dff_heat.set_title(f'Fiber ΔF/F Heatmap {wl}nm')
 
        ax_zscore_heat = fig.add_subplot(2, NUM_COLS, 6)
        all_with_opto_zscore = []
        all_without_opto_zscore = []
        for row_name, data in results.items():
            if wl in data['with_opto']['zscore']:
                all_with_opto_zscore.extend(data['with_opto']['zscore'][wl]['episodes'])
            if wl in data['without_opto']['zscore']:
                all_without_opto_zscore.extend(data['without_opto']['zscore'][wl]['episodes'])
        if all_with_opto_zscore and all_without_opto_zscore:
            combined_zscore = np.vstack([np.array(all_with_opto_zscore), np.array(all_without_opto_zscore)])
            n_with = len(all_with_opto_zscore)
            draw_heatmap(ax_zscore_heat, combined_zscore, time_array,
                         'coolwarm', 'Z-score',
                         extra_lines=[n_with] if n_with > 0 and len(combined_zscore) > n_with else None)
            ax_zscore_heat.set_title(f'Fiber Z-score Heatmap {wl}nm')
        elif all_with_opto_zscore:
            draw_heatmap(ax_zscore_heat, np.array(all_with_opto_zscore), time_array,
                         'coolwarm', 'Z-score')
            ax_zscore_heat.set_title(f'Fiber Z-score Heatmap {wl}nm')
        elif all_without_opto_zscore:
            draw_heatmap(ax_zscore_heat, np.array(all_without_opto_zscore), time_array,
                         'coolwarm', 'Z-score')
            ax_zscore_heat.set_title(f'Fiber Z-score Heatmap {wl}nm')
        else:
            ax_zscore_heat.axis('off')
            ax_zscore_heat.set_title(f'Fiber Z-score Heatmap {wl}nm')
 
        fig.tight_layout()
        embed_figure(inner, fig, row_in_frame=wl_idx)
        
    create_individual_row_windows_running_optogenetics(results, params)

def create_individual_row_windows_running_optogenetics(results, params):
    """Create individual windows for each row - running+optogenetics"""
    for row_name, data in results.items():
        create_single_row_window_running_optogenetics(row_name, data, params)

def create_single_row_window_running_optogenetics(row_name, data, params):
    """Create window for a single row - running+optogenetics"""
    target_wavelengths = data.get('target_wavelengths', ['470'])
    time_array = data['time']
 
    win, _, inner = make_scrollable_window(
        f"Running+Optogenetics Analysis - {row_name} - {params['full_event_type']}"
    )
 
    for wl_idx, wl in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        fig = make_figure(NUM_COLS)
        fig.suptitle(f"{row_name} — Wavelength {wl} nm (Running+Optogenetics)",
                     fontsize=12, fontweight="bold")
 
        # Row 1: Traces
        ax_running = fig.add_subplot(2, NUM_COLS, 1)
        if data['with_opto']['running']['mean'] is not None:
            ax_running.plot(time_array, data['with_opto']['running']['mean'],
                          color="#000000", linewidth=2, linestyle='-', alpha=1, label='With Opto')
            ax_running.fill_between(time_array,
                                   data['with_opto']['running']['mean'] - data['with_opto']['running']['sem'],
                                   data['with_opto']['running']['mean'] + data['with_opto']['running']['sem'],
                                   color="#000000", alpha=0.5)
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
        ax_running.set_title(f'{row_name} - Running Speed')
        ax_running.legend()
        ax_running.grid(False)
 
        ax_dff = fig.add_subplot(2, NUM_COLS, 2)
        if wl in data['with_opto']['dff']:
            ax_dff.plot(time_array, data['with_opto']['dff'][wl]['mean'],
                      color=color, linewidth=2, linestyle='-', alpha=1, label='With Opto')
            ax_dff.fill_between(time_array,
                               data['with_opto']['dff'][wl]['mean'] - data['with_opto']['dff'][wl]['sem'],
                               data['with_opto']['dff'][wl]['mean'] + data['with_opto']['dff'][wl]['sem'],
                               color=color, alpha=0.5)
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
        ax_dff.set_title(f'{row_name} - Fiber ΔF/F {wl}nm')
        ax_dff.legend()
        ax_dff.grid(False)
 
        ax_zscore = fig.add_subplot(2, NUM_COLS, 3)
        if wl in data['with_opto']['zscore']:
            ax_zscore.plot(time_array, data['with_opto']['zscore'][wl]['mean'],
                         color=color, linewidth=2, linestyle='-', alpha=1, label='With Opto')
            ax_zscore.fill_between(time_array,
                                  data['with_opto']['zscore'][wl]['mean'] - data['with_opto']['zscore'][wl]['sem'],
                                  data['with_opto']['zscore'][wl]['mean'] + data['with_opto']['zscore'][wl]['sem'],
                                  color=color, alpha=0.5)
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
        ax_zscore.set_title(f'{row_name} - Fiber Z-score {wl}nm')
        ax_zscore.legend()
        ax_zscore.grid(False)
 
        # Row 2: Heatmaps
        ax_running_heat = fig.add_subplot(2, NUM_COLS, 4)
        with_run = data['with_opto']['running']['episodes']
        without_run = data['without_opto']['running']['episodes']
        if len(with_run) > 0 and len(without_run) > 0:
            combined = np.vstack([with_run, without_run])
            n_with = len(with_run)
            draw_heatmap(ax_running_heat, combined, time_array,
                         'viridis', 'Speed (cm/s)',
                         extra_lines=[n_with] if n_with > 0 and len(combined) > n_with else None)
            ax_running_heat.set_title(f'{row_name} - Running Speed Heatmap')
        elif len(with_run) > 0:
            draw_heatmap(ax_running_heat, with_run, time_array, 'viridis', 'Speed (cm/s)')
            ax_running_heat.set_title(f'{row_name} - Running Speed Heatmap')
        elif len(without_run) > 0:
            draw_heatmap(ax_running_heat, without_run, time_array, 'viridis', 'Speed (cm/s)')
            ax_running_heat.set_title(f'{row_name} - Running Speed Heatmap')
        else:
            ax_running_heat.text(0.5, 0.5, 'No running data available',
                               ha='center', va='center', transform=ax_running_heat.transAxes,
                               fontsize=12, color='#666666')
            ax_running_heat.set_title(f'{row_name} - Running Speed Heatmap')
            ax_running_heat.axis('off')
 
        ax_dff_heat = fig.add_subplot(2, NUM_COLS, 5)
        if (wl in data['with_opto']['dff'] and wl in data['without_opto']['dff'] and
                len(data['with_opto']['dff'][wl]['episodes']) > 0 and
                len(data['without_opto']['dff'][wl]['episodes']) > 0):
            combined = np.vstack([data['with_opto']['dff'][wl]['episodes'],
                                  data['without_opto']['dff'][wl]['episodes']])
            n_with = len(data['with_opto']['dff'][wl]['episodes'])
            draw_heatmap(ax_dff_heat, combined, time_array,
                         'coolwarm', 'ΔF/F',
                         extra_lines=[n_with] if n_with > 0 and len(combined) > n_with else None)
            ax_dff_heat.set_title(f'{row_name} - Fiber ΔF/F Heatmap {wl}nm')
        elif wl in data['with_opto']['dff'] and len(data['with_opto']['dff'][wl]['episodes']) > 0:
            draw_heatmap(ax_dff_heat, data['with_opto']['dff'][wl]['episodes'],
                         time_array, 'coolwarm', 'ΔF/F')
            ax_dff_heat.set_title(f'{row_name} - Fiber ΔF/F Heatmap {wl}nm')
        elif wl in data['without_opto']['dff'] and len(data['without_opto']['dff'][wl]['episodes']) > 0:
            draw_heatmap(ax_dff_heat, data['without_opto']['dff'][wl]['episodes'],
                         time_array, 'coolwarm', 'ΔF/F')
            ax_dff_heat.set_title(f'{row_name} - Fiber ΔF/F Heatmap {wl}nm')
        else:
            ax_dff_heat.text(0.5, 0.5, f'No dFF data for {wl}nm',
                           ha='center', va='center', transform=ax_dff_heat.transAxes,
                           fontsize=12, color='#666666')
            ax_dff_heat.set_title(f'{row_name} - Fiber ΔF/F Heatmap {wl}nm')
            ax_dff_heat.axis('off')
 
        ax_zscore_heat = fig.add_subplot(2, NUM_COLS, 6)
        if (wl in data['with_opto']['zscore'] and wl in data['without_opto']['zscore'] and
                len(data['with_opto']['zscore'][wl]['episodes']) > 0 and
                len(data['without_opto']['zscore'][wl]['episodes']) > 0):
            combined = np.vstack([data['with_opto']['zscore'][wl]['episodes'],
                                  data['without_opto']['zscore'][wl]['episodes']])
            n_with = len(data['with_opto']['zscore'][wl]['episodes'])
            draw_heatmap(ax_zscore_heat, combined, time_array,
                         'coolwarm', 'Z-score',
                         extra_lines=[n_with] if n_with > 0 and len(combined) > n_with else None)
            ax_zscore_heat.set_title(f'{row_name} - Fiber Z-score Heatmap {wl}nm')
        elif wl in data['with_opto']['zscore'] and len(data['with_opto']['zscore'][wl]['episodes']) > 0:
            draw_heatmap(ax_zscore_heat, data['with_opto']['zscore'][wl]['episodes'],
                         time_array, 'coolwarm', 'Z-score')
            ax_zscore_heat.set_title(f'{row_name} - Fiber Z-score Heatmap {wl}nm')
        elif wl in data['without_opto']['zscore'] and len(data['without_opto']['zscore'][wl]['episodes']) > 0:
            draw_heatmap(ax_zscore_heat, data['without_opto']['zscore'][wl]['episodes'],
                         time_array, 'coolwarm', 'Z-score')
            ax_zscore_heat.set_title(f'{row_name} - Fiber Z-score Heatmap {wl}nm')
        else:
            ax_zscore_heat.text(0.5, 0.5, f'No z-score data for {wl}nm',
                              ha='center', va='center', transform=ax_zscore_heat.transAxes,
                              fontsize=12, color='#666666')
            ax_zscore_heat.set_title(f'{row_name} - Fiber Z-score Heatmap {wl}nm')
            ax_zscore_heat.axis('off')
 
        fig.tight_layout()
        embed_figure(inner, fig, row_in_frame=wl_idx)
 
    log_message(f"Individual row plot created for {row_name} (with/without optogenetics)")

def run_running_optogenetics_analysis(row_data, params, all_optogenetic_events, 
                                     power_values, all_drug_events, analysis_mode):
    """Run running+optogenetics analysis"""
    log_message(f"Starting running+optogenetics analysis for {len(row_data)} row(s)...")
    
    results = {}
    all_statistics = []
    
    for row_name, animals in row_data.items():
        log_message(f"Analyzing {row_name} with {len(animals)} animal(s)...")
        
        if analysis_mode == "running+optogenetics+drug":
            # Drug mode
            row_result, row_stats = analyze_row_running_optogenetics_drug(
                row_name, animals, params, all_optogenetic_events, 
                power_values, all_drug_events
            )
        else:
            # No drug mode
            row_result, row_stats = analyze_row_running_optogenetics(
                row_name, animals, params, all_optogenetic_events, power_values
            )
        
        if row_result:
            results[row_name] = row_result
        if row_stats:
            all_statistics.extend(row_stats)
    
    if params['export_stats'] and all_statistics:
        export_type = "running_opto_drug_induced" if analysis_mode == "running+optogenetics+drug" else "running_opto_induced"
        export_results(results, all_statistics, export_type, params['full_event_type'])
    
    if results:
        if analysis_mode == "running+optogenetics+drug":
            plot_running_optogenetics_drug_results(results, params)
        else:
            plot_running_optogenetics_results(results, params)
        log_message("Analysis completed successfully")
    else:
        log_message("No valid results", "ERROR")

def analyze_row_running_optogenetics_drug(row_name, animals, params, 
                                          all_optogenetic_events, power_values, all_drug_events):
    """Analyze one row for running+optogenetics+drug mode with multiple drugs"""
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
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'drug_name_config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            drug_name_config = json.load(f)
    else:
        drug_name_config = {}
    
    # Collect all unique drug categories
    all_drug_categories = []
    
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
                    for i in range(len(drug_info)):
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
                if category not in all_drug_categories:
                    all_drug_categories.append(category)
            
            log_message(f"{animal_id} all drug categories: {', '.join(all_drug_categories)}")
            
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
                            row_name, f"{animal_id}_{category}_with_opto", 
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
                            row_name, f"{animal_id}_{category}_without_opto",
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

def collect_statistics_with_condition(row_name, animal_id, event_type, result, 
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
            'row': row_name,
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
                        'row': row_name,
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
                        'row': row_name,
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
    for row_name, data in results.items():
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
    
    # Create individual row windows
    create_individual_row_windows_running_optogenetics_drug_multi(results, params)

def plot_comparison_window_multi_drug(results, params, category, condition1_key, condition2_key,
                                      window_title, label1, label2):
    target_wavelengths = []
    for row_name, data in results.items():
        if 'target_wavelengths' in data:
            target_wavelengths = data['target_wavelengths']
            break
    if not target_wavelengths:
        target_wavelengths = ['470']
 
    time_array = list(results.values())[0]['time']
 
    win, _, inner = make_scrollable_window(f"{window_title} - All Rows")
 
    for wl_idx, wl in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        fig = make_figure(NUM_COLS)
        fig.suptitle(f"Wavelength {wl} nm — {window_title}", fontsize=11, fontweight="bold")
 
        # Row 1: Traces
        ax_running = fig.add_subplot(2, NUM_COLS, 1)
        for idx, (row_name, data) in enumerate(results.items()):
            if category not in data:
                continue
            row_color = ROW_COLORS[idx % len(ROW_COLORS)]
            category_data = data[category]
            if condition1_key in category_data and category_data[condition1_key]['running']['mean'] is not None:
                ax_running.plot(time_array, category_data[condition1_key]['running']['mean'],
                              color=row_color, linestyle='-', linewidth=2, alpha=1,
                              label=f"{row_name} {label1}")
                ax_running.fill_between(time_array,
                                       category_data[condition1_key]['running']['mean'] - category_data[condition1_key]['running']['sem'],
                                       category_data[condition1_key]['running']['mean'] + category_data[condition1_key]['running']['sem'],
                                       color=row_color, alpha=0.5)
            if condition2_key in category_data and category_data[condition2_key]['running']['mean'] is not None:
                ax_running.plot(time_array, category_data[condition2_key]['running']['mean'],
                              color=row_color, linestyle='-', linewidth=2, alpha=0.5,
                              label=f"{row_name} {label2}")
                ax_running.fill_between(time_array,
                                       category_data[condition2_key]['running']['mean'] - category_data[condition2_key]['running']['sem'],
                                       category_data[condition2_key]['running']['mean'] + category_data[condition2_key]['running']['sem'],
                                       color=row_color, alpha=0.2)
        ax_running.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_running.set_xlim(time_array[0], time_array[-1])
        ax_running.set_xlabel('Time (s)')
        ax_running.set_ylabel('Speed (cm/s)')
        ax_running.set_title(f'{category} - Running Speed Comparison')
        ax_running.legend(fontsize=8, ncol=2)
        ax_running.grid(False)
 
        ax_dff = fig.add_subplot(2, NUM_COLS, 2)
        for idx, (row_name, data) in enumerate(results.items()):
            if category not in data:
                continue
            row_color = ROW_COLORS[idx % len(ROW_COLORS)]
            category_data = data[category]
            if condition1_key in category_data and wl in category_data[condition1_key]['dff']:
                ax_dff.plot(time_array, category_data[condition1_key]['dff'][wl]['mean'],
                          color=row_color, linewidth=2, linestyle='-', alpha=1,
                          label=f'{row_name} {label1}')
                ax_dff.fill_between(time_array,
                                   category_data[condition1_key]['dff'][wl]['mean'] - category_data[condition1_key]['dff'][wl]['sem'],
                                   category_data[condition1_key]['dff'][wl]['mean'] + category_data[condition1_key]['dff'][wl]['sem'],
                                   color=row_color, alpha=0.5)
            if condition2_key in category_data and wl in category_data[condition2_key]['dff']:
                ax_dff.plot(time_array, category_data[condition2_key]['dff'][wl]['mean'],
                          color=row_color, linewidth=2, linestyle='-', alpha=0.5,
                          label=f'{row_name} {label2}')
                ax_dff.fill_between(time_array,
                                   category_data[condition2_key]['dff'][wl]['mean'] - category_data[condition2_key]['dff'][wl]['sem'],
                                   category_data[condition2_key]['dff'][wl]['mean'] + category_data[condition2_key]['dff'][wl]['sem'],
                                   color=row_color, alpha=0.2)
        ax_dff.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_dff.set_xlim(time_array[0], time_array[-1])
        ax_dff.set_xlabel('Time (s)')
        ax_dff.set_ylabel('ΔF/F')
        ax_dff.set_title(f'{category} - Fiber ΔF/F {wl}nm Comparison')
        ax_dff.legend(fontsize=8, ncol=2)
        ax_dff.grid(False)
 
        ax_zscore = fig.add_subplot(2, NUM_COLS, 3)
        for idx, (row_name, data) in enumerate(results.items()):
            if category not in data:
                continue
            row_color = ROW_COLORS[idx % len(ROW_COLORS)]
            category_data = data[category]
            if condition1_key in category_data and wl in category_data[condition1_key]['zscore']:
                ax_zscore.plot(time_array, category_data[condition1_key]['zscore'][wl]['mean'],
                             color=row_color, linewidth=2, linestyle='-', alpha=1,
                             label=f'{row_name} {label1}')
                ax_zscore.fill_between(time_array,
                                      category_data[condition1_key]['zscore'][wl]['mean'] - category_data[condition1_key]['zscore'][wl]['sem'],
                                      category_data[condition1_key]['zscore'][wl]['mean'] + category_data[condition1_key]['zscore'][wl]['sem'],
                                      color=row_color, alpha=0.5)
            if condition2_key in category_data and wl in category_data[condition2_key]['zscore']:
                ax_zscore.plot(time_array, category_data[condition2_key]['zscore'][wl]['mean'],
                             color=row_color, linewidth=2, linestyle='-', alpha=0.5,
                             label=f'{row_name} {label2}')
                ax_zscore.fill_between(time_array,
                                      category_data[condition2_key]['zscore'][wl]['mean'] - category_data[condition2_key]['zscore'][wl]['sem'],
                                      category_data[condition2_key]['zscore'][wl]['mean'] + category_data[condition2_key]['zscore'][wl]['sem'],
                                      color=row_color, alpha=0.2)
        ax_zscore.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_zscore.set_xlim(time_array[0], time_array[-1])
        ax_zscore.set_xlabel('Time (s)')
        ax_zscore.set_ylabel('Z-score')
        ax_zscore.set_title(f'{category} - Fiber Z-score {wl}nm Comparison')
        ax_zscore.legend(fontsize=8, ncol=2)
        ax_zscore.grid(False)
 
        # Row 2: Heatmaps
        ax_running_heat = fig.add_subplot(2, NUM_COLS, 4)
        all_cond1 = []
        all_cond2 = []
        for row_name, data in results.items():
            if category not in data:
                continue
            category_data = data[category]
            if condition1_key in category_data and len(category_data[condition1_key]['running']['episodes']) > 0:
                all_cond1.extend(category_data[condition1_key]['running']['episodes'])
            if condition2_key in category_data and len(category_data[condition2_key]['running']['episodes']) > 0:
                all_cond2.extend(category_data[condition2_key]['running']['episodes'])
        if all_cond1 or all_cond2:
            combined = np.array(all_cond1 + all_cond2) if all_cond1 + all_cond2 else None
            if combined is not None:
                n_cond1 = len(all_cond1)
                draw_heatmap(ax_running_heat, combined, time_array,
                             'viridis', 'Speed (cm/s)',
                             extra_lines=[n_cond1] if n_cond1 > 0 and len(combined) > n_cond1 else None)
                ax_running_heat.set_title(f'{category} - Running Speed Heatmap')
        else:
            ax_running_heat.text(0.5, 0.5, 'No data available',
                               ha='center', va='center', fontsize=12, color='gray')
            ax_running_heat.set_title(f'{category} - Running Speed Heatmap')
            ax_running_heat.axis('off')
 
        ax_dff_heat = fig.add_subplot(2, NUM_COLS, 5)
        all_cond1_dff = []
        all_cond2_dff = []
        for row_name, data in results.items():
            if category not in data:
                continue
            category_data = data[category]
            if condition1_key in category_data and wl in category_data[condition1_key]['dff']:
                all_cond1_dff.extend(category_data[condition1_key]['dff'][wl]['episodes'])
            if condition2_key in category_data and wl in category_data[condition2_key]['dff']:
                all_cond2_dff.extend(category_data[condition2_key]['dff'][wl]['episodes'])
        if all_cond1_dff or all_cond2_dff:
            combined_dff = np.array(all_cond1_dff + all_cond2_dff) if all_cond1_dff + all_cond2_dff else None
            if combined_dff is not None:
                n_cond1 = len(all_cond1_dff)
                draw_heatmap(ax_dff_heat, combined_dff, time_array,
                             'coolwarm', 'ΔF/F',
                             extra_lines=[n_cond1] if n_cond1 > 0 and len(combined_dff) > n_cond1 else None)
                ax_dff_heat.set_title(f'{category} - Fiber ΔF/F Heatmap {wl}nm')
        else:
            ax_dff_heat.text(0.5, 0.5, 'No data available',
                           ha='center', va='center', fontsize=12, color='gray')
            ax_dff_heat.set_title(f'{category} - Fiber ΔF/F Heatmap {wl}nm')
            ax_dff_heat.axis('off')
 
        ax_zscore_heat = fig.add_subplot(2, NUM_COLS, 6)
        all_cond1_zscore = []
        all_cond2_zscore = []
        for row_name, data in results.items():
            if category not in data:
                continue
            category_data = data[category]
            if condition1_key in category_data and wl in category_data[condition1_key]['zscore']:
                all_cond1_zscore.extend(category_data[condition1_key]['zscore'][wl]['episodes'])
            if condition2_key in category_data and wl in category_data[condition2_key]['zscore']:
                all_cond2_zscore.extend(category_data[condition2_key]['zscore'][wl]['episodes'])
        if all_cond1_zscore or all_cond2_zscore:
            combined_zscore = np.array(all_cond1_zscore + all_cond2_zscore) if all_cond1_zscore + all_cond2_zscore else None
            if combined_zscore is not None:
                n_cond1 = len(all_cond1_zscore)
                draw_heatmap(ax_zscore_heat, combined_zscore, time_array,
                             'coolwarm', 'Z-score',
                             extra_lines=[n_cond1] if n_cond1 > 0 and len(combined_zscore) > n_cond1 else None)
                ax_zscore_heat.set_title(f'{category} - Fiber Z-score Heatmap {wl}nm')
        else:
            ax_zscore_heat.text(0.5, 0.5, 'No data available',
                              ha='center', va='center', fontsize=12, color='gray')
            ax_zscore_heat.set_title(f'{category} - Fiber Z-score Heatmap {wl}nm')
            ax_zscore_heat.axis('off')
 
        fig.tight_layout()
        embed_figure(inner, fig, row_in_frame=wl_idx)
 
    log_message(f"Comparison window created: {window_title}")

def plot_comparison_window_multi_drug_categories(results, params, condition_key,
                                                  categories, window_title):
    target_wavelengths = []
    for row_name, data in results.items():
        if 'target_wavelengths' in data:
            target_wavelengths = data['target_wavelengths']
            break
    if not target_wavelengths:
        target_wavelengths = ['470']
 
    time_array = list(results.values())[0]['time']
 
    win, _, inner = make_scrollable_window(f"{window_title} - All Rows")
 
    for wl_idx, wl in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        fig = make_figure(NUM_COLS)
        fig.suptitle(f"Wavelength {wl} nm — {window_title}", fontsize=11, fontweight="bold")
 
        # Row 1: Traces
        ax_running = fig.add_subplot(2, NUM_COLS, 1)
        for idx, (row_name, data) in enumerate(results.items()):
            row_color = ROW_COLORS[idx % len(ROW_COLORS)]
            for cat_idx, category in enumerate(categories):
                if category not in data:
                    continue
                category_data = data[category]
                if condition_key in category_data and category_data[condition_key]['running']['mean'] is not None:
                    alpha = 1/len(categories) + (1/len(categories) * cat_idx)
                    ax_running.plot(time_array, category_data[condition_key]['running']['mean'],
                                  color=row_color, linestyle='-', linewidth=2,
                                  alpha=alpha, label=f"{row_name} {category}")
                    ax_running.fill_between(time_array,
                                           category_data[condition_key]['running']['mean'] - category_data[condition_key]['running']['sem'],
                                           category_data[condition_key]['running']['mean'] + category_data[condition_key]['running']['sem'],
                                           color=row_color, alpha=alpha*0.5)
        ax_running.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_running.set_xlim(time_array[0], time_array[-1])
        ax_running.set_xlabel('Time (s)')
        ax_running.set_ylabel('Speed (cm/s)')
        ax_running.set_title(f'{window_title} - Running Speed')
        ax_running.legend(fontsize=7, ncol=2)
        ax_running.grid(False)
 
        ax_dff = fig.add_subplot(2, NUM_COLS, 2)
        for idx, (row_name, data) in enumerate(results.items()):
            row_color = ROW_COLORS[idx % len(ROW_COLORS)]
            for cat_idx, category in enumerate(categories):
                if category not in data:
                    continue
                category_data = data[category]
                if condition_key in category_data and wl in category_data[condition_key]['dff']:
                    alpha = 1/len(categories) + (1/len(categories) * cat_idx)
                    ax_dff.plot(time_array, category_data[condition_key]['dff'][wl]['mean'],
                              color=row_color, linewidth=2, linestyle='-',
                              alpha=alpha, label=f'{row_name} {category}')
                    ax_dff.fill_between(time_array,
                                       category_data[condition_key]['dff'][wl]['mean'] - category_data[condition_key]['dff'][wl]['sem'],
                                       category_data[condition_key]['dff'][wl]['mean'] + category_data[condition_key]['dff'][wl]['sem'],
                                       color=row_color, alpha=alpha*0.5)
        ax_dff.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_dff.set_xlim(time_array[0], time_array[-1])
        ax_dff.set_xlabel('Time (s)')
        ax_dff.set_ylabel('ΔF/F')
        ax_dff.set_title(f'{window_title} - Fiber ΔF/F {wl}nm')
        ax_dff.legend(fontsize=7, ncol=2)
        ax_dff.grid(False)
 
        ax_zscore = fig.add_subplot(2, NUM_COLS, 3)
        for idx, (row_name, data) in enumerate(results.items()):
            row_color = ROW_COLORS[idx % len(ROW_COLORS)]
            for cat_idx, category in enumerate(categories):
                if category not in data:
                    continue
                category_data = data[category]
                if condition_key in category_data and wl in category_data[condition_key]['zscore']:
                    alpha = 1/len(categories) + (1/len(categories) * cat_idx)
                    ax_zscore.plot(time_array, category_data[condition_key]['zscore'][wl]['mean'],
                                 color=row_color, linewidth=2, linestyle='-',
                                 alpha=alpha, label=f'{row_name} {category}')
                    ax_zscore.fill_between(time_array,
                                          category_data[condition_key]['zscore'][wl]['mean'] - category_data[condition_key]['zscore'][wl]['sem'],
                                          category_data[condition_key]['zscore'][wl]['mean'] + category_data[condition_key]['zscore'][wl]['sem'],
                                          color=row_color, alpha=alpha*0.5)
        ax_zscore.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_zscore.set_xlim(time_array[0], time_array[-1])
        ax_zscore.set_xlabel('Time (s)')
        ax_zscore.set_ylabel('Z-score')
        ax_zscore.set_title(f'{window_title} - Fiber Z-score {wl}nm')
        ax_zscore.legend(fontsize=7, ncol=2)
        ax_zscore.grid(False)
 
        # Row 2: Heatmaps
        ax_running_heat = fig.add_subplot(2, NUM_COLS, 4)
        all_episodes = []
        category_boundaries = []
        for category in categories:
            category_episodes = []
            for row_name, data in results.items():
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
            draw_heatmap(ax_running_heat, np.array(all_episodes), time_array,
                         'viridis', 'Speed (cm/s)',
                         extra_lines=category_boundaries[:-1] if len(category_boundaries) > 1 else None)
            ax_running_heat.set_title(f'{window_title} - Running Speed Heatmap')
        else:
            ax_running_heat.text(0.5, 0.5, 'No data available',
                               ha='center', va='center', fontsize=12, color='gray')
            ax_running_heat.set_title(f'{window_title} - Running Speed Heatmap')
            ax_running_heat.axis('off')
 
        ax_dff_heat = fig.add_subplot(2, NUM_COLS, 5)
        all_episodes = []
        category_boundaries = []
        for category in categories:
            category_episodes = []
            for row_name, data in results.items():
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
            draw_heatmap(ax_dff_heat, np.array(all_episodes), time_array,
                         'coolwarm', 'ΔF/F',
                         extra_lines=category_boundaries[:-1] if len(category_boundaries) > 1 else None)
            ax_dff_heat.set_title(f'{window_title} - Fiber ΔF/F Heatmap {wl}nm')
        else:
            ax_dff_heat.text(0.5, 0.5, 'No data available',
                           ha='center', va='center', fontsize=12, color='gray')
            ax_dff_heat.set_title(f'{window_title} - Fiber ΔF/F Heatmap {wl}nm')
            ax_dff_heat.axis('off')
 
        ax_zscore_heat = fig.add_subplot(2, NUM_COLS, 6)
        all_episodes = []
        category_boundaries = []
        for category in categories:
            category_episodes = []
            for row_name, data in results.items():
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
            draw_heatmap(ax_zscore_heat, np.array(all_episodes), time_array,
                         'coolwarm', 'Z-score',
                         extra_lines=category_boundaries[:-1] if len(category_boundaries) > 1 else None)
            ax_zscore_heat.set_title(f'{window_title} - Fiber Z-score Heatmap {wl}nm')
        else:
            ax_zscore_heat.text(0.5, 0.5, 'No data available',
                              ha='center', va='center', fontsize=12, color='gray')
            ax_zscore_heat.set_title(f'{window_title} - Fiber Z-score Heatmap {wl}nm')
            ax_zscore_heat.axis('off')
 
        fig.tight_layout()
        embed_figure(inner, fig, row_in_frame=wl_idx)
 
    log_message(f"Multi-drug categories window created: {window_title}")

def create_individual_row_windows_running_optogenetics_drug_multi(results, params):
    """Create individual windows for each row - running+optogenetics+drug with multiple drugs"""
    for row_name, data in results.items():
        # Get all drug categories
        drug_categories = data.get('drug_categories', [])
        
        # Create multiple comparison windows for this row
        # 1. For each category: with vs without opto
        for category in drug_categories:
            create_single_row_category_window(
                row_name, data, params, category,
                f'Running+Optogenetics+Drug - {row_name} - {category}: With vs Without Opto'
            )
        
        # 2. Overall comparison across categories
        create_single_row_all_categories_window(
            row_name, data, params,
            f'Running+Optogenetics+Drug - {row_name} - All Categories'
        )

def create_single_row_category_window(row_name, data, params, category, window_title):
    """Create window for one drug category showing with/without opto comparison"""
    if category not in data:
        return
 
    target_wavelengths = data.get('target_wavelengths', ['470'])
    time_array = data['time']
    category_data = data[category]
 
    win, _, inner = make_scrollable_window(window_title)
 
    for wl_idx, wl in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        fig = make_figure(NUM_COLS)
        fig.suptitle(f"Wavelength {wl} nm — {window_title}", fontsize=11, fontweight="bold")
 
        # Row 1: Traces
        ax_running = fig.add_subplot(2, NUM_COLS, 1)
        if 'with_opto' in category_data and category_data['with_opto']['running']['mean'] is not None:
            ax_running.plot(time_array, category_data['with_opto']['running']['mean'],
                          color="#000000", linewidth=2, linestyle='-', alpha=1, label='With Opto')
            ax_running.fill_between(time_array,
                                   category_data['with_opto']['running']['mean'] - category_data['with_opto']['running']['sem'],
                                   category_data['with_opto']['running']['mean'] + category_data['with_opto']['running']['sem'],
                                   color="#000000", alpha=0.5)
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
 
        ax_dff = fig.add_subplot(2, NUM_COLS, 2)
        if 'with_opto' in category_data and wl in category_data['with_opto']['dff']:
            ax_dff.plot(time_array, category_data['with_opto']['dff'][wl]['mean'],
                      color=color, linewidth=2, linestyle='-', alpha=1, label='With Opto')
            ax_dff.fill_between(time_array,
                               category_data['with_opto']['dff'][wl]['mean'] - category_data['with_opto']['dff'][wl]['sem'],
                               category_data['with_opto']['dff'][wl]['mean'] + category_data['with_opto']['dff'][wl]['sem'],
                               color=color, alpha=0.5)
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
 
        ax_zscore = fig.add_subplot(2, NUM_COLS, 3)
        if 'with_opto' in category_data and wl in category_data['with_opto']['zscore']:
            ax_zscore.plot(time_array, category_data['with_opto']['zscore'][wl]['mean'],
                         color=color, linewidth=2, linestyle='-', alpha=1, label='With Opto')
            ax_zscore.fill_between(time_array,
                                  category_data['with_opto']['zscore'][wl]['mean'] - category_data['with_opto']['zscore'][wl]['sem'],
                                  category_data['with_opto']['zscore'][wl]['mean'] + category_data['with_opto']['zscore'][wl]['sem'],
                                  color=color, alpha=0.5)
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
 
        # Row 2: Heatmaps
        ax_running_heat = fig.add_subplot(2, NUM_COLS, 4)
        with_episodes = []
        without_episodes = []
        if 'with_opto' in category_data and len(category_data['with_opto']['running']['episodes']) > 0:
            with_episodes = list(category_data['with_opto']['running']['episodes'])
        if 'without_opto' in category_data and len(category_data['without_opto']['running']['episodes']) > 0:
            without_episodes = list(category_data['without_opto']['running']['episodes'])
        if with_episodes or without_episodes:
            combined = np.array(with_episodes + without_episodes)
            n_with = len(with_episodes)
            draw_heatmap(ax_running_heat, combined, time_array,
                         'viridis', 'Speed (cm/s)',
                         extra_lines=[n_with] if n_with > 0 and len(combined) > n_with else None)
            ax_running_heat.set_title(f'{category} - Running Speed Heatmap')
            ax_running_heat.legend(loc='upper right', fontsize=8)
 
        ax_dff_heat = fig.add_subplot(2, NUM_COLS, 5)
        with_dff = []
        without_dff = []
        if 'with_opto' in category_data and wl in category_data['with_opto']['dff']:
            with_dff = list(category_data['with_opto']['dff'][wl]['episodes'])
        if 'without_opto' in category_data and wl in category_data['without_opto']['dff']:
            without_dff = list(category_data['without_opto']['dff'][wl]['episodes'])
        if with_dff or without_dff:
            combined = np.array(with_dff + without_dff)
            n_with = len(with_dff)
            draw_heatmap(ax_dff_heat, combined, time_array,
                         'coolwarm', 'ΔF/F',
                         extra_lines=[n_with] if n_with > 0 and len(combined) > n_with else None)
            ax_dff_heat.set_title(f'{category} - Fiber ΔF/F Heatmap {wl}nm')
            ax_dff_heat.legend(loc='upper right', fontsize=8)
 
        ax_zscore_heat = fig.add_subplot(2, NUM_COLS, 6)
        with_zscore = []
        without_zscore = []
        if 'with_opto' in category_data and wl in category_data['with_opto']['zscore']:
            with_zscore = list(category_data['with_opto']['zscore'][wl]['episodes'])
        if 'without_opto' in category_data and wl in category_data['without_opto']['zscore']:
            without_zscore = list(category_data['without_opto']['zscore'][wl]['episodes'])
        if with_zscore or without_zscore:
            combined = np.array(with_zscore + without_zscore)
            n_with = len(with_zscore)
            draw_heatmap(ax_zscore_heat, combined, time_array,
                         'coolwarm', 'Z-score',
                         extra_lines=[n_with] if n_with > 0 and len(combined) > n_with else None)
            ax_zscore_heat.set_title(f'{category} - Fiber Z-score Heatmap {wl}nm')
            ax_zscore_heat.legend(loc='upper right', fontsize=8)
 
        fig.tight_layout()
        embed_figure(inner, fig, row_in_frame=wl_idx)
 
    log_message(f"Category window created: {window_title}")

def create_single_row_all_categories_window(row_name, data, params, window_title):
    """Create window showing all categories with opto condition comparison"""
    target_wavelengths = data.get('target_wavelengths', ['470'])
    drug_categories = data.get('drug_categories', [])
    time_array = data['time']
 
    win, _, inner = make_scrollable_window(window_title)
 
    for wl_idx, wl in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        fig = make_figure(NUM_COLS)
        fig.suptitle(f"Wavelength {wl} nm — {window_title}", fontsize=11, fontweight="bold")
 
        # Row 1: Traces
        ax_running = fig.add_subplot(2, NUM_COLS, 1)
        for cat_idx, category in enumerate(drug_categories):
            if category not in data:
                continue
            category_data = data[category]
            if 'with_opto' in category_data and category_data['with_opto']['running']['mean'] is not None:
                alpha = 1/len(drug_categories) + (1/len(drug_categories) * cat_idx)
                log_message(f"Plotting {row_name} - {category} - {cat_idx} with alpha {alpha}")
                ax_running.plot(time_array, category_data['with_opto']['running']['mean'],
                              color=ROW_COLORS[cat_idx % len(ROW_COLORS)],
                              linewidth=2, linestyle='-', alpha=alpha,
                              label=f'{category} +Opto')
                ax_running.fill_between(time_array,
                                       category_data['with_opto']['running']['mean'] - category_data['with_opto']['running']['sem'],
                                       category_data['with_opto']['running']['mean'] + category_data['with_opto']['running']['sem'],
                                       color=ROW_COLORS[cat_idx % len(ROW_COLORS)], alpha=alpha*0.3)
            if 'without_opto' in category_data and category_data['without_opto']['running']['mean'] is not None:
                alpha = 1/len(drug_categories) + (1/len(drug_categories) * cat_idx)
                log_message(f"Plotting {row_name} - {category} - {cat_idx} without opto with alpha {alpha}")
                ax_running.plot(time_array, category_data['without_opto']['running']['mean'],
                              color=ROW_COLORS[cat_idx % len(ROW_COLORS)],
                              linewidth=2, linestyle='-', alpha=alpha,
                              label=f'{category} -Opto')
                ax_running.fill_between(time_array,
                                       category_data['without_opto']['running']['mean'] - category_data['without_opto']['running']['sem'],
                                       category_data['without_opto']['running']['mean'] + category_data['without_opto']['running']['sem'],
                                       color=ROW_COLORS[cat_idx % len(ROW_COLORS)], alpha=alpha*0.3)
        ax_running.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_running.set_xlim(time_array[0], time_array[-1])
        ax_running.set_xlabel('Time (s)')
        ax_running.set_ylabel('Speed (cm/s)')
        ax_running.set_title(f'{row_name} - Running Speed (All Categories)')
        ax_running.legend(fontsize=7, ncol=2)
        ax_running.grid(False)
 
        ax_dff = fig.add_subplot(2, NUM_COLS, 2)
        for cat_idx, category in enumerate(drug_categories):
            if category not in data:
                continue
            category_data = data[category]
            if 'with_opto' in category_data and wl in category_data['with_opto']['dff']:
                alpha = 1/len(drug_categories) + (1/len(drug_categories) * cat_idx)
                log_message(f"Plotting {row_name} - {category} - {cat_idx} with alpha {alpha}")
                ax_dff.plot(time_array, category_data['with_opto']['dff'][wl]['mean'],
                          color=ROW_COLORS[cat_idx % len(ROW_COLORS)],
                          linewidth=2, linestyle='-', alpha=alpha,
                          label=f'{category} +Opto')
                ax_dff.fill_between(time_array,
                                   category_data['with_opto']['dff'][wl]['mean'] - category_data['with_opto']['dff'][wl]['sem'],
                                   category_data['with_opto']['dff'][wl]['mean'] + category_data['with_opto']['dff'][wl]['sem'],
                                   color=ROW_COLORS[cat_idx % len(ROW_COLORS)], alpha=alpha*0.3)
            if 'without_opto' in category_data and wl in category_data['without_opto']['dff']:
                alpha = 1/len(drug_categories) + (1/len(drug_categories) * cat_idx)
                log_message(f"Plotting {row_name} - {category} - {cat_idx} without opto with alpha {alpha}")
                ax_dff.plot(time_array, category_data['without_opto']['dff'][wl]['mean'],
                          color=ROW_COLORS[cat_idx % len(ROW_COLORS)],
                          linewidth=2, linestyle='-', alpha=alpha,
                          label=f'{category} -Opto')
                ax_dff.fill_between(time_array,
                                   category_data['without_opto']['dff'][wl]['mean'] - category_data['without_opto']['dff'][wl]['sem'],
                                   category_data['without_opto']['dff'][wl]['mean'] + category_data['without_opto']['dff'][wl]['sem'],
                                   color=ROW_COLORS[cat_idx % len(ROW_COLORS)], alpha=alpha*0.3)
        ax_dff.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_dff.set_xlim(time_array[0], time_array[-1])
        ax_dff.set_xlabel('Time (s)')
        ax_dff.set_ylabel('ΔF/F')
        ax_dff.set_title(f'{row_name} - Fiber ΔF/F {wl}nm (All Categories)')
        ax_dff.legend(fontsize=6, ncol=2)
        ax_dff.grid(False)
 
        ax_zscore = fig.add_subplot(2, NUM_COLS, 3)
        for cat_idx, category in enumerate(drug_categories):
            if category not in data:
                continue
            category_data = data[category]
            if 'with_opto' in category_data and wl in category_data['with_opto']['zscore']:
                alpha = 1/len(drug_categories) + (1/len(drug_categories) * cat_idx)
                log_message(f"Plotting {row_name} - {category} - {cat_idx} with alpha {alpha}")
                ax_zscore.plot(time_array, category_data['with_opto']['zscore'][wl]['mean'],
                             color=ROW_COLORS[cat_idx % len(ROW_COLORS)],
                             linewidth=2, linestyle='-', alpha=alpha,
                             label=f'{category} +Opto')
                ax_zscore.fill_between(time_array,
                                      category_data['with_opto']['zscore'][wl]['mean'] - category_data['with_opto']['zscore'][wl]['sem'],
                                      category_data['with_opto']['zscore'][wl]['mean'] + category_data['with_opto']['zscore'][wl]['sem'],
                                      color=ROW_COLORS[cat_idx % len(ROW_COLORS)], alpha=alpha*0.3)
            if 'without_opto' in category_data and wl in category_data['without_opto']['zscore']:
                alpha = 1/len(drug_categories) + (1/len(drug_categories) * cat_idx)
                log_message(f"Plotting {row_name} - {category} - {cat_idx} without opto with alpha {alpha}")
                ax_zscore.plot(time_array, category_data['without_opto']['zscore'][wl]['mean'],
                             color=ROW_COLORS[cat_idx % len(ROW_COLORS)],
                             linewidth=2, linestyle='-', alpha=alpha,
                             label=f'{category} -Opto')
                ax_zscore.fill_between(time_array,
                                      category_data['without_opto']['zscore'][wl]['mean'] - category_data['without_opto']['zscore'][wl]['sem'],
                                      category_data['without_opto']['zscore'][wl]['mean'] + category_data['without_opto']['zscore'][wl]['sem'],
                                      color=ROW_COLORS[cat_idx % len(ROW_COLORS)], alpha=alpha*0.3)
        ax_zscore.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_zscore.set_xlim(time_array[0], time_array[-1])
        ax_zscore.set_xlabel('Time (s)')
        ax_zscore.set_ylabel('Z-score')
        ax_zscore.set_title(f'{row_name} - Fiber Z-score {wl}nm (All Categories)')
        ax_zscore.legend(fontsize=6, ncol=2)
        ax_zscore.grid(False)
 
        # Row 2: Heatmaps
        ax_running_heat = fig.add_subplot(2, NUM_COLS, 4)
        all_running_episodes = []
        category_boundaries = []
        condition_boundaries = []
        for category in drug_categories:
            if category not in data:
                continue
            category_data = data[category]
            if 'with_opto' in category_data and len(category_data['with_opto']['running']['episodes']) > 0:
                all_running_episodes.extend(category_data['with_opto']['running']['episodes'])
                if all_running_episodes:
                    condition_boundaries.append(len(all_running_episodes))
            if 'without_opto' in category_data and len(category_data['without_opto']['running']['episodes']) > 0:
                all_running_episodes.extend(category_data['without_opto']['running']['episodes'])
                if all_running_episodes:
                    category_boundaries.append(len(all_running_episodes))
        if all_running_episodes:
            extra = []
            extra += [b for b in condition_boundaries[:-1]]
            extra += [b for b in category_boundaries[:-1]]
            extra = sorted(set(extra)) if extra else None
            draw_heatmap(ax_running_heat, np.array(all_running_episodes), time_array,
                         'viridis', 'Speed (cm/s)', extra_lines=extra if extra else None)
            # category label ticks
            y_positions = []
            current_y = 0
            for i, category in enumerate(drug_categories):
                if category not in data:
                    continue
                category_data = data[category]
                h = 0
                if 'with_opto' in category_data:
                    h += len(category_data['with_opto']['running']['episodes'])
                if 'without_opto' in category_data:
                    h += len(category_data['without_opto']['running']['episodes'])
                if h > 0:
                    y_positions.append((current_y + h / 2, category))
                    current_y += h
            if y_positions:
                y_pos, y_labels = zip(*y_positions)
                ax_running_heat.set_yticks(y_pos)
                ax_running_heat.set_yticklabels(y_labels, fontsize=7)
            ax_running_heat.set_title(f'{row_name} - Running Speed Heatmap (All Categories)')
        else:
            ax_running_heat.text(0.5, 0.5, 'No running data available',
                               ha='center', va='center', transform=ax_running_heat.transAxes,
                               fontsize=12, color='#666666')
            ax_running_heat.set_title(f'{row_name} - Running Speed Heatmap (All Categories)')
            ax_running_heat.axis('off')
 
        ax_dff_heat = fig.add_subplot(2, NUM_COLS, 5)
        all_dff_episodes = []
        category_boundaries_dff = []
        condition_boundaries_dff = []
        for category in drug_categories:
            if category not in data:
                continue
            category_data = data[category]
            if 'with_opto' in category_data and wl in category_data['with_opto']['dff']:
                all_dff_episodes.extend(category_data['with_opto']['dff'][wl]['episodes'])
                if all_dff_episodes:
                    condition_boundaries_dff.append(len(all_dff_episodes))
            if 'without_opto' in category_data and wl in category_data['without_opto']['dff']:
                all_dff_episodes.extend(category_data['without_opto']['dff'][wl]['episodes'])
                if all_dff_episodes:
                    category_boundaries_dff.append(len(all_dff_episodes))
        if all_dff_episodes:
            extra = sorted(set(condition_boundaries_dff[:-1] + category_boundaries_dff[:-1])) if (condition_boundaries_dff[:-1] + category_boundaries_dff[:-1]) else None
            draw_heatmap(ax_dff_heat, np.array(all_dff_episodes), time_array,
                         'coolwarm', 'ΔF/F', extra_lines=extra)
            y_positions = []
            current_y = 0
            for i, category in enumerate(drug_categories):
                if category not in data:
                    continue
                category_data = data[category]
                h = 0
                if 'with_opto' in category_data and wl in category_data['with_opto']['dff']:
                    h += len(category_data['with_opto']['dff'][wl]['episodes'])
                if 'without_opto' in category_data and wl in category_data['without_opto']['dff']:
                    h += len(category_data['without_opto']['dff'][wl]['episodes'])
                if h > 0:
                    y_positions.append((current_y + h / 2, category))
                    current_y += h
            if y_positions:
                y_pos, y_labels = zip(*y_positions)
                ax_dff_heat.set_yticks(y_pos)
                ax_dff_heat.set_yticklabels(y_labels, fontsize=7)
            ax_dff_heat.set_title(f'{row_name} - Fiber ΔF/F Heatmap {wl}nm (All Categories)')
        else:
            ax_dff_heat.text(0.5, 0.5, f'No dFF data for {wl}nm',
                           ha='center', va='center', transform=ax_dff_heat.transAxes,
                           fontsize=12, color='#666666')
            ax_dff_heat.set_title(f'{row_name} - Fiber ΔF/F Heatmap {wl}nm (All Categories)')
            ax_dff_heat.axis('off')
 
        ax_zscore_heat = fig.add_subplot(2, NUM_COLS, 6)
        all_zscore_episodes = []
        category_boundaries_zscore = []
        condition_boundaries_zscore = []
        for category in drug_categories:
            if category not in data:
                continue
            category_data = data[category]
            if 'with_opto' in category_data and wl in category_data['with_opto']['zscore']:
                all_zscore_episodes.extend(category_data['with_opto']['zscore'][wl]['episodes'])
                if all_zscore_episodes:
                    condition_boundaries_zscore.append(len(all_zscore_episodes))
            if 'without_opto' in category_data and wl in category_data['without_opto']['zscore']:
                all_zscore_episodes.extend(category_data['without_opto']['zscore'][wl]['episodes'])
                if all_zscore_episodes:
                    category_boundaries_zscore.append(len(all_zscore_episodes))
        if all_zscore_episodes:
            extra = sorted(set(condition_boundaries_zscore[:-1] + category_boundaries_zscore[:-1])) if (condition_boundaries_zscore[:-1] + category_boundaries_zscore[:-1]) else None
            draw_heatmap(ax_zscore_heat, np.array(all_zscore_episodes), time_array,
                         'coolwarm', 'Z-score', extra_lines=extra)
            y_positions = []
            current_y = 0
            for i, category in enumerate(drug_categories):
                if category not in data:
                    continue
                category_data = data[category]
                h = 0
                if 'with_opto' in category_data and wl in category_data['with_opto']['zscore']:
                    h += len(category_data['with_opto']['zscore'][wl]['episodes'])
                if 'without_opto' in category_data and wl in category_data['without_opto']['zscore']:
                    h += len(category_data['without_opto']['zscore'][wl]['episodes'])
                if h > 0:
                    y_positions.append((current_y + h / 2, category))
                    current_y += h
            if y_positions:
                y_pos, y_labels = zip(*y_positions)
                ax_zscore_heat.set_yticks(y_pos)
                ax_zscore_heat.set_yticklabels(y_labels, fontsize=7)
            ax_zscore_heat.set_title(f'{row_name} - Fiber Z-score Heatmap {wl}nm (All Categories)')
        else:
            ax_zscore_heat.text(0.5, 0.5, f'No z-score data for {wl}nm',
                              ha='center', va='center', transform=ax_zscore_heat.transAxes,
                              fontsize=12, color='#666666')
            ax_zscore_heat.set_title(f'{row_name} - Fiber Z-score Heatmap {wl}nm (All Categories)')
            ax_zscore_heat.axis('off')
 
        fig.tight_layout()
        embed_figure(inner, fig, row_in_frame=wl_idx)
 
    log_message(f"All categories window created: {window_title}")