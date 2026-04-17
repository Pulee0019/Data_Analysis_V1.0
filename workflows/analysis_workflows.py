import tkinter as tk
from itertools import combinations
from tkinter import ttk

import matplotlib.cm as cm
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from analysis_core.Fiber_analysis import apply_preprocessing, calculate_dff, calculate_zscore
from analysis_core.Running_analysis import running_bout_analysis_classify, preprocess_running_data
from infrastructure.logger import log_message

_deps = {}

def bind_analysis_dependencies(deps):
    _deps.clear()
    _deps.update(deps)
    globals().update(deps)

def fiber_preprocessing():
    global preprocess_frame, multi_animal_data
    
    available_wavelengths = []
    all_detected_wavelengths = []
    
    if multi_animal_data:
        for animal_data in multi_animal_data:
            if 'channel_data' in animal_data:
                wavelength_combos = detect_wavelengths_and_generate_combinations(animal_data['channel_data'])
                available_wavelengths.extend(wavelength_combos)
                for ch_data in animal_data['channel_data'].values():
                    for wl, col in ch_data.items():
                        if col is not None:
                            all_detected_wavelengths.append(wl)
                break
    
    available_wavelengths = sorted(list(set(available_wavelengths)))
    all_detected_wavelengths = sorted(list(set(all_detected_wavelengths)))
    
    if not available_wavelengths:
        available_wavelengths = ["470", "560"]
    if not all_detected_wavelengths:
        all_detected_wavelengths = ["410", "470"]
    
    prep_window = tk.Toplevel(root)
    prep_window.title("Fiber Data Preprocessing")
    prep_window.geometry("320x550")
    prep_window.transient(root)
    prep_window.grab_set()
    
    status_label = tk.Label(prep_window, text="Fiber Data Preprocessing", font=("Arial", 12, "bold"))
    status_label.pack(pady=10)
    
    main_frame = ttk.Frame(prep_window)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    signal_frame = ttk.LabelFrame(main_frame, text="Signal Selection")
    signal_frame.pack(fill=tk.X, padx=5, pady=5)
    
    ttk.Label(signal_frame, text="Target Signal:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    target_menu = ttk.OptionMenu(signal_frame, target_signal_var, available_wavelengths[0], *available_wavelengths)
    target_menu.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
    
    ttk.Label(signal_frame, text="Reference Signal:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
    
    ref_menu_container = ttk.Frame(signal_frame)
    ref_menu_container.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
    ref_menu_holder = [None]
    
    def get_ref_options():
        current_target = target_signal_var.get()
        target_wls = set(current_target.split('+')) if '+' in current_target else {current_target}
        ref_wls = [wl for wl in all_detected_wavelengths if wl not in target_wls]
        ref_wls.append("baseline")
        return ref_wls
    
    def refresh_ref_menu(*args):
        try:
            if not prep_window.winfo_exists() or not ref_menu_container.winfo_exists():
                return
        except Exception:
            return
        
        if ref_menu_holder[0] is not None:
            try:
                ref_menu_holder[0].destroy()
            except Exception:
                pass
            ref_menu_holder[0] = None
        
        ref_options = get_ref_options()
        if reference_signal_var.get() not in ref_options:
            reference_signal_var.set(ref_options[0])
        
        new_menu = ttk.OptionMenu(ref_menu_container, reference_signal_var, reference_signal_var.get(), *ref_options)
        new_menu.pack(fill=tk.X, expand=True)
        ref_menu_holder[0] = new_menu
    
    refresh_ref_menu()
    
    trace_id = target_signal_var.trace_add("write", refresh_ref_menu)
    
    def on_prep_window_close():
        try:
            target_signal_var.trace_remove("write", trace_id)
        except Exception:
            pass
        prep_window.destroy()
    
    prep_window.protocol("WM_DELETE_WINDOW", on_prep_window_close)
    
    global baseline_frame
    baseline_frame = ttk.LabelFrame(main_frame, text="Baseline Period")
    baseline_frame.pack(fill=tk.X, padx=5, pady=5)
    
    ttk.Label(baseline_frame, text="Start (s):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    ttk.Entry(baseline_frame, textvariable=baseline_start, width=5).grid(row=0, column=1, padx=5, pady=5)
    ttk.Label(baseline_frame, text="End (s):").grid(row=0, column=2, sticky="w", padx=5, pady=5)
    ttk.Entry(baseline_frame, textvariable=baseline_end, width=5).grid(row=0, column=3, padx=5, pady=5)
    
    if reference_signal_var.get() != "baseline":
        baseline_frame.pack_forget()

    reference_signal_var.trace_add("write", update_baseline_ui)

    global smooth_frame
    smooth_frame = ttk.LabelFrame(main_frame, text="Smoothing")
    smooth_frame.pack(fill=tk.X, padx=5, pady=5)
    
    ttk.Checkbutton(smooth_frame, text="Apply Smoothing", variable=apply_smooth,
                    command=lambda: toggle_widgets(smooth_frame, apply_smooth.get(), 1)).grid(row=0, column=0, sticky="w")
    ttk.Label(smooth_frame, text="Window Size:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
    ttk.Scale(smooth_frame, from_=3, to=101, orient=tk.HORIZONTAL,
             variable=smooth_window, length=100).grid(row=1, column=1, padx=5, pady=5)
    ttk.Label(smooth_frame, textvariable=smooth_window).grid(row=1, column=2, padx=5, pady=5)
    ttk.Label(smooth_frame, text="Polynomial Order:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
    ttk.Scale(smooth_frame, from_=1, to=5, orient=tk.HORIZONTAL,
             variable=smooth_order, length=100).grid(row=2, column=1, padx=5, pady=5)
    ttk.Label(smooth_frame, textvariable=smooth_order).grid(row=2, column=2, padx=5, pady=5)
    
    global baseline_corr_frame
    baseline_corr_frame = ttk.LabelFrame(main_frame, text="Baseline Correction")
    baseline_corr_frame.pack(fill=tk.X, padx=5, pady=5)
    
    ttk.Checkbutton(baseline_corr_frame, text="Apply Baseline Correction", variable=apply_baseline,
                    command=lambda: toggle_widgets(baseline_corr_frame, apply_baseline.get(), 1)).grid(row=0, column=0, sticky="w")
    ttk.Label(baseline_corr_frame, text="Baseline Model:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
    model_options = ["Polynomial", "Exponential"]
    model_menu = ttk.OptionMenu(baseline_corr_frame, baseline_model, "Polynomial", *model_options)
    model_menu.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
    
    global motion_frame
    motion_frame = ttk.LabelFrame(main_frame, text="Motion Correction")
    motion_frame.pack(fill=tk.X, padx=5, pady=5)
    
    ttk.Checkbutton(motion_frame, text="Apply Motion Correction", variable=apply_motion,
        command=lambda: toggle_motion_correction()).grid(row=0, column=0, sticky="w")
    
    global button_frame
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X, padx=5, pady=10)
    
    ttk.Button(button_frame, text="Apply Preprocessing",
              command=lambda: apply_preprocessing_wrapper()).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Close",
              command=on_prep_window_close).pack(side=tk.RIGHT, padx=5)

def toggle_motion_correction():
    """Motion correction is only available with a wavelength-based reference (not 'baseline')"""
    if reference_signal_var.get() == "baseline":
        apply_motion.set(False)
        log_message("Motion correction is not available when reference signal is 'baseline'", "WARNING")

def detect_wavelengths_and_generate_combinations(channel_data):
    """Detect available wavelengths and generate all possible combinations"""
    # Get all available wavelengths (excluding 410)
    all_wavelengths = set()
    for channel_num, wavelengths in channel_data.items():
        for wl in wavelengths.keys():
            if wl not in ['410', '415'] and channel_data[channel_num][wl] is not None:  # Exclude reference wavelengths
                all_wavelengths.add(wl)
    
    all_wavelengths = sorted(list(all_wavelengths))
    
    if not all_wavelengths:
        return []
    
    # Generate all combinations
    combinations_list = []
    # Single wavelengths
    for wl in all_wavelengths:
        combinations_list.append(wl)
    
    # Multiple wavelength combinations
    for r in range(2, len(all_wavelengths) + 1):
        for combo in combinations(all_wavelengths, r):
            combinations_list.append('+'.join(combo))
    
    return combinations_list

def get_target_signal_data(animal_data, target_signal):
    """Get data for target signal (single or combined wavelengths)"""
    if '+' not in target_signal:
        # Single wavelength
        return {'type': 'single', 'wavelengths': [target_signal]}
    else:
        # Combined wavelengths
        wavelengths = target_signal.split('+')
        return {'type': 'combined', 'wavelengths': wavelengths}

def update_baseline_ui(*args):
    global baseline_frame, smooth_frame, baseline_corr_frame, motion_frame, button_frame

    try:
        if reference_signal_var.get() == "baseline":
            if baseline_frame.winfo_exists():
                baseline_frame.pack(fill="x", padx=5, pady=5)
            if smooth_frame.winfo_exists():
                smooth_frame.pack_forget()
                smooth_frame.pack(fill=tk.X, padx=5, pady=5)
            if baseline_corr_frame.winfo_exists():
                baseline_corr_frame.pack_forget()
                baseline_corr_frame.pack(fill=tk.X, padx=5, pady=5)
            if motion_frame.winfo_exists():
                motion_frame.pack_forget()
                motion_frame.pack(fill=tk.X, padx=5, pady=5)
            if button_frame.winfo_exists():
                button_frame.pack_forget()
                button_frame.pack(fill=tk.X, padx=5, pady=10)
        else:
            if baseline_frame.winfo_exists():
                baseline_frame.pack_forget()
            if smooth_frame.winfo_exists():
                smooth_frame.pack_forget()
                smooth_frame.pack(fill=tk.X, padx=5, pady=5)
            if baseline_corr_frame.winfo_exists():
                baseline_corr_frame.pack_forget()
                baseline_corr_frame.pack(fill=tk.X, padx=5, pady=5)
            if motion_frame.winfo_exists():
                motion_frame.pack_forget()
                motion_frame.pack(fill=tk.X, padx=5, pady=5)
            if button_frame.winfo_exists():
                button_frame.pack_forget()
                button_frame.pack(fill=tk.X, padx=5, pady=10)
    except tk.TclError:
        pass

def toggle_widgets(parent_frame, show, index):
        children = parent_frame.winfo_children()
        if len(children) > index:
            if show:
                children[index].grid()
            else:
                children[index].grid_remove()

def running_data_analysis():
    """Running data analysis dialog"""
    global multi_animal_data, current_animal_index, treadmill_diameter
    
    if not multi_animal_data:
        log_message("No animal data available for analysis", "WARNING")
        return
    
    animals_with_ast2 = [a for a in multi_animal_data if 'ast2_data_adjusted' in a or 'ast2_data' in a]
    if not animals_with_ast2:
        log_message("No animals with running data available", "WARNING")
        return
    
    preview_animal = None
    if current_animal_index < len(multi_animal_data):
        preview_animal = multi_animal_data[current_animal_index]
        if 'ast2_data_adjusted' not in preview_animal and 'ast2_data' not in preview_animal:
            preview_animal = animals_with_ast2[0]
    else:
        preview_animal = animals_with_ast2[0]
    
    ast2_data = preview_animal.get('ast2_data_adjusted') or preview_animal.get('ast2_data')
    
    if ast2_data is None:
        log_message("No running data available for preview", "WARNING")
        return
    
    analysis_window = tk.Toplevel(root)
    analysis_window.title("Running Data Analysis Settings - Batch Mode")
    analysis_window.geometry("1000x800")
    analysis_window.transient(root)
    analysis_window.grab_set()

    main_frame = ttk.Frame(analysis_window, padding=15)
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    title_label = ttk.Label(main_frame, text="Running Data Analysis (All Animals)", 
                           font=("Arial", 14, "bold"))
    title_label.pack(pady=(0, 15))
    
    info_text = f"Will apply to {len(animals_with_ast2)} animals with running data. Preview using: {preview_animal.get('animal_single_channel_id', 'Animal')}"
    info_label = ttk.Label(main_frame, text=info_text, 
                          font=("Arial", 9), foreground="gray")
    info_label.pack(pady=(0, 10))

    config_split = ttk.Frame(main_frame)
    config_split.pack(fill=tk.X, pady=(0, 10))

    top_row = ttk.Frame(config_split)
    top_row.pack(side=tk.TOP, fill=tk.X, anchor='nw')
    top_row.columnconfigure(0, weight=1)
    top_row.columnconfigure(1, weight=1)  

    filter_disp_frame = ttk.LabelFrame(top_row, text="Filter Configuration and Bouts Display", padding=10)
    filter_disp_frame.grid(row=0, column=0, sticky='ew', padx=(0, 5), pady=(0, 10))
    
    smooth_methods = [
        {"name": "No Smoothing", "type": "none", "params": []},
        {"name": "Moving Average", "type": "moving_average", 
         "params": [
             {"name": "window_size", "type": "int", "default": 10, "min": 3, "max": 51, "step": 2}
         ]},
        {"name": "Median Filter", "type": "median",
         "params": [
             {"name": "window_size", "type": "int", "default": 10, "min": 3, "max": 51, "step": 2}
         ]},
        {"name": "Savitzky-Golay", "type": "savitzky_golay",
         "params": [
             {"name": "window_size", "type": "int", "default": 10, "min": 5, "max": 51, "step": 2},
             {"name": "poly_order", "type": "int", "default": 3, "min": 1, "max": 5}
         ]},
        {"name": "Butterworth Low-pass", "type": "butterworth",
         "params": [
             {"name": "sampling_rate", "type": "float", "default": 10.0, "min": 1.0, "max": 100.0},
             {"name": "cutoff_freq", "type": "float", "default": 2.0, "min": 0.1, "max": 10.0},
             {"name": "filter_order", "type": "int", "default": 2, "min": 1, "max": 5}
         ]}
    ]
    
    method_frame = ttk.Frame(filter_disp_frame)
    method_frame.pack(fill=tk.X, pady=(0, 10))
    
    ttk.Label(method_frame, text="Smoothing Method:").pack(side=tk.LEFT)
    
    method_names = [method["name"] for method in smooth_methods]
    method_var = tk.StringVar(value=method_names[0])
    method_combo = ttk.Combobox(method_frame, textvariable=method_var, 
                               values=method_names, state="readonly", width=20)
    method_combo.pack(side=tk.RIGHT, padx=(10, 0))
    
    params_frame = ttk.Frame(filter_disp_frame)
    params_frame.pack(fill=tk.X, pady=5)
    
    param_vars = {}
    
    def update_parameters(*args):
        for widget in params_frame.winfo_children():
            widget.destroy()
        
        param_vars.clear()
        
        selected_method_name = method_var.get()
        selected_method = None
        for method in smooth_methods:
            if method["name"] == selected_method_name:
                selected_method = method
                break
        
        if not selected_method or not selected_method["params"]:
            ttk.Label(params_frame, text="No parameters needed for this method", 
                     foreground="gray").pack(pady=10)
            return
        
        ttk.Label(params_frame, text="Parameters:", font=("Arial", 9, "bold")).pack(anchor="w", pady=(0, 5))
        
        for param in selected_method["params"]:
            param_frame = ttk.Frame(params_frame)
            param_frame.pack(fill=tk.X, pady=2)
            
            ttk.Label(param_frame, text=f"{param['name'].replace('_', ' ').title()}:").pack(side=tk.LEFT)
            
            if param['type'] == 'int':
                var = tk.IntVar(value=param['default'])
                widget = ttk.Spinbox(param_frame, from_=param['min'], to=param['max'], 
                                   textvariable=var, width=8)
            else:  # float
                var = tk.DoubleVar(value=param['default'])
                widget = ttk.Spinbox(param_frame, from_=param['min'], to=param['max'], 
                                   increment=0.1, textvariable=var, width=8)
            
            widget.pack(side=tk.RIGHT, padx=(10, 0))
            param_vars[param['name']] = var
    
    method_var.trace('w', update_parameters)
    update_parameters()

    bouts_param = ['general_bouts', 'locomotion_bouts', 'reset_bouts', 'jerk_bouts',
                   'other_bouts', 'rest_bouts']
    bout_directions = ['general', 'forward', 'backward', 'balanced']
    # Display Bouts 
    bout_row = ttk.Frame(filter_disp_frame)
    bout_row.pack(fill=tk.X, pady=(0, 5))
    ttk.Label(bout_row, text="Display Bouts:").pack(side=tk.LEFT)
    ttk.Combobox(bout_row, textvariable=disp_var, values=bouts_param, 
                state="readonly", width=20).pack(side=tk.RIGHT)

    # Direction 
    dir_row = ttk.Frame(filter_disp_frame)
    dir_row.pack(fill=tk.X, pady=(0, 10))
    ttk.Label(dir_row, text="Direction:").pack(side=tk.LEFT)
    ttk.Combobox(dir_row, textvariable=direction_var, values=bout_directions,
                state="readonly", width=20).pack(side=tk.RIGHT)
    
    # Running only checkbox
    flag_row = ttk.Frame(filter_disp_frame)
    flag_row.pack(fill=tk.X, pady=(0, 10))
    only_running_var = tk.IntVar(value=0)
    ttk.Checkbutton(flag_row, text="Only Running Analysis", variable=only_running_var).pack(side=tk.LEFT)

    disp_var.set(bouts_param[1])
    direction_var.set(bout_directions[1])
    
    

    bout_param_frame = ttk.LabelFrame(top_row,
                                    text="Bout Detection Parameters",
                                    padding=10)
    bout_param_frame.grid(row=0, column=1, sticky='ew', padx=(5, 0), pady=(0, 10))

    bout_param_defs = [
        ("General threshold (cm/s)",   "threshold",                "float", 0.5,  0.1, (0.1, 10)),
        ("General min duration (s)",   "gen_min_dur",              "float", 0.5,  0.1, (0.1, 20)),
        ("Min rest duration (s)",      "rest_dur",                 "float", 4.0,  0.5, (0.5, 30)),
        ("Pre-locomotion buffer (s)",  "pre_buffer",               "float", 5.0,  0.5, (0, 20)),
        ("Post-locomotion buffer (s)", "post_buffer",              "float", 5.0,  0.5, (0, 20)),
        ("Locomotion duration (s)",    "locomotion_duration",      "float", 2.0,  0.5, (0, 10)),
        ("Move direction threshold",   "move_direction_threshold", "float", 0.5,  0.1, (0.1, 1.0))
    ]
    bout_vars = {}
    for row, (lab, key, typ, default, incr, (vmin, vmax)) in enumerate(bout_param_defs):
        ttk.Label(bout_param_frame, text=lab, width=28).grid(row=row, column=0, sticky="w", pady=2)
        var = tk.DoubleVar(value=default) if typ == "float" else tk.IntVar(value=int(default))
        bout_vars[key] = var
        sp = ttk.Spinbox(bout_param_frame, from_=vmin, to=vmax, increment=incr,
                         textvariable=var, width=8)
        sp.grid(row=row, column=1, padx=5, pady=2)
    
    preview_frame = ttk.LabelFrame(main_frame, text="Preview", padding=10)
    preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
    
    fig = Figure(figsize=(6, 3), dpi=80)
    ax1 = fig.add_subplot(121)
    ax2 = fig.add_subplot(122)
    canvas = FigureCanvasTkAgg(fig, preview_frame)
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    def update_preview():
        ax1.clear()
        
        selected_method_name = method_var.get()
        selected_method = None
        for method in smooth_methods:
            if method["name"] == selected_method_name:
                selected_method = method
                break
        
        filter_settings = []
        if selected_method and selected_method["type"] != "none":
            params = {}
            for param_name, var in param_vars.items():
                params[param_name] = var.get()
            
            filter_settings.append({
                'type': selected_method['type'],
                'params': params
            })
        
        threshold                = bout_vars["threshold"].get()
        gen_min_dur              = bout_vars["gen_min_dur"].get()
        rest_dur                 = bout_vars["rest_dur"].get()
        pre_buf                  = bout_vars["pre_buffer"].get()
        post_buf                 = bout_vars["post_buffer"].get()
        locomotion_duration      = bout_vars["locomotion_duration"].get()
        move_direction_threshold = bout_vars["move_direction_threshold"].get()
        only_running             = bool(only_running_var.get())
        
        processed_data = preprocess_running_data(ast2_data, filter_settings)
        if not processed_data:
            canvas.draw(); return
        
        fs = ast2_data['header']['inputRate'] / ast2_data['header']['saveEvery']
        bouts, bouts_with_direction = running_bout_analysis_classify(
            processed_data,
            general_threshold=threshold,
            general_min_duration=gen_min_dur,
            rest_min_duration=rest_dur,
            pre_locomotion_buffer=pre_buf,
            post_locomotion_buffer=post_buf,
            locomotion_duration=locomotion_duration,
            move_direction_threshold=move_direction_threshold,
            only_running=only_running)
        
        if processed_data:
            timestamps = processed_data['timestamps']
            original_speed = processed_data['original_speed']
            filtered_speed = processed_data['filtered_speed']
            
            ax1.plot(timestamps, original_speed, 'k-', alpha=0.7, label='Original', linewidth=1)
            ax1.plot(timestamps, filtered_speed, 'r-', label='Filtered', linewidth=1)
            
            ax1.set_xlabel('Time (s)', fontsize=9)
            ax1.set_ylabel('Speed (cm/s)', fontsize=9)
            ax1.set_xlim(timestamps[0], timestamps[-1])
            ax1.set_title('Running Speed: Original vs Filtered', fontsize=10, fontweight='bold')
            ax1.legend()
            ax1.grid(False)
            if bouts:
                keys = sorted([k for k in bouts.keys() if k.endswith('_bouts')])
                n_row = len(keys)
                try:
                    # matplotlib ≥ 3.6
                    base_cmap = plt.colormaps['tab10']
                except AttributeError:
                    # matplotlib < 3.6
                    base_cmap = cm.get_cmap('tab10')
                colors = [base_cmap(i % base_cmap.N) for i in range(n_row)]

                all_times = []
                for v in bouts.values():
                    if isinstance(v, list) and v:
                        all_times.extend([item[0]/fs for item in v])
                        all_times.extend([item[1]/fs for item in v])
                tmin = min(all_times) if all_times else 0
                tmax = max(all_times) if all_times else 1
                tlim = (tmin, tmax)

                labels = []
                for y, key in enumerate(keys):
                    segments = bouts[key]
                    for (t_start, t_end) in segments:
                        ax2.barh(y, width=(t_end-t_start)/fs, left=t_start/fs,
                                height=0.6, color=colors[y], alpha=1, linewidth=0)
                    labels.append(key.replace('_bouts', ''))
                
                ax2.set_xlim(tlim)
                ax2.set_ylim(-0.5, n_row-0.5)
                ax2.set_yticks(range(n_row))
                ax2.set_yticklabels(labels, fontsize=9)
                ax2.set_xlabel('Time (s)', fontsize=9)
                ax2.set_title('Running bouts raster', fontsize=10, fontweight='bold')
                ax2.invert_yaxis()
                # ax2.spines['top'].set_visible(False)
                # ax2.spines['right'].set_visible(False)
                ax2.grid(False)
                
            canvas.draw()
    
    def apply_all_settings():
        try:
            selected_method_name = method_var.get()
            selected_method = None
            for method in smooth_methods:
                if method["name"] == selected_method_name:
                    selected_method = method
                    break
            
            filter_settings = []
            if selected_method and selected_method["type"] != "none":
                params = {}
                for param_name, var in param_vars.items():
                    params[param_name] = var.get()
                
                filter_settings.append({
                    'type': selected_method['type'],
                    'params': params
                })

            threshold                = bout_vars["threshold"].get()
            gen_min_dur              = bout_vars["gen_min_dur"].get()
            rest_dur                 = bout_vars["rest_dur"].get()
            pre_buf                  = bout_vars["pre_buffer"].get()
            post_buf                 = bout_vars["post_buffer"].get()
            locomotion_duration      = bout_vars["locomotion_duration"].get()
            move_direction_threshold = bout_vars["move_direction_threshold"].get()
            only_running             = bool(only_running_var.get())

            successful = 0
            failed = 0
            
            for idx, animal_data in enumerate(multi_animal_data):
                animal_single_channel_id = animal_data.get('animal_single_channel_id', f'Animal {idx}')
                try:
                    if 'ast2_data_adjusted' not in animal_data:
                        log_message(f"Skipping {animal_single_channel_id}: No adjusted AST2 data", "WARNING")
                        failed += 1; continue

                    processed_data = preprocess_running_data(
                        animal_data['ast2_data_adjusted'], filter_settings)
                    if not processed_data:
                        failed += 1; continue

                    bouts, bouts_with_direction = running_bout_analysis_classify(
                        processed_data,
                        general_threshold=threshold,
                        general_min_duration=gen_min_dur,
                        rest_min_duration=rest_dur,
                        pre_locomotion_buffer=pre_buf,
                        post_locomotion_buffer=post_buf,
                        locomotion_duration=locomotion_duration,
                        move_direction_threshold=move_direction_threshold,
                        only_running=only_running
                    )
                    
                    animal_data['running_processed_data'] = processed_data
                    animal_data['running_bouts'] = bouts
                    animal_data['bouts_with_direction'] = bouts_with_direction
                    successful += 1
                    log_message(f"Processed {animal_single_channel_id}", "INFO")
                except Exception as e:
                    log_message(f"Error processing {animal_single_channel_id}: {e}", "ERROR")
                    failed += 1

            if current_animal_index < len(multi_animal_data) and running_plot_window:
                running_plot_window.animal_data = multi_animal_data[current_animal_index]
                running_plot_window.update_plot()
                _deps['running_plot_window'] = running_plot_window

            analysis_manager.set_last_analysis('running_analysis')

            if current_animal_index < len(multi_animal_data):
                display_running_analysis_for_animal(multi_animal_data[current_animal_index])

            log_message(f"Running preprocessing completed: "
                        f"Diameter {treadmill_diameter} cm, "
                        f"Threshold {threshold} cm/s, "
                        f"Method: {selected_method_name}", "INFO")
            log_message(f"Results: {successful} successful, {failed} failed", "INFO")
            analysis_window.destroy()

        except ValueError as e:
            log_message(f"Invalid setting value: {e}", "ERROR")
        except Exception as e:
            log_message(f"Error applying running settings: {e}", "ERROR")
    
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X, pady=10)
    
    ttk.Button(button_frame, text="Update Preview", 
              command=update_preview).pack(side=tk.LEFT, padx=5)
    
    ttk.Button(button_frame, text="Apply to All Animals", 
              command=apply_all_settings).pack(side=tk.LEFT, padx=5)
    
    ttk.Button(button_frame, text="Cancel", 
              command=analysis_window.destroy).pack(side=tk.RIGHT, padx=5)
    
    update_preview()

def apply_preprocessing_wrapper():
    """Apply fiber preprocessing to ALL animals"""
    try:
        if not multi_animal_data:
            log_message("No animal data available for preprocessing", "WARNING")
            return
        
        # Get parameters from UI
        target_signal = str(target_signal_var.get())
        reference_signal = str(reference_signal_var.get())
        baseline_start_val = float(baseline_start.get())
        baseline_end_val = float(baseline_end.get())
        apply_smooth_val = bool(apply_smooth.get())
        window_size_val = int(smooth_window.get())
        poly_order_val = int(smooth_order.get())
        apply_baseline_val = bool(apply_baseline.get())
        baseline_model_val = str(baseline_model.get())
        apply_motion_val = bool(apply_motion.get())
        
        successful_preprocessing = 0
        failed_preprocessing = 0
        
        for idx, animal_data in enumerate(multi_animal_data):
            animal_single_channel_id = animal_data.get('animal_single_channel_id', f'Animal {idx}')
            
            try:
                if 'fiber_data_trimmed' not in animal_data:
                    log_message(f"Skipping {animal_single_channel_id}: No fiber data", "WARNING")
                    failed_preprocessing += 1
                    continue
                
                success = apply_preprocessing(
                    animal_data, 
                    target_signal,
                    reference_signal,
                    (baseline_start_val, baseline_end_val),
                    apply_smooth_val,
                    window_size_val,
                    poly_order_val,
                    apply_baseline_val,
                    baseline_model_val,
                    apply_motion_val
                )
                
                if success:
                    successful_preprocessing += 1
                    log_message(f"Preprocessed {animal_single_channel_id}", "INFO")
                else:
                    failed_preprocessing += 1
                    log_message(f"Failed to preprocess {animal_single_channel_id}", "ERROR")
                    
            except Exception as e:
                log_message(f"Error preprocessing {animal_single_channel_id}: {str(e)}", "ERROR")
                failed_preprocessing += 1
        
        # Set last analysis type
        analysis_manager.set_last_analysis('fiber_preprocessing')
        
        # Update display for current animal
        if current_animal_index < len(multi_animal_data):
            display_fiber_results_for_animal(multi_animal_data[current_animal_index])
        
        # Show summary
        log_message(f"Fiber preprocessing completed: "
                   f"{successful_preprocessing} successful, {failed_preprocessing} failed", "INFO")
        
    except Exception as e:
        log_message(f"Batch fiber preprocessing failed: {str(e)}", "ERROR")

def calculate_and_plot_dff_wrapper():
    """Calculate ΔF/F for ALL animals"""
    try:
        if not multi_animal_data:
            log_message("No animal data available", "WARNING")
            return
        
        target_signal = str(target_signal_var.get())
        reference_signal = str(reference_signal_var.get())
        baseline_start_val = float(baseline_start.get())
        baseline_end_val = float(baseline_end.get())
        apply_baseline_val = bool(apply_baseline.get())
        
        successful_calculations = 0
        failed_calculations = 0
        
        for idx, animal_data in enumerate(multi_animal_data):
            animal_single_channel_id = animal_data.get('animal_single_channel_id', f'Animal {idx}')
            
            try:
                calculate_dff(
                    animal_data, 
                    target_signal,
                    reference_signal,
                    (baseline_start_val, baseline_end_val),
                    apply_baseline_val
                )
                
                animal_data['apply_baseline'] = apply_baseline_val
                animal_data['reference_signal'] = reference_signal
                
                successful_calculations += 1
                log_message(f"Calculated ΔF/F for {animal_single_channel_id}", "INFO")
                
            except Exception as e:
                log_message(f"Failed ΔF/F for {animal_single_channel_id}: {str(e)}", "ERROR")
                failed_calculations += 1
        
        analysis_manager.set_last_analysis('dff')
        
        # Update display for current animal
        if current_animal_index < len(multi_animal_data):
            if fiber_plot_window:
                fiber_plot_window.set_plot_type("dff")
        
        log_message(f"ΔF/F calculation completed: "
                   f"{successful_calculations} successful, {failed_calculations} failed", "INFO")
        
    except Exception as e:
        log_message(f"Batch ΔF/F calculation failed: {str(e)}", "ERROR")

def calculate_and_plot_zscore_wrapper():
    """Calculate Z-score for ALL animals"""
    try:
        if not multi_animal_data:
            log_message("No animal data available", "WARNING")
            return
        
        successful_calculations = 0
        failed_calculations = 0
        
        for idx, animal_data in enumerate(multi_animal_data):
            animal_single_channel_id = animal_data.get('animal_single_channel_id', f'Animal {idx}')
            
            try:
                zscore_data = calculate_zscore(
                    animal_data,
                    target_signal_var.get(),
                    reference_signal_var.get(),
                    (baseline_start.get(), baseline_end.get()),
                    apply_baseline.get()
                )
                
                if zscore_data:
                    animal_data['zscore_data'] = zscore_data
                    successful_calculations += 1
                    log_message(f"Calculated Z-score for {animal_single_channel_id}", "INFO")
                else:
                    failed_calculations += 1
                    
            except Exception as e:
                log_message(f"Failed Z-score for {animal_single_channel_id}: {str(e)}", "ERROR")
                failed_calculations += 1
        
        analysis_manager.set_last_analysis('zscore')
        
        # Update display for current animal
        if current_animal_index < len(multi_animal_data):
            if fiber_plot_window:
                fiber_plot_window.set_plot_type("zscore")
        
        log_message(f"Z-score calculation completed: "
                   f"{successful_calculations} successful, {failed_calculations} failed", "INFO")
        
    except Exception as e:
        log_message(f"Batch Z-score calculation failed: {str(e)}", "ERROR")
