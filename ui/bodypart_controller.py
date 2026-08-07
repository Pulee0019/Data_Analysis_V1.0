import tkinter as tk
import ui.view_controller as view_controller

from tkinter import ttk
from infrastructure.logger import log_message

_deps = {}
_bodypart_dialog = None

def bind_bodypart_dependencies(deps):
    _deps.clear()
    _deps.update(deps)
    globals().update(deps)

def toggle_bodypart(bodypart_name, button):
    """Toggle the state of the bodypart button"""
    global skeleton_building, skeleton_sequence
    
    if skeleton_building:
        # Special handling in skeleton building mode
        if bodypart_name in skeleton_sequence:
            # If already in the sequence, remove it and all subsequent connections
            index = skeleton_sequence.index(bodypart_name)
            skeleton_sequence = skeleton_sequence[:index]
            # Update button states
            for bp in bodypart_buttons:
                if bp in skeleton_sequence:
                    bodypart_buttons[bp].config(relief=tk.SUNKEN, bg="#e67e22")
                else:
                    bodypart_buttons[bp].config(relief=tk.RAISED)
        else:
            # Add to the skeleton sequence
            skeleton_sequence.append(bodypart_name)
            button.config(relief=tk.SUNKEN, bg="#e67e22")  # Orange indicates skeleton building
        
        log_message(f"Skeleton building sequence: {skeleton_sequence}"f"Skeleton building sequence: {skeleton_sequence}")
        
        # Enable confirm button if there are at least 2 points
        if len(skeleton_sequence) >= 2:
            confirm_skeleton_button.config(state=tk.NORMAL)
        else:
            confirm_skeleton_button.config(state=tk.DISABLED)
    else:
        # Normal selection mode
        if bodypart_name in selected_bodyparts:
            selected_bodyparts.remove(bodypart_name)
            button.config(relief=tk.RAISED)
        else:
            selected_bodyparts.add(bodypart_name)
            button.config(relief=tk.SUNKEN)
        log_message(f"Currently selected bodyparts: {list(selected_bodyparts)}")

def start_skeleton_building():
    """Start skeleton building mode"""
    global skeleton_building, skeleton_sequence
    
    skeleton_building = True
    skeleton_sequence = []
    
    # Reset all button states
    for bodypart, button in bodypart_buttons.items():
        button.config(relief=tk.RAISED)
    
    # Update button states
    add_skeleton_button.config(state=tk.DISABLED, text="Building...")
    confirm_skeleton_button.config(state=tk.DISABLED)
    
    # Clear current selections
    selected_bodyparts.clear()
    
    log_message("Skeleton building mode: Click bodyparts to create connections")
    log_message("Skeleton building mode started")

def confirm_skeleton():
    """Confirm skeleton building"""
    global skeleton_building, skeleton_sequence, skeleton_connections
    
    if len(skeleton_sequence) < 2:
        log_message("At least 2 bodyparts are required to build a skeleton", "WARNING")
        return
    
    # Create connections
    new_connections = []
    for i in range(len(skeleton_sequence) - 1):
        connection = (skeleton_sequence[i], skeleton_sequence[i + 1])
        new_connections.append(connection)
    
    skeleton_connections.extend(new_connections)
    
    # Exit skeleton building mode
    skeleton_building = False
    skeleton_sequence = []
    
    # Restore button states
    add_skeleton_button.config(state=tk.NORMAL, text="Add Skeleton")
    confirm_skeleton_button.config(state=tk.DISABLED)
    
    # Reset all button colors
    colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', 
             '#1abc9c', '#e67e22', '#34495e', '#f1c40f', '#95a5a6']
    
    for i, (bodypart, button) in enumerate(bodypart_buttons.items()):
        color = colors[i % len(colors)]
        button.config(bg=color, relief=tk.RAISED)
    
    # Update visualization window to display skeleton
    if hasattr(view_controller, 'visualization_window') and view_controller.visualization_window:
        view_controller.visualization_window.update_plot_optimized()

    log_message(f"Skeleton connections: {skeleton_connections}")
    log_message(f"Skeleton building completed!\n{len(new_connections)} connections added")

