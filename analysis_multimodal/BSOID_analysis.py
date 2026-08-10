"""
BSOID Analysis with table configuration: use the classified bouts from the BSOID analysis and create a table with selection of BSOID bout types and assignments of animal IDs.
"""
import os
import json
import numpy as np
import pandas as pd
import tkinter as tk

from itertools import chain
from infrastructure.logger import log_message
from analysis_multimodal.Multimodal_analysis import (
    create_parameter_panel, get_parameters_from_ui, create_control_panel, 
    create_table_window, initialize_table, FIBER_COLORS, ROW_COLORS,
    make_scrollable_window, make_figure, draw_heatmap, embed_figure,
    export_results, get_events_from_bsoid, calculate_event_traces,
    show_plot_controller, get_target_fps
)

NUM_COLS = 2     # Δ(ΔF/F) | Z-score

_deps = {}

def bind_bsoid_dependencies(deps):
    _deps.clear()
    _deps.update(deps)
    globals().update(deps)
    
def show_bsoid_analysis(root, multi_animal_data, analysis_mode="bsoid"):
    """
    Show BSOID analysis configuration window
    analysis_mode: "bsoid"
    """
    if not multi_animal_data:
        log_message("No animal data available", "ERROR")
        return
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'cluster mapping.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        cluster_mapping = json.load(f)
        
    available_bsoid_bout_types = []
    for animal_data in multi_animal_data:
        if "bsoid_data" in animal_data:
            bsoid_data = animal_data["bsoid_data"]
            if bsoid_data is not None:
                for bout_type in bsoid_data['B-SOiD labels'].unique():
                    bout_type_name = cluster_mapping.get(str(bout_type), f"Unknown {bout_type}")
                    if bout_type_name not in available_bsoid_bout_types:
                        available_bsoid_bout_types.append(bout_type_name)
    
    log_message(f"Available BSOID bout types: {available_bsoid_bout_types}")
                        
    if not available_bsoid_bout_types:
        log_message("No BSOID data available for any animal", "ERROR")
        return
    
    # Create main window with parameter panel and table
    main_window = tk.Toplevel(root)
    main_window.title("BSOID Analysis")
    main_window.geometry("900x700")
    # main_window.transient(root)
    # main_window.grab_set()
    
    # Main container with two sections
    container = tk.Frame(main_window, bg="#f8f8f8")
    container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # Left panel: Parameters
    param_config = {
        'show_plot_window': True,
        'plot_start': "-5",
        'plot_end': "15",
        'show_baseline_window': True,
        'baseline_start': "-5",
        'baseline_end': "0",
        'show_bout_type': True,
        'bout_types': available_bsoid_bout_types,
        'show_event_type': True
    }
    param_frame = create_parameter_panel(container, param_config)
    param_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 5))
    
    # Right panel: Table
    table_frame = tk.Frame(container, bg="#f8f8f8")
    table_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
    
    btn_frame = tk.Frame(main_window, bg="#f8f8f8")
    btn_frame.pack(fill=tk.X, padx=10, pady=10)
    
    # Initialize table manager
    table_manager = TableManager(root, table_frame, btn_frame, multi_animal_data, analysis_mode)
    
    def run_analysis():
        params = get_parameters_from_ui(param_frame, require_plot_window=True, require_baseline_window=True, require_bout_type=True, require_event_type=True)
        if params:
            params['full_event_type'] = f"{params['bout_type'].replace('_bouts', '')}_{params['event_type']}s"
            table_manager.run_analysis(params)
    
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
    
    def run_analysis(self, params):
        """Run analysis with current table configuration"""
        # Group animals by row
        row_data = {}
        target_animals = []
        for animal_data in self.multi_animal_data:
            animal_id = animal_data.get('animal_single_channel_id')
            if animal_id in self.used_animals:
                target_animals.append(animal_data)
        target_fps = get_target_fps(target_animals)
        log_message(f"Target FPS for analysis: {target_fps}")
        
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
        
        run_bsoid_analysis(row_data, params, target_fps)
        
