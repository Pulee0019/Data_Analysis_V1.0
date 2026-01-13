"""
Drug-induced activity analysis with table configuration
Supports multi-animal drug event analysis
"""
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
    create_table_window, initialize_table, create_control_panel
)

# Colors for different days
DAY_COLORS = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', 
              '#1abc9c', '#e67e22', '#34495e', '#f1c40f', '#95a5a6']
FIBER_COLORS = ['#008000', "#FF0000", '#FFA500']

def show_drug_induced_analysis(root, multi_animal_data, analysis_mode="drug"):
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
    param_frame = create_parameter_panel(container)
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
    start_time_var = tk.StringVar(value="-10")
    tk.Entry(start_frame, textvariable=start_time_var, width=8, 
            font=("Microsoft YaHei", 8)).pack(side=tk.LEFT, padx=5)
    
    end_frame = tk.Frame(time_frame, bg="#f8f8f8")
    end_frame.pack(fill=tk.X, pady=5)
    tk.Label(end_frame, text="End:", bg="#f8f8f8", 
            font=("Microsoft YaHei", 8), width=8, anchor='w').pack(side=tk.LEFT, padx=10)
    end_time_var = tk.StringVar(value="20")
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
    baseline_start_var = tk.StringVar(value="-2")
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
    
    def run_analysis(self, params):
        """Run drug-induced analysis with current table configuration"""
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

