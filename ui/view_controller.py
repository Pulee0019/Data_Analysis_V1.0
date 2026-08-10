import platform
import tkinter as tk
import ui.view_controller as view_controller
import ui.settings_dialogs as settings_dialogs
import workflows.data_workflows as data_workflows
import ui.bodypart_controller as bodypart_controller
import workflows.analysis_workflows as analysis_workflows
import analysis_multimodal.Bout_analysis as bout_analysis
import analysis_multimodal.BSOID_analysis as bsoid_analysis
import analysis_multimodal.Event_analysis as event_analysis
import analysis_multimodal.Freezing_analysis as freezing_analysis
import ui.windows.visualization_windows as visualization_windows
import analysis_multimodal.Multimodal_analysis as multimodal_analysis
import analysis_multimodal.Drug_induced_activity_analysis as drug_induced_analysis
import analysis_multimodal.Optogenetic_induced_activity_analysis as optogenetic_induced_analysis

from tkinter import ttk, messagebox
from infrastructure.logger import log_message
from core.analysis_results import AnalysisResultsManager
from analysis_multimodal.Bout_analysis import show_bout_analysis
from analysis_multimodal.BSOID_analysis import show_bsoid_analysis
from analysis_multimodal.Event_analysis import show_event_analysis
from analysis_multimodal.Freezing_analysis import show_freezing_analysis
from analysis_multimodal.Drug_induced_activity_analysis import show_drug_induced_analysis
from analysis_multimodal.Running_induced_activity_analysis import show_running_induced_analysis
from analysis_multimodal.Optogenetic_induced_activity_analysis import show_optogenetic_induced_analysis
from analysis_core.Behavior_analysis import (
    displacement_analysis, 
    position_analysis, 
    x_displacement_analysis,
    trajectory_pointcloud_analysis
)
from core.config_store import (
    channel_memory,
    drug_name_config,
    event_config,
    opto_power_config,
    save_channel_memory,
    save_drug_name_config,
    save_event_config,
    save_opto_power_config,
)
from ui.settings_dialogs import (
    save_log,
    save_path_setting,
    export_animal_data,
    on_closing,
    setup_log_display,
    show_drug_name_config_dialog,
    show_opto_power_config_dialog
)
from workflows.analysis_workflows import (
    calculate_and_plot_dff_wrapper,
    calculate_and_plot_zscore_wrapper,
    fiber_preprocessing,
    running_data_analysis,
)
from workflows.data_workflows import (
    import_multi_animals, 
    import_single_animal, 
    show_channel_selection_dialog)


_deps = {}

def bind_view_dependencies(deps):
    _deps.clear()
    _deps.update(deps)
    globals().update(deps)

_notebook = None

def _ensure_notebook():
    """Create or return the Notebook in central_display_frame (Req 4)"""
    global _notebook
    if _notebook is not None:
        try:
            _notebook.winfo_exists()
            return _notebook
        except tk.TclError:
            _notebook = None
    for widget in central_display_frame.winfo_children():
        widget.destroy()
    _notebook = ttk.Notebook(central_display_frame)
    _notebook.pack(fill=tk.BOTH, expand=True)
    return _notebook


def _add_tab(notebook, title):
    """Add a tab to the notebook and return its content frame"""
    for child in notebook.winfo_children():
        if isinstance(child, ttk.Frame):
            try:
                tab_text = notebook.tab(child, "text")
            except tk.TclError:
                continue
            if tab_text == title:
                notebook.select(child)
                for w in child.winfo_children():
                    w.destroy()
                return child
    frame = ttk.Frame(notebook)
    notebook.add(frame, text=title)
    notebook.select(frame)
    return frame