def apply_fps_conversion():
    """Apply FPS conversion settings"""
    global fps_conversion_enabled, current_fps
    
    try:
        # Get FPS value
        fps_value = float(fps_var.get())
        if fps_value <= 0:
            log_message("FPS value must be greater than 0", "ERROR")
            return
        
        current_fps = fps_value
        fps_conversion_enabled = fps_conversion_var.get()
        
        # Update visualization window
        if visualization_window:
            visualization_window.update_plot_optimized()
        
        if fps_conversion_enabled:
            time_unit = time_unit_var.get()
            log_message(f"FPS conversion enabled: FPS={current_fps}, Time unit={time_unit}")
        else:
            log_message("FPS conversion disabled, displaying frame numbers")
            
    except ValueError:
        log_message("Please enter a valid FPS value", "ERROR")
    except Exception as e:
        log_message(f"Error applying FPS conversion: {str(e)}", "ERROR")

def frame_to_time(frame_index):
    """Convert frame index to time"""
    global fps_conversion_enabled, current_fps
    
    if not fps_conversion_enabled:
        return frame_index + 1  # Return frame number (starting from 1)
    
    # Calculate time in seconds
    time_seconds = frame_index / current_fps
    
    # Convert based on time unit
    time_unit = time_unit_var.get() if time_unit_var else "seconds"
    if time_unit == "minutes":
        return time_seconds / 60
    else:
        return time_seconds

def get_time_label():
    """Get time axis label"""
    global fps_conversion_enabled
    
    if not fps_conversion_enabled:
        return "Frame"
    
    time_unit = time_unit_var.get() if time_unit_var else "seconds"
    return f"Time({time_unit})"

