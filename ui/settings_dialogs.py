import os
import signal
import pickle
import tkinter as tk

from datetime import datetime

from analysis_multimodal.Multimodal_analysis import calculate_optogenetic_pulse_info, group_optogenetic_sessions, identify_drug_sessions, identify_optogenetic_events
from infrastructure.logger import log_message, set_log_widget
import ui.windows.visualization_windows as visualization_windows
import workflows.data_workflows as data_workflows
import workflows.analysis_workflows as analysis_workflows
import ui.bodypart_controller as bodypart_controller
import ui.view_controller as view_controller

_deps = {}

def bind_settings_dependencies(deps):
    _deps.clear()
    _deps.update(deps)
    globals().update(deps)

def setup_log_display():
    global log_text_widget
    for widget in bottom_display_frame.winfo_children():
        widget.destroy()
    
    log_text_widget = tk.Text(bottom_display_frame, wrap=tk.WORD, height=10, font=("Consolas", 9))
    log_text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    set_log_widget(log_text_widget)
    log_message("The log system has been initialized. All messages will be displayed here.", "INFO")

def select_experiment_mode():
    """Open dialog to select experiment mode"""
    global current_experiment_mode
    
    mode_window = tk.Toplevel(root)
    mode_window.title("Select Experiment Mode")
    mode_window.geometry("400x500")
    mode_window.transient(root)
    mode_window.grab_set()
    
    # Title
    title_label = tk.Label(mode_window, text="Experiment Mode Selection", 
                          font=("Arial", 14, "bold"))
    title_label.pack(pady=20)
    
    # Description
    desc_label = tk.Label(mode_window, 
                         text="Select the type of data you want to analyze:",
                         font=("Arial", 10))
    desc_label.pack(pady=5)
    
    # Mode selection frame
    mode_frame = tk.Frame(mode_window)
    mode_frame.pack(pady=20)
    
    mode_var = tk.StringVar(value=current_experiment_mode)
    
    # Mode 1: AST2
    mode1_radio = tk.Radiobutton(
        mode_frame,
        text="AST2",
        variable=mode_var,
        value=EXPERIMENT_MODE_AST2,
        font=("Arial", 10),
        justify=tk.LEFT
    )
    mode1_radio.pack(anchor="w", pady=5)

    mode1_desc = tk.Label(mode_frame, 
                         text="  • Running wheel data (AST2)",
                         font=("Arial", 9), fg="gray", justify=tk.LEFT)
    mode1_desc.pack(anchor="w", padx=20)

    # Mode 2: Fiber + AST2
    mode2_radio = tk.Radiobutton(
        mode_frame,
        text="Fiber + AST2",
        variable=mode_var,
        value=EXPERIMENT_MODE_FIBER_AST2,
        font=("Arial", 10),
        justify=tk.LEFT
    )
    mode2_radio.pack(anchor="w", pady=5)
    
    mode2_desc = tk.Label(mode_frame, 
                         text="  • Fiber photometry data\n  • Running wheel data (AST2)",
                         font=("Arial", 9), fg="gray", justify=tk.LEFT)
    mode2_desc.pack(anchor="w", padx=20)
    
    # Mode 3: Fiber + AST2 + DLC
    mode3_radio = tk.Radiobutton(
        mode_frame,
        text="Fiber + AST2 + DLC",
        variable=mode_var,
        value=EXPERIMENT_MODE_FIBER_AST2_DLC,
        font=("Arial", 10),
        justify=tk.LEFT
    )
    mode3_radio.pack(anchor="w", pady=(15, 5))
    
    mode3_desc = tk.Label(mode_frame, 
                         text="  • Fiber photometry data\n  • Running wheel data (AST2)\n  • DeepLabCut behavioral tracking",
                         font=("Arial", 9), fg="gray", justify=tk.LEFT)
    mode3_desc.pack(anchor="w", padx=20)
    
    def apply_mode():
        global current_experiment_mode
        new_mode = mode_var.get()
        
        # Check if there's existing data
        if multi_animal_data:
            response = tk.messagebox.askyesno(
                "Confirm Mode Change",
                "Changing experiment mode will clear all loaded data.\nDo you want to continue?"
            )
            if not response:
                return
            
            # Clear existing data
            clear_all()
        
        current_experiment_mode = new_mode
        visualization_windows.bind_window_dependencies(globals())
        data_workflows.bind_workflow_dependencies(globals())
        analysis_workflows.bind_analysis_dependencies(globals())
        bodypart_controller.bind_bodypart_dependencies(globals())
        view_controller.bind_view_dependencies(globals())
        bind_settings_dependencies(globals())
        
        # Update UI based on mode
        update_ui_for_mode()
        
        if new_mode == EXPERIMENT_MODE_AST2:
            log_message("Experiment mode set to: AST2 only", "INFO")
        elif new_mode == EXPERIMENT_MODE_FIBER_AST2:
            log_message("Experiment mode set to: Fiber + AST2", "INFO")
        elif new_mode == EXPERIMENT_MODE_FIBER_AST2_DLC:
             log_message("Experiment mode set to: Fiber + AST2 + DLC", "INFO")
        
        mode_window.destroy()
    
    # Button frame
    button_frame = tk.Frame(mode_window)
    button_frame.pack(pady=10)
    
    tk.Button(button_frame, text="Apply", command=apply_mode,
             bg="#27ae60", fg="white", font=("Arial", 10, "bold"),
             padx=20, pady=5).pack(side=tk.LEFT, padx=5)
    
    tk.Button(button_frame, text="Cancel", command=mode_window.destroy,
             bg="#95a5a6", fg="white", font=("Arial", 10, "bold"),
             padx=20, pady=5).pack(side=tk.LEFT, padx=5)