def main_visualization(animal_data=None):
    """Modified to handle different experiment modes with Notebook tabs (Req 4)"""
    global parsed_data, visualization_window, fiber_plot_window, running_plot_window
    global current_experiment_mode, _current_bodyparts, _notebook
    if animal_data:
        input3_events = animal_data.get('input3_events')
        drug_events = animal_data.get('drug_events')
    else:
        input3_events = globals().get('input3_events')
        drug_events = globals().get('drug_events')
        
    nb = _ensure_notebook()
    
    def _vis(parent, mode, adata):
        global visualization_window, fiber_plot_window, running_plot_window
        if mode in (EXPERIMENT_MODE_FIBER_AST2_DLC, EXPERIMENT_MODE_FIBER_AST2):
            fb = _add_tab(nb, "Fiber Data")
            rb = _add_tab(nb, "Running Data")
            fiber_plot_window = FiberVisualizationWindow(fb, adata, 
                target_signal_var.get() if 'target_signal_var' in globals() else "470",
                input3_events, drug_events)
            running_plot_window = RunningVisualizationWindow(rb, adata)
        if mode == EXPERIMENT_MODE_FIBER_AST2_DLC and parsed_data:
            bp = _add_tab(nb, "Bodyparts")
            visualization_window = BodypartVisualizationWindow(bp, parsed_data)
        if mode == EXPERIMENT_MODE_AST2:
            rb = _add_tab(nb, "Running Data")
            running_plot_window = RunningVisualizationWindow(rb, adata)
        if mode in (EXPERIMENT_MODE_FIBER, EXPERIMENT_MODE_FIBER_BSOID, EXPERIMENT_MODE_FIBER_EVENT):
            fb = _add_tab(nb, "Fiber Data")
            fiber_plot_window = FiberVisualizationWindow(fb, adata,
                target_signal_var.get() if 'target_signal_var' in globals() else "470",
                input3_events, drug_events)
    
    if animal_data is None:
        if current_experiment_mode == EXPERIMENT_MODE_FIBER_AST2_DLC:
            if not hasattr(globals(), 'parsed_data') or not parsed_data:
                log_message("No DLC data available for visualization", "WARNING")
                return
            _current_bodyparts = list(parsed_data.keys())
            _vis(nb, current_experiment_mode, None)
        else:
            _vis(nb, current_experiment_mode, None)
    else:
        animal_mode = animal_data.get('experiment_mode', EXPERIMENT_MODE_FIBER_AST2_DLC)
        if animal_mode == EXPERIMENT_MODE_FIBER_AST2_DLC:
            if 'dlc_data' not in animal_data or not animal_data['dlc_data']:
                log_message("No DLC data available for visualization", "WARNING")
            else:
                parsed_data = animal_data['dlc_data']
                _current_bodyparts = list(parsed_data.keys())
        _vis(nb, animal_mode, animal_data)


def create_running_visualization(animal_data=None, parent=None):
    global running_plot_window
    
    if running_plot_window:
        running_plot_window.close_window()
    
    parent = parent or _get_running_tab()
    running_plot_window = RunningVisualizationWindow(parent, animal_data)
    _deps['running_plot_window'] = running_plot_window


def display_analysis_results(analysis_type, animal_data):
    """Display analysis results for current animal"""
    if analysis_type == 'running_analysis':
        display_running_analysis_for_animal(animal_data)
    elif analysis_type == 'fiber_preprocessing':
        display_fiber_results_for_animal(animal_data, plot_type="motion_corrected")
    elif analysis_type == 'dff':
        display_fiber_results_for_animal(animal_data, plot_type="dff")
    elif analysis_type == 'z-score':
        display_fiber_results_for_animal(animal_data, plot_type="z-score")


def display_running_analysis_for_animal(animal_data):
    """Display running analysis results for specific animal"""
    if 'running_bouts' in animal_data and 'bouts' not in animal_data:
        animal_data['bouts'] = animal_data['running_bouts']
    
    # Update running plot window
    if running_plot_window:
        running_plot_window.animal_data = animal_data
        running_plot_window.update_plot()
    
    # Update fiber plot window if exists
    if fiber_plot_window:
        fiber_plot_window.animal_data = animal_data
        fiber_plot_window.update_plot()


def display_fiber_results_for_animal(animal_data, plot_type="raw"):
    """Display fiber preprocessing results for specific animal"""
    if fiber_plot_window:
        fiber_plot_window.animal_data = animal_data
        
        # Determine which plot type to show based on available data
        if 'zscore_data' in animal_data and animal_data['zscore_data'] and plot_type == "z-score":
            fiber_plot_window.set_plot_type("zscore")
        elif 'dff_data' in animal_data and animal_data['dff_data'] and plot_type == "dff":
            fiber_plot_window.set_plot_type("dff")
        elif 'preprocessed_data' in animal_data and plot_type == "motion_corrected":
            fiber_plot_window.set_plot_type("motion_corrected")
        else:
            fiber_plot_window.set_plot_type("raw")


def create_animal_list(parent=None):
    if parent is None:
        parent = right_frame if 'right_frame' in globals() and right_frame is not None else left_frame
    for widget in parent.winfo_children():
        widget.destroy()

    multi_animal_frame = ttk.LabelFrame(parent, text="Animal List")
    multi_animal_frame.pack(fill=tk.X, padx=5, pady=5)
    
    list_frame = ttk.Frame(multi_animal_frame)
    list_frame.pack(fill=tk.X, expand=True, padx=5, pady=5)
    
    xscroll = tk.Scrollbar(list_frame, orient=tk.HORIZONTAL)
    xscroll.pack(side=tk.BOTTOM, fill=tk.X)

    yscroll = tk.Scrollbar(list_frame)
    yscroll.pack(side=tk.RIGHT, fill=tk.Y)

    global file_listbox
    file_listbox = tk.Listbox(list_frame,
                              selectmode=tk.SINGLE,
                              xscrollcommand=xscroll.set,
                              yscrollcommand=yscroll.set,
                              height=30)
    file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    xscroll.config(command=file_listbox.xview)
    yscroll.config(command=file_listbox.yview)
    
    list_frame.columnconfigure(0, weight=1)
    list_frame.rowconfigure(0, weight=1)
    
    file_listbox.bind('<<ListboxSelect>>', on_animal_select)

    btn_frame = ttk.Frame(multi_animal_frame)
    btn_frame.pack(fill="x", padx=5, pady=5)

    style = ttk.Style()
    style.configure("Accent.TButton", 
                    font=("Microsoft YaHei", 9),
                    padding=(5, 2))

    ttk.Button(btn_frame, text="Clear Selected", command=clear_selected,
               style="Accent.TButton").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=1)
    ttk.Button(btn_frame, text="Clear All", command=clear_all,
               style="Accent.TButton").pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=1)


