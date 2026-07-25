import tkinter as tk
from tkinter import ttk

from infrastructure.logger import log_message
from ui.bodypart_controller import create_bodypart_buttons, create_visualization_window
import workflows.analysis_workflows as analysis_workflows
import workflows.data_workflows as data_workflows

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
    
    nb = _ensure_notebook()
    
    def _vis(parent, mode, adata):
        global visualization_window, fiber_plot_window, running_plot_window
        if mode in (EXPERIMENT_MODE_FIBER_AST2_DLC, EXPERIMENT_MODE_FIBER_AST2):
            fb = _add_tab(nb, "Fiber Data")
            rb = _add_tab(nb, "Running Data")
            fiber_plot_window = FiberVisualizationWindow(fb, adata, 
                target_signal_var.get() if 'target_signal_var' in globals() else "470",
                globals().get('input3_events'), globals().get('drug_events'))
            running_plot_window = RunningVisualizationWindow(rb, adata)
        if mode == EXPERIMENT_MODE_FIBER_AST2_DLC and parsed_data:
            bp = _add_tab(nb, "Bodyparts")
            visualization_window = BodypartVisualizationWindow(bp, parsed_data)
        if mode == EXPERIMENT_MODE_AST2:
            rb = _add_tab(nb, "Running Data")
            running_plot_window = RunningVisualizationWindow(rb, adata)
        if mode in (EXPERIMENT_MODE_FIBER, EXPERIMENT_MODE_FIBER_BSOID):
            fb = _add_tab(nb, "Fiber Data")
            fiber_plot_window = FiberVisualizationWindow(fb, adata,
                target_signal_var.get() if 'target_signal_var' in globals() else "470",
                globals().get('input3_events'), globals().get('drug_events'))
    
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

def _get_fiber_tab():
    """Get or create the Fiber Data tab frame"""
    nb = globals().get('_notebook')
    if nb and nb.winfo_exists():
        return _add_tab(nb, "Fiber Data")
    return central_display_frame

def _get_running_tab():
    """Get or create the Running Data tab frame"""
    nb = globals().get('_notebook')
    if nb and nb.winfo_exists():
        return _add_tab(nb, "Running Data")
    return central_display_frame

def create_fiber_visualization(animal_data=None, parent=None):
    global fiber_plot_window, input3_events, drug_events
    if animal_data:
        input3_events = animal_data.get('input3_events')
        drug_events = animal_data.get('drug_events')
    else:
        input3_events = globals().get('input3_events')
        drug_events = globals().get('drug_events')
    
    if fiber_plot_window:
        fiber_plot_window.close_window()
    
    parent = parent or _get_fiber_tab()
    target_signal = target_signal_var.get() if 'target_signal_var' in globals() else "470"
    
    if animal_data:
        if 'preprocessed_data' in animal_data:
            fiber_plot_window = FiberVisualizationWindow(
                parent, animal_data, target_signal, input3_events, drug_events,
            )
        else:
            if 'fiber_data_trimmed' not in animal_data or animal_data['fiber_data_trimmed'] is None:
                if 'fiber_data' in animal_data and animal_data['fiber_data'] is not None:
                    log_message("Using fiber_data instead of fiber_data_trimmed", "INFO")
                    animal_data['fiber_data_trimmed'] = animal_data['fiber_data']
                else:
                    log_message("No fiber data available in animal_data", "WARNING")
                    return

            if 'channels' not in animal_data or not animal_data['channels']:
                log_message("No channels configuration in animal_data", "WARNING")
                return
                
            if 'active_channels' not in animal_data or not animal_data['active_channels']:
                log_message("No active channels in animal_data", "WARNING")
                return
                
            fiber_plot_window = FiberVisualizationWindow(
                parent, animal_data, target_signal, input3_events, drug_events,
            )

    _deps['fiber_plot_window'] = fiber_plot_window

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
