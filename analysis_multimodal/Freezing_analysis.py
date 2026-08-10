"""
Freezing Analysis with table configuration: create a table with assignments of animal IDs.
"""
from fileinput import filename
import os
import math
import numpy as np
import pandas as pd
import tkinter as tk
import matplotlib.pyplot as plt

from tkinter import ttk
from itertools import groupby
from infrastructure.logger import log_message
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from analysis_multimodal.Multimodal_analysis import create_control_panel, create_table_window, initialize_table

_deps = {}

def bind_freezing_dependencies(deps):
    _deps.clear()
    _deps.update(deps)
    globals().update(deps)
    
def show_freezing_analysis(root, multi_animal_data, analysis_mode="freezing"):
    """Show the freezing analysis with a table configuration."""
    if not multi_animal_data:
        log_message("No animal data available", "ERROR")
        return

    # Create main window with parameter panel and table
    main_window = tk.Toplevel(root)
    main_window.title("Event Analysis")
    main_window.geometry("900x700")
    # main_window.transient(root)
    # main_window.grab_set()
    
    # Main container with two sections
    container = tk.Frame(main_window, bg="#f8f8f8")
    container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # Left panel: Parameters of threshold and duration settings
    param_frame = tk.Frame(container, bg="#f8f8f8")
    param_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
    param_frame = tk.LabelFrame(container, text="Analysis Parameters", 
                                font=("Microsoft YaHei", 11, "bold"), 
                                bg="#f8f8f8", width=350)
    param_frame.pack_propagate(False)
    
    # Freezing detect setting
    detect_setting_frame = tk.LabelFrame(param_frame, text="Freezing Detection Settings", 
                            font=("Microsoft YaHei", 9, "bold"), bg="#f8f8f8")
    detect_setting_frame.pack(fill=tk.X, padx=10, pady=10)
    # Threshold setting (default: 1.20)
    threshold_frame = tk.Frame(detect_setting_frame, bg="#f8f8f8")
    threshold_frame.pack(fill=tk.X, pady=5)
    tk.Label(threshold_frame, text="Threshold:", bg="#f8f8f8", 
            font=("Microsoft YaHei", 8), width=8, anchor='w').pack(side=tk.LEFT, padx=10)
    threshold_var = tk.DoubleVar(value=1.20)
    threshold_entry = tk.Entry(threshold_frame, textvariable=threshold_var, width=8, 
            font=("Microsoft YaHei", 8))
    threshold_entry.pack(side=tk.LEFT, padx=5)
    # Duration setting (default: 15 frames)
    duration_frame = tk.Frame(detect_setting_frame, bg="#f8f8f8")
    duration_frame.pack(fill=tk.X, pady=5)
    tk.Label(duration_frame, text="Duration:", bg="#f8f8f8", 
            font=("Microsoft YaHei", 8), width=8, anchor='w').pack(side=tk.LEFT, padx=10)
    duration_var = tk.IntVar(value=15)
    duration_entry = tk.Entry(duration_frame, textvariable=duration_var, width=8, 
            font=("Microsoft YaHei", 8))
    duration_entry.pack(side=tk.LEFT, padx=5)
    # Export option
    export_frame = tk.LabelFrame(param_frame, text="Export Options", 
                                font=("Microsoft YaHei", 9, "bold"), bg="#f8f8f8")
    export_frame.pack(fill=tk.X, padx=10, pady=10)
    
    export_var = tk.BooleanVar(value=False)
    tk.Checkbutton(export_frame, text="Export results to CSV", 
                    variable=export_var, bg="#f8f8f8",
                    font=("Microsoft YaHei", 8)).pack(anchor=tk.W, padx=10, pady=5)
    
    param_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 5))

    # Right panel: Table
    table_frame = tk.Frame(container, bg="#f8f8f8")
    table_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
    
    btn_frame = tk.Frame(main_window, bg="#f8f8f8")
    btn_frame.pack(fill=tk.X, padx=10, pady=10)
    
    # Initialize table manager
    table_manager = TableManager(root, table_frame, btn_frame, multi_animal_data, analysis_mode)
    
    def run_analysis():
        params = {
            "threshold": float(threshold_entry.get()),
            "duration": int(duration_entry.get()),
            "export": export_var.get()
        }
        if params:
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
        
        run_freezing_analysis(row_data, params)
        
def run_freezing_analysis(row_data, params):
    """Run freezing analysis"""
    log_message("Running freezing analysis...")
    results = {}
    for row_name, animals in row_data.items():
        log_message(f"Analyzing {row_name} with {len(animals)} animals...")
        row_result = analyze_row_freezing(row_name, animals, params)
        results[row_name] = row_result
        
    if results:
        log_message("Plotting freezing distribution...")
        plot_freezing_distribution(results)
        if params.get("export", False):
            log_message("Exporting freezing results and statistics...")
            export_freezing_results_and_stats(results)
    else:
        log_message("No valid results", "ERROR")
        
