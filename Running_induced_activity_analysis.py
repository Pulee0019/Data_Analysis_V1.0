"""
Running-induced activity analysis with table configuration
Supports both running-only and running+drug analysis
"""
import tkinter as tk
from tkinter import ttk
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from logger import log_message
from Multimodal_analysis import (
    get_events_from_bouts, calculate_running_episodes, export_statistics,
    create_table_window, initialize_table, create_control_panel, identify_optogenetic_events, identify_drug_events,     calculate_optogenetic_pulse_info, get_events_within_optogenetic, create_opto_parameter_string
)

# Colors for different days
DAY_COLORS = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', 
              '#1abc9c', '#e67e22', '#34495e', '#f1c40f', '#95a5a6']
FIBER_COLORS = ['#008000', "#FF0000", '#FFA500']

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
                sessions = group_optogenetic_sessions_running(events, animal_id)
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
            drug_events = identify_drug_events(events_data)
            log_message(f"Found {len(drug_events)} drug events for {animal_id}")
            
            if drug_events:
                all_drug_events[animal_id] = drug_events

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
    param_frame = create_parameter_panel(container, available_bout_types, analysis_mode)
    param_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 5))
    
    # Right panel: Table
    table_frame = tk.Frame(container, bg="#f8f8f8")
    table_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
    
    btn_frame = tk.Frame(main_window, bg="#f8f8f8")
    btn_frame.pack(fill=tk.X, padx=10, pady=10)

    # Initialize table manager
    if analysis_mode == "running+optogenetics" or analysis_mode == "running+optogenetics+drug":
        # Show power input dialog for optogenetic events
        power_dialog = OptoPowerInputDialog(root, all_optogenetic_events)
        root.wait_window(power_dialog.dialog)
        
        if not power_dialog.power_values:
            log_message("Power input cancelled", "INFO")
            return
        
        table_manager = OptogeneticTableManager(root, table_frame, btn_frame, 
                                              multi_animal_data, analysis_mode,
                                              all_optogenetic_events,power_dialog.power_values, all_drug_events)
    else:
        table_manager = TableManager(root, table_frame, btn_frame, multi_animal_data, analysis_mode)

    def run_analysis():
        params = get_parameters_from_ui(param_frame, analysis_mode)
        if params:
            table_manager.run_analysis(params, analysis_mode)

    tk.Button(btn_frame, text="Run Analysis", command=run_analysis,
             bg="#ffffff", fg="#000000", font=("Microsoft YaHei", 9, "bold"),
             relief=tk.FLAT, padx=10, pady=5).pack(side=tk.LEFT, padx=5)

def create_parameter_panel(parent, available_bout_types, analysis_mode):
    """Create parameter configuration panel"""
    param_frame = tk.LabelFrame(parent, text="Analysis Parameters", 
                               font=("Microsoft YaHei", 11, "bold"), 
                               bg="#f8f8f8", width=350)
    param_frame.pack_propagate(False)
    
    # Bout type selection
    bout_frame = tk.LabelFrame(param_frame, text="Bout Type", 
                              font=("Microsoft YaHei", 9, "bold"), bg="#f8f8f8")
    bout_frame.pack(fill=tk.X, padx=10, pady=10)
    
    tk.Label(bout_frame, text="Select Type:", bg="#f8f8f8", 
            font=("Microsoft YaHei", 8)).pack(anchor=tk.W, padx=10, pady=(5,2))
    
    bout_type_var = tk.StringVar()
    bout_type_combo = ttk.Combobox(bout_frame, textvariable=bout_type_var,
                                  values=available_bout_types, state="readonly",
                                  font=("Microsoft YaHei", 8))
    bout_type_combo.pack(padx=10, pady=5, fill=tk.X)
    if available_bout_types:
        bout_type_combo.set(available_bout_types[0])
    
    param_frame.bout_type_var = bout_type_var
    
    # Event type selection
    event_frame = tk.LabelFrame(param_frame, text="Event Type", 
                               font=("Microsoft YaHei", 9, "bold"), bg="#f8f8f8")
    event_frame.pack(fill=tk.X, padx=10, pady=10)
    
    event_type_var = tk.StringVar(value="onset")
    tk.Radiobutton(event_frame, text="Onset", variable=event_type_var, 
                  value="onset", bg="#f8f8f8", font=("Microsoft YaHei", 8)).pack(anchor=tk.W, padx=20)
    tk.Radiobutton(event_frame, text="Offset", variable=event_type_var, 
                  value="offset", bg="#f8f8f8", font=("Microsoft YaHei", 8)).pack(anchor=tk.W, padx=20)
    
    param_frame.event_type_var = event_type_var
    
    # Time window settings
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
    
    # Drug name (only for running+drug mode)
    if analysis_mode == "running+drug":
        drug_frame = tk.LabelFrame(param_frame, text="Drug Information", 
                                  font=("Microsoft YaHei", 9, "bold"), bg="#f8f8f8")
        drug_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(drug_frame, text="Drug Name:", bg="#f8f8f8", 
                font=("Microsoft YaHei", 8)).pack(anchor=tk.W, padx=10, pady=(5,2))
        drug_name_var = tk.StringVar(value="Drug")
        tk.Entry(drug_frame, textvariable=drug_name_var,
                font=("Microsoft YaHei", 8)).pack(padx=10, pady=5, fill=tk.X)
        
        param_frame.drug_name_var = drug_name_var
    
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

def get_parameters_from_ui(param_frame, analysis_mode):
    """Extract parameters from UI"""
    try:
        bout_type = param_frame.bout_type_var.get()
        event_type = param_frame.event_type_var.get()
        start_time = float(param_frame.start_time_var.get())
        end_time = float(param_frame.end_time_var.get())
        baseline_start = float(param_frame.baseline_start_var.get())
        baseline_end = float(param_frame.baseline_end_var.get())
        export_stats = param_frame.export_var.get()
        
        if not bout_type:
            log_message("Please select a bout type", "WARNING")
            return None
        
        if start_time >= end_time:
            log_message("Start time must be less than end time", "WARNING")
            return None
        
        if baseline_start >= baseline_end:
            log_message("Baseline start must be less than baseline end", "WARNING")
            return None
        
        full_event_type = f"{bout_type.replace('_bouts', '')}_{event_type}s"
        pre_time = abs(min(0, start_time))
        post_time = max(0, end_time)
        
        params = {
            'bout_type': bout_type,
            'event_type': event_type,
            'full_event_type': full_event_type,
            'start_time': start_time,
            'end_time': end_time,
            'pre_time': pre_time,
            'post_time': post_time,
            'baseline_start': baseline_start,
            'baseline_end': baseline_end,
            'export_stats': export_stats
        }
        
        if analysis_mode == "running+drug":
            drug_name = param_frame.drug_name_var.get().strip()
            if not drug_name:
                log_message("Please enter drug name", "WARNING")
                return None
            params['drug_name'] = drug_name
        
        return params
        
    except ValueError:
        log_message("Please enter valid parameter values", "WARNING")
        return None

def group_optogenetic_sessions_running(events, animal_id):
    """
    Group optogenetic events into sessions for running+optogenetics analysis
    """
    if not events:
        return []
    
    # Sort events by time
    events.sort(key=lambda x: x[0])
    
    sessions = []
    current_session = []
    
    for time, event_type in events:
        if not current_session:
            current_session.append((time, event_type))
        else:
            # Calculate time difference from last event
            last_time = current_session[-1][0]
            time_diff = time - last_time
            
            # If time difference > 10 seconds, start new session
            if time_diff > 10.0:
                if len(current_session) >= 2:  # Need at least one complete pulse
                    sessions.append(current_session)
                current_session = [(time, event_type)]
            else:
                current_session.append((time, event_type))
    
    # Add the last session
    if len(current_session) >= 2:
        sessions.append(current_session)
    
    return sessions

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