def update_file_listbox():
    """Update the file listbox to show animal_single_channel_id"""
    file_listbox.delete(0, tk.END)
    
    for animal_data in multi_animal_data:
        animal_single_channel_id = animal_data.get('animal_single_channel_id', 'Unknown')
        display_text = animal_single_channel_id
        
        # Add group info if available
        if 'group' in animal_data and animal_data['group']:
            display_text += f" ({animal_data['group']})"
        
        file_listbox.insert(tk.END, display_text)


def clear_selected():
    """Modified to handle single-channel entries"""
    selected_indices = file_listbox.curselection()
    for index in sorted(selected_indices, reverse=True):
        file_listbox.delete(index)
        
        if index < len(selected_files):
            animal_data = selected_files.pop(index)
            animal_single_channel_id = animal_data.get('animal_single_channel_id')
            
            for i, data in enumerate(multi_animal_data):
                if data.get('animal_single_channel_id') == animal_single_channel_id:
                    multi_animal_data.pop(i)
                    break
    
    # Reset if no channels left
    if not multi_animal_data:
        analysis_manager.last_analysis_type = None
        reset_visualization_area()


def on_animal_select(event):
    """Modified to display channel-specific ID"""
    global current_animal_index
    selection = file_listbox.curselection()
    if selection:
        current_animal_index = selection[0]
        _deps['current_animal_index'] = current_animal_index
        if current_animal_index < len(multi_animal_data):
            animal_data = multi_animal_data[current_animal_index]
            
            # Update main visualization
            main_visualization(animal_data)
            
            # Check if there's a last analysis and if current animal has results
            last_analysis = analysis_manager.get_last_analysis()
            if last_analysis:
                animal_single_channel_id = animal_data.get('animal_single_channel_id', 'Unknown')
                log_message(f"Switching to {animal_single_channel_id}", "INFO")
                display_analysis_results(last_analysis, animal_data)
            else:
                animal_single_channel_id = animal_data.get('animal_single_channel_id', 'Unknown')
                log_message(f"Viewing {animal_single_channel_id}", "INFO")


def clear_all():
    """Clear all animals"""
    file_listbox.delete(0, tk.END)
    selected_files.clear()
    multi_animal_data.clear()

    if hasattr(data_workflows, 'selected_files') and isinstance(data_workflows.selected_files, list):
        data_workflows.selected_files.clear()
    if hasattr(data_workflows, 'multi_animal_data') and isinstance(data_workflows.multi_animal_data, list):
        data_workflows.multi_animal_data.clear()
    if hasattr(analysis_workflows, 'multi_animal_data') and isinstance(analysis_workflows.multi_animal_data, list):
        analysis_workflows.multi_animal_data.clear()

    _deps['selected_files'] = selected_files
    _deps['multi_animal_data'] = multi_animal_data
    _deps['current_animal_index'] = 0
    
    # Reset analysis manager
    analysis_manager.last_analysis_type = None
    
    reset_visualization_area()