def run_bsoid_analysis(row_data, params, target_fps):
    """Run BSOID analysis for each row group"""
    log_message(f"Running BSOID analysis for {len(row_data)} groups")
    
    results = {}
    all_statistics = []
    
    for row_name, animals in row_data.items():
        log_message(f"Analyzing group '{row_name}' with {len(animals)} animals")
        row_result, row_stats = analyze_row_bsoid(row_name, animals, params, target_fps)
        
        if row_result:
            results[row_name] = row_result
        if row_stats:
            all_statistics.extend(row_stats)
            
    if params['export_stats'] and all_statistics:
        export_results(results, all_statistics, "bsoid_analysis")
    
    if results:
        all_figures = []
        all_figures.extend(plot_bsoid_results(results, params))
        all_figures.extend(create_individual_row_windows(results, params))
        show_plot_controller(all_figures)
        log_message("Analysis completed successfully")
    else:
        log_message("No valid results", "ERROR")
        
def analyze_row_bsoid(row_name, animals, params, target_fps):
    """Analyze BSOID data for a single row group"""
    time_array = np.linspace(-params['plot_pre'], params['plot_post'], 
                            int((params['plot_pre'] + params['plot_post']) * target_fps))
    
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
    all_dff_episodes = {wl: [] for wl in target_wavelengths}
    all_zscore_episodes = {wl: [] for wl in target_wavelengths}
    statistics_rows = []
    
    # Process each animal
    for animal_data in animals:
        try:
            animal_id = animal_data.get('animal_single_channel_id', 'Unknown')
            events = get_events_from_bsoid(animal_data, params['full_event_type'])
            
            preprocessed_data = animal_data.get('preprocessed_data')
            if preprocessed_data is None or preprocessed_data.empty:
                continue
                
            channels = animal_data.get('channels', {})
            time_col = channels['time']
            fiber_timestamps = preprocessed_data[time_col].values
            
            dff_data = animal_data.get('dff_data', {})
            active_channels = animal_data.get('active_channels', [])
            
            result = calculate_event_traces(time_array, events, fiber_timestamps, dff_data, active_channels, target_wavelengths,
                                            params['plot_pre'], params['plot_post'], params['baseline_start'], params['baseline_end'], target_fps)
            
            for wl in target_wavelengths:
                if wl in result['dff']:
                    all_dff_episodes[wl].append(result['dff'][wl])
                if wl in result['zscore']:
                    all_zscore_episodes[wl].append(result['zscore'][wl])
            
            # Collect statistics if requested
            if params['export_stats']:
                statistics_rows.extend(collect_statistics(
                    row_name, animal_id, params['full_event_type'],
                    result, time_array, params, target_wavelengths, active_channels
                ))
                
        except Exception as e:
            log_message(f"Error analyzing {animal_data.get('animal_single_channel_id', 'Unknown')}: {str(e)}", "ERROR")
            continue
    
    # Calculate results
    result = {
        'time': time_array,
        'dff': {},
        'zscore': {},
        'target_wavelengths': target_wavelengths
    }
    
    for wl in target_wavelengths:
        if all_dff_episodes[wl]:
            episodes_array = np.array(all_dff_episodes[wl])
            converted_episodes = np.array(list(chain.from_iterable(list(episodes_array))))
            result['dff'][wl] = {
                'episodes': episodes_array,
                'mean': np.nanmean(converted_episodes, axis=0),
                'sem': np.nanstd(converted_episodes, axis=0) / np.sqrt(len(converted_episodes))
            }
        
        if all_zscore_episodes[wl]:
            episodes_array = np.array(all_zscore_episodes[wl])
            converted_episodes = np.array(list(chain.from_iterable(list(episodes_array))))
            result['zscore'][wl] = {
                'episodes': episodes_array,
                'mean': np.nanmean(converted_episodes, axis=0),
                'sem': np.nanstd(converted_episodes, axis=0) / np.sqrt(len(converted_episodes))
            }
    
    return result, statistics_rows if params['export_stats'] else None
            