def create_bodypart_buttons(bodyparts):
    """Open a dialog for bodypart/keypoint selection"""
    global _bodypart_dialog, add_skeleton_button, confirm_skeleton_button
    global fps_var, time_unit_var, fps_conversion_var
    global bodypart_buttons, selected_bodyparts

    bodypart_buttons.clear()
    selected_bodyparts.clear()

    # Close existing dialog if open
    if _bodypart_dialog is not None:
        try:
            _bodypart_dialog.destroy()
        except tk.TclError:
            pass
        _bodypart_dialog = None

    _bodypart_dialog = tk.Toplevel(root)
    _bodypart_dialog.title("Bodypart / Keypoint Selection")
    _bodypart_dialog.geometry("200x700")
    # _bodypart_dialog.transient(root)
    # _bodypart_dialog.grab_set()

    container = tk.Frame(_bodypart_dialog, bg="#e0e0e0", padx=12, pady=12)
    container.pack(fill=tk.BOTH, expand=True)

    # Define color configuration (consistent with visualization window)
    colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6',
             '#1abc9c', '#e67e22', '#34495e', '#f1c40f', '#95a5a6']

    # Bodypart title
    tk.Label(container, text="Bodyparts:", font=("Microsoft YaHei", 12, "bold"),
             bg="#e0e0e0", fg="#2c3e50").pack(pady=(0, 8))

    # Scrollable area for bodypart buttons
    scroll_frame = tk.Frame(container, bg="#e0e0e0")
    scroll_frame.pack(fill=tk.BOTH, expand=True)

    canvas = tk.Canvas(scroll_frame, bg="#e0e0e0", highlightthickness=0)
    scrollbar = tk.Scrollbar(scroll_frame, orient="vertical", command=canvas.yview)
    bp_frame = tk.Frame(canvas, bg="#e0e0e0")

    canvas.configure(yscrollcommand=scrollbar.set)

    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    canvas.create_window((0, 0), window=bp_frame, anchor="nw")

    def on_frame_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
    bp_frame.bind("<Configure>", on_frame_configure)

    for i, bodypart in enumerate(bodyparts):
        color = colors[i % len(colors)]
        button = tk.Button(
            bp_frame,
            text=f"{i+1}. {bodypart}",
            width=18, relief=tk.RAISED, bg=color, fg="white",
            font=("Microsoft YaHei", 9, "bold"),
            activebackground=color, activeforeground="white", cursor="hand2",
            command=lambda bp=bodypart: toggle_bodypart(bp, bodypart_buttons[bp])
        )
        button.pack(pady=2, fill=tk.X)
        bodypart_buttons[bodypart] = button

    # Separator
    tk.Frame(container, height=2, bg="#bdc3c7").pack(fill=tk.X, pady=10)

    # Skeleton building section
    tk.Label(container, text="Skeleton Building:", font=("Microsoft YaHei", 12, "bold"),
             bg="#e0e0e0", fg="#2c3e50").pack(pady=(0, 5))

    add_skeleton_btn = tk.Button(container, text="Add Skeleton", width=18,
        relief=tk.RAISED, bg="#3498db", fg="white",
        font=("Microsoft YaHei", 9, "bold"),
        activebackground="#2980b9", activeforeground="white", cursor="hand2",
        command=start_skeleton_building)
    add_skeleton_btn.pack(pady=2)

    confirm_skeleton_btn = tk.Button(container, text="Confirm", width=18,
        relief=tk.RAISED, bg="#27ae60", fg="white",
        font=("Microsoft YaHei", 9, "bold"),
        activebackground="#229954", activeforeground="white", cursor="hand2",
        command=confirm_skeleton, state=tk.DISABLED)
    confirm_skeleton_btn.pack(pady=2)

    add_skeleton_button = add_skeleton_btn
    confirm_skeleton_button = confirm_skeleton_btn

    # Separator
    tk.Frame(container, height=2, bg="#bdc3c7").pack(fill=tk.X, pady=10)

    # FPS conversion section
    tk.Label(container, text="FPS Conversion:", font=("Microsoft YaHei", 12, "bold"),
             bg="#e0e0e0", fg="#2c3e50").pack(pady=(0, 5))

    fps_frame = tk.Frame(container, bg="#e0e0e0")
    fps_frame.pack(fill=tk.X, pady=2)
    tk.Label(fps_frame, text="FPS:", font=("Microsoft YaHei", 9),
             bg="#e0e0e0", fg="#2c3e50").pack(side=tk.LEFT)
    fps_var = tk.StringVar(value="30")
    tk.Entry(fps_frame, textvariable=fps_var, width=8, font=("Microsoft YaHei", 9)).pack(side=tk.RIGHT)

    tu_frame = tk.Frame(container, bg="#e0e0e0")
    tu_frame.pack(fill=tk.X, pady=2)
    tk.Label(tu_frame, text="Time Unit:", font=("Microsoft YaHei", 9),
             bg="#e0e0e0", fg="#2c3e50").pack(side=tk.LEFT)
    time_unit_var = tk.StringVar(value="seconds")
    ttk.Combobox(tu_frame, textvariable=time_unit_var,
                 values=["seconds", "minutes"], width=6, state="readonly").pack(side=tk.RIGHT)

    fps_conversion_var = tk.BooleanVar()
    tk.Checkbutton(container, text="Enable FPS Conversion",
                   variable=fps_conversion_var,
                   font=("Microsoft YaHei", 9),
                   bg="#e0e0e0", fg="#2c3e50",
                   activebackground="#e0e0e0",
                   command=apply_fps_conversion).pack(pady=2)

    tk.Button(container, text="Apply Settings", width=18,
        relief=tk.RAISED, bg="#e67e22", fg="white",
        font=("Microsoft YaHei", 9, "bold"),
        activebackground="#d35400", activeforeground="white", cursor="hand2",
        command=apply_fps_conversion).pack(pady=4)

    # Close button
    tk.Button(container, text="Close", width=18,
        relief=tk.RAISED, bg="#95a5a6", fg="white",
        font=("Microsoft YaHei", 9, "bold"), cursor="hand2",
        command=lambda: _bodypart_dialog.destroy()).pack(pady=(8, 0))