def reset_visualization_area():
    """Reset the central visualization area to initial state"""
    global _notebook, visualization_window, fiber_plot_window, running_plot_window
    
    if _notebook is not None:
        try:
            _notebook.destroy()
        except tk.TclError:
            pass
        _notebook = None
    visualization_window = None
    fiber_plot_window = None
    running_plot_window = None
    
    for widget in central_display_frame.winfo_children():
        widget.destroy()
    central_label = tk.Label(
        central_display_frame,
        text="Central Display Area",
        bg="#f8f8f8",
        fg="#666666"
    )
    central_label.pack(pady=20)
    
    _deps['visualization_window'] = None
    _deps['fiber_plot_window'] = None
    _deps['running_plot_window'] = None


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
        multimodal_menu.entryconfig("BSOID Analysis", state="disabled")
        bsoid_menu.entryconfig("BSOID", state="disabled")
        multimodal_menu.entryconfig("Event Analysis", state="disabled")
        event_menu.entryconfig("Event", state="disabled")
        multimodal_menu.entryconfig("Freezing Analysis", state="disabled")
        freezing_menu.entryconfig("Freezing", state="disabled")
    elif current_experiment_mode == EXPERIMENT_MODE_FIBER:
        analysis_menu.entryconfig("Behavior Analysis", state="disabled")
        analysis_menu.entryconfig("Running Data Analysis", state="disabled")
        analysis_menu.entryconfig("Fiber Data Preprocessing", state="normal")
        analysis_menu.entryconfig("Fiber Data Analysis", state="normal")
        multimodal_menu.entryconfig("Running-Induced Activity Analysis", state="disabled")
        multimodal_menu.entryconfig("Drug-Induced Activity Analysis", state="normal")
        multimodal_menu.entryconfig("Optogenetics-Induced Activity Analysis", state="normal")
        multimodal_menu.entryconfig("Bout Analysis", state="disabled")
        bout_menu.entryconfig("Running", state="disabled")
        bout_menu.entryconfig("Running + Drug", state="disabled")
        multimodal_menu.entryconfig("BSOID Analysis", state="disabled")
        bsoid_menu.entryconfig("BSOID", state="disabled")
        multimodal_menu.entryconfig("Event Analysis", state="disabled")
        event_menu.entryconfig("Event", state="disabled")
        multimodal_menu.entryconfig("Freezing Analysis", state="disabled")
        freezing_menu.entryconfig("Freezing", state="disabled")
    elif current_experiment_mode == EXPERIMENT_MODE_FREEZING:
        analysis_menu.entryconfig("Behavior Analysis", state="disabled")
        analysis_menu.entryconfig("Running Data Analysis", state="disabled")
        analysis_menu.entryconfig("Fiber Data Preprocessing", state="disabled")
        analysis_menu.entryconfig("Fiber Data Analysis", state="disabled")
        multimodal_menu.entryconfig("Running-Induced Activity Analysis", state="disabled")
        multimodal_menu.entryconfig("Drug-Induced Activity Analysis", state="disabled")
        multimodal_menu.entryconfig("Optogenetics-Induced Activity Analysis", state="disabled")
        multimodal_menu.entryconfig("Bout Analysis", state="disabled")
        bout_menu.entryconfig("Running", state="disabled")
        bout_menu.entryconfig("Running + Drug", state="disabled")
        multimodal_menu.entryconfig("BSOID Analysis", state="disabled")
        bsoid_menu.entryconfig("BSOID", state="disabled")
        multimodal_menu.entryconfig("Event Analysis", state="disabled")
        event_menu.entryconfig("Event", state="disabled")
        multimodal_menu.entryconfig("Freezing Analysis", state="normal")
        freezing_menu.entryconfig("Freezing", state="normal")
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
        multimodal_menu.entryconfig("BSOID Analysis", state="disabled")
        bsoid_menu.entryconfig("BSOID", state="disabled")
        multimodal_menu.entryconfig("Event Analysis", state="disabled")
        event_menu.entryconfig("Event", state="disabled")
        multimodal_menu.entryconfig("Freezing Analysis", state="disabled")
        freezing_menu.entryconfig("Freezing", state="disabled")
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
        multimodal_menu.entryconfig("BSOID Analysis", state="disabled")
        bsoid_menu.entryconfig("BSOID", state="disabled")
        multimodal_menu.entryconfig("Event Analysis", state="disabled")
        event_menu.entryconfig("Event", state="disabled")
        multimodal_menu.entryconfig("Freezing Analysis", state="disabled")
        freezing_menu.entryconfig("Freezing", state="disabled")
    elif current_experiment_mode == EXPERIMENT_MODE_FIBER_BSOID:
        analysis_menu.entryconfig("Behavior Analysis", state="disabled")
        analysis_menu.entryconfig("Running Data Analysis", state="disabled")
        analysis_menu.entryconfig("Fiber Data Preprocessing", state="normal")
        analysis_menu.entryconfig("Fiber Data Analysis", state="normal")
        multimodal_menu.entryconfig("Running-Induced Activity Analysis", state="disabled")
        multimodal_menu.entryconfig("Drug-Induced Activity Analysis", state="normal")
        multimodal_menu.entryconfig("Optogenetics-Induced Activity Analysis", state="normal")
        multimodal_menu.entryconfig("Bout Analysis", state="disabled")
        bout_menu.entryconfig("Running", state="disabled")
        bout_menu.entryconfig("Running + Drug", state="disabled")
        multimodal_menu.entryconfig("BSOID Analysis", state="normal")
        bsoid_menu.entryconfig("BSOID", state="normal")
        multimodal_menu.entryconfig("Event Analysis", state="disabled")
        event_menu.entryconfig("Event", state="disabled")
        multimodal_menu.entryconfig("Freezing Analysis", state="disabled")
        freezing_menu.entryconfig("Freezing", state="disabled")
    elif current_experiment_mode == EXPERIMENT_MODE_FIBER_EVENT:
        analysis_menu.entryconfig("Behavior Analysis", state="disabled")
        analysis_menu.entryconfig("Running Data Analysis", state="disabled")
        analysis_menu.entryconfig("Fiber Data Preprocessing", state="normal")
        analysis_menu.entryconfig("Fiber Data Analysis", state="normal")
        multimodal_menu.entryconfig("Running-Induced Activity Analysis", state="disabled")
        multimodal_menu.entryconfig("Drug-Induced Activity Analysis", state="normal")
        multimodal_menu.entryconfig("Optogenetics-Induced Activity Analysis", state="normal")
        multimodal_menu.entryconfig("Bout Analysis", state="disabled")
        bout_menu.entryconfig("Running", state="disabled")
        bout_menu.entryconfig("Running + Drug", state="disabled")
        multimodal_menu.entryconfig("BSOID Analysis", state="disabled")
        bsoid_menu.entryconfig("BSOID", state="disabled")
        multimodal_menu.entryconfig("Event Analysis", state="normal")
        event_menu.entryconfig("Event", state="normal")
        multimodal_menu.entryconfig("Freezing Analysis", state="disabled")
        freezing_menu.entryconfig("Freezing", state="disabled")


