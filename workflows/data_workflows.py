import fnmatch
import glob
import os
import traceback
import tkinter as tk
from tkinter import filedialog, ttk

import numpy as np

from infrastructure.logger import log_message
from core.io import h_AST2_raw2Speed, h_AST2_readData, load_fiber_data, load_fiber_events, read_dlc_file

EXPERIMENT_MODE_FIBER_AST2 = "fiber+ast2"
EXPERIMENT_MODE_FIBER_AST2_DLC = "fiber+ast2+dlc"

_deps = {}

def bind_workflow_dependencies(deps):
    _deps.clear()
    _deps.update(deps)
    globals().update(deps)

def import_multi_animals():
    """Modified to create separate entries for each channel"""
    global selected_files, multi_animal_data, current_experiment_mode

    base_dir = filedialog.askdirectory(title="Select directory upper data folder")
    if not base_dir:
        return

    try:
        before_count = len(multi_animal_data)
        log_message("Scanning for multi-animal data...")

        date_dirs = glob.glob(os.path.join(base_dir, "20*"))
        for date_dir in date_dirs:
            if not os.path.isdir(date_dir):
                continue

            date_name = os.path.basename(date_dir)
            num_dirs = glob.glob(os.path.join(date_dir, "*"))
            for num_dir in num_dirs:
                if not os.path.isdir(num_dir):
                    continue
                num_name = os.path.basename(num_dir)
                ear_bar_dirs = glob.glob(os.path.join(num_dir, "*"))[0]
                ear_tag = os.path.basename(ear_bar_dirs)
                base_animal_id = f"{num_name}-{ear_tag}"

                files_found = {}
                patterns = {
                    'dlc': ['*dlc*.csv'],
                    'fiber': ['fluorescence.csv'],
                    'fiber_events': ['Events.csv'],
                    'ast2': ['*.ast2']
                }

                # Determine required files based on mode
                if current_experiment_mode == EXPERIMENT_MODE_FIBER_AST2:
                    required_files = ['fiber', 'fiber_events', 'ast2']
                else:  # FIBER_AST2_DLC
                    required_files = ['dlc', 'fiber', 'fiber_events', 'ast2']

                for file_type, file_patterns in patterns.items():
                    # Skip DLC search if not needed
                    if file_type == 'dlc' and current_experiment_mode == EXPERIMENT_MODE_FIBER_AST2:
                        continue
                    
                    found_file = None
                    for root_path, dirs, files in os.walk(num_dir):
                        for file in files:
                            file_lower = file.lower()
                            for pattern in file_patterns:
                                if fnmatch.fnmatch(file_lower, pattern.lower()):
                                    found_file = os.path.join(root_path, file)
                                    files_found[file_type] = found_file
                                    break
                            if found_file:
                                break
                        if found_file:
                            break

                if not all(ft in files_found for ft in required_files):
                    continue

                # Process fiber data to get available channels
                fiber_result = load_fiber_data(files_found['fiber'])
                if not fiber_result or 'channel_data' not in fiber_result:
                    continue

                fiber_events = load_fiber_events(files_found['fiber_events'])

                available_channels = list(fiber_result['channel_data'].keys())

                # Process DLC file (only if in full mode)
                dlc_data = None
                if current_experiment_mode == EXPERIMENT_MODE_FIBER_AST2_DLC and 'dlc' in files_found:
                    try:
                        dlc_data = read_dlc_file(files_found['dlc'])
                    except Exception as e:
                        log_message(f"Failed to load DLC for {base_animal_id}: {str(e)}", "ERROR")

                # Process AST2 file
                ast2_data = None
                if 'ast2' in files_found:
                    try:
                        header, raw_data = h_AST2_readData(files_found['ast2'])
                        if running_channel < len(raw_data):
                            speed = h_AST2_raw2Speed(raw_data[running_channel], header, voltageRange=None, invert_running=invert_running, treadmill_diameter=treadmill_diameter)
                            ast2_data = {
                                'header': header,
                                'data': speed
                            }
                        else:
                            log_message(f"Running channel {running_channel} out of range for {base_animal_id}", "WARNING")
                    except Exception as e:
                        log_message(f"Failed to load AST2 for {base_animal_id}: {str(e)}", "ERROR")

                # Create separate animal_data for each channel
                for channel_num in available_channels:
                    animal_single_channel_id = f"{base_animal_id}-Ch{channel_num}"
                    
                    # Check for duplicates
                    if any(d['animal_single_channel_id'] == animal_single_channel_id for d in multi_animal_data):
                        log_message(f"Skip duplicate: {animal_single_channel_id}")
                        continue

                    # Create single-channel fiber data
                    single_channel_fiber_data = fiber_result['fiber_data'].copy()
                    
                    animal_data = {
                        'animal_id': base_animal_id,
                        'animal_single_channel_id': animal_single_channel_id,
                        'channel_num': channel_num,
                        'files': files_found.copy(),
                        'fiber_data': single_channel_fiber_data,
                        'fiber_events': fiber_events,
                        'channels': fiber_result['channels'].copy(),
                        'channel_data': {channel_num: fiber_result['channel_data'][channel_num]},
                        'active_channels': [channel_num],  # Only this channel
                        'processed': True,
                        'event_time_absolute': False,
                        'experiment_mode': current_experiment_mode
                    }

                    # Add DLC data (same for all channels of this animal)
                    if dlc_data:
                        animal_data['dlc_data'] = dlc_data

                    # Add AST2 data (same for all channels of this animal)
                    if ast2_data:
                        animal_data['ast2_data'] = ast2_data

                    multi_animal_data.append(animal_data)
                    selected_files.append(animal_data)

        added_count = len(multi_animal_data) - before_count if 'before_count' in locals() else len(selected_files)

        if added_count <= 0:
            log_message("No valid animal data found in the selected directory", "WARNING")
        else:
            mode_name = "Fiber+AST2" if current_experiment_mode == EXPERIMENT_MODE_FIBER_AST2 else "Fiber+AST2+DLC"
            log_message(f"Found {added_count} new channel entries in {mode_name} mode", "INFO")
            show_channel_selection_dialog()

    except Exception as e:
        log_message(f"Failed to import data: {str(e)}", "ERROR")