def update_ui_for_mode():
    """Update UI elements based on current experiment mode"""
    global current_experiment_mode
    
    # Update menu items
    if current_experiment_mode == EXPERIMENT_MODE_AST2:
        analysis_menu.entryconfig("Behavior Analysis", state="disabled")
        analysis_menu.entryconfig("Running Data Analysis", state="normal")
        analysis_menu.entryconfig("Fiber Data Preprocessing", state="disabled")
        analysis_menu.entryconfig("Fiber Data Analysis", state="disabled")
        multimodal_menu.entryconfig("Running-Induced Activity Analysis", state="disabled")
        multimodal_menu.entryconfig("Drug-Induced Activity Analysis", state="disabled")
        multimodal_menu.entryconfig("Optogenetics-Induced Activity Analysis", state="disabled")
        multimodal_menu.entryconfig("Bout Analysis", state="normal")
        bout_menu.entryconfig("Running", state="normal")
        bout_menu.entryconfig("Running + Drug", state="disabled")
    elif current_experiment_mode == EXPERIMENT_MODE_FIBER_AST2:
        analysis_menu.entryconfig("Behavior Analysis", state="disabled")
        analysis_menu.entryconfig("Running Data Analysis", state="normal")
        analysis_menu.entryconfig("Fiber Data Preprocessing", state="normal")
        analysis_menu.entryconfig("Fiber Data Analysis", state="normal")
        multimodal_menu.entryconfig("Running-Induced Activity Analysis", state="normal")
        multimodal_menu.entryconfig("Drug-Induced Activity Analysis", state="normal")
        multimodal_menu.entryconfig("Optogenetics-Induced Activity Analysis", state="normal")
        multimodal_menu.entryconfig("Bout Analysis", state="normal")
        bout_menu.entryconfig("Running", state="normal")
        bout_menu.entryconfig("Running + Drug", state="normal")
    elif current_experiment_mode == EXPERIMENT_MODE_FIBER_AST2_DLC:
        analysis_menu.entryconfig("Behavior Analysis", state="disabled")
        analysis_menu.entryconfig("Running Data Analysis", state="normal")
        analysis_menu.entryconfig("Fiber Data Preprocessing", state="normal")
        analysis_menu.entryconfig("Fiber Data Analysis", state="normal")
        multimodal_menu.entryconfig("Running-Induced Activity Analysis", state="normal")
        multimodal_menu.entryconfig("Drug-Induced Activity Analysis", state="normal")
        multimodal_menu.entryconfig("Optogenetics-Induced Activity Analysis", state="normal")
        multimodal_menu.entryconfig("Bout Analysis", state="normal")
        bout_menu.entryconfig("Running", state="normal")
        bout_menu.entryconfig("Running + Drug", state="normal")
    
    # Clear left panel if in Fiber+AST2 mode
    if current_experiment_mode != EXPERIMENT_MODE_FIBER_AST2_DLC:
        for widget in left_frame.winfo_children():
            widget.destroy()
        
        info_label = tk.Label(left_frame, 
                             text="Fiber + AST2 Mode\n\nBodypart tracking\nnot available",
                             bg="#e0e0e0", fg="#666666",
                             font=("Arial", 10))
        info_label.pack(pady=50)