def bootstrap_globals(root):
    state = {
        "root": root,
        "global_save_dir": False,
        "analysis_manager": AnalysisResultsManager(),
        "EXPERIMENT_MODE_AST2": "ast2",
        "EXPERIMENT_MODE_FIBER": "fiber",
        "EXPERIMENT_MODE_FREEZING": "freezing",
        "EXPERIMENT_MODE_FIBER_AST2": "fiber+ast2",
        "EXPERIMENT_MODE_FIBER_AST2_DLC": "fiber+ast2+dlc",
        "EXPERIMENT_MODE_FIBER_BSOID": "fiber+bsoid",
        "EXPERIMENT_MODE_FIBER_EVENT": "fiber+event",
        "current_experiment_mode": "fiber+ast2",
        'method_var': tk.StringVar(),
        'only_running_var': tk.IntVar(value=0),
        "disp_var": tk.StringVar(),
        "direction_var": tk.StringVar(),
        "target_signal_var": tk.StringVar(value="470"),
        "reference_signal_var": tk.StringVar(value="baseline"),
        "baseline_start": tk.DoubleVar(value=0),
        "baseline_end": tk.DoubleVar(value=120),
        "apply_smooth": tk.BooleanVar(value=False),
        "smooth_window": tk.IntVar(value=11),
        "smooth_order": tk.IntVar(value=5),
        "apply_baseline": tk.BooleanVar(value=False),
        "baseline_model": tk.StringVar(value="Polynomial"),
        "baseline_poly_order": tk.IntVar(value=21),
        "apply_motion": tk.BooleanVar(value=False),
        "preprocess_frame": None,
        "multimodal_analyzer": None,
        "accrossday_analyzer": None,
        "current_animal_index": 0,
        "selected_files": [],
        "multi_animal_data": [],
        "fiber_plot_window": None,
        "running_plot_window": None,
        "bodypart_buttons": {},
        "selected_bodyparts": set(),
        "visualization_window": None,
        "skeleton_connections": [],
        "skeleton_building": False,
        "skeleton_sequence": [],
        "fps_var": None,
        "time_unit_var": None,
        "fps_conversion_var": None,
        "fps_conversion_enabled": False,
        "current_fps": 30,
        "running_channel": 2,
        "invert_running": False,
        "treadmill_diameter": 22,
        "log_text_widget": None,
        "channel_memory": channel_memory,
        "event_config": event_config,
        "opto_power_config": opto_power_config,
        "drug_name_config": drug_name_config,
        "save_channel_memory": save_channel_memory,
        "save_event_config": save_event_config,
        "save_opto_power_config": save_opto_power_config,
        "save_drug_name_config": save_drug_name_config,
        "BodypartVisualizationWindow": visualization_windows.BodypartVisualizationWindow,
        "FiberVisualizationWindow": visualization_windows.FiberVisualizationWindow,
        "RunningVisualizationWindow": visualization_windows.RunningVisualizationWindow,
        "main_visualization": view_controller.main_visualization,
        "update_file_listbox": view_controller.update_file_listbox,
        "display_analysis_results": view_controller.display_analysis_results,
        "display_running_analysis_for_animal": view_controller.display_running_analysis_for_animal,
        "display_fiber_results_for_animal": view_controller.display_fiber_results_for_animal,
    }
    state["state"] = state
    return state