def collect_statistics(row_name, animal_id, event_type, result, time_array, params, target_wavelengths, active_channels):
    """Collect statistics for export"""
    rows = []
    pre_mask = (time_array >= -params['plot_pre']) & (time_array <= 0)
    post_mask = (time_array >= 0) & (time_array <= params['plot_post'])
    
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
                        'pre_std': np.std(pre_data) if len(pre_data) > 0 else np.nan,
                        'pre_area': np.trapz(pre_data, time_array[pre_mask]) if len(pre_data) > 0 else np.nan,
                        'post_min': np.min(post_data) if len(post_data) > 0 else np.nan,
                        'post_max': np.max(post_data) if len(post_data) > 0 else np.nan,
                        'post_mean': np.mean(post_data) if len(post_data) > 0 else np.nan,
                        'post_std': np.std(post_data) if len(post_data) > 0 else np.nan,
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
                        'pre_std': np.std(pre_data) if len(pre_data) > 0 else np.nan,
                        'pre_area': np.trapz(pre_data, time_array[pre_mask]) if len(pre_data) > 0 else np.nan,
                        'post_min': np.min(post_data) if len(post_data) > 0 else np.nan,
                        'post_max': np.max(post_data) if len(post_data) > 0 else np.nan,
                        'post_mean': np.mean(post_data) if len(post_data) > 0 else np.nan,
                        'post_std': np.std(post_data) if len(post_data) > 0 else np.nan,
                        'post_area': np.trapz(post_data, time_array[post_mask]) if len(post_data) > 0 else np.nan,
                        'signal_type': 'fiber_zscore',
                        'baseline_start': params['baseline_start'],
                        'baseline_end': params['baseline_end']
                    })
    
    return rows
    
def plot_bsoid_results(results, params):
    """Plot BSOID results for all groups"""
    target_wavelengths = []
    for data in results.values():
        if "target_wavelengths" in data:
            target_wavelengths = data["target_wavelengths"]
            break
    if not target_wavelengths:
        target_wavelengths = ["470"]
 
    wavelength_label = "+".join(target_wavelengths)
    time_array = list(results.values())[0]["time"]
 
    win_title = f"BSOID Analysis - All Rows ({wavelength_label}nm)"
    win, _, inner = make_scrollable_window(win_title)
    collected = []

    for wl_idx, wl in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        fig = make_figure(NUM_COLS)
        fig.suptitle(f"Wavelength {wl} nm — All Rows",
                     fontsize=12, fontweight="bold")
        
        ax_dff = fig.add_subplot(2, NUM_COLS, 1)
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
        ax_dff.set_ylabel("Δ(ΔF/F)")
        ax_dff.set_title(f"Fiber Δ(ΔF/F) {wl}nm - All Rows")
        ax_dff.legend(fontsize=7)
        ax_dff.grid(False)
 
        ax_zs = fig.add_subplot(2, NUM_COLS, 2)
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
        
        ax_dff_heat = fig.add_subplot(2, NUM_COLS, 3)
        all_dff, counts = [], []
        dff_vmin, dff_vmax = None, None
        for data in results.values():
            if wl in data["dff"]:
                ep = list(chain.from_iterable(list(data["dff"][wl]["episodes"])))
                all_dff.extend(ep)
                counts.append(len(ep))
                if dff_vmin is None and dff_vmax is None:
                    dff_vmin = min(data["dff"][wl]["mean"] - data["dff"][wl]["sem"])
                    dff_vmax = max(data["dff"][wl]["mean"] + data["dff"][wl]["sem"])
                else:
                    dff_vmin = min(dff_vmin, min(data["dff"][wl]["mean"] - data["dff"][wl]["sem"]))
                    dff_vmax = max(dff_vmax, max(data["dff"][wl]["mean"] + data["dff"][wl]["sem"]))
        if all_dff:
            boundaries = []
            acc = 0
            for c in counts[:-1]:
                acc += c
                boundaries.append(acc)
            draw_heatmap(ax_dff_heat, np.array(all_dff), time_array,
                          "coolwarm", "Δ(ΔF/F)",
                          extra_lines=boundaries if boundaries else None, vmin=dff_vmin, vmax=dff_vmax)
            ax_dff_heat.set_title(f"Fiber Δ(ΔF/F) Heatmap {wl}nm")
        else:
            ax_dff_heat.axis("off")
            ax_dff_heat.set_title(f"Fiber Δ(ΔF/F) Heatmap {wl}nm")
 
        ax_zs_heat = fig.add_subplot(2, NUM_COLS, 4)
        all_zs, counts = [], []
        zs_vmin, zs_vmax = None, None
        for data in results.values():
            if wl in data["zscore"]:
                ep = list(chain.from_iterable(list(data["zscore"][wl]["episodes"])))
                all_zs.extend(ep)
                counts.append(len(ep))
                if zs_vmin is None and zs_vmax is None:
                    zs_vmin = min(data["zscore"][wl]["mean"] - data["zscore"][wl]["sem"])
                    zs_vmax = max(data["zscore"][wl]["mean"] + data["zscore"][wl]["sem"])
                else:
                    zs_vmin = min(zs_vmin, min(data["zscore"][wl]["mean"] - data["zscore"][wl]["sem"]))
                    zs_vmax = max(zs_vmax, max(data["zscore"][wl]["mean"] + data["zscore"][wl]["sem"]))
        if all_zs:
            boundaries = []
            acc = 0
            for c in counts[:-1]:
                acc += c
                boundaries.append(acc)
            draw_heatmap(ax_zs_heat, np.array(all_zs), time_array,
                          "coolwarm", "Z-score",
                          extra_lines=boundaries if boundaries else None, vmin=zs_vmin, vmax=zs_vmax)
            ax_zs_heat.set_title(f"Fiber Z-score Heatmap {wl}nm")
        else:
            ax_zs_heat.axis("off")
            ax_zs_heat.set_title(f"Fiber Z-score Heatmap {wl}nm")
 
        fig.tight_layout(rect=[0, 0, 1, 0.96])
        c = embed_figure(inner, fig, row_in_frame=wl_idx)
        collected.append((fig, c, win_title))

    log_message("BSOID analysis results plotted.")
    return collected

