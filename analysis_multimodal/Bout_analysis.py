"""
Activated during Only Running Analysis. Supports both running and running+drug analysis for only running analysis results in multi_animal_data. Bout analysis with table configuration to select and analyze different running sessions(running: different days, running+drug: baseline, drug1, drug2, etc.). Bout analysis with parameters configuration to select different bout types(general, locomotion, reset, jerk, other, and rest), different directions(general, forward, backward and balance) and statistic windows(start and end, you can enter 'start' and 'end' to start and end, you can also enter 'start' and 'start+1000' / 'end-1000' and 'end' to acquire the same statistic duration). When run analysis, output the all bouts speed distribution figure in differnt rows meet the selected bout type and direction, Optionally outputs a table with the number of bouts, duration, mean speed and peak speed for selected bout type, direction and statistic windows.)
"""

import os
import csv
import json
import numpy as np
import tkinter as tk
import matplotlib.pyplot as plt

from matplotlib import colors
from tkinter import filedialog
from matplotlib.ticker import PercentFormatter

from infrastructure.logger import log_message
from analysis_multimodal.Multimodal_analysis import get_events_from_bouts, create_parameter_panel, get_parameters_from_ui, identify_drug_sessions, create_control_panel, create_table_window, initialize_table

def show_bout_analysis(root, multi_animal_data, analysis_mode="running"):
    """
    Show bout analysis configuration window
    analysis_mode: "running", "running+drug"
    """
    if not multi_animal_data:
        log_message("No animal data available", "ERROR")
        return
    
    all_drug_events = {}
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
    
    available_bout_directions = []
    for animal_data in multi_animal_data:
        if 'bouts_with_direction' in animal_data and animal_data['bouts_with_direction']:
            bouts_with_direction = animal_data['bouts_with_direction']
            for bout_type, bouts_with_direction1 in bouts_with_direction.items():
                for bout_direction, bout in bouts_with_direction1.items():
                    if bout_direction not in available_bout_directions:
                        available_bout_directions.append(bout_direction)
                        
    log_message(f"Available bout types: {available_bout_types}")
    log_message(f"Available bout directions: {available_bout_directions}")

    if not available_bout_types:
        log_message("No bout types found in animal data", "ERROR")
        return
    
    # Create main window with parameter panel and table
    main_window = tk.Toplevel(root)
    if analysis_mode == "running":
        title = "Running-Bout Analysis"
    elif analysis_mode == "running+drug":
        title = "Running+Drug-Bout Analysis"
        
    main_window.title(title)
    main_window.geometry("900x700")
    main_window.transient(root)
    main_window.grab_set()
    
    # Main container with two sections
    container = tk.Frame(main_window, bg="#f8f8f8")
    container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # Left panel: Parameters
    param_config = {
        'show_stats_window': True,
        'stats_start': "start",
        'stats_end': "end",
        'show_bout_type': True,
        'bout_types': available_bout_types,
        'show_bout_directions': True,
        'bout_directions': available_bout_directions
    }
    
    param_frame = create_parameter_panel(container, param_config)
    param_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 5))
    
    # Right panel: Table
    table_frame = tk.Frame(container, bg="#f8f8f8")
    table_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
    
    btn_frame = tk.Frame(main_window, bg="#f8f8f8")
    btn_frame.pack(fill=tk.X, padx=10, pady=10)
    
    table_manager = TableManager(root, table_frame, btn_frame, multi_animal_data, analysis_mode)
        
    def run_analysis():
        params = get_parameters_from_ui(param_frame, require_statistics_window=True, require_bout_type=True, require_bout_direction=True)
        if params:
            # Add full_event_type
            params['full_event_type'] = f"{params['bout_type'].replace('_bouts', '')}_{params['bout_direction']}"
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
            run_running_only_bout_analysis(row_data, params)
        elif analysis_mode == "running+drug":
            run_running_drug_bout_analysis(row_data, params)
            
def run_running_only_bout_analysis(row_data, params):
    """Run only running bout analysis"""
    log_message("Running bout analysis...")
    results = {}
    for row_name, animals in row_data.items():
        log_message(f"Analyzing {row_name} with {len(animals)} animals...")
        row_result = analyze_row_running_bouts(row_name, animals, params)
        results[row_name] = row_result
        
    if results:
        plot_running_bout_speed_distribution(results, params, 'running_only_bout_analysis')
        log_message("Analysis completed successfully")
        if params['export_stats']:
            export_running_bout_stats(results, params, 'running_only_bout_analysis')
    else:
        log_message("No valid results", "ERROR")

def run_running_drug_bout_analysis(row_data, params):
    """Run running+drug bout analysis"""
    log_message("Running+Drug bout analysis...")
    results = {}
    for row_name, animals in row_data.items():
        log_message(f"Analyzing {row_name} with {len(animals)} animals...")
        row_result = analyze_row_running_drug_bout(animals, params, row_name)
        results[row_name] = row_result
        
    if results:
        plot_running_bout_speed_distribution(results, params, 'running_drug_bout_analysis')
        log_message("Analysis completed successfully")
        if params['export_stats']:
            export_running_bout_stats(results, params, 'running_drug_bout_analysis')
        