def show_event_config_dialog():
    """Show event configuration dialog"""
    global event_config
    
    dialog = tk.Toplevel(root)
    dialog.title("Event Configuration")
    dialog.geometry("400x250")
    dialog.transient(root)
    dialog.grab_set()
    
    main_frame = tk.Frame(dialog, bg="#f8f8f8", padx=20, pady=20)
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    tk.Label(main_frame, text="Event String Configuration", 
            font=("Microsoft YaHei", 12, "bold"), bg="#f8f8f8").pack(pady=(0, 20))
    
    # Drug event
    drug_frame = tk.Frame(main_frame, bg="#f8f8f8")
    drug_frame.pack(fill=tk.X, pady=5)
    tk.Label(drug_frame, text="Drug Event:", bg="#f8f8f8", 
            font=("Microsoft YaHei", 10), width=15, anchor='w').pack(side=tk.LEFT)
    drug_var = tk.StringVar(value=event_config.get('drug_event', 'Event1'))
    tk.Entry(drug_frame, textvariable=drug_var, 
            font=("Microsoft YaHei", 10), width=15).pack(side=tk.LEFT, padx=10)
    
    # Optogenetic event
    opto_frame = tk.Frame(main_frame, bg="#f8f8f8")
    opto_frame.pack(fill=tk.X, pady=5)
    tk.Label(opto_frame, text="Optogenetic Event:", bg="#f8f8f8", 
            font=("Microsoft YaHei", 10), width=15, anchor='w').pack(side=tk.LEFT)
    opto_var = tk.StringVar(value=event_config.get('opto_event', 'Input3'))
    tk.Entry(opto_frame, textvariable=opto_var, 
            font=("Microsoft YaHei", 10), width=15).pack(side=tk.LEFT, padx=10)
    
    # Running start event
    running_frame = tk.Frame(main_frame, bg="#f8f8f8")
    running_frame.pack(fill=tk.X, pady=5)
    tk.Label(running_frame, text="Running Start:", bg="#f8f8f8", 
            font=("Microsoft YaHei", 10), width=15, anchor='w').pack(side=tk.LEFT)
    running_var = tk.StringVar(value=event_config.get('running_start', 'Input2'))
    tk.Entry(running_frame, textvariable=running_var, 
            font=("Microsoft YaHei", 10), width=15).pack(side=tk.LEFT, padx=10)
    
    def apply_config():
        event_config['drug_event'] = drug_var.get().strip()
        event_config['opto_event'] = opto_var.get().strip()
        event_config['running_start'] = running_var.get().strip()
        save_event_config()
        log_message("Event configuration saved", "INFO")
        dialog.destroy()
    
    # Buttons
    btn_frame = tk.Frame(main_frame, bg="#f8f8f8")
    btn_frame.pack(pady=(20, 0))
    
    tk.Button(btn_frame, text="Apply", command=apply_config,
             bg="#27ae60", fg="white", font=("Microsoft YaHei", 10, "bold"),
             relief=tk.FLAT, padx=20, pady=5).pack(side=tk.LEFT, padx=5)
    
    tk.Button(btn_frame, text="Cancel", command=dialog.destroy,
             bg="#95a5a6", fg="white", font=("Microsoft YaHei", 10, "bold"),
             relief=tk.FLAT, padx=20, pady=5).pack(side=tk.LEFT, padx=5)