def create_individual_row_windows(results, params):
    """Create individual windows for each row group"""
    all_figs = []
    for row_name, data in results.items():
        all_figs.extend(create_single_row_window(row_name, data, params))
    return all_figs
        
def create_single_row_window(row_name, data, params):
    """Create individual window for a single row group"""
    target_wavelengths = data.get("target_wavelengths", ["470"])
    time_array = data["time"]

    win_title = f"BSOID analysis - {row_name} - {params['full_event_type']}"
    win, _, inner = make_scrollable_window(win_title)
    collected = []
 
    for wl_idx, wl in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        fig = make_figure(NUM_COLS)
        fig.suptitle(f"{row_name} — Wavelength {wl} nm",
                     fontsize=12, fontweight="bold")
 
        # Row 1: Traces
        ax_dff = fig.add_subplot(2, NUM_COLS, 1)
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
            ax_dff.set_ylabel("Δ(ΔF/F)")
            ax_dff.legend()
            ax_dff.grid(False)
        ax_dff.set_title(f"{row_name} - Fiber Δ(ΔF/F) {wl}nm")
 
        ax_zs = fig.add_subplot(2, NUM_COLS, 2)
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
        ax_dff_heat = fig.add_subplot(2, NUM_COLS, 3)
        if wl in data["dff"]:
            dff_vmin = min(data["dff"][wl]["mean"] - data["dff"][wl]["sem"])
            dff_vmax = max(data["dff"][wl]["mean"] + data["dff"][wl]["sem"])
            draw_heatmap(ax_dff_heat, list(chain.from_iterable(list(data["dff"][wl]["episodes"]))),
                          time_array, "coolwarm", "Δ(ΔF/F)", vmin=dff_vmin, vmax=dff_vmax)
            ax_dff_heat.set_title(f"{row_name} - Fiber Δ(ΔF/F) Heatmap {wl}nm")
        else:
            ax_dff_heat.axis("off")
            ax_dff_heat.set_title(f"{row_name} - Fiber Δ(ΔF/F) Heatmap {wl}nm")
 
        ax_zs_heat = fig.add_subplot(2, NUM_COLS, 4)
        if wl in data["zscore"]:
            zs_vmin = min(data["zscore"][wl]["mean"] - data["zscore"][wl]["sem"])
            zs_vmax = max(data["zscore"][wl]["mean"] + data["zscore"][wl]["sem"])
            draw_heatmap(ax_zs_heat, list(chain.from_iterable(list(data["zscore"][wl]["episodes"]))),
                          time_array, "coolwarm", "Z-score", vmin=zs_vmin, vmax=zs_vmax)
            ax_zs_heat.set_title(f"{row_name} - Fiber Z-score Heatmap {wl}nm")
        else:
            ax_zs_heat.axis("off")
            ax_zs_heat.set_title(f"{row_name} - Fiber Z-score Heatmap {wl}nm")
 
        fig.tight_layout(rect=[0, 0, 1, 0.96])
        c = embed_figure(inner, fig, row_in_frame=wl_idx)
        collected.append((fig, c, win_title))

    log_message(f"Individual row plot created for {row_name}")
    return collected