def import_single_animal():
    """Modified to create separate entries for each channel"""
    global selected_files, multi_animal_data, current_experiment_mode

    folder_path = filedialog.askdirectory(title="Select animal ear bar folder")
    if not folder_path:
        return

    try:
        before_count = len(multi_animal_data)
        folder_path = os.path.normpath(folder_path)
        parent_folder_path = os.path.dirname(folder_path)
        path_parts = folder_path.split(os.sep)
        if len(path_parts) < 4:
            log_message("Selected directory is not a valid animal data folder", "WARNING")
            return

        batch_name = path_parts[-3]
        num_name = path_parts[-2]
        ear_tag = path_parts[-1]
        base_animal_id = f"{num_name}-{ear_tag}"

        patterns = {
            'dlc': ['*dlc*.csv'],
            'fiber': ['fluorescence.csv'],
            'fiber_events': ['Events.csv'],
            'ast2': ['*.ast2']
        }

        # Determine required files based on mode
        if current_experiment_mode == EXPERIMENT_MODE_FIBER_AST2:
            required_files = ['fiber', 'fiber_events', 'ast2']
        else:  # FIBER_AST2_DLC
            required_files = ['dlc', 'fiber', 'fiber_events', 'ast2']

        files_found = {}
        for file_type, file_patterns in patterns.items():
            # Skip DLC search if not needed
            if file_type == 'dlc' and current_experiment_mode == EXPERIMENT_MODE_FIBER_AST2:
                continue
            
            found_file = None
            for root_path, dirs, files in os.walk(parent_folder_path):
                for file in files:
                    file_lower = file.lower()
                    for pattern in file_patterns:
                        if fnmatch.fnmatch(file_lower, pattern.lower()):
                            found_file = os.path.join(root_path, file)
                            files_found[file_type] = found_file
                            break
                    if found_file:
                        break
                if found_file:
                    break

        missing_files = [ft for ft in required_files if ft not in files_found]
        if missing_files:
            log_message(f"Required files missing: {', '.join(missing_files)}", "WARNING")
            return

        # Process fiber data to get available channels
        fiber_result = load_fiber_data(files_found['fiber'])
        if not fiber_result or 'channel_data' not in fiber_result:
            return

        available_channels = list(fiber_result['channel_data'].keys())

        fiber_events = load_fiber_events(files_found['fiber_events'])
        
        # Process DLC file (only if in full mode)
        dlc_data = None
        if current_experiment_mode == EXPERIMENT_MODE_FIBER_AST2_DLC and 'dlc' in files_found:
            try:
                dlc_data = read_dlc_file(files_found['dlc'])
            except Exception as e:
                log_message(f"Failed to load DLC for {base_animal_id}: {str(e)}", "ERROR")

        # Process AST2 file
        ast2_data = None
        if 'ast2' in files_found:
            try:
                header, raw_data = h_AST2_readData(files_found['ast2'])
                if running_channel < len(raw_data):
                    speed = h_AST2_raw2Speed(
                        raw_data[running_channel],
                        header,
                        voltageRange=None,
                        invert_running=invert_running,
                        treadmill_diameter=treadmill_diameter,
                    )
                    ast2_data = {
                        'header': header,
                        'data': speed
                    }
                else:
                    log_message(f"Running channel {running_channel} out of range", "WARNING")
            except Exception as e:
                log_message(f"Failed to load AST2 for {base_animal_id}: {str(e)}", "ERROR")

        # Create separate animal_data for each channel
        added_channels = []
        for channel_num in available_channels:
            animal_single_channel_id = f"{base_animal_id}-Ch{channel_num}"
            
            # Check for duplicates
            if any(d['animal_single_channel_id'] == animal_single_channel_id for d in multi_animal_data):
                log_message(f"Channel {channel_num} already exists for {base_animal_id}", "INFO")
                continue

            # Create single-channel fiber data
            single_channel_fiber_data = fiber_result['fiber_data'].copy()
            
            animal_data = {
                'animal_id': base_animal_id,
                'animal_single_channel_id': animal_single_channel_id,
                'channel_num': channel_num,
                'files': files_found.copy(),
                'fiber_data': single_channel_fiber_data,
                'fiber_events': fiber_events,
                'channels': fiber_result['channels'].copy(),
                'channel_data': {channel_num: fiber_result['channel_data'][channel_num]},
                'active_channels': [channel_num],  # Only this channel
                'processed': True,
                'event_time_absolute': False,
                'experiment_mode': current_experiment_mode
            }

            # Add DLC data (same for all channels of this animal)
            if dlc_data:
                animal_data['dlc_data'] = dlc_data

            # Add AST2 data (same for all channels of this animal)
            if ast2_data:
                animal_data['ast2_data'] = ast2_data

            multi_animal_data.append(animal_data)
            selected_files.append(animal_data)
            added_channels.append(channel_num)

        added_count = len(multi_animal_data) - before_count

        if added_count > 0:
            show_channel_selection_dialog()
            mode_name = "Fiber+AST2" if current_experiment_mode == EXPERIMENT_MODE_FIBER_AST2 else "Fiber+AST2+DLC"
            log_message(f"Added {base_animal_id} with {added_count} channels ({mode_name} mode)", "INFO")
        else:
            log_message(f"No new channels added for {base_animal_id}", "WARNING")

    except Exception as e:
        log_message(f"Failed to add single animal: {str(e)}", "ERROR")