class OptoPowerInputDialog:
    """Dialog for entering power values for optogenetic events in running analysis"""
    def __init__(self, root, all_optogenetic_events):
        self.root = root
        self.all_optogenetic_events = all_optogenetic_events
        self.power_values = {}
        
        self.dialog = tk.Toplevel(root)
        self.dialog.title("Optogenetic Power Input (Running+Optogenetics)")
        self.dialog.geometry("800x600")
        self.dialog.transient(root)
        self.dialog.grab_set()
        
        self.create_widgets()
    
    def create_widgets(self):
        """Create power input widgets"""
        container = tk.Frame(self.dialog, bg="#f8f8f8")
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        tk.Label(container, text="Enter Power (mW) for Optogenetic Sessions", 
                font=("Microsoft YaHei", 12, "bold"), bg="#f8f8f8").pack(pady=10)
        
        # Create scrollable frame
        canvas = tk.Canvas(container, bg="#f8f8f8", highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#f8f8f8")
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Add inputs
        row = 0
        self.power_vars = {}
        
        for animal_id, sessions in self.all_optogenetic_events.items():
            tk.Label(scrollable_frame, text=f"Animal: {animal_id}", 
                    font=("Microsoft YaHei", 10, "bold"), bg="#f8f8f8",
                    anchor="w").grid(row=row, column=0, columnspan=4, sticky="w", pady=(10, 5))
            row += 1
            
            # Headers
            headers = ["Session", "Frequency (Hz)", "Pulse Width (s)", "Duration (s)", "Power (mW)"]
            for col, header in enumerate(headers):
                tk.Label(scrollable_frame, text=header, font=("Microsoft YaHei", 9, "bold"),
                        bg="#f8f8f8").grid(row=row, column=col, sticky="w", padx=5, pady=2)
            row += 1
            
            # Session rows
            for session_idx, session in enumerate(sessions):
                freq, pulse_width, duration = calculate_optogenetic_pulse_info(session, animal_id)
                
                # Session labels
                tk.Label(scrollable_frame, text=f"Session{session_idx+1}", 
                        bg="#f8f8f8").grid(row=row, column=0, sticky="w", padx=5)
                tk.Label(scrollable_frame, text=f"{freq:.1f}", 
                        bg="#f8f8f8").grid(row=row, column=1, sticky="w", padx=5)
                tk.Label(scrollable_frame, text=f"{pulse_width:.3f}", 
                        bg="#f8f8f8").grid(row=row, column=2, sticky="w", padx=5)
                tk.Label(scrollable_frame, text=f"{duration:.1f}", 
                        bg="#f8f8f8").grid(row=row, column=3, sticky="w", padx=5)
                
                # Power entry
                power_var = tk.StringVar(value="5.0")
                power_entry = tk.Entry(scrollable_frame, textvariable=power_var, 
                                      width=10, font=("Microsoft YaHei", 9))
                power_entry.grid(row=row, column=4, sticky="w", padx=5, pady=2)
                
                # Store with base ID
                base_id = f"{animal_id}_Session{session_idx+1}_{freq:.1f}Hz_{pulse_width*1000:.0f}ms_{duration:.1f}s"
                self.power_vars[base_id] = power_var
                row += 1
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Buttons
        btn_frame = tk.Frame(self.dialog, bg="#f8f8f8")
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Button(btn_frame, text="Apply", command=self.apply_power,
                 bg="#4CAF50", fg="white", font=("Microsoft YaHei", 9, "bold"),
                 relief=tk.FLAT, padx=20, pady=5).pack(side=tk.RIGHT, padx=5)
        
        tk.Button(btn_frame, text="Cancel", command=self.dialog.destroy,
                 bg="#f44336", fg="white", font=("Microsoft YaHei", 9, "bold"),
                 relief=tk.FLAT, padx=20, pady=5).pack(side=tk.RIGHT, padx=5)
    
    def apply_power(self):
        """Apply power values"""
        try:
            for base_id, power_var in self.power_vars.items():
                power = float(power_var.get())
                if power <= 0:
                    raise ValueError(f"Power must be positive for {base_id}")
                
                # Create final ID
                final_id = f"{base_id}_{power:.1f}mW"
                self.power_values[final_id] = power
            
            self.dialog.destroy()
            log_message(f"Power values applied for {len(self.power_values)} sessions")
            
        except ValueError as e:
            log_message(f"Invalid power value: {str(e)}", "ERROR")

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
            events = get_events_from_bouts(animal_data, params['full_event_type'], duation = False)
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
    """Analyze one day for running+drug mode"""
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
    
    # Initialize storage for pre and post drug
    pre_running = []
    post_running = []
    pre_dff = {wl: [] for wl in target_wavelengths}
    post_dff = {wl: [] for wl in target_wavelengths}
    pre_zscore = {wl: [] for wl in target_wavelengths}
    post_zscore = {wl: [] for wl in target_wavelengths}
    
    statistics_rows = []
    
    # Process each animal
    for animal_data in animals:
        try:
            animal_id = animal_data.get('animal_single_channel_id', 'Unknown')
            
            # Find drug event
            fiber_data = animal_data.get('fiber_data_trimmed')
            if fiber_data is None or fiber_data.empty:
                fiber_data = animal_data.get('fiber_data')
                
            channels = animal_data.get('channels', {})
            events_col = channels.get('events')
            
            if not events_col or events_col not in fiber_data.columns:
                continue
            
            drug_events = fiber_data[fiber_data[events_col].str.contains('Event2', na=False)]
            if len(drug_events) == 0:
                log_message(f"No drug events for {animal_id}", "WARNING")
                continue
            
            time_col = channels['time']
            drug_start_time = drug_events[time_col].iloc[0]
            
            # Get running events
            events = get_events_from_bouts(animal_data, params['full_event_type'], duration = False)
            if not events:
                continue
            
            # Split events into pre/post drug
            pre_drug_events = [e for e in events if e < drug_start_time]
            post_drug_events = [e for e in events if e >= drug_start_time]
            
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
                
            fiber_timestamps = preprocessed_data[time_col].values
            dff_data = animal_data.get('dff_data', {})
            active_channels = animal_data.get('active_channels', [])
            
            # Process pre-drug events
            if pre_drug_events:
                pre_result = calculate_running_episodes(
                    pre_drug_events, running_timestamps, running_speed,
                    fiber_timestamps, dff_data,
                    active_channels, target_wavelengths,
                    params['pre_time'], params['post_time'],
                    params['baseline_start'], params['baseline_end']
                )
                
                if len(pre_result['running']) > 0:
                    pre_running.extend(pre_result['running'])
                
                for wl in target_wavelengths:
                    if wl in pre_result['dff']:
                        pre_dff[wl].extend(pre_result['dff'][wl])
                    if wl in pre_result['zscore']:
                        pre_zscore[wl].extend(pre_result['zscore'][wl])
            
            # Process post-drug events
            if post_drug_events:
                post_result = calculate_running_episodes(
                    post_drug_events, running_timestamps, running_speed,
                    fiber_timestamps, dff_data,
                    active_channels, target_wavelengths,
                    params['pre_time'], params['post_time'],
                    params['baseline_start'], params['baseline_end']
                )
                
                if len(post_result['running']) > 0:
                    post_running.extend(post_result['running'])
                
                for wl in target_wavelengths:
                    if wl in post_result['dff']:
                        post_dff[wl].extend(post_result['dff'][wl])
                    if wl in post_result['zscore']:
                        post_zscore[wl].extend(post_result['zscore'][wl])

            # Collect statistics if requested
            if params['export_stats']:
                # Pre-drug statistics
                if pre_drug_events:
                    statistics_rows.extend(collect_statistics(
                        day_name, animal_id, f"pre_{params['full_event_type']}",
                        {
                            'running': pre_result['running'],
                            'dff': pre_result['dff'],
                            'zscore': pre_result['zscore']
                        },
                        time_array, params, target_wavelengths, active_channels
                    ))
                
                # Post-drug statistics
                if post_drug_events:
                    statistics_rows.extend(collect_statistics(
                        day_name, animal_id, f"post_{params['full_event_type']}",
                        {
                            'running': post_result['running'],
                            'dff': post_result['dff'],
                            'zscore': post_result['zscore']
                        },
                        time_array, params, target_wavelengths, active_channels
                    ))
                        
        except Exception as e:
            log_message(f"Error analyzing {animal_data.get('animal_single_channel_id', 'Unknown')}: {str(e)}", "ERROR")
            continue
    
    # Combine results
    result = {
        'time': time_array,
        'pre_drug': {
            'running': {
                'episodes': np.array(pre_running) if pre_running else np.array([]),
                'mean': np.nanmean(pre_running, axis=0) if pre_running else None,
                'sem': np.nanstd(pre_running, axis=0) / np.sqrt(len(pre_running)) if pre_running else None
            },
            'dff': {},
            'zscore': {}
        },
        'post_drug': {
            'running': {
                'episodes': np.array(post_running) if post_running else np.array([]),
                'mean': np.nanmean(post_running, axis=0) if post_running else None,
                'sem': np.nanstd(post_running, axis=0) / np.sqrt(len(post_running)) if post_running else None
            },
            'dff': {},
            'zscore': {}
        },
        'target_wavelengths': target_wavelengths
    }
    
    for wl in target_wavelengths:
        if pre_dff[wl]:
            episodes_array = np.array(pre_dff[wl])
            result['pre_drug']['dff'][wl] = {
                'episodes': episodes_array,
                'mean': np.nanmean(episodes_array, axis=0),
                'sem': np.nanstd(episodes_array, axis=0) / np.sqrt(len(pre_dff[wl]))
            }
        
        if pre_zscore[wl]:
            episodes_array = np.array(pre_zscore[wl])
            result['pre_drug']['zscore'][wl] = {
                'episodes': episodes_array,
                'mean': np.nanmean(episodes_array, axis=0),
                'sem': np.nanstd(episodes_array, axis=0) / np.sqrt(len(pre_zscore[wl]))
            }
        
        if post_dff[wl]:
            episodes_array = np.array(post_dff[wl])
            result['post_drug']['dff'][wl] = {
                'episodes': episodes_array,
                'mean': np.nanmean(episodes_array, axis=0),
                'sem': np.nanstd(episodes_array, axis=0) / np.sqrt(len(post_dff[wl]))
            }
        
        if post_zscore[wl]:
            episodes_array = np.array(post_zscore[wl])
            result['post_drug']['zscore'][wl] = {
                'episodes': episodes_array,
                'mean': np.nanmean(episodes_array, axis=0),
                'sem': np.nanstd(episodes_array, axis=0) / np.sqrt(len(post_zscore[wl]))
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
            im = ax_running_heat.imshow(all_running, aspect='auto',
                                        extent=[time_array[0], time_array[-1], 0, 1],
                                        cmap='viridis', origin='lower')
            ax_running_heat.set_yticks(np.arange(0, 2, 1))
        else:
            im = ax_running_heat.imshow(all_running, aspect='auto',
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
                im = ax_dff_heat.imshow(all_dff, aspect='auto',
                                    extent=[time_array[0], time_array[-1], 0, 1],
                                    cmap='coolwarm', origin='lower')
                ax_dff_heat.set_yticks(np.arange(0, 2, 1))
            else:
                im = ax_dff_heat.imshow(all_dff, aspect='auto',
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
                im = ax_zscore_heat.imshow(all_zscore, aspect='auto',
                                        extent=[time_array[0], time_array[-1], 0, 1],
                                        cmap='coolwarm', origin='lower')
                ax_zscore_heat.set_yticks(np.arange(0, 2, 1))
            else:
                im = ax_zscore_heat.imshow(all_zscore, aspect='auto',
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
            im = ax_running_heat.imshow(episodes_array, aspect='auto',
                                        extent=[time_array[0], time_array[-1], 0, 1],
                                        cmap='viridis', origin='lower')
            ax_running_heat.set_yticks(np.arange(0, 2, 1))
        else:
            im = ax_running_heat.imshow(episodes_array, aspect='auto',
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
            ax_dff_heat.set_title(f'{day_name} - Fiber ΔF/F Heatmap {wl}nm')
            plt.colorbar(im, ax=ax_dff_heat, label='ΔF/F', orientation='horizontal')
        plot_idx += 1
        
        # Z-score heatmap
        ax_zscore_heat = fig.add_subplot(2, num_cols, plot_idx)
        if wl in data['zscore']:
            episodes_array = data['zscore'][wl]['episodes']

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
            im = ax_running_heat.imshow(combined, aspect='auto',
                                       extent=[time_array[0], time_array[-1], 0, 1],
                                       cmap='viridis', origin='lower')
            ax_running_heat.set_yticks(np.arange(0, 2, 1))
        else:
            im = ax_running_heat.imshow(combined, aspect='auto',
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
                im = ax_dff_heat.imshow(combined, aspect='auto',
                                    extent=[time_array[0], time_array[-1], 0, 1],
                                    cmap='coolwarm', origin='lower')
                ax_dff_heat.set_yticks(np.arange(0, 2, 1))
            else:
                im = ax_dff_heat.imshow(combined, aspect='auto',
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
                im = ax_zscore_heat.imshow(combined, aspect='auto',
                                       extent=[time_array[0], time_array[-1], 0, 1],
                                       cmap='coolwarm', origin='lower')
                ax_zscore_heat.set_yticks(np.arange(0, 2, 1))
            else:
                im = ax_zscore_heat.imshow(combined, aspect='auto',
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
    """Plot running+drug results with pre/post comparison"""
    target_wavelengths = []
    for day_name, data in results.items():
        if 'target_wavelengths' in data:
            target_wavelengths = data['target_wavelengths']
            break
    
    if not target_wavelengths:
        target_wavelengths = ['470']
    
    drug_name = params.get('drug_name', 'Drug')
    
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
    
    # Row 1: Traces
    # Running trace
    ax_running = fig.add_subplot(2, num_cols, plot_idx)
    for idx, (day_name, data) in enumerate(results.items()):
        day_color = DAY_COLORS[idx % len(DAY_COLORS)]
        
        if data['pre_drug']['running']['mean'] is not None:
            ax_running.plot(time_array, data['pre_drug']['running']['mean'],
                          color=day_color, linestyle='-', linewidth=2, alpha=0.5, label=f"{day_name} Pre-{drug_name}")
            ax_running.fill_between(time_array,
                                   data['pre_drug']['running']['mean'] - data['pre_drug']['running']['sem'],
                                   data['pre_drug']['running']['mean'] + data['pre_drug']['running']['sem'],
                                   color=day_color, alpha=0.2)
        
        if data['post_drug']['running']['mean'] is not None:
            ax_running.plot(time_array, data['post_drug']['running']['mean'],
                        color=day_color, linewidth=2, linestyle='-', alpha=1,
                        label=f'{day_name} Post {drug_name}')
            ax_running.fill_between(time_array,
                                data['post_drug']['running']['mean'] - data['post_drug']['running']['sem'],
                                data['post_drug']['running']['mean'] + data['post_drug']['running']['sem'],
                                color=day_color, alpha=0.5)

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
        # dFF trace
        ax_dff = fig.add_subplot(2, num_cols, plot_idx)
        for idx, (day_name, data) in enumerate(results.items()):
            day_color = DAY_COLORS[idx % len(DAY_COLORS)]
            
            if wl in data['pre_drug']['dff']:
                ax_dff.plot(time_array, data['pre_drug']['dff'][wl]['mean'],
                        color=day_color, linewidth=2, linestyle='-', alpha=0.5,
                        label=f'{day_name} Pre {drug_name}')
                ax_dff.fill_between(time_array,
                                data['pre_drug']['dff'][wl]['mean'] - data['pre_drug']['dff'][wl]['sem'],
                                data['pre_drug']['dff'][wl]['mean'] + data['pre_drug']['dff'][wl]['sem'],
                                color=day_color, alpha=0.2)
            
            if wl in data['post_drug']['dff']:
                ax_dff.plot(time_array, data['post_drug']['dff'][wl]['mean'],
                        color=day_color, linewidth=2, linestyle='-', alpha=1,
                        label=f'{day_name} Post {drug_name}')
                ax_dff.fill_between(time_array,
                                data['post_drug']['dff'][wl]['mean'] - data['post_drug']['dff'][wl]['sem'],
                                data['post_drug']['dff'][wl]['mean'] + data['post_drug']['dff'][wl]['sem'],
                                color=day_color, alpha=0.5)
        
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
            
            if wl in data['pre_drug']['zscore']:
                ax_zscore.plot(time_array, data['pre_drug']['zscore'][wl]['mean'],
                            color=day_color, linewidth=2, linestyle='-', alpha=0.5,
                            label=f'{day_name} Pre {drug_name}')
                ax_zscore.fill_between(time_array,
                                    data['pre_drug']['zscore'][wl]['mean'] - data['pre_drug']['zscore'][wl]['sem'],
                                    data['pre_drug']['zscore'][wl]['mean'] + data['pre_drug']['zscore'][wl]['sem'],
                                    color=day_color, alpha=0.2)
            
            if wl in data['post_drug']['zscore']:
                ax_zscore.plot(time_array, data['post_drug']['zscore'][wl]['mean'],
                            color=day_color, linewidth=2, linestyle='-', alpha=1,
                            label=f'{day_name} Post {drug_name}')
                ax_zscore.fill_between(time_array,
                                    data['post_drug']['zscore'][wl]['mean'] - data['post_drug']['zscore'][wl]['sem'],
                                    data['post_drug']['zscore'][wl]['mean'] + data['post_drug']['zscore'][wl]['sem'],
                                    color=day_color, alpha=0.5)
        
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
    all_pre = []
    all_post = []
    for day_name, data in results.items():
        if len(data['pre_drug']['running']['episodes']) > 0:
            all_pre.extend(data['pre_drug']['running']['episodes'])
        if len(data['post_drug']['running']['episodes']) > 0:
            all_post.extend(data['post_drug']['running']['episodes'])

    if all_pre and all_post:
        combined = np.vstack([np.array(all_pre), np.array(all_post)])
        n_pre = len(all_pre)
        
        if len(combined) == 1:
            combined = np.vstack([combined[0], combined[0]])
            im = ax_running_heat.imshow(combined, aspect='auto',
                                        extent=[time_array[0], time_array[-1], 0, 1],
                                        cmap='viridis', origin='lower')
            ax_running_heat.set_yticks(np.arange(0, 2, 1))
        else:
            im = ax_running_heat.imshow(combined, aspect='auto',
                                        extent=[time_array[0], time_array[-1], 0, len(combined)],
                                        cmap='viridis', origin='lower')
            if len(combined) <= 10:
                ax_running_heat.set_yticks(np.arange(0, len(combined)+1, 1))

        ax_running_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
        ax_running_heat.axhline(y=n_pre, color='k', linestyle='--', linewidth=1)
        ax_running_heat.set_xlabel('Time (s)')
        ax_running_heat.set_ylabel('Trials')
        ax_running_heat.set_title('Running Speed Heatmap')
        plt.colorbar(im, ax=ax_running_heat, label='Speed (cm/s)', orientation='horizontal')
    plot_idx += 1

    # Fiber heatmaps
    for wl_idx, wl in enumerate(target_wavelengths):
        # dFF heatmap
        ax_dff_heat = fig.add_subplot(2, num_cols, plot_idx)
        all_pre_dff = []
        all_post_dff = []
        for day_name, data in results.items():
            if wl in data['pre_drug']['dff']:
                all_pre_dff.extend(data['pre_drug']['dff'][wl]['episodes'])
            if wl in data['post_drug']['dff']:
                all_post_dff.extend(data['post_drug']['dff'][wl]['episodes'])
        
        if all_pre_dff and all_post_dff:
            combined_dff = np.vstack([np.array(all_pre_dff), np.array(all_post_dff)])
            n_pre = len(all_pre_dff)
            if len(combined_dff) == 1:
                combined_dff = np.vstack([combined_dff[0], combined_dff[0]])
                im = ax_dff_heat.imshow(combined_dff, aspect='auto',
                                    extent=[time_array[0], time_array[-1], 0, 1],
                                    cmap='coolwarm', origin='lower')
                ax_dff_heat.set_yticks(np.arange(0, 2, 1))
            else:
                im = ax_dff_heat.imshow(combined_dff, aspect='auto',
                                    extent=[time_array[0], time_array[-1], 0, len(combined_dff)],
                                    cmap='coolwarm', origin='lower')
                if len(combined_dff) <= 10:
                    ax_dff_heat.set_yticks(np.arange(0, len(combined_dff)+1, 1))
            
            ax_dff_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            ax_dff_heat.axhline(y=n_pre, color='k', linestyle='--', linewidth=1)
            ax_dff_heat.set_xlabel('Time (s)')
            ax_dff_heat.set_ylabel('Trials')
            ax_dff_heat.set_title(f'Fiber ΔF/F Heatmap {wl}nm')
            plt.colorbar(im, ax=ax_dff_heat, label='ΔF/F', orientation='horizontal')
        plot_idx += 1
        
        # Z-score heatmap
        ax_zscore_heat = fig.add_subplot(2, num_cols, plot_idx)
        all_pre_zscore = []
        all_post_zscore = []
        for day_name, data in results.items():
            if wl in data['pre_drug']['zscore']:
                all_pre_zscore.extend(data['pre_drug']['zscore'][wl]['episodes'])
            if wl in data['post_drug']['zscore']:
                all_post_zscore.extend(data['post_drug']['zscore'][wl]['episodes'])
        
        if all_pre_zscore and all_post_zscore:
            combined_zscore = np.vstack([np.array(all_pre_zscore), np.array(all_post_zscore)])
            n_pre = len(all_pre_zscore)
            if len(combined_zscore) == 1:
                combined_zscore = np.vstack([combined_zscore[0], combined_zscore[0]])
                im = ax_zscore_heat.imshow(combined_zscore, aspect='auto',
                                        extent=[time_array[0], time_array[-1], 0, 1],
                                        cmap='coolwarm', origin='lower')
                ax_zscore_heat.set_yticks(np.arange(0, 2, 1))
            else:
                im = ax_zscore_heat.imshow(combined_zscore, aspect='auto',
                                        extent=[time_array[0], time_array[-1], 0, len(combined_zscore)],
                                        cmap='coolwarm', origin='lower')
                if len(combined_zscore) <= 10:
                    ax_zscore_heat.set_yticks(np.arange(0, len(combined_zscore)+1, 1))

            ax_zscore_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            ax_zscore_heat.axhline(y=n_pre, color='k', linestyle='--', linewidth=1)
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
    ax_running.set_title(f'{day_name} - Running Speed')
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
            im = ax_running_heat.imshow(combined, aspect='auto',
                                    extent=[time_array[0], time_array[-1], 0, 1],
                                    cmap='viridis', origin='lower')
            ax_running_heat.set_yticks(np.arange(0, 2, 1))
        else:
            im = ax_running_heat.imshow(combined, aspect='auto',
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
                im = ax_dff_heat.imshow(combined, aspect='auto',
                                    extent=[time_array[0], time_array[-1], 0, 1],
                                    cmap='coolwarm', origin='lower')
                ax_dff_heat.set_yticks(np.arange(0, 2, 1))
            else:
                im = ax_dff_heat.imshow(combined, aspect='auto',
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
                im = ax_zscore_heat.imshow(combined, aspect='auto',
                                        extent=[time_array[0], time_array[-1], 0, 1],
                                        cmap='coolwarm', origin='lower')
                ax_zscore_heat.set_yticks(np.arange(0, 2, 1))
            else:
                im = ax_zscore_heat.imshow(combined, aspect='auto',
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
            im = ax_running_heat.imshow(combined, aspect='auto',
                                        extent=[time_array[0], time_array[-1], 0, 1],
                                        cmap='viridis', origin='lower')
            ax_running_heat.set_yticks(np.arange(0, 2, 1))
        else:
            im = ax_running_heat.imshow(combined, aspect='auto',
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
                im = ax_dff_heat.imshow(combined_dff, aspect='auto',
                                    extent=[time_array[0], time_array[-1], 0, 1],
                                    cmap='coolwarm', origin='lower')
                ax_dff_heat.set_yticks(np.arange(0, 2, 1))
            else:
                im = ax_dff_heat.imshow(combined_dff, aspect='auto',
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
                im = ax_zscore_heat.imshow(combined_zscore, aspect='auto',
                                        extent=[time_array[0], time_array[-1], 0, 1],
                                        cmap='coolwarm', origin='lower')
                ax_zscore_heat.set_yticks(np.arange(0, 2, 1))
            else:
                im = ax_zscore_heat.imshow(combined_zscore, aspect='auto',
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
            im = ax_running_heat.imshow(combined, aspect='auto',
                                    extent=[time_array[0], time_array[-1], 0, 1],
                                    cmap='viridis', origin='lower')
            ax_running_heat.set_yticks(np.arange(0, 2, 1))
        else:
            im = ax_running_heat.imshow(combined, aspect='auto',
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
                im = ax_dff_heat.imshow(combined, aspect='auto',
                                    extent=[time_array[0], time_array[-1], 0, 1],
                                    cmap='coolwarm', origin='lower')
                ax_dff_heat.set_yticks(np.arange(0, 2, 1))
            else:
                im = ax_dff_heat.imshow(combined, aspect='auto',
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
                im = ax_zscore_heat.imshow(combined, aspect='auto',
                                        extent=[time_array[0], time_array[-1], 0, 1],
                                        cmap='coolwarm', origin='lower')
                ax_zscore_heat.set_yticks(np.arange(0, 2, 1))
            else:
                im = ax_zscore_heat.imshow(combined, aspect='auto',
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
    """Analyze one day for running+optogenetics+drug mode"""
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
    
    # Initialize storage for four conditions
    conditions = {
        'pre_drug_with_opto': {
            'running': [],
            'dff': {wl: [] for wl in target_wavelengths},
            'zscore': {wl: [] for wl in target_wavelengths}
        },
        'pre_drug_without_opto': {
            'running': [],
            'dff': {wl: [] for wl in target_wavelengths},
            'zscore': {wl: [] for wl in target_wavelengths}
        },
        'post_drug_with_opto': {
            'running': [],
            'dff': {wl: [] for wl in target_wavelengths},
            'zscore': {wl: [] for wl in target_wavelengths}
        },
        'post_drug_without_opto': {
            'running': [],
            'dff': {wl: [] for wl in target_wavelengths},
            'zscore': {wl: [] for wl in target_wavelengths}
        }
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
            
            # Get optogenetic sessions
            opto_sessions = all_optogenetic_events[animal_id]
            if not opto_sessions:
                continue
            
            # Use first session
            opto_session = opto_sessions[0]
            
            # Find drug event
            fiber_data = animal_data.get('fiber_data_trimmed')
            if fiber_data is None or fiber_data.empty:
                fiber_data = animal_data.get('fiber_data')
            
            channels = animal_data.get('channels', {})
            events_col = channels.get('events')
            
            if not events_col or events_col not in fiber_data.columns:
                continue
            
            drug_events = fiber_data[fiber_data[events_col].str.contains('Event2', na=False)]
            if len(drug_events) == 0:
                log_message(f"No drug events for {animal_id}", "WARNING")
                continue
            
            time_col = channels['time']
            drug_start_time = drug_events[time_col].iloc[0]
            
            # Get running events
            running_events = get_events_from_bouts(animal_data, params['full_event_type'], duration=True)
            if not running_events:
                log_message(f"No running events for {animal_id}", "WARNING")
                continue
            
            # Categorize running events into four groups
            pre_drug_events = [e for e in running_events if e[0] < drug_start_time]
            post_drug_events = [e for e in running_events if e[0] >= drug_start_time]
            
            # Further categorize by optogenetics
            pre_with_opto, pre_without_opto = get_events_within_optogenetic(
                opto_session, pre_drug_events, params['full_event_type']
            )
            post_with_opto, post_without_opto = get_events_within_optogenetic(
                opto_session, post_drug_events, params['full_event_type']
            )
            
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
            
            fiber_timestamps = preprocessed_data[time_col].values
            dff_data = animal_data.get('dff_data', {})
            active_channels = animal_data.get('active_channels', [])
            
            # Process four conditions
            condition_events = {
                'pre_drug_with_opto': pre_with_opto,
                'pre_drug_without_opto': pre_without_opto,
                'post_drug_with_opto': post_with_opto,
                'post_drug_without_opto': post_without_opto
            }
            
            for condition_name, events in condition_events.items():
                if events:
                    result = calculate_running_episodes(
                        events, running_timestamps, running_speed,
                        fiber_timestamps, dff_data,
                        active_channels, target_wavelengths,
                        params['pre_time'], params['post_time'],
                        params['baseline_start'], params['baseline_end']
                    )
                    
                    if len(result['running']) > 0:
                        conditions[condition_name]['running'].extend(result['running'])
                    
                    for wl in target_wavelengths:
                        if wl in result['dff']:
                            conditions[condition_name]['dff'][wl].extend(result['dff'][wl])
                        if wl in result['zscore']:
                            conditions[condition_name]['zscore'][wl].extend(result['zscore'][wl])
                    
                    # Collect statistics
                    if params['export_stats'] and len(result['running']) > 0:
                        stats = collect_statistics_with_condition(
                            day_name, animal_id, params['full_event_type'],
                            result, time_array, params, target_wavelengths, 
                            active_channels, condition_name
                        )
                        statistics_rows.extend(stats)
        
        except Exception as e:
            log_message(f"Error analyzing {animal_id}: {str(e)}", "ERROR")
            continue
    
    # Combine results
    result = {
        'time': time_array,
        'target_wavelengths': target_wavelengths
    }
    
    # Process each condition
    for condition_name, condition_data in conditions.items():
        result[condition_name] = {
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
                result[condition_name]['dff'][wl] = {
                    'episodes': episodes_array,
                    'mean': np.nanmean(episodes_array, axis=0),
                    'sem': np.nanstd(episodes_array, axis=0) / np.sqrt(len(condition_data['dff'][wl]))
                }
            
            if condition_data['zscore'][wl]:
                episodes_array = np.array(condition_data['zscore'][wl])
                result[condition_name]['zscore'][wl] = {
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
    
    return rows

def plot_running_optogenetics_drug_results(results, params):
    """Plot running+optogenetics+drug results"""
    
    # 1. Pre Drug: With vs Without Opto
    plot_comparison_window(
        results, params, 
        'pre_drug_with_opto', 'pre_drug_without_opto',
        'Pre Drug: With vs Without Optogenetics',
        'Pre Drug + Opto', 'Pre Drug - Opto'
    )
    
    # 2. Post Drug: With vs Without Opto
    plot_comparison_window(
        results, params,
        'post_drug_with_opto', 'post_drug_without_opto',
        'Post Drug: With vs Without Optogenetics',
        'Post Drug + Opto', 'Post Drug - Opto'
    )
    
    # 3. With Opto: Pre vs Post Drug
    plot_comparison_window(
        results, params,
        'pre_drug_with_opto', 'post_drug_with_opto',
        'With Optogenetics: Pre vs Post Drug',
        'Pre Drug', 'Post Drug'
    )
    
    # 4. Without Opto: Pre vs Post Drug
    plot_comparison_window(
        results, params,
        'pre_drug_without_opto', 'post_drug_without_opto',
        'Without Optogenetics: Pre vs Post Drug',
        'Pre Drug', 'Post Drug'
    )
    
    # Create individual day windows
    create_individual_day_windows_running_optogenetics_drug(results, params)

def plot_comparison_window(results, params, condition1, condition2, 
                           window_title, label1, label2):
    """Create a comparison window for two conditions"""
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
    
    # Row 1: Traces
    # Running trace
    ax_running = fig.add_subplot(2, num_cols, plot_idx)
    for idx, (day_name, data) in enumerate(results.items()):
        day_color = DAY_COLORS[idx % len(DAY_COLORS)]
        
        # Condition 1
        if condition1 in data and data[condition1]['running']['mean'] is not None:
            ax_running.plot(time_array, data[condition1]['running']['mean'],
                          color=day_color, linestyle='-', linewidth=2, alpha=1,
                          label=f"{day_name} {label1}")
            ax_running.fill_between(time_array,
                                   data[condition1]['running']['mean'] - data[condition1]['running']['sem'],
                                   data[condition1]['running']['mean'] + data[condition1]['running']['sem'],
                                   color=day_color, alpha=0.5)
        
        # Condition 2
        if condition2 in data and data[condition2]['running']['mean'] is not None:
            ax_running.plot(time_array, data[condition2]['running']['mean'],
                          color=day_color, linestyle='-', linewidth=2, alpha=0.5,
                          label=f"{day_name} {label2}")
            ax_running.fill_between(time_array,
                                   data[condition2]['running']['mean'] - data[condition2]['running']['sem'],
                                   data[condition2]['running']['mean'] + data[condition2]['running']['sem'],
                                   color=day_color, alpha=0.3)
    
    ax_running.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
    ax_running.set_xlim(time_array[0], time_array[-1])
    ax_running.set_xlabel('Time (s)')
    ax_running.set_ylabel('Speed (cm/s)')
    ax_running.set_title(f'Running Speed - {window_title}')
    ax_running.legend(fontsize=7, ncol=2)
    ax_running.grid(False)
    plot_idx += 1
    
    # Fiber traces
    for wl_idx, wl in enumerate(target_wavelengths):
        color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        
        # dFF trace
        ax_dff = fig.add_subplot(2, num_cols, plot_idx)
        for idx, (day_name, data) in enumerate(results.items()):
            day_color = DAY_COLORS[idx % len(DAY_COLORS)]
            
            if condition1 in data and wl in data[condition1]['dff']:
                ax_dff.plot(time_array, data[condition1]['dff'][wl]['mean'],
                          color=day_color, linewidth=2, linestyle='-', alpha=1,
                          label=f'{day_name} {label1}')
                ax_dff.fill_between(time_array,
                                   data[condition1]['dff'][wl]['mean'] - data[condition1]['dff'][wl]['sem'],
                                   data[condition1]['dff'][wl]['mean'] + data[condition1]['dff'][wl]['sem'],
                                   color=day_color, alpha=0.5)
            
            if condition2 in data and wl in data[condition2]['dff']:
                ax_dff.plot(time_array, data[condition2]['dff'][wl]['mean'],
                          color=day_color, linewidth=2, linestyle='-', alpha=0.5,
                          label=f'{day_name} {label2}')
                ax_dff.fill_between(time_array,
                                   data[condition2]['dff'][wl]['mean'] - data[condition2]['dff'][wl]['sem'],
                                   data[condition2]['dff'][wl]['mean'] + data[condition2]['dff'][wl]['sem'],
                                   color=day_color, alpha=0.3)
        
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
            
            if condition1 in data and wl in data[condition1]['zscore']:
                ax_zscore.plot(time_array, data[condition1]['zscore'][wl]['mean'],
                             color=day_color, linewidth=2, linestyle='-', alpha=1,
                             label=f'{day_name} {label1}')
                ax_zscore.fill_between(time_array,
                                      data[condition1]['zscore'][wl]['mean'] - data[condition1]['zscore'][wl]['sem'],
                                      data[condition1]['zscore'][wl]['mean'] + data[condition1]['zscore'][wl]['sem'],
                                      color=day_color, alpha=0.5)
            
            if condition2 in data and wl in data[condition2]['zscore']:
                ax_zscore.plot(time_array, data[condition2]['zscore'][wl]['mean'],
                             color=day_color, linewidth=2, linestyle='-', alpha=0.5,
                             label=f'{day_name} {label2}')
                ax_zscore.fill_between(time_array,
                                      data[condition2]['zscore'][wl]['mean'] - data[condition2]['zscore'][wl]['sem'],
                                      data[condition2]['zscore'][wl]['mean'] + data[condition2]['zscore'][wl]['sem'],
                                      color=day_color, alpha=0.3)
        
        ax_zscore.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_zscore.set_xlim(time_array[0], time_array[-1])
        ax_zscore.set_xlabel('Time (s)')
        ax_zscore.set_ylabel('Z-score')
        ax_zscore.set_title(f'Fiber Z-score {wl}nm')
        ax_zscore.legend(fontsize=7, ncol=2)
        ax_zscore.grid(False)
        plot_idx += 1
    
    # Row 2: Heatmaps
    # Running heatmap
    ax_running_heat = fig.add_subplot(2, num_cols, plot_idx)
    all_cond1 = []
    all_cond2 = []
    
    for day_name, data in results.items():
        if condition1 in data and len(data[condition1]['running']['episodes']) > 0:
            all_cond1.extend(data[condition1]['running']['episodes'])
        if condition2 in data and len(data[condition2]['running']['episodes']) > 0:
            all_cond2.extend(data[condition2]['running']['episodes'])
    
    if all_cond1 and all_cond2:
        combined = np.vstack([np.array(all_cond1), np.array(all_cond2)])
        n_cond1 = len(all_cond1)
        
        if len(combined) == 1:
            combined = np.vstack([combined[0], combined[0]])
            im = ax_running_heat.imshow(combined, aspect='auto',
                                        extent=[time_array[0], time_array[-1], 0, 1],
                                        cmap='viridis', origin='lower')
        else:
            im = ax_running_heat.imshow(combined, aspect='auto',
                                        extent=[time_array[0], time_array[-1], 0, len(combined)],
                                        cmap='viridis', origin='lower')
        
        ax_running_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
        ax_running_heat.axhline(y=n_cond1, color='k', linestyle='--', linewidth=1)
        ax_running_heat.set_xlabel('Time (s)')
        ax_running_heat.set_ylabel('Trials')
        ax_running_heat.set_title('Running Speed Heatmap')
        plt.colorbar(im, ax=ax_running_heat, label='Speed (cm/s)', orientation='horizontal')
    plot_idx += 1
    
    # Fiber heatmaps
    for wl_idx, wl in enumerate(target_wavelengths):
        # dFF heatmap
        ax_dff_heat = fig.add_subplot(2, num_cols, plot_idx)
        all_cond1_dff = []
        all_cond2_dff = []
        
        for day_name, data in results.items():
            if condition1 in data and wl in data[condition1]['dff']:
                all_cond1_dff.extend(data[condition1]['dff'][wl]['episodes'])
            if condition2 in data and wl in data[condition2]['dff']:
                all_cond2_dff.extend(data[condition2]['dff'][wl]['episodes'])
        
        if all_cond1_dff and all_cond2_dff:
            combined_dff = np.vstack([np.array(all_cond1_dff), np.array(all_cond2_dff)])
            n_cond1 = len(all_cond1_dff)
            
            if len(combined_dff) == 1:
                combined_dff = np.vstack([combined_dff[0], combined_dff[0]])
                im = ax_dff_heat.imshow(combined_dff, aspect='auto',
                                    extent=[time_array[0], time_array[-1], 0, 1],
                                    cmap='coolwarm', origin='lower')
            else:
                im = ax_dff_heat.imshow(combined_dff, aspect='auto',
                                    extent=[time_array[0], time_array[-1], 0, len(combined_dff)],
                                    cmap='coolwarm', origin='lower')
            
            ax_dff_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            ax_dff_heat.axhline(y=n_cond1, color='k', linestyle='--', linewidth=1)
            ax_dff_heat.set_xlabel('Time (s)')
            ax_dff_heat.set_ylabel('Trials')
            ax_dff_heat.set_title(f'Fiber ΔF/F Heatmap {wl}nm')
            plt.colorbar(im, ax=ax_dff_heat, label='ΔF/F', orientation='horizontal')
        plot_idx += 1
        
        # Z-score heatmap
        ax_zscore_heat = fig.add_subplot(2, num_cols, plot_idx)
        all_cond1_zscore = []
        all_cond2_zscore = []
        
        for day_name, data in results.items():
            if condition1 in data and wl in data[condition1]['zscore']:
                all_cond1_zscore.extend(data[condition1]['zscore'][wl]['episodes'])
            if condition2 in data and wl in data[condition2]['zscore']:
                all_cond2_zscore.extend(data[condition2]['zscore'][wl]['episodes'])
        
        if all_cond1_zscore and all_cond2_zscore:
            combined_zscore = np.vstack([np.array(all_cond1_zscore), np.array(all_cond2_zscore)])
            n_cond1 = len(all_cond1_zscore)
            
            if len(combined_zscore) == 1:
                combined_zscore = np.vstack([combined_zscore[0], combined_zscore[0]])
                im = ax_zscore_heat.imshow(combined_zscore, aspect='auto',
                                        extent=[time_array[0], time_array[-1], 0, 1],
                                        cmap='coolwarm', origin='lower')
            else:
                im = ax_zscore_heat.imshow(combined_zscore, aspect='auto',
                                        extent=[time_array[0], time_array[-1], 0, len(combined_zscore)],
                                        cmap='coolwarm', origin='lower')
            
            ax_zscore_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            ax_zscore_heat.axhline(y=n_cond1, color='k', linestyle='--', linewidth=1)
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

def create_individual_day_windows_running_optogenetics_drug(results, params):
    """Create individual windows for each day - running+optogenetics+drug"""
    for day_name, data in results.items():
        conditions = [
            {
                'condition1': 'pre_drug_with_opto',
                'condition2': 'pre_drug_without_opto',
                'title': f'Running+Optogenetics+Drug - {day_name} - Pre Drug: With vs Without Opto',
                'label1': 'With Opto',
                'label2': 'Without Opto'
            },
            {
                'condition1': 'post_drug_with_opto',
                'condition2': 'post_drug_without_opto',
                'title': f'Running+Optogenetics+Drug - {day_name} - Post Drug: With vs Without Opto',
                'label1': 'With Opto',
                'label2': 'Without Opto'
            },
            {
                'condition1': 'pre_drug_with_opto',
                'condition2': 'post_drug_with_opto',
                'title': f'Running+Optogenetics+Drug - {day_name} - With Opto: Pre vs Post Drug',
                'label1': 'Pre Drug',
                'label2': 'Post Drug'
            },
            {
                'condition1': 'pre_drug_without_opto',
                'condition2': 'post_drug_without_opto',
                'title': f'Running+Optogenetics+Drug - {day_name} - Without Opto: Pre vs Post Drug',
                'label1': 'Pre Drug',
                'label2': 'Post Drug'
            }
        ]
        
        for condition_info in conditions:
            create_single_day_comparison_window(
                day_name, data, params,
                condition_info['condition1'], condition_info['condition2'],
                condition_info['title'],
                condition_info['label1'], condition_info['label2']
            )

def create_single_day_comparison_window(day_name, data, params, condition1, condition2,
                                        window_title, label1, label2):
    """Create a single window for one comparison condition on one day"""
    target_wavelengths = data.get('target_wavelengths', ['470'])
    
    if not target_wavelengths:
        target_wavelengths = ['470']
    
    result_window = tk.Toplevel()
    result_window.title(window_title)
    result_window.state('zoomed')
    result_window.configure(bg='#f8f8f8')
    
    num_wavelengths = len(target_wavelengths)
    num_cols = 1 + 2 * num_wavelengths
    
    fig = Figure(figsize=(4 * num_cols, 8), dpi=100)
    
    plot_idx = 1
    time_array = data['time']
    
    # Row 1: Traces
    # Running trace
    ax_running = fig.add_subplot(2, num_cols, plot_idx)
    
    # Plot condition 1
    if condition1 in data and data[condition1]['running']['mean'] is not None:
        ax_running.plot(time_array, data[condition1]['running']['mean'],
                      color="#000000", linewidth=2, label=label1, alpha=0.5)
        ax_running.fill_between(time_array,
                               data[condition1]['running']['mean'] - data[condition1]['running']['sem'],
                               data[condition1]['running']['mean'] + data[condition1]['running']['sem'],
                               color="#000000", alpha=0.3)
    
    # Plot condition 2
    if condition2 in data and data[condition2]['running']['mean'] is not None:
        ax_running.plot(time_array, data[condition2]['running']['mean'],
                      color="#000000", linewidth=2, label=label2, alpha=1)
        ax_running.fill_between(time_array,
                               data[condition2]['running']['mean'] - data[condition2]['running']['sem'],
                               data[condition2]['running']['mean'] + data[condition2]['running']['sem'],
                               color="#000000", alpha=0.5)
    
    ax_running.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
    ax_running.set_xlim(time_array[0], time_array[-1])
    ax_running.set_xlabel('Time (s)')
    ax_running.set_ylabel('Speed (cm/s)')
    ax_running.set_title(f'Running Speed - {label1} vs {label2}')
    ax_running.legend()
    ax_running.grid(False)
    plot_idx += 1
    
    # Fiber traces
    for wl_idx, wl in enumerate(target_wavelengths):
        fiber_color = FIBER_COLORS[wl_idx % len(FIBER_COLORS)]
        
        # dFF trace
        ax_dff = fig.add_subplot(2, num_cols, plot_idx)
        
        if condition1 in data and wl in data[condition1]['dff']:
            ax_dff.plot(time_array, data[condition1]['dff'][wl]['mean'],
                      color=fiber_color, linewidth=2, linestyle='-', alpha=0.5, label=f'{label1}')
            ax_dff.fill_between(time_array,
                               data[condition1]['dff'][wl]['mean'] - data[condition1]['dff'][wl]['sem'],
                               data[condition1]['dff'][wl]['mean'] + data[condition1]['dff'][wl]['sem'],
                               color=fiber_color, alpha=0.3)
        
        if condition2 in data and wl in data[condition2]['dff']:
            ax_dff.plot(time_array, data[condition2]['dff'][wl]['mean'],
                      color=fiber_color, linewidth=2, linestyle='-', alpha=1, label=f'{label2}')
            ax_dff.fill_between(time_array,
                               data[condition2]['dff'][wl]['mean'] - data[condition2]['dff'][wl]['sem'],
                               data[condition2]['dff'][wl]['mean'] + data[condition2]['dff'][wl]['sem'],
                               color=fiber_color, alpha=0.5)
        
        ax_dff.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_dff.set_xlim(time_array[0], time_array[-1])
        ax_dff.set_xlabel('Time (s)')
        ax_dff.set_ylabel('ΔF/F')
        ax_dff.set_title(f'Fiber ΔF/F {wl}nm')
        ax_dff.legend()
        ax_dff.grid(False)
        plot_idx += 1
        
        # Z-score trace
        ax_zscore = fig.add_subplot(2, num_cols, plot_idx)
        
        if condition1 in data and wl in data[condition1]['zscore']:
            ax_zscore.plot(time_array, data[condition1]['zscore'][wl]['mean'],
                         color=fiber_color, linewidth=2, linestyle='-', alpha=0.5, label=f'{label1}')
            ax_zscore.fill_between(time_array,
                                  data[condition1]['zscore'][wl]['mean'] - data[condition1]['zscore'][wl]['sem'],
                                  data[condition1]['zscore'][wl]['mean'] + data[condition1]['zscore'][wl]['sem'],
                                  color=fiber_color, alpha=0.3)
        
        if condition2 in data and wl in data[condition2]['zscore']:
            ax_zscore.plot(time_array, data[condition2]['zscore'][wl]['mean'],
                         color=fiber_color, linewidth=2, linestyle='-', alpha=1, label=f'{label2}')
            ax_zscore.fill_between(time_array,
                                  data[condition2]['zscore'][wl]['mean'] - data[condition2]['zscore'][wl]['sem'],
                                  data[condition2]['zscore'][wl]['mean'] + data[condition2]['zscore'][wl]['sem'],
                                  color=fiber_color, alpha=0.5)
        
        ax_zscore.axvline(x=0, color='#808080', linestyle='--', alpha=0.8)
        ax_zscore.set_xlim(time_array[0], time_array[-1])
        ax_zscore.set_xlabel('Time (s)')
        ax_zscore.set_ylabel('Z-score')
        ax_zscore.set_title(f'Fiber Z-score {wl}nm')
        ax_zscore.legend()
        ax_zscore.grid(False)
        plot_idx += 1
    
    # Row 2: Heatmaps
    # Running heatmap
    ax_running_heat = fig.add_subplot(2, num_cols, plot_idx)
    
    cond1_running = []
    cond2_running = []
    
    if condition1 in data and len(data[condition1]['running']['episodes']) > 0:
        cond1_running = data[condition1]['running']['episodes']
    
    if condition2 in data and len(data[condition2]['running']['episodes']) > 0:
        cond2_running = data[condition2]['running']['episodes']
    
    if cond1_running is not None or cond2_running is not None:
        # Combine episodes from both conditions
        all_episodes = []
        if cond1_running is not None:
            all_episodes.extend(cond1_running)
        if cond2_running is not None:
            all_episodes.extend(cond2_running)
        
        all_episodes = np.array(all_episodes)
        n_cond1 = len(cond1_running)
        
        if len(all_episodes) > 0:
            im = ax_running_heat.imshow(all_episodes, aspect='auto',
                                      extent=[time_array[0], time_array[-1], 0, len(all_episodes)],
                                      cmap='viridis', origin='lower')
            
            ax_running_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
            if n_cond1 > 0 and len(all_episodes) > n_cond1:
                ax_running_heat.axhline(y=n_cond1, color='k', linestyle='--', linewidth=1, 
                                      label=f'{label1}/{label2} boundary')
            
            ax_running_heat.set_xlabel('Time (s)')
            ax_running_heat.set_ylabel('Trials')
            ax_running_heat.set_title('Running Speed Heatmap')
            ax_running_heat.legend(loc='upper right', fontsize=8)
            plt.colorbar(im, ax=ax_running_heat, label='Speed (cm/s)', orientation='horizontal')
    else:
        ax_running_heat.text(0.5, 0.5, 'No running data available',
                           ha='center', va='center', transform=ax_running_heat.transAxes,
                           fontsize=12, color='#666666')
        ax_running_heat.set_title('Running Speed Heatmap')
        ax_running_heat.axis('off')
    
    plot_idx += 1
    
    # Fiber heatmaps
    for wl_idx, wl in enumerate(target_wavelengths):
        # dFF heatmap
        ax_dff_heat = fig.add_subplot(2, num_cols, plot_idx)
        
        cond1_dff = []
        cond2_dff = []
        
        if condition1 in data and wl in data[condition1]['dff']:
            cond1_dff = data[condition1]['dff'][wl]['episodes']
        
        if condition2 in data and wl in data[condition2]['dff']:
            cond2_dff = data[condition2]['dff'][wl]['episodes']
        
        if cond1_dff is not None or cond2_dff is not None:
            # Combine episodes from both conditions
            all_dff = []
            if cond1_dff is not None:
                all_dff.extend(cond1_dff)
            if cond2_dff is not None:
                all_dff.extend(cond2_dff)
            
            all_dff = np.array(all_dff)
            n_cond1 = len(cond1_dff)
            
            if len(all_dff) > 0:
                im = ax_dff_heat.imshow(all_dff, aspect='auto',
                                      extent=[time_array[0], time_array[-1], 0, len(all_dff)],
                                      cmap='coolwarm', origin='lower')
                
                ax_dff_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
                if n_cond1 > 0 and len(all_dff) > n_cond1:
                    ax_dff_heat.axhline(y=n_cond1, color='k', linestyle='--', linewidth=1,
                                      label=f'{label1}/{label2} boundary')
                
                ax_dff_heat.set_xlabel('Time (s)')
                ax_dff_heat.set_ylabel('Trials')
                ax_dff_heat.set_title(f'Fiber ΔF/F Heatmap {wl}nm')
                ax_dff_heat.legend(loc='upper right', fontsize=8)
                plt.colorbar(im, ax=ax_dff_heat, label='ΔF/F', orientation='horizontal')
        else:
            ax_dff_heat.text(0.5, 0.5, f'No dFF data for {wl}nm',
                           ha='center', va='center', transform=ax_dff_heat.transAxes,
                           fontsize=12, color='#666666')
            ax_dff_heat.set_title(f'Fiber ΔF/F Heatmap {wl}nm')
            ax_dff_heat.axis('off')
        
        plot_idx += 1
        
        # Z-score heatmap
        ax_zscore_heat = fig.add_subplot(2, num_cols, plot_idx)
        
        cond1_zscore = []
        cond2_zscore = []
        
        if condition1 in data and wl in data[condition1]['zscore']:
            cond1_zscore = data[condition1]['zscore'][wl]['episodes']
        
        if condition2 in data and wl in data[condition2]['zscore']:
            cond2_zscore = data[condition2]['zscore'][wl]['episodes']
        
        if cond1_zscore is not None or cond2_zscore is not None:
            # Combine episodes from both conditions
            all_zscore = []
            if cond1_zscore is not None:
                all_zscore.extend(cond1_zscore)
            if cond2_zscore is not None:
                all_zscore.extend(cond2_zscore)
            
            all_zscore = np.array(all_zscore)
            n_cond1 = len(cond1_zscore)
            
            if len(all_zscore) > 0:
                im = ax_zscore_heat.imshow(all_zscore, aspect='auto',
                                         extent=[time_array[0], time_array[-1], 0, len(all_zscore)],
                                         cmap='coolwarm', origin='lower')
                
                ax_zscore_heat.axvline(x=0, color="#FF0000", linestyle='--', alpha=0.8)
                if n_cond1 > 0 and len(all_zscore) > n_cond1:
                    ax_zscore_heat.axhline(y=n_cond1, color='k', linestyle='--', linewidth=1,
                                         label=f'{label1}/{label2} boundary')
                
                ax_zscore_heat.set_xlabel('Time (s)')
                ax_zscore_heat.set_ylabel('Trials')
                ax_zscore_heat.set_title(f'Fiber Z-score Heatmap {wl}nm')
                ax_zscore_heat.legend(loc='upper right', fontsize=8)
                plt.colorbar(im, ax=ax_zscore_heat, label='Z-score', orientation='horizontal')
        else:
            ax_zscore_heat.text(0.5, 0.5, f'No Z-score data for {wl}nm',
                              ha='center', va='center', transform=ax_zscore_heat.transAxes,
                              fontsize=12, color='#666666')
            ax_zscore_heat.set_title(f'Fiber Z-score Heatmap {wl}nm')
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
    
    log_message(f"Comparison plot created: {window_title}")