def show_opto_power_config_dialog():
    """Show optogenetic power configuration dialog"""
    global opto_power_config, multi_animal_data
    
    if not multi_animal_data:
        log_message("Please import animal data first", "WARNING")
        return
    
    all_optogenetic_events = {}
    
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
    
    if not all_optogenetic_events:
        log_message("No optogenetic events found in loaded data", "WARNING")
        return
    
    dialog = tk.Toplevel(root)
    dialog.title("Optogenetic Power Configuration")
    dialog.geometry("800x600")
    dialog.transient(root)
    dialog.grab_set()
    
    container = tk.Frame(dialog, bg="#f8f8f8")
    container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    tk.Label(container, text="Configure Power (mW) for Optogenetic Sessions", 
            font=("Microsoft YaHei", 12, "bold"), bg="#f8f8f8").pack(pady=10)
    
    # Scrollable frame
    canvas = tk.Canvas(container, bg="#f8f8f8", highlightthickness=0)
    scrollbar = tk.Scrollbar(container, orient=tk.VERTICAL, command=canvas.yview)
    scrollable_frame = tk.Frame(canvas, bg="#f8f8f8")
    
    scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    power_vars = {}
    row = 0
    
    for animal_id, sessions in all_optogenetic_events.items():
            # Animal header
            tk.Label(scrollable_frame, text=f"Animal: {animal_id}", 
                    font=("Microsoft YaHei", 10, "bold"), bg="#f8f8f8",
                    anchor="w").grid(row=row, column=0, columnspan=4, 
                                    sticky="w", pady=(10, 5), padx=5)
            row += 1
            
            # Session headers
            headers = ["Session", "Frequency (Hz)", "Pulse Width (s)", "Duration (s)", "Power (mW)"]
            for col, header in enumerate(headers):
                tk.Label(scrollable_frame, text=header, font=("Microsoft YaHei", 9, "bold"),
                        bg="#f8f8f8").grid(row=row, column=col, sticky="w", padx=5, pady=2)
            row += 1
            
            # Session rows
            for session_idx, session in enumerate(sessions):
                # Calculate session info
                freq, pulse_width, duration = calculate_optogenetic_pulse_info(session, animal_id)
                
                # Create unique ID (without power)
                base_id = f"{animal_id}+Session{session_idx+1}+{freq:.1f}Hz+{pulse_width*1000:.0f}ms+{duration:.1f}s"
                
                # Session info labels
                tk.Label(scrollable_frame, text=f"Session{session_idx+1}", 
                        bg="#f8f8f8").grid(row=row, column=0, sticky="w", padx=5)
                tk.Label(scrollable_frame, text=f"{freq:.1f}", 
                        bg="#f8f8f8").grid(row=row, column=1, sticky="w", padx=5)
                tk.Label(scrollable_frame, text=f"{pulse_width:.3f}", 
                        bg="#f8f8f8").grid(row=row, column=2, sticky="w", padx=5)
                tk.Label(scrollable_frame, text=f"{duration:.1f}", 
                        bg="#f8f8f8").grid(row=row, column=3, sticky="w", padx=5)
                
                # Power entry
                saved_power = next((v for k, v in opto_power_config.items() if k.startswith(base_id)), "5.0")
                power_var = tk.StringVar(value=saved_power)
                power_entry = tk.Entry(scrollable_frame, textvariable=power_var, 
                                      width=10, font=("Microsoft YaHei", 9))
                power_entry.grid(row=row, column=4, sticky="w", padx=5, pady=2)
                
                power_vars[base_id] = power_var
                row += 1
    
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def apply_power():
        """Apply power values and create final IDs"""
        try:
            # Clear old entries with the same base_id
            new_config = {}
            
            for base_id, power_var in power_vars.items():
                power = float(power_var.get())
                if power <= 0:
                    raise ValueError(f"Power must be positive for {base_id}")
                
                # Create final ID with power
                final_id = f"{base_id}+{power:.1f}mW"
                new_config[final_id] = power
            
            # Remove old entries that match any base_id
            keys_to_remove = []
            for existing_key in opto_power_config.keys():
                for base_id in power_vars.keys():
                    if existing_key.startswith(base_id):
                        keys_to_remove.append(existing_key)
                        break
            
            for key in keys_to_remove:
                del opto_power_config[key]
            
            # Add new entries
            opto_power_config.update(new_config)
            
            save_opto_power_config()
            log_message(f"Power values applied for {len(new_config)} sessions", "INFO")
            dialog.destroy()
            
        except ValueError as e:
            log_message(f"Invalid power value: {str(e)}", "ERROR")

    # Buttons
    btn_frame = tk.Frame(dialog, bg="#f8f8f8")
    btn_frame.pack(fill=tk.X, padx=10, pady=10)
    
    tk.Button(btn_frame, text="Apply", command=apply_power,
                bg="#4CAF50", fg="white", font=("Microsoft YaHei", 9, "bold"),
                relief=tk.FLAT, padx=20, pady=5).pack(side=tk.RIGHT, padx=5)
    
    tk.Button(btn_frame, text="Cancel", command=dialog.destroy,
                bg="#f44336", fg="white", font=("Microsoft YaHei", 9, "bold"),
                relief=tk.FLAT, padx=20, pady=5).pack(side=tk.RIGHT, padx=5)