def show_channel_selection_dialog():
    """Modified to show each channel as a separate row with its own settings"""
    dialog = tk.Toplevel(root)
    dialog.title("Configure Single-Channel Settings")
    dialog.geometry("600x340")
    dialog.transient(root)
    dialog.grab_set()
    
    main_frame = ttk.Frame(dialog, padding=10)
    main_frame.pack(fill="both", expand=True)
    
    # Create canvas with scrollbar
    canvas = tk.Canvas(main_frame)
    scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas) 
    
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    global channel_vars, running_channel_vars, invert_running_vars, diameter_vars, enable_channel_vars
    enable_channel_vars = {}
    running_channel_vars = {}
    invert_running_vars = {}
    diameter_vars = {}
    
    if not multi_animal_data:
        log_message("No animal data available for channel selection", "WARNING")
        dialog.destroy()
        return
    
    # Header row
    header_frame = ttk.Frame(scrollable_frame)
    header_frame.pack(fill="x", padx=5, pady=5)
    
    ttk.Label(header_frame, text="Enable", width=11, font=("Arial", 9, "bold")).grid(row=0, column=0, padx=2)
    ttk.Label(header_frame, text="Animal ID-Channel ID", width=25, font=("Arial", 9, "bold")).grid(row=0, column=1, padx=2)
    ttk.Label(header_frame, text="Running Ch", width=13, font=("Arial", 9, "bold")).grid(row=0, column=2, padx=2)
    ttk.Label(header_frame, text="Invert", width=10, font=("Arial", 9, "bold")).grid(row=0, column=3, padx=2)
    ttk.Label(header_frame, text="Diameter(cm)", width=12, font=("Arial", 9, "bold")).grid(row=0, column=4, padx=2)
    
    ttk.Separator(scrollable_frame, orient='horizontal').pack(fill='x', pady=5)
    
    # Create row for each channel
    for animal_data in multi_animal_data:
        animal_single_channel_id = animal_data['animal_single_channel_id']
        
        row_frame = ttk.Frame(scrollable_frame)
        row_frame.pack(fill="x", padx=5, pady=2)
        
        # Enable checkbox
        saved_enable = channel_memory.get(f"{animal_single_channel_id}_enable", True)
        enable_var = tk.BooleanVar(value=saved_enable)
        enable_channel_vars[animal_single_channel_id] = enable_var
        ttk.Checkbutton(row_frame, variable=enable_var, width=8).grid(row=0, column=0, padx=2)
        
        # Animal-Channel ID label
        ttk.Label(row_frame, text=animal_single_channel_id, width=25).grid(row=0, column=1, padx=2)
        
        # Running channel selection
        available_channels = []
        if 'ast2_data' in animal_data and animal_data['ast2_data']:
            header = animal_data['ast2_data']['header']
            if 'activeChIDs' in header:
                available_channels = header['activeChIDs']
            else:
                if 'files' in animal_data and 'ast2' in animal_data['files']:
                    try:
                        header, raw_data = h_AST2_readData(animal_data['files']['ast2'])
                        available_channels = list(range(len(raw_data)))
                    except:
                        available_channels = [0, 1, 2, 3]
        
        if not available_channels:
            available_channels = [0, 1, 2, 3]
        
        saved_running_channel = channel_memory.get(f"{animal_single_channel_id}_running_channel", running_channel)
        running_channel_var = tk.StringVar(value=str(saved_running_channel))
        running_channel_vars[animal_single_channel_id] = running_channel_var
        
        running_combo = ttk.Combobox(row_frame, textvariable=running_channel_var,
                                    values=available_channels, state="readonly", width=10)
        running_combo.grid(row=0, column=2, padx=2)
        
        # Invert checkbox
        saved_invert = channel_memory.get(f"{animal_single_channel_id}_invert_running", invert_running)
        invert_var = tk.BooleanVar(value=saved_invert)
        invert_running_vars[animal_single_channel_id] = invert_var
        ttk.Checkbutton(row_frame, variable=invert_var, width=8).grid(row=0, column=3, padx=2)
        
        # Diameter entry
        saved_diameter = channel_memory.get(f"{animal_single_channel_id}_diameter", treadmill_diameter)
        diameter_var = tk.StringVar(value=str(saved_diameter))
        diameter_vars[animal_single_channel_id] = diameter_var
        ttk.Entry(row_frame, textvariable=diameter_var, width=10).grid(row=0, column=4, padx=2)
    
    # Button frame
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(fill="x", pady=10)
    
    ttk.Button(btn_frame, text="Select All", 
              command=lambda: toggle_all_channel_enable(True)).grid(row=0, column=0, sticky="ew", padx=2, pady=2)
    ttk.Button(btn_frame, text="Deselect All", 
              command=lambda: toggle_all_channel_enable(False)).grid(row=0, column=1, sticky="ew", padx=2, pady=2)
    ttk.Button(btn_frame, text="Confirm", 
              command=lambda: finalize_channel_selection(dialog)).grid(row=0, column=2, sticky="ew", padx=2, pady=2)