def build_layout(root, state):
    main_container = tk.Frame(root)
    main_container.pack(fill=tk.BOTH, expand=True)

    # Horizontal PanedWindow: left panel | middle area
    h_paned = ttk.PanedWindow(main_container, orient=tk.HORIZONTAL)
    h_paned.pack(fill=tk.BOTH, expand=True, padx=(6, 5), pady=5)

    # --- Left control panel ---
    left_frame = tk.Frame(h_paned, width=260, bg="#e8e8e8")
    h_paned.add(left_frame, weight=0)

    # Vertical PanedWindow inside middle: central area | bottom log
    v_paned = ttk.PanedWindow(h_paned, orient=tk.VERTICAL)
    h_paned.add(v_paned, weight=1)

    central_display_frame = tk.Frame(v_paned, bg="#f8f8f8", relief=tk.SUNKEN, bd=1)
    v_paned.add(central_display_frame, weight=1)

    bottom_display_frame = tk.Frame(v_paned, bg="#f0f0f0", relief=tk.SUNKEN, bd=1, height=170)
    v_paned.add(bottom_display_frame, weight=0)

    central_label = tk.Label(central_display_frame, text="Central Display Area", bg="#f8f8f8", fg="#666666")
    central_label.pack(pady=20)
    bottom_label = tk.Label(bottom_display_frame, text="Bottom Log Area", bg="#f0f0f0", fg="#666666")
    bottom_label.pack(pady=10)

    state.update(
        {
            "main_container": main_container,
            "left_frame": left_frame,
            "middle_frame": v_paned,
            "central_display_frame": central_display_frame,
            "bottom_display_frame": bottom_display_frame,
            "central_label": central_label,
            "bottom_label": bottom_label,
        }
    )


def bind_modules(state):
    visualization_windows.bind_window_dependencies(state)
    data_workflows.bind_workflow_dependencies(state)
    analysis_workflows.bind_analysis_dependencies(state)
    bodypart_controller.bind_bodypart_dependencies(state)
    view_controller.bind_view_dependencies(state)
    settings_dialogs.bind_settings_dependencies(state)
    multimodal_analysis.bind_multimodal_dependencies(state)
    bout_analysis.bind_bout_dependencies(state)
    drug_induced_analysis.bind_drug_induced_dependencies(state)
    optogenetic_induced_analysis.bind_optogenetic_induced_dependencies(state)
    bsoid_analysis.bind_bsoid_dependencies(state)
    event_analysis.bind_event_dependencies(state)
    freezing_analysis.bind_freezing_dependencies(state)