def analyze_row_running_bouts(row_name, animals, params):
    """"Compute bout duration, mean speed and peak speed for each animal in the row duration statistic window, and return the results"""
    start_window = params.get('stats_start', 'start')
    end_window = params.get('stats_end', 'end')
    if start_window != 'start':
        start_index_str, start_shift_str = start_window.split('+') if '+' in start_window else start_window.split('-')
        start_shift_time = int(start_shift_str)
    
    if end_window != 'end':
        end_index_str, end_shift_str = end_window.split('+') if '+' in end_window else end_window.split('-')
        end_shift_time = int(end_shift_str)
        
    results = []
    for animal_data in animals:
        try:
            animal_id = animal_data.get('animal_single_channel_id', 'Unknown')
            
            # Get events
            events = get_events_from_bouts(animal_data, params['full_event_type'], duration=True)
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
            
            for event in events:
                event_start, event_end = event
                if start_window != 'start':
                    if start_index_str == 'start':
                        window_start = running_timestamps[0] + start_shift_time
                    elif start_index_str == 'end':
                        window_start = running_timestamps[-1] - start_shift_time
                else:
                    window_start = running_timestamps[0]
                    
                if end_window != 'end':
                    if end_index_str == 'start':
                        window_end = running_timestamps[0] + end_shift_time
                    elif end_index_str == 'end':
                        window_end = running_timestamps[-1] - end_shift_time
                else:
                    window_end = running_timestamps[-1]
                        
                # Check if event falls within the statistic window
                if event_start >= window_start and event_end <= window_end:
                    event_speeds = running_speed[(running_timestamps >= event_start) & (running_timestamps <= event_end)]
                    if len(event_speeds) == 0:
                        continue
                    bout_duration = event_end - event_start
                    mean_speed = np.mean(event_speeds)
                    peak_speed = np.max(event_speeds)
                    results.append({
                        'row_name': row_name,
                        'animal_id': animal_id,
                        'bout_start': event_start,
                        'bout_end': event_end,
                        'duration_s': bout_duration,
                        'mean_speed_cm_s': mean_speed,
                        'peak_speed_cm_s': peak_speed,
                        'bout_speeds': event_speeds
                    })
        
        except Exception as e:
            log_message(f"Error analyzing {animal_id}: {str(e)}", "ERROR")
                    
    return results

def analyze_row_running_drug_bout(animals, params, row_name):
    """Analysis for running+drug bout analysis, compute bout duration, mean speed and peak speed for each animal in the row duration statistic window, and return the results, need auto identify drug sessions and analyze bouts in each drug session"""
    start_window = params.get('stats_start', 'start')
    end_window = params.get('stats_end', 'end')
    if start_window != 'start':
        start_index_str, start_shift_str = start_window.split('+') if '+' in start_window else start_window.split('-')
        start_shift_time = int(start_shift_str)
    
    if end_window != 'end':
        end_index_str, end_shift_str = end_window.split('+') if '+' in end_window else end_window.split('-')
        end_shift_time = int(end_shift_str)
        
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
                
                if start_window != 'start':
                    if start_index_str == 'start':
                        window_start = running_end_time + start_shift_time if running_end_time else onset_time + start_shift_time
                    elif start_index_str == 'end':
                        window_start = offset_time - start_shift_time
                else:
                    window_start = onset_time
                
                if end_window != 'end':
                    if end_index_str == 'start':
                        window_end = running_end_time + end_shift_time if running_end_time else onset_time + end_shift_time
                    elif end_index_str == 'end':
                        window_end = offset_time - end_shift_time
                else:
                    window_end = offset_time
                
                drug_info.append({
                    'name': drug_name,
                    'onset': window_start,
                    'offset': window_end,
                    'idx': idx
                })
            
            # Sort by onset time
            drug_info.sort(key=lambda x: x['onset'])
            
            log_message(f"Animal {animal_id} drug timing:")
            for d in drug_info:
                log_message(f"{d['name']}: onset={d['onset']:.1f}s, offset={d['offset']:.1f}s")
            
            # Get running events
            events = get_events_from_bouts(animal_data, params['full_event_type'], duration=True)
            if not events:
                continue
            
            # Classify running events into drug categories
            # Now using onset/offset times instead of just onset
            event_categories = {}
            
            for event in events:
                event_start, event_end = event
                category = 'baseline'
                
                # Check if event is before first drug onset
                if event_start < drug_info[0]['onset']:
                    category = 'baseline'
                else:
                    # Find which drug period this event belongs to
                    # Check from latest to earliest drug
                    for i in range(len(drug_info)):
                        # Event must be after onset AND before offset
                        if drug_info[i]['onset'] <= event_start < drug_info[i]['offset']:
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
                event_categories[category].append((event_start, event_end))
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
            
            for category, cat_events in event_categories.items():
                for event in cat_events:
                    event_start, event_end = event
                    event_speeds = running_speed[(running_timestamps >= event_start) & (running_timestamps <= event_end)]
                    if len(event_speeds) == 0:
                        continue
                    bout_duration = event_end - event_start
                    mean_speed = np.mean(event_speeds)
                    peak_speed = np.max(event_speeds)
                    
                    if category not in category_data:
                        category_data[category] = []
                    
                    category_data[category].append({
                        'row_name': row_name,
                        'animal_id': animal_id,
                        'bout_start': event_start,
                        'bout_end': event_end,
                        'duration_s': bout_duration,
                        'mean_speed_cm_s': mean_speed,
                        'peak_speed_cm_s': peak_speed,
                        'bout_speeds': event_speeds
                    })
                    
        except Exception as e:
            log_message(f"Error analyzing {animal_id}: {str(e)}", "ERROR")
            
    return category_data