def toggle_all_channel_enable(select):
    """Toggle all channel enable checkboxes"""
    for var in enable_channel_vars.values():
        var.set(select)

def finalize_channel_selection(dialog):
    """Modified to handle single-channel settings and filter disabled channels"""
    global channel_memory, multi_animal_data, selected_files
    
    if not multi_animal_data:
        log_message("No animal data available to finalize channel selection", "WARNING")
        dialog.destroy()
        return
    
    # Create list to store enabled animal data
    enabled_animal_data = []
    
    for animal_data in multi_animal_data:
        animal_single_channel_id = animal_data['animal_single_channel_id']
        
        # Check if this channel is enabled
        if animal_single_channel_id in enable_channel_vars:
            enable_value = enable_channel_vars[animal_single_channel_id].get()
            channel_memory[f"{animal_single_channel_id}_enable"] = enable_value
            
            if not enable_value:
                log_message(f"Skipping disabled channel: {animal_single_channel_id}", "INFO")
                continue
        
        # Running settings
        if animal_single_channel_id in running_channel_vars:
            try:
                selected_running_channel = int(running_channel_vars[animal_single_channel_id].get())
                animal_data['running_channel'] = selected_running_channel
                channel_memory[f"{animal_single_channel_id}_running_channel"] = selected_running_channel
            except ValueError:
                log_message(f"Invalid running channel for {animal_single_channel_id}", "WARNING")
                continue
        
        if animal_single_channel_id in invert_running_vars:
            invert_value = bool(invert_running_vars[animal_single_channel_id].get())
            animal_data['invert_running'] = invert_value
            channel_memory[f"{animal_single_channel_id}_invert_running"] = invert_value
        
        # Diameter setting
        if animal_single_channel_id in diameter_vars:
            try:
                diameter_value = float(diameter_vars[animal_single_channel_id].get())
                if diameter_value <= 0:
                    raise ValueError("Diameter must be positive")
                animal_data['treadmill_diameter'] = diameter_value
                channel_memory[f"{animal_single_channel_id}_diameter"] = diameter_value
            except ValueError as e:
                log_message(f"Invalid diameter for {animal_single_channel_id}: {e}", "WARNING")
                continue
        
        # Reload AST2 data with channel-specific settings
        if 'files' in animal_data and 'ast2' in animal_data['files']:
            try:
                header, raw_data = h_AST2_readData(animal_data['files']['ast2'])
                selected_channel = animal_data.get('running_channel', running_channel)
                
                if selected_channel < len(raw_data):
                    # Temporarily set global invert_running for this animal
                    old_invert = globals().get('invert_running', False)
                    old_diameter = globals().get('treadmill_diameter', 22)
                    
                    globals()['invert_running'] = animal_data.get('invert_running', False)
                    globals()['treadmill_diameter'] = animal_data.get('treadmill_diameter', 22)
                    
                    speed = h_AST2_raw2Speed(
                        raw_data[selected_channel],
                        header,
                        voltageRange=None,
                        invert_running=animal_data.get('invert_running', False),
                        treadmill_diameter=animal_data.get('treadmill_diameter', 22),
                    )
                    ast2_data = {
                        'header': header,
                        'data': speed
                    }
                    animal_data['ast2_data'] = ast2_data
                    
                    # Restore global settings
                    globals()['invert_running'] = old_invert
                    globals()['treadmill_diameter'] = old_diameter
                else:
                    log_message(f"Running channel {selected_channel} out of range for {animal_single_channel_id}", "ERROR")
                    continue
            except Exception as e:
                log_message(f"Failed to reload AST2 for {animal_single_channel_id}: {str(e)}", "ERROR")
                continue
        
        # Align data
        if 'fiber_data' in animal_data and animal_data['fiber_data'] is not None:
            alignment_success = align_data(animal_data)
            if not alignment_success:
                log_message(f"Failed to align data for {animal_single_channel_id}", "WARNING")
                if 'fiber_data' in animal_data:
                    animal_data['fiber_data_trimmed'] = animal_data['fiber_data']
        
        enabled_animal_data.append(animal_data)
    
    # Update global data structures with only enabled channels
    multi_animal_data[:] = enabled_animal_data
    selected_files[:] = enabled_animal_data
    
    save_channel_memory()
    _deps['channel_memory'] = channel_memory
    
    dialog.destroy()
    
    # Update file listbox
    update_file_listbox()
    
    log_message(f"Configuration complete: {len(enabled_animal_data)} channels enabled", "INFO")
    
    if multi_animal_data:
        global current_animal_index
        current_animal_index = 0
        main_visualization(multi_animal_data[current_animal_index])
        
        create_fiber_visualization(multi_animal_data[current_animal_index])
        if fiber_plot_window:
            fiber_plot_window.set_plot_type("raw")
            fiber_plot_window.update_plot()