def analyze_row_freezing(row_name, animals, params):
    """"Compute freezing for each animal in the row, and return the results"""
    threshold = params.get('threshold', 1.20)
    duration = params.get('duration', 15)   
    
    results = []
    for animal_data in animals:
        try:
            animal_id = animal_data.get('animal_single_channel_id', 'Unknown')
            data_dir = animal_data.get('data_dir', None)
            fps = animal_data.get('video_fps', 30)
            
            # Get events
            event_data = animal_data.get('events', [])
            if event_data is None:
                log_message(f"No events found for {animal_id}", "WARNING")
                continue
            freezing_data = animal_data.get('freezing_data_trimmed', [])['freezing']
            freeze_flag = freezing_data < threshold

            groups = groupby(enumerate(freeze_flag), key=lambda x: x[1])
            freeze_idx = []
            for k, g in groups:
                g = list(g)
                if k and len(g) >= 15:
                    idxs = [i for i, _ in g]
                    freeze_idx.extend(idxs)
                    
            # Calculate freezing by event periods
            freezing_results = []
            exp_start_time = event_data['start_time'].iloc[0]
            for _, event in event_data.iterrows():
                event_type = event['Event Type']
                if event_type not in [0, 1, 3, 4]:  # Only process wait, sound, wait-optogenetics, sound-optogenetics
                    continue
                
                start_frame = int((event['start_time'] - exp_start_time) * fps)
                end_frame = int((event['end_time'] - exp_start_time) * fps)
                
                event_frames = np.arange(start_frame, min(end_frame, len(freezing_data)))
                freeze_frames = np.intersect1d(event_frames, freeze_idx)
                
                total_time = len(event_frames) / fps
                freeze_time = len(freeze_frames) / fps
                freeze_percent = (len(freeze_frames) / len(event_frames) * 100) if len(event_frames) > 0 else 0
                
                freezing_results.append({
                    'event_type': event_type,
                    'start_time': event['start_time'],
                    'end_time': event['end_time'],
                    'total_time': total_time,
                    'freeze_time': freeze_time,
                    'freeze_percent': freeze_percent
                })

            dlc_freeze_status = np.zeros(len(freezing_data), dtype=int)
            dlc_freeze_status[freeze_idx] = 1
            
            results.append({
                'row_name': row_name,
                'animal_id': animal_id,
                'data_dir': data_dir,
                'freezing_results': freezing_results,
                'dlc_freeze_status': dlc_freeze_status
            })
        
        except Exception as e:
            log_message(f"Error analyzing {animal_id}: {str(e)}", "ERROR")
                    
    return results