def build_menu(root, state):
    menubar = tk.Menu(root)
    root.config(menu=menubar)

    file_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="File", menu=file_menu)
    import_animals_menu = tk.Menu(file_menu, tearoff=0)
    file_menu.add_cascade(label="Import Animals", menu=import_animals_menu, state="normal")
    import_animals_menu.add_command(label="Import Single Animal", command=import_single_animal)
    import_animals_menu.add_command(label="Import Multiple Animals", command=import_multi_animals)
    import_animals_menu.add_command(label="Show Channel Selection", command=lambda: show_channel_selection_dialog())
    export_menu = tk.Menu(file_menu, tearoff=0)
    file_menu.add_cascade(label="Export", menu=export_menu)
    export_menu.add_command(label="Animal Data", command=export_animal_data)
    export_menu.add_command(label="Log", command=save_log)
    file_menu.add_command(label="Exit", command=root.quit)

    analysis_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Analysis", menu=analysis_menu)
    analysis_menu.add_command(label="Running Data Analysis", command=running_data_analysis)
    analysis_menu.add_separator()
    analysis_menu.add_command(label="Fiber Data Preprocessing", command=fiber_preprocessing)

    fiber_analysis_menu = tk.Menu(analysis_menu, tearoff=0)
    analysis_menu.add_cascade(label="Fiber Data Analysis", menu=fiber_analysis_menu, state="normal")
    fiber_analysis_menu.add_command(label="Calculate ΔF/F", command=lambda: calculate_and_plot_dff_wrapper())
    fiber_analysis_menu.add_command(label="Calculate Z-Score", command=lambda: calculate_and_plot_zscore_wrapper())

    analysis_menu.add_separator()
    behaviour_analysis_menu = tk.Menu(analysis_menu, tearoff=0)
    analysis_menu.add_cascade(label="Behavior Analysis", menu=behaviour_analysis_menu, state="normal")
    behaviour_analysis_menu.add_command(
        label="Position Analysis",
        command=lambda: position_analysis(view_controller.parsed_data if hasattr(view_controller, 'parsed_data') and view_controller.parsed_data is not None else None, state["selected_bodyparts"], root),
    )
    behaviour_analysis_menu.add_command(
        label="Displacement Analysis",
        command=lambda: displacement_analysis(view_controller.parsed_data if hasattr(view_controller, 'parsed_data') and view_controller.parsed_data is not None else None, state["selected_bodyparts"], root),
    )
    behaviour_analysis_menu.add_command(
        label="X Displacement Analysis",
        command=lambda: x_displacement_analysis(view_controller.parsed_data if hasattr(view_controller, 'parsed_data') and view_controller.parsed_data is not None else None, state["selected_bodyparts"], root),
    )
    behaviour_analysis_menu.add_command(
        label="Trajectory Point Cloud",
        command=lambda: trajectory_pointcloud_analysis(
            view_controller.parsed_data if hasattr(view_controller, 'parsed_data') and view_controller.parsed_data is not None else None,
            state["selected_bodyparts"], root
        ),
    )

    multimodal_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Multimodal Analysis", menu=multimodal_menu)

    running_induced_menu = tk.Menu(multimodal_menu, tearoff=0)
    multimodal_menu.add_cascade(label="Running-Induced Activity Analysis", menu=running_induced_menu)
    running_induced_menu.add_command(
        label="Running",
        command=lambda: show_running_induced_analysis(root, state["multi_animal_data"], "running"),
    )
    running_induced_menu.add_command(
        label="Running + Drug",
        command=lambda: show_running_induced_analysis(root, state["multi_animal_data"], "running+drug"),
    )
    running_induced_menu.add_command(
        label="Running + Optogenetics",
        command=lambda: show_running_induced_analysis(root, state["multi_animal_data"], "running+optogenetics"),
    )
    running_induced_menu.add_command(
        label="Running + Optogenetics + Drug",
        command=lambda: show_running_induced_analysis(root, state["multi_animal_data"], "running+optogenetics+drug"),
    )

    multimodal_menu.add_command(
        label="Drug-Induced Activity Analysis",
        command=lambda: show_drug_induced_analysis(root, state["multi_animal_data"]),
    )

    optogenetics_induced_menu = tk.Menu(multimodal_menu, tearoff=0)
    multimodal_menu.add_cascade(label="Optogenetics-Induced Activity Analysis", menu=optogenetics_induced_menu)
    optogenetics_induced_menu.add_command(
        label="Optogenetics",
        command=lambda: show_optogenetic_induced_analysis(root, state["multi_animal_data"], "optogenetics"),
    )
    optogenetics_induced_menu.add_command(
        label="Optogenetics + Drug",
        command=lambda: show_optogenetic_induced_analysis(root, state["multi_animal_data"], "optogenetics+drug"),
    )
    
    bout_menu = tk.Menu(multimodal_menu, tearoff=0)
    multimodal_menu.add_cascade(label="Bout Analysis", menu=bout_menu)
    bout_menu.add_command(
        label="Running",
        command=lambda: show_bout_analysis(root, state["multi_animal_data"], "running"),
    )
    bout_menu.add_command(
        label="Running + Drug",
        command=lambda: show_bout_analysis(root, state["multi_animal_data"], "running+drug"),
    )
    
    bsoid_menu = tk.Menu(multimodal_menu, tearoff=0)
    multimodal_menu.add_cascade(label="BSOID Analysis", menu=bsoid_menu)
    bsoid_menu.add_command(
        label="BSOID",
        command=lambda: show_bsoid_analysis(root, state["multi_animal_data"], "bsoid"),
    )
    
    event_menu = tk.Menu(multimodal_menu, tearoff=0)
    multimodal_menu.add_cascade(label="Event Analysis", menu=event_menu)
    event_menu.add_command(label="Event", command=lambda: show_event_analysis(root, state["multi_animal_data"], "event"))
    
    freezing_menu = tk.Menu(multimodal_menu, tearoff=0)
    multimodal_menu.add_cascade(label="Freezing Analysis", menu=freezing_menu)
    freezing_menu.add_command(
        label="Freezing",
        command=lambda: show_freezing_analysis(root, state["multi_animal_data"], "freezing"),
    )

    menubar.add_command(label="Figure Controller",
                        command=multimodal_analysis.open_figure_controller)

    setting_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Settings", menu=setting_menu)
    setting_menu.add_command(label="Default Path", command=save_path_setting)
    setting_menu.add_command(label="Drug Configuration", command=show_drug_name_config_dialog, state="disabled")
    setting_menu.add_command(label="Optogenetic Configuration", command=show_opto_power_config_dialog, state="disabled")

    state.update(
        {
            "menubar": menubar,
            "analysis_menu": analysis_menu,
            "behaviour_analysis_menu": behaviour_analysis_menu,
            "setting_menu": setting_menu,
            "import_animals_menu": import_animals_menu,
            "file_menu": file_menu,
            "multimodal_menu": multimodal_menu,
            "running_induced_menu": running_induced_menu,
            "optogenetics_induced_menu": optogenetics_induced_menu,
            "bout_menu": bout_menu,
            "bsoid_menu": bsoid_menu,
            "event_menu": event_menu,
            "freezing_menu": freezing_menu,
        }
    )


def create_root():
    root = tk.Tk()
    root.title("Fiber Photometry with Behavior Analysis")
    if platform.system() == "Windows":
        root.state("zoomed")
    else:
        root.attributes("-zoomed", True)
    return root