def align_data(animal_data=None):
    """Modified align_data to support different experiment modes"""
    global current_experiment_mode
    
    try:
        # Determine which data to use
        if animal_data:
            fiber_data = animal_data.get('fiber_data')
            ast2_data = animal_data.get('ast2_data')
            channels = animal_data.get('channels', {})
            active_channels = animal_data.get('active_channels', [])
            experiment_mode = animal_data.get('experiment_mode', current_experiment_mode)
            dlc_data = animal_data.get('dlc_data') if experiment_mode == EXPERIMENT_MODE_FIBER_AST2_DLC else None
        else:
            fiber_data = globals().get('fiber_data')
            ast2_data = globals().get('ast2_data')
            channels = globals().get('channels', {})
            active_channels = globals().get('active_channels', [])
            experiment_mode = current_experiment_mode
            dlc_data = globals().get('dlc_data') if experiment_mode == EXPERIMENT_MODE_FIBER_AST2_DLC else None
        
        log_message(f"Alignment debug - Experiment mode: {experiment_mode}")
        log_message(f"Alignment debug - Fiber data: {fiber_data is not None}")
        log_message(f"Alignment debug - Channels: {channels}")
        log_message(f"Alignment debug - Active channels: {active_channels}")
        log_message(f"Alignment debug - DLC data: {dlc_data is not None}")
        log_message(f"Alignment debug - AST2 data: {ast2_data is not None}")

        # Check if we have the necessary data
        if fiber_data is None:
            log_message("Fiber data is None, cannot align", "ERROR")
            return False
            
        if not active_channels:
            log_message("No active channels selected, cannot align", "ERROR")
            return False
            
        if ast2_data is None:
            log_message("No running data available, cannot align", "ERROR")
            return False
        
        # DLC data is optional based on experiment mode
        if experiment_mode == EXPERIMENT_MODE_FIBER_AST2_DLC and dlc_data is None:
            log_message("DLC mode selected but no DLC data available, cannot align", "ERROR")
            return False
        
        # Get events column from fiber data
        events_col = channels.get('events')
        if events_col is None or events_col not in fiber_data.columns:
            log_message("Events column not found in fiber data", "ERROR")
            return False
        
        time_col = channels['time']
        
        opto_event_name = event_config.get('opto_event', 'Input3')
        running_start_name = event_config.get('running_start', 'Input2')
        drug_event_names = event_config.get('drug_event', 'Event1')
        # Support multiple drug events separated by comma
        if isinstance(drug_event_names, str):
            drug_event_names = [name.strip() for name in drug_event_names.split(',')]
        elif not isinstance(drug_event_names, list):
            drug_event_names = [str(drug_event_names)]

        # Find Input2 events (running markers) - running start time
        input2_events = fiber_data[fiber_data[events_col].str.startswith(running_start_name, na=False)]
        if len(input2_events) < 1:
            log_message("Could not find Input2 events for running start", "ERROR")
            return False
        
        global input3_events, drug_events

        input3_events = fiber_data[fiber_data[events_col].str.startswith(opto_event_name, na=False)]
        if len(input3_events) < 1:
            multimodal_menu.entryconfig("Optogenetics-Induced Activity Analysis", state="disabled")
            log_message("Could not find Input3 events for optogenetic analysis", "INFO")
            running_induced_menu.entryconfig("Running + Optogenetics", state="disabled")
            setting_menu.entryconfig("Optogenetic Configuration", state="disabled")
        else:
            multimodal_menu.entryconfig("Optogenetics-Induced Activity Analysis", state="normal")
            running_induced_menu.entryconfig("Running + Optogenetics", state="normal")
            setting_menu.entryconfig("Optogenetic Configuration", state="normal")
        
        drug_events = fiber_data[fiber_data[events_col].str.contains('|'.join(drug_event_names), na=False)]
        if len(drug_events) < 1:
            multimodal_menu.entryconfig("Drug-Induced Activity Analysis", state="disabled")
            running_induced_menu.entryconfig("Running + Drug", state="disabled")
            setting_menu.entryconfig("Drug Configuration", state="disabled")
            log_message("Could not find Event2 events for drug analysis", "INFO")
        else:
            multimodal_menu.entryconfig("Drug-Induced Activity Analysis", state="normal")
            running_induced_menu.entryconfig("Running + Drug", state="normal")
            setting_menu.entryconfig("Drug Configuration", state="normal")

        if len(input3_events) < 1 or len(drug_events) < 1:
            optogenetics_induced_menu.entryconfig("Optogenetics + Drug", state="disabled")
            running_induced_menu.entryconfig("Running + Optogenetics + Drug", state="disabled")
        elif len(input3_events) >= 1 and len(drug_events) >= 1:
            optogenetics_induced_menu.entryconfig("Optogenetics + Drug", state="normal")
            running_induced_menu.entryconfig("Running + Optogenetics + Drug", state="normal") 

        if animal_data is not None:
            animal_data['input3_events'] = input3_events
            animal_data['drug_events'] = drug_events

        # Get running start time (first Input2 event)
        running_start_time = input2_events[time_col].iloc[0]
        
        # Get fiber start time (first timestamp in fiber data)
        fiber_start_time = fiber_data[time_col].iloc[0]
        
        # Calculate running end time based on AST2 data
        running_timestamps = ast2_data['data']['timestamps']
        running_duration = running_timestamps[-1] - running_timestamps[0] if len(running_timestamps) > 1 else 0
        running_end_time = running_start_time + running_duration
        
        log_message(f"Running start time: {running_start_time:.2f}s")
        log_message(f"Running end time: {running_end_time:.2f}s")
        log_message(f"Running duration: {running_duration:.2f}s")
        log_message(f"Fiber start time: {fiber_start_time:.2f}s")
        
        # Adjust fiber data relative to running start time
        fiber_data_adjusted = fiber_data.copy()
        fiber_data_adjusted[time_col] = fiber_data_adjusted[time_col] - running_start_time
        
        # Trim fiber data to running duration
        fiber_data_trimmed = fiber_data_adjusted[
            (fiber_data_adjusted[time_col] >= 0) & 
            (fiber_data_adjusted[time_col] <= running_duration)].copy()
        
        if fiber_data_trimmed.empty:
            log_message("Trimmed fiber data is empty after alignment", "ERROR")
            return False
        
        # Initialize video-related variables
        video_start_time = None
        video_end_time = None
        video_total_frames = 0
        video_total_frames_trimmed = 0
        video_fps = 30  # Default
        video_start_offset = 0
        dlc_data_trimmed = None
        valid_video_frames = []
        
        # Process DLC data only in FIBER_AST2_DLC mode
        if experiment_mode == EXPERIMENT_MODE_FIBER_AST2_DLC and dlc_data is not None:
            # Find Input4 events (video markers) - video start time
            input4_events = fiber_data[fiber_data[events_col].str.contains('Input4', na=False)]
            if len(input4_events) < 1:
                log_message("Could not find Input4 events for video start", "WARNING")
                log_message("Continuing without video alignment", "INFO")
            else:
                video_start_time = input4_events[time_col].iloc[0]
                
                # Calculate video parameters
                unique_bodyparts = list(dlc_data.keys())
                if unique_bodyparts:
                    video_total_frames = len(dlc_data[unique_bodyparts[0]]['x'])
                    video_duration = video_total_frames / video_fps
                    video_end_time = video_start_time + video_duration
                    
                    log_message(f"Video start time: {video_start_time:.2f}s")
                    log_message(f"Video total frames: {video_total_frames}")
                    log_message(f"Video duration: {video_duration:.2f}s")
                    log_message(f"Video end time: {video_end_time:.2f}s")
                    
                    # Trim video data to running duration
                    video_start_offset = video_start_time - running_start_time
                    video_end_offset = video_end_time - running_start_time
                    
                    # Only include video frames that are within the running period
                    valid_video_frames = []
                    for frame_idx in range(video_total_frames):
                        frame_time = video_start_offset + (frame_idx / video_fps)
                        if 0 <= frame_time <= running_duration:
                            valid_video_frames.append(frame_idx)
                    
                    # Create trimmed DLC data with only valid frames
                    dlc_data_trimmed = {}
                    for bodypart, data in dlc_data.items():
                        dlc_data_trimmed[bodypart] = {
                            'x': data['x'][valid_video_frames],
                            'y': data['y'][valid_video_frames],
                            'likelihood': data['likelihood'][valid_video_frames]
                        }
                    
                    video_total_frames_trimmed = len(valid_video_frames)
                    
                    log_message(f"Trimmed video frames: {video_total_frames_trimmed}/{video_total_frames}")
                    log_message(f"Video start offset: {video_start_offset:.2f}s")
                    log_message(f"Video end offset: {video_end_offset:.2f}s")
        
        # Adjust AST2 data relative to running start
        if ast2_data is not None:
            ast2_timestamps = ast2_data['data']['timestamps']
            ast2_timestamps_adjusted = ast2_timestamps - ast2_timestamps[0]  # AST2 timestamps are relative to running start
            
            # Trim AST2 data (should already be within running duration)
            valid_indices = (ast2_timestamps_adjusted >= 0) & (ast2_timestamps_adjusted <= running_duration)
            ast2_timestamps_trimmed = ast2_timestamps_adjusted[valid_indices]
            ast2_speed_trimmed = ast2_data['data']['speed'][valid_indices]
            
            # Create adjusted AST2 data
            ast2_data_adjusted = {
                'header': ast2_data['header'],
                'data': {
                    'timestamps': ast2_timestamps_trimmed,
                    'speed': ast2_speed_trimmed
                }
            }
            
            # Calculate sampling rate
            if len(ast2_timestamps_trimmed) > 1:
                ast2_sampling_rate = 1 / np.mean(np.diff(ast2_timestamps_trimmed))
            else:
                ast2_sampling_rate = 10  # Default assumption
        else:
            ast2_data_adjusted = None
            ast2_sampling_rate = None
        
        # Update the appropriate data structure
        if animal_data:
            animal_data.update({
                'fiber_data_adjusted': fiber_data_adjusted,
                'fiber_data_trimmed': fiber_data_trimmed,
                'ast2_data_adjusted': ast2_data_adjusted,
                'running_start_time': running_start_time,
                'running_end_time': running_end_time,
                'running_duration': running_duration,
                'fiber_sampling_rate': 10,  # Assuming fiber sampling rate is 10 Hz
                'ast2_sampling_rate': ast2_sampling_rate
            })
            
            # Add DLC-related data only in FIBER_AST2_DLC mode
            if experiment_mode == EXPERIMENT_MODE_FIBER_AST2_DLC and dlc_data_trimmed is not None:
                animal_data.update({
                    'dlc_data_trimmed': dlc_data_trimmed,
                    'video_start_time': video_start_time,
                    'video_end_time': video_end_time,
                    'video_total_frames': video_total_frames_trimmed,
                    'video_fps': video_fps,
                    'video_start_offset': video_start_offset,
                    'valid_video_frames': valid_video_frames
                })
                # Replace original dlc_data with trimmed version for visualization
                animal_data['dlc_data'] = dlc_data_trimmed
        else:
            globals()['fiber_data_adjusted'] = fiber_data_adjusted
            globals()['fiber_data_trimmed'] = fiber_data_trimmed
            globals()['ast2_data_adjusted'] = ast2_data_adjusted
            globals()['running_start_time'] = running_start_time
            globals()['running_end_time'] = running_end_time
            globals()['running_duration'] = running_duration
            
            # Add DLC-related data only in FIBER_AST2_DLC mode
            if experiment_mode == EXPERIMENT_MODE_FIBER_AST2_DLC and dlc_data_trimmed is not None:
                globals()['dlc_data'] = dlc_data_trimmed
                globals()['parsed_data'] = dlc_data_trimmed
                globals()['video_start_time'] = video_start_time
                globals()['video_end_time'] = video_end_time
                globals()['video_total_frames'] = video_total_frames_trimmed
                globals()['video_fps'] = video_fps
                globals()['video_start_offset'] = video_start_offset
        
        # Display alignment information
        info_message = f"Data aligned successfully (running data as reference)!\n"
        info_message += f"Experiment Mode: {experiment_mode}\n"
        info_message += f"Running start time: {running_start_time:.2f}s\n"
        info_message += f"Running end time: {running_end_time:.2f}s\n"
        info_message += f"Running duration: {running_duration:.2f}s\n"
        
        if experiment_mode == EXPERIMENT_MODE_FIBER_AST2_DLC and video_start_time is not None:
            info_message += f"Video start time: {video_start_time:.2f}s\n"
            info_message += f"Video offset: {video_start_offset:.2f}s\n"
            info_message += f"Video frames (original/trimmed): {video_total_frames}/{video_total_frames_trimmed}\n"
            info_message += f"Video FPS: {video_fps}\n"
        
        info_message += f"Fiber sampling rate: 10 Hz\n"
        
        if ast2_sampling_rate is not None:
            info_message += f"Running wheel sampling rate: {ast2_sampling_rate:.2f} Hz"
        
        log_message(info_message, "INFO")
        log_message("Data aligned successfully using running data as reference")
        return True
        
    except Exception as e:
        log_message(f"Failed to align data: {str(e)}", "ERROR")
        log_message(f"Traceback: {traceback.format_exc()}", "ERROR")
        return False