def plot_freezing_distribution(results):
    """Plot freezing bar graph for each row and animal with a plot notebook (fisrt: row, second: animal)"""
    # Initialize the main window for plotting (full screen)
    plot_window = tk.Toplevel()
    plot_window.title("Freezing Analysis")
    plot_window.state("zoomed")
    # plot_window.transient()
    # plot_window.grab_set()
    
    # Create a notebook for each row
    row_notebook = ttk.Notebook(plot_window)
    row_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    for row_name, row_results in results.items():
        row_frame = tk.Frame(row_notebook)
        row_notebook.add(row_frame, text=row_name)
        
        # Create a notebook for each animal in the row
        animal_notebook = ttk.Notebook(row_frame)
        animal_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        for animal_result in row_results:
            animal_id = animal_result['animal_id']
            freezing_results = animal_result['freezing_results']
            
            animal_frame = tk.Frame(animal_notebook)
            animal_notebook.add(animal_frame, text=animal_id)
            
            # Plot freezing bar graph for this animal
            fig, ax = plt.subplots(figsize=(8, 4))
            canvas = FigureCanvasTkAgg(fig, master=animal_frame)
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            all_labels = []
            all_percentages = []
            for i, res in enumerate(freezing_results):
                event_type = res['event_type']
                if event_type == 0:
                    label = f"wait{math.ceil((i+1)/2)}"
                elif event_type == 1:
                    label = f"sound{math.ceil((i+1)/2)}"
                elif event_type == 3:
                    label = f"wait-optogenetics{math.ceil((i+1)/2)}"
                elif event_type == 4:
                    label = f"sound-optogenetics{math.ceil((i+1)/2)}"
                if label not in all_labels:
                    all_labels.append(label)
                all_percentages.append(res['freeze_percent'])
                
            ax.bar(np.arange(len(all_labels)), all_percentages, capsize=5,
                edgecolor='white', linewidth=1.2, joinstyle='round',
                capstyle='round', alpha=0.85, color="#212121")
            ax.tick_params(axis='both', which='both', length=0)
            ax.set_xticks(np.arange(len(all_labels)))
            ax.set_xticklabels(all_labels, fontsize=11, fontweight='normal', rotation=45, ha='right')
            ax.set_xlabel("Events", fontsize=14, fontweight='bold')
            ax.set_yticks([0, 25, 50, 75, 100])
            ax.set_yticklabels(['0','25','50','75','100'], fontsize=11, fontweight='normal')
            ax.set_ylabel("Freezing %", fontsize=14, fontweight='bold')
            ax.set_title("Freezing Timeline by Event", fontsize=18, fontweight='bold')
            ax.grid(False)
            fig.tight_layout()
            canvas.draw()
            
        # Create all animal with mean and sem freezing bar graph
        total_tab = ttk.Frame(animal_notebook)
        animal_notebook.add(total_tab, text="Total")
        fig_total, ax_total = plt.subplots(figsize=(8, 4))
        canvas_total = FigureCanvasTkAgg(fig_total, master=total_tab)
        canvas_total.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        row_animal_data = {}
        for animal_result in row_results:
            for i, res in enumerate(animal_result['freezing_results']):
                event_type = res['event_type']
                if event_type == 0:
                    label = f"wait{math.ceil((i+1)/2)}"
                elif event_type == 1:
                    label = f"sound{math.ceil((i+1)/2)}"
                elif event_type == 3:
                    label = f"wait-optogenetics{math.ceil((i+1)/2)}"
                elif event_type == 4:
                    label = f"sound-optogenetics{math.ceil((i+1)/2)}"

                row_animal_data.setdefault(label, []).append(res['freeze_percent'])
                
        labels_order = list(row_animal_data.keys())
        mean_vals = np.array([np.mean(row_animal_data[l]) for l in labels_order])
        sem_vals  = np.array([np.std(row_animal_data[l])/np.sqrt(len(row_animal_data[l]))
                            if len(row_animal_data[l]) > 1 else 0 for l in labels_order])
        
        ax_total.bar(np.arange(len(labels_order)), mean_vals, yerr=sem_vals,
                            capsize=5, edgecolor='white', linewidth=1.2,
                            joinstyle='round', capstyle='round', alpha=0.85, color='#212121')
        ax_total.tick_params(axis='both', which='both', length=0)
        ax_total.set_xticks(np.arange(len(labels_order)))
        ax_total.set_xticklabels(labels_order, fontsize=11, fontweight='normal', rotation=45, ha='right')
        ax_total.set_yticks([0, 25, 50, 75, 100])
        ax_total.set_yticklabels(['0','25','50','75','100'], fontsize=11, fontweight='normal')
        ax_total.set_ylabel("Freezing %", fontsize=14, fontweight='bold')
        ax_total.set_xlabel("Events", fontsize=14, fontweight='bold')
        ax_total.set_title(f" All animal {row_name}  Mean ± SEM of Freezing Timeline by Event", fontsize=16, fontweight='bold')
        ax_total.grid(False)
        fig_total.tight_layout()
        canvas_total.draw()
        
def export_freezing_results_and_stats(results):
    """Export freezing results and statistics to CSV files to the same directory as the input data"""
    for row_name, row_results in results.items():
        for animal_result in row_results:
            data_dir = animal_result.get('data_dir', None)
            animal_id = animal_result['animal_id']
            filename1 = f"{row_name}_{animal_id}_freezing_results.csv"
            filename2 = f"{row_name}_{animal_id}_freezing_status.csv"
            if data_dir:
                save_path1 = os.path.join(data_dir, filename1)
                save_path2 = os.path.join(data_dir, filename2)
                freezing_results = animal_result['freezing_results']
                freezing_stat = animal_result['dlc_freeze_status']
                # Export individual animal results
                df1 = pd.DataFrame(freezing_results)
                # If the same file exists, overwrite it
                if os.path.exists(save_path1):
                    log_message(f"File {save_path1} already exists, overwriting...")
                df1.to_csv(save_path1, index=False)
                # Export animal statistics
                df2 = pd.DataFrame({'frame': np.arange(len(freezing_stat)), 'freeze_status': freezing_stat})
                if os.path.exists(save_path2):
                    log_message(f"File {save_path2} already exists, overwriting...")
                df2.to_csv(save_path2, index=False)
                log_message(f"Exported freezing results to {save_path1}")
                log_message(f"Exported freezing status to {save_path2}")
            else:
                log_message(f"No data directory found for {animal_id}, skipping export", "WARNING")