def analyze_day_drug_induced(day_name, animals, params):
    """Analyze drug-induced effects for one day (multiple animals combined)"""
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
    all_dff_episodes = {wl: [] for wl in target_wavelengths}
    all_zscore_episodes = {wl: [] for wl in target_wavelengths}
    statistics_rows = []
    
    # Process each animal
    for animal_data in animals:
        try:
            animal_id = animal_data.get('animal_single_channel_id', 'Unknown')

            fiber_data = animal_data.get('fiber_data_trimmed')
            if fiber_data is None or fiber_data.empty:
                fiber_data = animal_data.get('fiber_data')

            channels = animal_data.get('channels', {})
            events_col = channels.get('events')

            if not events_col or events_col not in fiber_data.columns:
                log_message(f"Events column not found for {animal_id}", "WARNING")
                continue

            # Find Drug events (Event1)
            drug_events = fiber_data[fiber_data[events_col].str.contains('Event1', na=False)]
            
            if len(drug_events) == 0:
                log_message(f"No drug events found for {animal_id}", "WARNING")
                continue
            
            time_col = channels['time']
            drug_start_time = drug_events[time_col].iloc[0]
            
            preprocessed_data = animal_data.get('preprocessed_data')
            if preprocessed_data is None:
                continue
            
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
                        baseline_start_time = drug_start_time + params['baseline_start']
                        baseline_end_time = drug_start_time + params['baseline_end']
                        
                        baseline_start_idx = np.argmin(np.abs(fiber_timestamps - baseline_start_time))
                        baseline_end_idx = np.argmin(np.abs(fiber_timestamps - baseline_end_time))
                        
                        if baseline_end_idx > baseline_start_idx:
                            baseline_data = data[baseline_start_idx:baseline_end_idx]
                            mean_baseline = np.nanmean(baseline_data)
                            std_baseline = np.nanstd(baseline_data)
                            
                            if std_baseline == 0:
                                std_baseline = 1e-10
                            
                            # Extract plotting window
                            start_idx = np.argmin(np.abs(fiber_timestamps - (drug_start_time - params['pre_time'])))
                            end_idx = np.argmin(np.abs(fiber_timestamps - (drug_start_time + params['post_time'])))
                            
                            if end_idx > start_idx:
                                episode_data = data[start_idx:end_idx]
                                episode_times = fiber_timestamps[start_idx:end_idx] - drug_start_time
                                
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
                                            'day': day_name,
                                            'animal_single_channel_id': animal_id,
                                            'analysis_type': 'drug_induced',
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
                                            'baseline_end': params['baseline_end']
                                        })
                                        
                                        pre_zscore_data = interp_zscore[pre_mask]
                                        post_zscore_data = interp_zscore[post_mask]
                                        
                                        statistics_rows.append({
                                            'day': day_name,
                                            'animal_single_channel_id': animal_id,
                                            'analysis_type': 'drug_induced',
                                            'channel': channel,
                                            'wavelength': wavelength,
                                            'trial': 1,
                                            'pre_min': np.min(pre_zscore_data) if len(pre_zscore_data) > 0 else np.nan,
                                            'pre_max': np.max(pre_zscore_data) if len(pre_zscore_data) > 0 else np.nan,
                                            'pre_mean': np.mean(pre_zscore_data) if len(pre_zscore_data) > 0 else np.nan,
                                            'pre_area': np.trapz(pre_zscore_data, time_array[pre_mask]) if len(pre_zscore_data) > 0 else np.nan,
                                            'post_min': np.min(post_zscore_data) if len(post_zscore_data) > 0 else np.nan,
                                            'post_max': np.max(post_zscore_data) if len(post_zscore_data) > 0 else np.nan,
                                            'post_mean': np.mean(post_zscore_data) if len(post_zscore_data) > 0 else np.nan,
                                            'post_area': np.trapz(post_zscore_data, time_array[post_mask]) if len(post_zscore_data) > 0 else np.nan,
                                            'signal_type': 'fiber_zscore',
                                            'baseline_start': params['baseline_start'],
                                            'baseline_end': params['baseline_end']
                                        })
        
        except Exception as e:
            log_message(f"Error analyzing {animal_data.get('animal_single_channel_id', 'Unknown')}: {str(e)}", "ERROR")
            continue
    
    # Calculate results
    result = {
        'time': time_array,
        'dff': all_dff_episodes,
        'zscore': all_zscore_episodes,
        'target_wavelengths': target_wavelengths
    }
    
    return result, statistics_rows if params['export_stats'] else None

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
        for day_name, data in results.items():
            episodes = data['dff'].get(wavelength, [])
            if episodes:
                all_episodes.extend(episodes)

        if all_episodes:
            episodes_array = np.array(all_episodes)

            if len(episodes_array) == 1:
                episodes_array = np.vstack([episodes_array[0], episodes_array[0]])
                im = ax_dff_heat.imshow(episodes_array, aspect='auto',
                                extent=[time_array[0], time_array[-1], 0, 1],
                                cmap='coolwarm', origin='lower')
                ax_dff_heat.set_yticks(np.arange(0, 2, 1))
            else:
                im = ax_dff_heat.imshow(episodes_array, aspect='auto',
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
        
        # Z-score heatmap
        ax_zscore_heat = fig.add_subplot(2, num_cols, plot_idx)
        all_episodes = []
        for day_name, data in results.items():
            episodes = data['zscore'].get(wavelength, [])
            if episodes:
                all_episodes.extend(episodes)
        
        if all_episodes:
            episodes_array = np.array(all_episodes)
            if len(episodes_array) == 1:
                episodes_array = np.vstack([episodes_array[0], episodes_array[0]])
                im = ax_zscore_heat.imshow(episodes_array, aspect='auto',
                                        extent=[time_array[0], time_array[-1], 0, 1],
                                        cmap='coolwarm', origin='lower')
                ax_zscore_heat.set_yticks(np.arange(0, 2, 1))
            else:
                im = ax_zscore_heat.imshow(episodes_array, aspect='auto',
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
                im = ax_dff_heat.imshow(episodes_array, aspect='auto',
                                    extent=[time_array[0], time_array[-1], 0, 1],
                                    cmap='coolwarm', origin='lower')
                ax_dff_heat.set_yticks(np.arange(0, 2, 1))
                ax_dff_heat.set_ylabel('Trials')
            else:
                im = ax_dff_heat.imshow(episodes_array, aspect='auto',
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
                im = ax_zscore_heat.imshow(episodes_array, aspect='auto',
                                        extent=[time_array[0], time_array[-1], 0, 1],
                                        cmap='coolwarm', origin='lower')
                ax_zscore_heat.set_yticks(np.arange(0, 2, 1))
                ax_zscore_heat.set_ylabel('Trials')
            else:
                im = ax_zscore_heat.imshow(episodes_array, aspect='auto',
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