def create_control_panel(root, state):
    _FONT = ("Microsoft YaHei", 9)
    _BG = "#e8e8e8"

    # Title label (LEFT)
    title_label = tk.Label(state["left_frame"], text="Control Panel", bg=_BG, font=("Microsoft YaHei", 10, "bold"))
    title_label.pack(anchor=tk.W, padx=6, pady=(6, 2))
    # -- Step1: Exp Mode row --
    # Model selection row
    mode_label = tk.Label(state["left_frame"], text="Mode Selection", bg=_BG, font=_FONT)
    mode_label.pack(anchor=tk.W, padx=6, pady=(6, 1))
    mode_row = tk.Frame(state["left_frame"], bg=_BG)
    mode_row.pack(fill=tk.X, padx=6, pady=(6, 2))
    tk.Label(mode_row, text="Exp Mode", bg=_BG, font=_FONT).pack(side=tk.LEFT)
    mode_combo = ttk.Combobox(mode_row,
        values=[state["EXPERIMENT_MODE_FIBER_AST2"], state["EXPERIMENT_MODE_FIBER_AST2_DLC"],
                state["EXPERIMENT_MODE_AST2"], state["EXPERIMENT_MODE_FIBER"],
                state["EXPERIMENT_MODE_FIBER_BSOID"], state["EXPERIMENT_MODE_FIBER_EVENT"], state['EXPERIMENT_MODE_FREEZING']],
        state="readonly", font=_FONT, width=12)
    mode_combo.set(state["current_experiment_mode"])
    mode_combo.pack(side=tk.RIGHT, padx=(6, 0))
    
    def on_mode_change(event):
        new_mode = mode_combo.get()
        if state["multi_animal_data"]:
            if not messagebox.askyesno("Confirm", "Changing mode clears loaded data. Continue?"):
                mode_combo.set(state["current_experiment_mode"])
                return
            clear_all()
        state["current_experiment_mode"] = new_mode
        bind_modules(state)
        update_ui_for_mode()
        log_message(f"Experiment mode set to: {new_mode}", "INFO")
    mode_combo.bind("<<ComboboxSelected>>", on_mode_change)

    # -- Step2: Events row --
    tk.Label(state["left_frame"], text="Events Config", bg=_BG, font=_FONT).pack(anchor=tk.W, padx=6, pady=(6, 1))

    _ev_entries = {}

    def _rebuild_event_rows():
        for w in ev_container.winfo_children():
            w.destroy()
        _ev_entries.clear()
        events = event_config
        if not events:
            events = {'drug_event': 'Event1', 'opto_event': 'Input3', 'running_start': 'Input2'}
        for lbl, value in events.items():
            row = tk.Frame(ev_container, bg=_BG)
            row.pack(fill=tk.X, pady=1)
            tk.Label(row, text=lbl, bg=_BG, fg="#333", font=_FONT, anchor=tk.W).pack(side=tk.LEFT)
            
            # All entry have same length in right side
            ve = tk.Entry(row, font=_FONT, width=15)
            ve.insert(0, value)
            ve.pack(side=tk.RIGHT, padx=(6, 0)) 
            ve.bind("<FocusOut>", lambda *a, e=ve: _sync_events())
            _ev_entries[lbl] = ve

    ev_container = tk.Frame(state["left_frame"], bg=_BG)
    ev_container.pack(fill=tk.X, padx=6)
    _rebuild_event_rows()

    def _sync_events():
        drug_vals = []
        opto_val = None
        run_val = None
        for name, ve in _ev_entries.items():
            val = ve.get().strip()
            if "drug" in name.lower():
                drug_vals.append(val)
            elif "opto" in name.lower():
                opto_val = val
            elif "running" in name.lower():
                run_val = val
                
        event_config['drug_event'] = ', '.join(drug_vals) or 'Event1'
        event_config['opto_event'] = opto_val or 'Input3'
        event_config['running_start'] = run_val or 'Input2'
        save_event_config()

    # -- Step3: Animal info preview (bottom) --
    state['animal_preview_frame'] = tk.Frame(state["left_frame"], bg=_BG)
    state['animal_preview_frame'].pack(side=tk.BOTTOM, fill=tk.X, pady=4)

    # -- Step4: Animal list (fills remaining) --
    state['animal_list_frame'] = tk.Frame(state["left_frame"], bg=_BG)
    state['animal_list_frame'].pack(fill=tk.BOTH, expand=True, padx=6, pady=(4, 6))
    create_animal_list(parent=state['animal_list_frame'])


def bootstrap():
    root = create_root()
    state = bootstrap_globals(root)
    build_layout(root, state)
    build_menu(root, state)
    bind_modules(state)
    root.protocol("WM_DELETE_WINDOW", on_closing)
    update_ui_for_mode()
    create_control_panel(root, state)
    setup_log_display()
    return root