def plot_running_bout_speed_distribution(results, params, event_type):
    """Plot speed histogram distribution for all bouts in different rows"""
    if event_type == 'running_only_bout_analysis':
        for row_name, row_result in results.items():
            all_bout_speeds = np.concatenate([res['bout_speeds'] for res in row_result if 'bout_speeds' in res])
            ax = plt.figure(figsize=(9, 6)).add_subplot(1, 1, 1)
            N, bins, patches = ax.hist(all_bout_speeds, bins=30, alpha=1, density=True)
            fracs = N / N.max()
            norm = colors.Normalize(fracs.min(), fracs.max())
            ax.yaxis.set_major_formatter(PercentFormatter(xmax=1))
            for thisfrac, thispatch in zip(fracs, patches):
                color = plt.cm.coolwarm(thisfrac)
                thispatch.set_facecolor(color)
            ax.set_title(f"{row_name} - Bout Speed Distribution", fontsize=14, fontweight='bold')
            ax.set_xlabel("Speed (cm/s)", fontsize=12)
            ax.set_ylabel("Density", fontsize=12)
            plt.tight_layout()
            plt.show()
    elif event_type == 'running_drug_bout_analysis':
        for row_name, category_data in results.items():
            ax = plt.figure(figsize=(10, 6)).add_subplot(1, 1, 1)
            colors_list = plt.cm.tab10.colors  # Get a list of 10 distinct colors
            i = 1
            for category, cat_results in category_data.items():
                all_bout_speeds = np.concatenate([res['bout_speeds'] for res in cat_results if 'bout_speeds' in res])
                if len(all_bout_speeds) == 0:
                    continue
                N, bins, patches = ax.hist(all_bout_speeds, bins=30, alpha=0.5, density=True, label=category, color=colors_list[i % len(colors_list)])
                # fracs = N / N.max()
                # norm = colors.Normalize(fracs.min(), fracs.max())
                # ax.yaxis.set_major_formatter(PercentFormatter(xmax=1))
                # for thisfrac, thispatch in zip(fracs, patches):
                #     color = plt.cm.coolwarm(thisfrac)
                #     thispatch.set_facecolor(color)
                i += 1
            ax.set_title(f"{row_name} - Bout Speed Distribution by Drug Category", fontsize=14, fontweight='bold')
            ax.set_xlabel("Speed (cm/s)", fontsize=12)
            ax.set_ylabel("Density", fontsize=12)
            ax.legend()
            plt.tight_layout()
            plt.show()

def export_running_bout_stats(results, params, event_type):
    """Export bout stats to CSV file"""
    output_file = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], title="Save Running Bout Analysis Results")
    if not output_file:
        log_message("No file selected. Running bout analysis results were not saved.", "WARNING")
        return
    
    with open(output_file, mode='w', newline='') as file:
        writer = csv.writer(file)
        if event_type == 'running_only_bout_analysis':
            writer.writerow(['Row Name', 'Animal ID', 'Event Type', 'Trial', 'Bout Start', 'Bout End', 'Duration (s)', 'Mean Speed (cm/s)', 'Peak Speed (cm/s)'])
            
            for row_name, row_result in results.items():
                i = 1
                for res in row_result:
                    writer.writerow([
                        res.get('row_name', ''),
                        res.get('animal_id', ''),
                        event_type,
                        i,
                        res.get('bout_start', ''),
                        res.get('bout_end', ''),
                        res.get('duration_s', ''),
                        res.get('mean_speed_cm_s', ''),
                        res.get('peak_speed_cm_s', '')
                    ])
                    i += 1
        elif event_type == 'running_drug_bout_analysis':
            writer.writerow(['Row Name', 'Animal ID', 'Event Type', 'Drug Category', 'Trial', 'Bout Start', 'Bout End', 'Duration (s)', 'Mean Speed (cm/s)', 'Peak Speed (cm/s)'])
            
            for row_name, category_data in results.items():
                for category, cat_results in category_data.items():
                    i = 1
                    for res in cat_results:
                        writer.writerow([
                            res.get('row_name', ''),
                            res.get('animal_id', ''),
                            event_type,
                            category,
                            i,
                            res.get('bout_start', ''),
                            res.get('bout_end', ''),
                            res.get('duration_s', ''),
                            res.get('mean_speed_cm_s', ''),
                            res.get('peak_speed_cm_s', '')
                        ])
                        i += 1
    
    log_message(f"Running bout analysis results saved to {output_file}")