def show_drug_name_config_dialog():
    """Show drug name configuration dialog with onset and offset times"""
    global drug_name_config, multi_animal_data
    
    if not multi_animal_data:
        log_message("Please import animal data first", "WARNING")
        return
    
    all_drug_sessions = {}
    
    for animal_data in multi_animal_data:
        animal_id = animal_data.get('animal_single_channel_id', 'Unknown')
        events_data = animal_data.get('fiber_events')
        
        # Identify drug sessions with event names
        drug_sessions = identify_drug_sessions(events_data)
        
        if drug_sessions:
            all_drug_sessions[animal_id] = {
                'sessions': drug_sessions,
                'animal_data': animal_data
            }
            log_message(f"Found {len(drug_sessions)} drug sessions for {animal_id}")
    
    if not all_drug_sessions:
        log_message("No drug events found in loaded data", "WARNING")
        return
    
    dialog = tk.Toplevel(root)
    dialog.title("Drug Configuration")
    dialog.geometry("700x500")
    dialog.transient(root)
    dialog.grab_set()
    
    container = tk.Frame(dialog, bg="#f8f8f8")
    container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    tk.Label(container, text="Configure Drug Names and Timing for Each Session", 
            font=("Microsoft YaHei", 12, "bold"), bg="#f8f8f8").pack(pady=10)
    
    # Scrollable frame
    canvas = tk.Canvas(container, bg="#f8f8f8", highlightthickness=0)
    scrollbar = tk.Scrollbar(container, orient=tk.VERTICAL, command=canvas.yview)
    scrollable_frame = tk.Frame(canvas, bg="#f8f8f8")
    
    scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    drug_config_vars = {}
    row = 0
    
    for animal_id, animal_info in all_drug_sessions.items():
        sessions = animal_info['sessions']
        animal_data = animal_info['animal_data']
        
        # Get running end time if available
        running_end_time = None
        ast2_data = animal_data.get('ast2_data_adjusted')
        if ast2_data and 'data' in ast2_data and 'timestamps' in ast2_data['data']:
            running_end_time = ast2_data['data']['timestamps'][-1]
        
        # Animal header
        tk.Label(scrollable_frame, text=f"Animal: {animal_id}", 
                font=("Microsoft YaHei", 10, "bold"), bg="#f8f8f8",
                anchor="w").grid(row=row, column=0, columnspan=7, 
                                sticky="w", pady=(10, 5), padx=5)
        row += 1
        
        # Session headers
        headers = ["Session", "Event Name", "Admin Time (s)", "Drug Name", 
                  "Onset Time (s)", "Offset Time (s)", ""]
        for col, header in enumerate(headers):
            tk.Label(scrollable_frame, text=header, font=("Microsoft YaHei", 9, "bold"),
                    bg="#f8f8f8").grid(row=row, column=col, sticky="w", padx=5, pady=2)
        row += 1
        
        # Session rows
        for session_idx, session_info in enumerate(sessions):
            session_id = f"{animal_id}_Session{session_idx+1}"
            admin_time = session_info['time']
            
            # Get saved config or set defaults
            saved_config = drug_name_config.get(session_id, {})
            if isinstance(saved_config, str):  # Old format compatibility
                saved_config = {
                    'name': saved_config,
                    'onset_time': admin_time,
                    'offset_time': None
                }
            
            default_name = saved_config.get('name', 'Drug')
            default_onset = saved_config.get('onset_time', admin_time)
            
            # Calculate default offset time
            if session_idx < len(sessions) - 1:
                default_offset = saved_config.get('offset_time', sessions[session_idx + 1]['time'])
            else:
                default_offset = saved_config.get('offset_time', running_end_time if running_end_time else admin_time + 1000)
            
            # Session info labels
            tk.Label(scrollable_frame, text=f"Session{session_idx+1}", 
                    bg="#f8f8f8").grid(row=row, column=0, sticky="w", padx=5)
            tk.Label(scrollable_frame, text=session_info['event_name'], 
                    bg="#f8f8f8", fg="blue").grid(row=row, column=1, sticky="w", padx=5)
            tk.Label(scrollable_frame, text=f"{admin_time:.1f}", 
                    bg="#f8f8f8").grid(row=row, column=2, sticky="w", padx=5)
            
            # Drug name entry
            name_var = tk.StringVar(value=default_name)
            name_entry = tk.Entry(scrollable_frame, textvariable=name_var, 
                                 width=15, font=("Microsoft YaHei", 9))
            name_entry.grid(row=row, column=3, sticky="w", padx=5, pady=2)
            
            # Onset time entry
            onset_var = tk.StringVar(value=f"{default_onset:.1f}")
            onset_entry = tk.Entry(scrollable_frame, textvariable=onset_var, 
                                  width=12, font=("Microsoft YaHei", 9))
            onset_entry.grid(row=row, column=4, sticky="w", padx=5, pady=2)
            
            # Offset time entry
            offset_var = tk.StringVar(value=f"{default_offset:.1f}" if default_offset else "")
            offset_entry = tk.Entry(scrollable_frame, textvariable=offset_var, 
                                   width=12, font=("Microsoft YaHei", 9))
            offset_entry.grid(row=row, column=5, sticky="w", padx=5, pady=2)
            
            # Auto-fill button
            def make_auto_fill(s_idx, sessions_list, r_end, o_var, off_var, a_time):
                def auto_fill():
                    o_var.set(f"{a_time:.1f}")
                    if s_idx < len(sessions_list) - 1:
                        off_var.set(f"{sessions_list[s_idx + 1]['time']:.1f}")
                    else:
                        if r_end:
                            off_var.set(f"{r_end:.1f}")
                        else:
                            off_var.set(f"{a_time + 1000:.1f}")
                return auto_fill
            
            auto_btn = tk.Button(scrollable_frame, text="Auto", 
                               command=make_auto_fill(session_idx, sessions, running_end_time, 
                                                     onset_var, offset_var, admin_time),
                               bg="#e0e0e0", font=("Microsoft YaHei", 8))
            auto_btn.grid(row=row, column=6, sticky="w", padx=5, pady=2)
            
            drug_config_vars[session_id] = {
                'name': name_var,
                'onset': onset_var,
                'offset': offset_var,
                'admin_time': admin_time
            }
            row += 1
    
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def apply_config():
        """Apply drug configuration"""
        try:
            for session_id, vars_dict in drug_config_vars.items():
                drug_name = vars_dict['name'].get().strip()
                if not drug_name:
                    drug_name = "Drug"
                
                try:
                    onset_time = float(vars_dict['onset'].get())
                except:
                    onset_time = vars_dict['admin_time']
                    log_message(f"Invalid onset time for {session_id}, using admin time", "WARNING")
                
                try:
                    offset_str = vars_dict['offset'].get().strip()
                    offset_time = float(offset_str) if offset_str else None
                except:
                    offset_time = None
                    log_message(f"Invalid offset time for {session_id}, will use default", "WARNING")
                
                drug_name_config[session_id] = {
                    'name': drug_name,
                    'admin_time': vars_dict['admin_time'],
                    'onset_time': onset_time,
                    'offset_time': offset_time
                }
            
            save_drug_name_config()
            log_message(f"Drug configuration saved for {len(drug_config_vars)} sessions", "INFO")
            dialog.destroy()
            
        except Exception as e:
            log_message(f"Error configuring drugs: {str(e)}", "ERROR")
            import traceback
            traceback.print_exc()

    # Buttons
    btn_frame = tk.Frame(dialog, bg="#f8f8f8")
    btn_frame.pack(fill=tk.X, padx=10, pady=10)
    
    tk.Button(btn_frame, text="Apply", command=apply_config,
                bg="#4CAF50", fg="white", font=("Microsoft YaHei", 9, "bold"),
                relief=tk.FLAT, padx=15, pady=5).pack(side=tk.LEFT, padx=5)
    
    tk.Button(btn_frame, text="Cancel", command=dialog.destroy,
                bg="#f44336", fg="white", font=("Microsoft YaHei", 9, "bold"),
                relief=tk.FLAT, padx=15, pady=5).pack(side=tk.LEFT, padx=5)
    
    # Help text
    help_text = ("Onset Time: When the drug starts to take effect (default: admin time)\n"
                "Offset Time: When the drug effect ends (default: next drug admin or running end)\n"
                "Click 'Auto' to auto-fill with defaults")
    tk.Label(btn_frame, text=help_text, bg="#f8f8f8", fg="#666666",
            font=("Microsoft YaHei", 8), justify=tk.LEFT).pack(side=tk.RIGHT, padx=10)

