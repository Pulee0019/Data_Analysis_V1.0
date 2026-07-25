import tkinter as tk
from tkinter import ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from infrastructure.logger import log_message

_deps = {}

def bind_bodypart_dependencies(deps):
    _deps.clear()
    _deps.update(deps)
    globals().update(deps)

def create_visualization_window(parent=None):
    """Create the bodyparts location visualization window"""
    global visualization_window, parsed_data, central_label
    
    if 'parsed_data' not in globals() or not parsed_data:
        log_message("Please load the behavior data file first", "WARNING")
        return
    
    # If the window already exists, close it first
    if visualization_window:
        visualization_window.close_window()
    
    # Use notebook tab if available
    if parent is None:
        try:
            from ui.view_controller import _notebook, _add_tab
            if _notebook is not None and _notebook.winfo_exists():
                parent = _add_tab(_notebook, "Bodyparts")
            else:
                parent = central_display_frame
        except Exception:
            parent = central_display_frame
    
    # Create a new visualization window
    visualization_window = BodypartVisualizationWindow(parent, parsed_data)

def create_trajectory_pointcloud():
    """Create the trajectory point cloud visualization window"""
    global parsed_data, selected_bodyparts, central_label, show_data_points_var
    
    if 'parsed_data' not in globals() or not parsed_data:
        log_message("Please load the behavior data file first", "WARNING")
        return
    
    if not selected_bodyparts:
        log_message("Please select the bodyparts to display the trajectory first", "WARNING")
        return
    
    # Hide the default label in the central display area
    if 'central_label' in globals():
        central_label.pack_forget()
    
    # Clear the central display area
    for widget in central_display_frame.winfo_children():
        widget.destroy()
    
    # Create a matplotlib figure
    fig = Figure(figsize=(10, 8), dpi=100)
    ax = fig.add_subplot(111)
    
    # Set figure properties
    ax.set_title("🌟 Trajectory Point Cloud Visualization", fontsize=16, fontweight='bold', color='#2c3e50', pad=20)
    ax.set_xlabel("X Coordinate", fontsize=12, fontweight='bold', color='#2c3e50')
    ax.set_ylabel("Y Coordinate", fontsize=12, fontweight='bold', color='#2c3e50')
    ax.grid(True, alpha=0.3, linestyle='--', color='#bdc3c7')
    ax.set_facecolor('#ffffff')
    
    # Use the same color configuration as the buttons
    colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', 
             '#1abc9c', '#e67e22', '#34495e', '#f1c40f', '#95a5a6']
    
    # Get the list of all bodyparts (in the same order as when the buttons were created)
    all_bodyparts = list(parsed_data.keys())
    
    # Plot the trajectory point cloud for the selected bodyparts
    for bodypart in selected_bodyparts:
        if bodypart in parsed_data:
            data = parsed_data[bodypart]
            x_data = data['x']
            y_data = data['y']
            
            # Downsample by a factor of 2
            step = 2
            x_sampled = x_data[::step]
            y_sampled = y_data[::step]
            
            # Get the corresponding color based on the bodypart's index in the original list (consistent with button colors)
            bodypart_index = all_bodyparts.index(bodypart)
            color = colors[bodypart_index % len(colors)]
            
            # Plot the trajectory lines
            ax.plot(x_sampled, y_sampled, color='lightgray', linewidth=0.5, alpha=0.3)

            # Plot the point cloud based on the checkbox state
            if show_data_points_var and show_data_points_var.get():
                # Plot the point cloud with 70% opacity
                ax.scatter(x_sampled, y_sampled, s=10, alpha=0.7, 
                          color=color, edgecolors='white', linewidth=0.5, 
                          label=f'{bodypart} ({len(x_sampled)} points)')
            else:
                # Only show the trajectory line, not the points, but still need to add a legend entry
                ax.plot([], [], color=color, linewidth=2, label=f'{bodypart} trajectory')
    
    # Set axis limits
    if selected_bodyparts:
        all_x = []
        all_y = []
        for bodypart in selected_bodyparts:
            if bodypart in parsed_data:
                all_x.extend(parsed_data[bodypart]['x'])
                all_y.extend(parsed_data[bodypart]['y'])
        
        if all_x and all_y:
            margin_x = (max(all_x) - min(all_x)) * 0.1
            margin_y = (max(all_y) - min(all_y)) * 0.1
            ax.set_xlim(min(all_x) - margin_x, max(all_x) + margin_x)
            ax.set_ylim(min(all_y) - margin_y, max(all_y) + margin_y)
    
    # Add legend
    ax.legend(loc='upper right', framealpha=0.9, fontsize=10)
    
    # Set axis style
    ax.tick_params(colors='#2c3e50', labelsize=10)
    for spine in ax.spines.values():
        spine.set_color('#bdc3c7')
        spine.set_linewidth(1)
    
    # Create canvas and add to central display area
    canvas = FigureCanvasTkAgg(fig, central_display_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    # Create control panel
    control_frame = tk.Frame(central_display_frame, bg='#f8f8f8', height=50)
    control_frame.pack(fill=tk.X, side=tk.BOTTOM)
    control_frame.pack_propagate(False)
    
    # Add close button
    close_btn = tk.Button(control_frame, text="❌ Close Point Cloud", 
                         command=lambda: close_pointcloud_window(),
                         bg='#e74c3c', fg='white', font=('Arial', 10, 'bold'),
                         relief=tk.FLAT, padx=15, pady=5)
    close_btn.pack(side=tk.RIGHT, padx=10, pady=10)

    # Add show/hide data points checkbox
    if show_data_points_var is None:
        show_data_points_var = tk.BooleanVar(value=True)

    show_points_check = tk.Checkbutton(control_frame, text="Show Data Points", 
                                       variable=show_data_points_var, 
                                       command=create_trajectory_pointcloud,
                                       bg='#f8f8f8', font=('Arial', 10))
    show_points_check.pack(side=tk.RIGHT, padx=10)
    
    # Add information label
    info_label = tk.Label(control_frame, 
                         text=f"Displaying trajectory point cloud for {len(selected_bodyparts)} bodyparts",
                         bg='#f8f8f8', fg='#2c3e50', font=('Arial', 10))
    info_label.pack(side=tk.LEFT, padx=10, pady=10)
    
    log_message(f"Trajectory point cloud display completed - {len(selected_bodyparts)} bodyparts displayed")

def close_pointcloud_window():
    """Close the trajectory point cloud window and restore the visualization window"""
    global visualization_window, parsed_data
    
    # Clear the central display area
    for widget in central_display_frame.winfo_children():
        widget.destroy()
    
    # If data is available, restore the visualization window
    if 'parsed_data' in globals() and parsed_data:
        visualization_window = BodypartVisualizationWindow(central_display_frame, parsed_data)
        log_message("Bodyparts location visualization restored")
    else:
        # If no data, show the default label
        central_label = tk.Label(central_display_frame, text="Central Display Area\nThe bodyparts location visualization window will be displayed after loading the CSV file", bg="#f8f8f8", fg="#666666")
        central_label.pack(pady=20)
        log_message("Trajectory point cloud closed")

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
    
    log_message("Skeleton building mode: Click bodyparts to create connections\n")
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
    if visualization_window:
        visualization_window.update_plot_optimized()

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

_bodypart_dialog = None

def create_bodypart_buttons(bodyparts):
    """Open a dialog for bodypart/keypoint selection (Req 2: dialog, not in left_frame)"""
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
    _bodypart_dialog.geometry("340x620")
    _bodypart_dialog.transient(root)
    _bodypart_dialog.grab_set()

    container = tk.Frame(_bodypart_dialog, bg="#e0e0e0", padx=12, pady=12)
    container.pack(fill=tk.BOTH, expand=True)

    # Define color configuration (consistent with visualization window)
    colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6',
             '#1abc9c', '#e67e22', '#34495e', '#f1c40f', '#95a5a6']

    # Bodypart title
    tk.Label(container, text="Bodyparts:", font=("Microsoft YaHei", 12, "bold"),
             bg="#e0e0e0", fg="#2c3e50").pack(pady=(0, 8))

    # Scrollable area for bodypart buttons
    canvas = tk.Canvas(container, bg="#e0e0e0", highlightthickness=0, height=200)
    scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
    bp_frame = tk.Frame(canvas, bg="#e0e0e0")
    bp_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=bp_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

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