def save_path_setting():
    save_dir = tk.filedialog.askdirectory(title='Select directory to save results')
    if not save_dir:
        log_message("Save path selection cancelled. No directory selected.", "INFO")
        return
    
    state["global_save_dir"] = save_dir
    log_message(f"Save path set to: {save_dir}", "INFO")

def export_animal_data():
    if not multi_animal_data:
        log_message("No animal data to export. Please import data first.", "WARNING")
        return
    
    save_dir = state.get("global_save_dir", '') if "state" in globals() else None
    if not save_dir:
        save_dir = tk.filedialog.askdirectory(title='Select directory to save results')
        if not save_dir:
            log_message("Export cancelled. No directory selected.", "INFO")
            return
    
    else:
        log_message(f"Using global save directory: {save_dir}", "INFO")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"multi_animal_data_{timestamp}.pickle"
    save_path = os.path.join(save_dir, filename)
    
    if not save_path:
        log_message("Export cancelled. No file selected.", "INFO")
        return
    
    try:
        with open(save_path, 'wb') as f:
            pickle.dump(multi_animal_data, f)
        log_message(f"Animal data successfully exported to {save_path}", "INFO")
    except Exception as e:
        log_message(f"Error exporting animal data: {str(e)}", "ERROR")

def save_log():
    if not log_text_widget:
        log_message("Log widget not initialized. Cannot save log.", "ERROR")
        return
    
    save_dir = state.get("global_save_dir", '') if "state" in globals() else None
    if not save_dir:
        save_dir = tk.filedialog.askdirectory(title='Select directory to save log')
        if not save_dir:
            log_message("Log save cancelled. No directory selected.", "INFO")
            return
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"analysis_log_{timestamp}.txt"
    save_path = os.path.join(save_dir, filename)
    
    try:
        with open(save_path, 'w', encoding='utf-8') as f:
            log_content = log_text_widget.get("1.0", tk.END).strip()
            f.write(log_content)
        log_message(f"Log successfully saved to {save_path}", "INFO")
    except Exception as e:
        log_message(f"Error saving log: {str(e)}", "ERROR")
    
def on_closing():
    log_message("Main window closed, exiting the program...", "INFO")
    export_animal_data()
    save_log()
    root.quit()
    root.destroy()
    os.kill(os.getpid(), signal.SIGTERM)
