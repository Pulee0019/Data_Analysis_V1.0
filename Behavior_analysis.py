import tkinter as tk
from tkinter import ttk
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from logger import log_message

def position_analysis(parsed_data, selected_bodyparts, root):
    """Position analysis function"""
    if not parsed_data:
        log_message("Please read behavioral data file first", "WARNING")
        return
    
    if not selected_bodyparts:
        log_message("Please select bodyparts to analyze first", "WARNING")
        return
    
    # Create new popup window
    analysis_window = tk.Toplevel(root)
    analysis_window.title("Position Analysis Results")
    analysis_window.geometry("1000x700")
    analysis_window.resizable(True, True)
    
    # Window title
    title_label = tk.Label(analysis_window, text="Position Analysis Results", font=("Arial", 16, "bold"))
    title_label.pack(pady=10)
    
    # Create main container
    main_frame = tk.Frame(analysis_window)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # Left statistics frame
    left_frame = tk.Frame(main_frame)
    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 10))
    
    # Create scrollable text box to display analysis results
    text_frame = tk.Frame(left_frame)
    text_frame.pack(fill=tk.BOTH, expand=True)
    
    scrollbar = tk.Scrollbar(text_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    text_widget = tk.Text(text_frame, yscrollcommand=scrollbar.set, wrap=tk.WORD, font=("Consolas", 10), width=40)
    text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=text_widget.yview)
    
    # Right chart frame
    right_frame = tk.Frame(main_frame)
    right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
    
    # Display position statistics for selected bodyparts
    for bodypart in selected_bodyparts:
        if bodypart in parsed_data:
            data = parsed_data[bodypart]
            x_data = data['x']
            y_data = data['y']
            
            text_widget.insert(tk.END, f"\n=== {bodypart} Position Analysis ===\n")
            text_widget.insert(tk.END, f"X Coordinate Statistics:\n")
            text_widget.insert(tk.END, f"  Mean: {np.mean(x_data):.2f}\n")
            text_widget.insert(tk.END, f"  Std Dev: {np.std(x_data):.2f}\n")
            text_widget.insert(tk.END, f"  Min: {np.min(x_data):.2f}\n")
            text_widget.insert(tk.END, f"  Max: {np.max(x_data):.2f}\n")
            
            text_widget.insert(tk.END, f"Y Coordinate Statistics:\n")
            text_widget.insert(tk.END, f"  Mean: {np.mean(y_data):.2f}\n")
            text_widget.insert(tk.END, f"  Std Dev: {np.std(y_data):.2f}\n")
            text_widget.insert(tk.END, f"  Min: {np.min(y_data):.2f}\n")
            text_widget.insert(tk.END, f"  Max: {np.max(y_data):.2f}\n")
            text_widget.insert(tk.END, f"  Data Points: {len(x_data)}\n\n")
    
    text_widget.config(state=tk.DISABLED)
    
    # Create matplotlib chart
    fig = Figure(figsize=(8, 6), dpi=100)
    
    # Create subplots
    ax1 = fig.add_subplot(211)  # X coordinate plot
    ax2 = fig.add_subplot(212)  # Y coordinate plot
    
    # Define color configuration (consistent with button colors)
    colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', 
             '#1abc9c', '#e67e22', '#34495e', '#f1c40f', '#95a5a6']
    
    # Get list of all bodyparts (maintain same order as when buttons were created)
    all_bodyparts = list(parsed_data.keys())
    
    # Plot position curves for selected bodyparts
    for bodypart in selected_bodyparts:
        if bodypart in parsed_data:
            data = parsed_data[bodypart]
            x_data = data['x']
            y_data = data['y']
            
            # Get corresponding color based on bodypart index in original list
            bodypart_index = all_bodyparts.index(bodypart)
            color = colors[bodypart_index % len(colors)]
            
            # Create time axis
            time_axis = range(len(x_data))
            
            # Plot X coordinate curve
            ax1.plot(time_axis, x_data, color=color, linewidth=2, label=f'{bodypart} X', alpha=0.8)
            
            # Plot Y coordinate curve
            ax2.plot(time_axis, y_data, color=color, linewidth=2, label=f'{bodypart} Y', alpha=0.8)
    
    # Set chart properties
    ax1.set_title('X Coordinate Over Time', fontsize=12, fontweight='bold')
    ax1.set_xlabel('Time Frame')
    ax1.set_ylabel('X Coordinate')
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    ax2.set_title('Y Coordinate Over Time', fontsize=12, fontweight='bold')
    ax2.set_xlabel('Time Frame')
    ax2.set_ylabel('Y Coordinate')
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    
    fig.tight_layout()
    
    # Embed chart in tkinter window
    canvas = FigureCanvasTkAgg(fig, right_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    # Add close button
    close_button = tk.Button(analysis_window, text="Close", command=analysis_window.destroy, width=10)
    close_button.pack(pady=10)
    
    log_message(f"Position analysis completed - Analyzed {len(selected_bodyparts)} bodyparts", "INFO")

def displacement_analysis(parsed_data, selected_bodyparts, root):
    """Displacement analysis function"""
    if not parsed_data:
        log_message("Please read behavioral data file first", "WARNING")
        return
    
    if not selected_bodyparts:
        log_message("Please select bodyparts to analyze first", "WARNING")
        return
    
    # Create new popup window
    analysis_window = tk.Toplevel(root)
    analysis_window.title("Displacement Analysis Results")
    analysis_window.geometry("1200x800")
    analysis_window.resizable(True, True)
    
    # Window title
    title_label = tk.Label(analysis_window, text="Displacement Analysis Results", font=("Arial", 16, "bold"))
    title_label.pack(pady=10)
    
    # Create control panel
    control_frame = tk.Frame(analysis_window, bg="#f0f0f0", relief=tk.RAISED, bd=1)
    control_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
    
    # Frame rate conversion settings
    fps_frame = tk.LabelFrame(control_frame, text="⏱️ Frame Rate Conversion Settings", font=("Arial", 10, "bold"), bg="#f0f0f0")
    fps_frame.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.Y)
    
    # FPS input
    fps_input_frame = tk.Frame(fps_frame, bg="#f0f0f0")
    fps_input_frame.pack(pady=5)
    tk.Label(fps_input_frame, text="FPS:", bg="#f0f0f0", font=("Arial", 9)).pack(side=tk.LEFT)
    fps_var = tk.StringVar(value="30")
    fps_entry = tk.Entry(fps_input_frame, textvariable=fps_var, width=8, font=("Arial", 9))
    fps_entry.pack(side=tk.LEFT, padx=(5, 0))
    
    # Time unit selection
    time_unit_frame = tk.Frame(fps_frame, bg="#f0f0f0")
    time_unit_frame.pack(pady=5)
    tk.Label(time_unit_frame, text="Time Unit:", bg="#f0f0f0", font=("Arial", 9)).pack(side=tk.LEFT)
    time_unit_var = tk.StringVar(value="Seconds")
    time_unit_combo = ttk.Combobox(time_unit_frame, textvariable=time_unit_var, values=["Seconds", "Minutes"], width=6, state="readonly")
    time_unit_combo.pack(side=tk.LEFT, padx=(5, 0))
    
    # Enable frame rate conversion checkbox
    fps_conversion_var = tk.BooleanVar()
    fps_checkbox = tk.Checkbutton(fps_frame, text="Enable Frame Rate Conversion", variable=fps_conversion_var, bg="#f0f0f0", font=("Arial", 9))
    fps_checkbox.pack(pady=5)
    
    # Zoom window settings
    zoom_frame = tk.LabelFrame(control_frame, text="🔍 Zoom Window", font=("Arial", 10, "bold"), bg="#f0f0f0")
    zoom_frame.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.Y)
    
    # Start position input
    start_frame = tk.Frame(zoom_frame, bg="#f0f0f0")
    start_frame.pack(pady=5)
    tk.Label(start_frame, text="Start:", bg="#f0f0f0", font=("Arial", 9)).pack(side=tk.LEFT)
    start_var = tk.StringVar(value="0")
    start_entry = tk.Entry(start_frame, textvariable=start_var, width=10, font=("Arial", 9))
    start_entry.pack(side=tk.LEFT, padx=(5, 0))
    
    # End position input
    end_frame = tk.Frame(zoom_frame, bg="#f0f0f0")
    end_frame.pack(pady=5)
    tk.Label(end_frame, text="End:", bg="#f0f0f0", font=("Arial", 9)).pack(side=tk.LEFT)
    end_var = tk.StringVar(value="")
    end_entry = tk.Entry(end_frame, textvariable=end_var, width=10, font=("Arial", 9))
    end_entry.pack(side=tk.LEFT, padx=(5, 0))
    
    # Enable zoom checkbox
    zoom_enabled_var = tk.BooleanVar()
    zoom_checkbox = tk.Checkbutton(zoom_frame, text="Enable Zoom", variable=zoom_enabled_var, bg="#f0f0f0", font=("Arial", 9))
    zoom_checkbox.pack(pady=5)
    
    # Apply settings button
    apply_frame = tk.Frame(control_frame, bg="#f0f0f0")
    apply_frame.pack(side=tk.RIGHT, padx=10, pady=10)
    
    def apply_settings():
        """Apply settings and update chart"""
        update_analysis()
    
    apply_btn = tk.Button(apply_frame, text="Apply Settings", command=apply_settings, 
                         bg="#3498db", fg="white", font=("Arial", 10, "bold"),
                         relief=tk.FLAT, padx=15, pady=5, cursor="hand2")
    apply_btn.pack()
    
    # Create main container
    main_frame = tk.Frame(analysis_window)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # Left statistics frame
    left_frame = tk.Frame(main_frame)
    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 10))
    
    # Create scrollable text box to display analysis results
    text_frame = tk.Frame(left_frame)
    text_frame.pack(fill=tk.BOTH, expand=True)
    
    scrollbar = tk.Scrollbar(text_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    text_widget = tk.Text(text_frame, yscrollcommand=scrollbar.set, wrap=tk.WORD, font=("Consolas", 10), width=40)
    text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=text_widget.yview)
    
    # Right chart frame
    right_frame = tk.Frame(main_frame)
    right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
    
    # Create matplotlib chart
    fig = Figure(figsize=(8, 6), dpi=100)
    ax = fig.add_subplot(111)
    
    # Embed chart in tkinter window
    canvas = FigureCanvasTkAgg(fig, right_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    def frame_to_time(frame_index, fps):
        """Convert frame index to time"""
        time_seconds = frame_index / fps
        time_unit = time_unit_var.get()
        if time_unit == "Minutes":
            return time_seconds / 60
        else:
            return time_seconds
    
    def time_to_frame(time_value, fps):
        """Convert time to frame index"""
        time_unit = time_unit_var.get()
        if time_unit == "Minutes":
            time_seconds = time_value * 60
        else:
            time_seconds = time_value
        return int(time_seconds * fps)
    
    def get_time_range():
        """Get time range"""
        try:
            if zoom_enabled_var.get():
                start_val = start_var.get().strip()
                end_val = end_var.get().strip()
                
                if fps_conversion_var.get():
                    # When frame rate conversion is enabled, input is time
                    fps = float(fps_var.get())
                    start_frame = time_to_frame(float(start_val), fps) if start_val else 0
                    
                    # Calculate maximum frames
                    max_frames = min([len(parsed_data[bp]['x']) for bp in selected_bodyparts]) - 1
                    end_frame = time_to_frame(float(end_val), fps) if end_val else max_frames
                else:
                    # When frame rate conversion is disabled, input is frame numbers
                    start_frame = int(float(start_val)) if start_val else 0
                    max_frames = min([len(parsed_data[bp]['x']) for bp in selected_bodyparts]) - 1
                    end_frame = int(float(end_val)) if end_val else max_frames
                
                # Ensure valid range
                max_frames = min([len(parsed_data[bp]['x']) for bp in selected_bodyparts]) - 1
                start_frame = max(0, min(start_frame, max_frames))
                end_frame = max(start_frame, min(end_frame, max_frames))
                
                return start_frame, end_frame
            else:
                # Zoom not enabled, use all data
                max_frames = min([len(parsed_data[bp]['x']) for bp in selected_bodyparts]) - 1
                return 0, max_frames
        except ValueError:
            log_message("Please enter valid values", "ERROR")
            return None, None
    
    def update_analysis():
        """Update analysis results and chart"""
        # Clear text box
        text_widget.config(state=tk.NORMAL)
        text_widget.delete(1.0, tk.END)
        
        # Get time range
        start_frame, end_frame = get_time_range()
        if start_frame is None or end_frame is None:
            return
        
        # Clear chart
        ax.clear()
        
        # Define color configuration (consistent with button colors)
        colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', 
                 '#1abc9c', '#e67e22', '#34495e', '#f1c40f', '#95a5a6']
        
        # Get list of all bodyparts (maintain same order as when buttons were created)
        all_bodyparts = list(parsed_data.keys())
        
        # Calculate and display displacement statistics for selected bodyparts
        for bodypart in selected_bodyparts:
            if bodypart in parsed_data:
                data = parsed_data[bodypart]
                x_data = data['x'][start_frame:end_frame+1]
                y_data = data['y'][start_frame:end_frame+1]
                
                # Calculate displacement
                if len(x_data) > 1:
                    dx = np.diff(x_data)
                    dy = np.diff(y_data)
                    displacement = np.sqrt(dx**2 + dy**2)
                    
                    text_widget.insert(tk.END, f"\n=== {bodypart} Displacement Analysis ===\n")
                    if zoom_enabled_var.get():
                        if fps_conversion_var.get():
                            fps = float(fps_var.get())
                            start_time = frame_to_time(start_frame, fps)
                            end_time = frame_to_time(end_frame, fps)
                            time_unit = time_unit_var.get()
                            text_widget.insert(tk.END, f"Analysis Range: {start_time:.2f}-{end_time:.2f} {time_unit}\n")
                        else:
                            text_widget.insert(tk.END, f"Analysis Range: Frames {start_frame}-{end_frame}\n")
                    text_widget.insert(tk.END, f"Displacement Statistics:\n")
                    text_widget.insert(tk.END, f"  Mean Displacement: {np.mean(displacement):.2f}\n")
                    text_widget.insert(tk.END, f"  Displacement Std Dev: {np.std(displacement):.2f}\n")
                    text_widget.insert(tk.END, f"  Max Displacement: {np.max(displacement):.2f}\n")
                    text_widget.insert(tk.END, f"  Min Displacement: {np.min(displacement):.2f}\n")
                    text_widget.insert(tk.END, f"  Total Displacement: {np.sum(displacement):.2f}\n")
                    text_widget.insert(tk.END, f"  Displacement Data Points: {len(displacement)}\n\n")
                else:
                    text_widget.insert(tk.END, f"\n=== {bodypart} ===\n")
                    text_widget.insert(tk.END, f"Insufficient data points to calculate displacement\n\n")
        
        # Plot displacement curves for selected bodyparts
        for bodypart in selected_bodyparts:
            if bodypart in parsed_data:
                data = parsed_data[bodypart]
                x_data = data['x'][start_frame:end_frame+1]
                y_data = data['y'][start_frame:end_frame+1]
                
                # Calculate displacement
                if len(x_data) > 1:
                    dx = np.diff(x_data)
                    dy = np.diff(y_data)
                    displacement = np.sqrt(dx**2 + dy**2)
                    
                    # Get corresponding color based on bodypart index in original list
                    bodypart_index = all_bodyparts.index(bodypart)
                    color = colors[bodypart_index % len(colors)]
                    
                    # Create time axis
                    if fps_conversion_var.get():
                        fps = float(fps_var.get())
                        time_axis = [frame_to_time(start_frame + i, fps) for i in range(len(displacement))]
                        time_unit = time_unit_var.get()
                        xlabel = f'Time ({time_unit})'
                    else:
                        time_axis = range(start_frame, start_frame + len(displacement))
                        xlabel = 'Time Frame'
                    
                    # Plot displacement curve
                    ax.plot(time_axis, displacement, color=color, linewidth=2, 
                           label=f'{bodypart}', alpha=0.8, marker='o', markersize=2)
        
        # Set chart properties
        ax.set_title('Displacement Over Time', fontsize=14, fontweight='bold')
        ax.set_xlabel(xlabel if 'xlabel' in locals() else 'Time Frame', fontsize=12)
        ax.set_ylabel('Displacement Distance', fontsize=12)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.legend()
        
        fig.tight_layout()
        canvas.draw()
        
        text_widget.config(state=tk.DISABLED)
    
    # Initialize display
    # Set default end value
    max_frames = min([len(parsed_data[bp]['x']) for bp in selected_bodyparts]) - 1
    end_var.set(str(max_frames))
    
    # Initial update
    update_analysis()
    
    # Add close button
    close_button = tk.Button(analysis_window, text="Close", command=analysis_window.destroy, width=10)
    close_button.pack(pady=10)
    
    log_message(f"Displacement analysis completed - Analyzed {len(selected_bodyparts)} bodyparts", "INFO")

def x_displacement_analysis(parsed_data, selected_bodyparts, root):
    """X displacement analysis function"""
    if not parsed_data:
        log_message("Please read behavioral data file first", "WARNING")
        return
    
    if not selected_bodyparts:
        log_message("Please select bodyparts to analyze first", "WARNING")
        return
    
    # Create new popup window
    analysis_window = tk.Toplevel(root)
    analysis_window.title("X Displacement Analysis Results")
    analysis_window.geometry("1200x800")
    analysis_window.resizable(True, True)
    
    # Window title
    title_label = tk.Label(analysis_window, text="X Displacement Analysis Results", font=("Arial", 16, "bold"))
    title_label.pack(pady=10)
    
    # Create control panel
    control_frame = tk.Frame(analysis_window, bg="#f0f0f0", relief=tk.RAISED, bd=1)
    control_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
    
    # Frame rate conversion settings
    fps_frame = tk.LabelFrame(control_frame, text="⏱️ Frame Rate Conversion Settings", font=("Arial", 10, "bold"), bg="#f0f0f0")
    fps_frame.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.Y)
    
    # FPS input
    fps_input_frame = tk.Frame(fps_frame, bg="#f0f0f0")
    fps_input_frame.pack(pady=5)
    tk.Label(fps_input_frame, text="FPS:", bg="#f0f0f0", font=("Arial", 9)).pack(side=tk.LEFT)
    fps_var = tk.StringVar(value="30")
    fps_entry = tk.Entry(fps_input_frame, textvariable=fps_var, width=8, font=("Arial", 9))
    fps_entry.pack(side=tk.LEFT, padx=(5, 0))
    
    # Time unit selection
    time_unit_frame = tk.Frame(fps_frame, bg="#f0f0f0")
    time_unit_frame.pack(pady=5)
    tk.Label(time_unit_frame, text="Time Unit:", bg="#f0f0f0", font=("Arial", 9)).pack(side=tk.LEFT)
    time_unit_var = tk.StringVar(value="s")
    time_unit_combo = ttk.Combobox(time_unit_frame, textvariable=time_unit_var, 
                                  values=["s", "ms", "min"], width=6, font=("Arial", 9))
    time_unit_combo.pack(side=tk.LEFT, padx=(5, 0))
    time_unit_combo.state(['readonly'])
    
    # Enable frame rate conversion checkbox
    fps_conversion_var = tk.BooleanVar()
    fps_conversion_check = tk.Checkbutton(fps_frame, text="Enable Frame Rate Conversion", variable=fps_conversion_var,
                                        bg="#f0f0f0", font=("Arial", 9))
    fps_conversion_check.pack(pady=5)
    
    # Zoom window settings
    zoom_frame = tk.LabelFrame(control_frame, text="🔍 Zoom Window", font=("Arial", 10, "bold"), bg="#f0f0f0")
    zoom_frame.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.Y)
    
    # Start position input
    start_frame_frame = tk.Frame(zoom_frame, bg="#f0f0f0")
    start_frame_frame.pack(pady=5)
    tk.Label(start_frame_frame, text="Start:", bg="#f0f0f0", font=("Arial", 9)).pack(side=tk.LEFT)
    start_var = tk.StringVar(value="0")
    start_entry = tk.Entry(start_frame_frame, textvariable=start_var, width=10, font=("Arial", 9))
    start_entry.pack(side=tk.LEFT, padx=(5, 0))
    
    # End position input
    end_frame_frame = tk.Frame(zoom_frame, bg="#f0f0f0")
    end_frame_frame.pack(pady=5)
    tk.Label(end_frame_frame, text="End:", bg="#f0f0f0", font=("Arial", 9)).pack(side=tk.LEFT)
    end_var = tk.StringVar(value="100")
    end_entry = tk.Entry(end_frame_frame, textvariable=end_var, width=10, font=("Arial", 9))
    end_entry.pack(side=tk.LEFT, padx=(5, 0))
    
    # Enable zoom checkbox
    zoom_enabled_var = tk.BooleanVar()
    zoom_enabled_check = tk.Checkbutton(zoom_frame, text="Enable Zoom", variable=zoom_enabled_var,
                                      bg="#f0f0f0", font=("Arial", 9))
    zoom_enabled_check.pack(pady=5)
    
    # Apply settings button
    apply_frame = tk.Frame(control_frame, bg="#f0f0f0")
    apply_frame.pack(side=tk.RIGHT, padx=10, pady=10)
    
    def frame_to_time(frame, fps):
        """Convert frames to time"""
        time_in_seconds = frame / fps
        time_unit = time_unit_var.get()
        if time_unit == "ms":
            return time_in_seconds * 1000
        elif time_unit == "min":
            return time_in_seconds / 60
        else:  # seconds
            return time_in_seconds
    
    def time_to_frame(time_value, fps):
        """Convert time to frames"""
        time_unit = time_unit_var.get()
        if time_unit == "ms":
            time_in_seconds = time_value / 1000
        elif time_unit == "min":
            time_in_seconds = time_value * 60
        else:  # seconds
            time_in_seconds = time_value
        return int(time_in_seconds * fps)
    
    def get_time_range():
        """Get time range"""
        try:
            if zoom_enabled_var.get():
                if fps_conversion_var.get():
                    # Time mode
                    fps = float(fps_var.get())
                    start_time = float(start_var.get())
                    end_time = float(end_var.get())
                    start_frame = time_to_frame(start_time, fps)
                    end_frame = time_to_frame(end_time, fps)
                else:
                    # Frame mode
                    start_frame = int(start_var.get())
                    end_frame = int(end_var.get())
            else:
                # Full range
                start_frame = 0
                end_frame = min([len(parsed_data[bp]['x']) for bp in selected_bodyparts]) - 1
            
            # Validate range
            max_frames = min([len(parsed_data[bp]['x']) for bp in selected_bodyparts]) - 1
            start_frame = max(0, min(start_frame, max_frames))
            end_frame = max(start_frame, min(end_frame, max_frames))
            
            return start_frame, end_frame
        except ValueError:
            log_message("Please enter valid values", "ERROR")
            return None, None
    
    def apply_settings():
        """Apply settings and update chart"""
        update_analysis()
    
    apply_btn = tk.Button(apply_frame, text="Apply Settings", command=apply_settings, 
                         bg="#3498db", fg="white", font=("Arial", 10, "bold"),
                         relief=tk.FLAT, padx=15, pady=5, cursor="hand2")
    apply_btn.pack()
    
    # Create main container
    main_frame = tk.Frame(analysis_window)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # Left statistics frame
    left_frame = tk.Frame(main_frame)
    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 10))
    
    # Create scrollable text box to display analysis results
    text_frame = tk.Frame(left_frame)
    text_frame.pack(fill=tk.BOTH, expand=True)
    
    scrollbar = tk.Scrollbar(text_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    text_widget = tk.Text(text_frame, yscrollcommand=scrollbar.set, wrap=tk.WORD, font=("Consolas", 10), width=40)
    text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=text_widget.yview)
    
    # Right chart frame
    right_frame = tk.Frame(main_frame)
    right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
    
    # Create matplotlib chart
    fig = Figure(figsize=(8, 6), dpi=100)
    ax = fig.add_subplot(111)
    
    # Embed chart in tkinter window
    canvas = FigureCanvasTkAgg(fig, right_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    def update_analysis():
        """Update analysis results and chart"""
        # Clear text box
        text_widget.config(state=tk.NORMAL)
        text_widget.delete(1.0, tk.END)
        
        # Get time range
        start_frame, end_frame = get_time_range()
        if start_frame is None or end_frame is None:
            return
        
        # Clear chart
        ax.clear()
        
        # Define color configuration (consistent with button colors)
        colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', 
                 '#1abc9c', '#e67e22', '#34495e', '#f1c40f', '#95a5a6']
        
        # Get list of all bodyparts (maintain same order as when buttons were created)
        all_bodyparts = list(parsed_data.keys())
        
        # Calculate and display X displacement statistics for selected bodyparts
        for bodypart in selected_bodyparts:
            if bodypart in parsed_data:
                data = parsed_data[bodypart]
                x_data = data['x'][start_frame:end_frame+1]
                
                # Calculate X displacement (next frame minus previous frame)
                if len(x_data) > 1:
                    x_displacement = np.diff(x_data)  # Next frame minus previous frame
                    
                    text_widget.insert(tk.END, f"\n=== {bodypart} X Displacement Analysis ===\n")
                    if zoom_enabled_var.get():
                        if fps_conversion_var.get():
                            fps = float(fps_var.get())
                            start_time = frame_to_time(start_frame, fps)
                            end_time = frame_to_time(end_frame, fps)
                            time_unit = time_unit_var.get()
                            text_widget.insert(tk.END, f"Analysis Range: {start_time:.2f}-{end_time:.2f} {time_unit}\n")
                        else:
                            text_widget.insert(tk.END, f"Analysis Range: Frames {start_frame}-{end_frame}\n")
                    text_widget.insert(tk.END, f"X Displacement Statistics:\n")
                    text_widget.insert(tk.END, f"  Mean X Displacement: {np.mean(x_displacement):.2f}\n")
                    text_widget.insert(tk.END, f"  X Displacement Std Dev: {np.std(x_displacement):.2f}\n")
                    text_widget.insert(tk.END, f"  Max X Displacement: {np.max(x_displacement):.2f}\n")
                    text_widget.insert(tk.END, f"  Min X Displacement: {np.min(x_displacement):.2f}\n")
                    text_widget.insert(tk.END, f"  Positive X Displacement Sum: {np.sum(x_displacement[x_displacement > 0]):.2f}\n")
                    text_widget.insert(tk.END, f"  Negative X Displacement Sum: {np.sum(x_displacement[x_displacement < 0]):.2f}\n")
                    text_widget.insert(tk.END, f"  Net X Displacement: {np.sum(x_displacement):.2f}\n")
                    text_widget.insert(tk.END, f"  X Displacement Data Points: {len(x_displacement)}\n\n")
                else:
                    text_widget.insert(tk.END, f"\n=== {bodypart} ===\n")
                    text_widget.insert(tk.END, f"Insufficient data points to calculate X displacement\n\n")
        
        # Plot X displacement curves for selected bodyparts
        for bodypart in selected_bodyparts:
            if bodypart in parsed_data:
                data = parsed_data[bodypart]
                x_data = data['x'][start_frame:end_frame+1]
                
                # Calculate X displacement
                if len(x_data) > 1:
                    x_displacement = np.diff(x_data)
                    
                    # Get corresponding color based on bodypart index in original list
                    bodypart_index = all_bodyparts.index(bodypart)
                    color = colors[bodypart_index % len(colors)]
                    
                    # Create time axis
                    if fps_conversion_var.get():
                        fps = float(fps_var.get())
                        time_axis = [frame_to_time(start_frame + i, fps) for i in range(len(x_displacement))]
                        time_unit = time_unit_var.get()
                        xlabel = f'Time ({time_unit})'
                    else:
                        time_axis = range(start_frame, start_frame + len(x_displacement))
                        xlabel = 'Time Frame'
                    
                    # Plot X displacement curve
                    ax.plot(time_axis, x_displacement, color=color, linewidth=2, 
                           label=f'{bodypart}', alpha=0.8, marker='o', markersize=2)
        
        # Add zero reference line
        if fps_conversion_var.get():
            fps = float(fps_var.get())
            time_axis_full = [frame_to_time(start_frame + i, fps) for i in range(end_frame - start_frame)]
            if time_axis_full:
                ax.axhline(y=0, color='black', linestyle='--', alpha=0.5, linewidth=1)
        else:
            ax.axhline(y=0, color='black', linestyle='--', alpha=0.5, linewidth=1)
        
        # Set chart properties
        ax.set_title('X Displacement Over Time', fontsize=14, fontweight='bold')
        ax.set_xlabel(xlabel if 'xlabel' in locals() else 'Time Frame', fontsize=12)
        ax.set_ylabel('X Displacement Distance', fontsize=12)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.legend()
        
        fig.tight_layout()
        canvas.draw()
        
        text_widget.config(state=tk.DISABLED)
    
    # Initialize display
    # Set default end value
    max_frames = min([len(parsed_data[bp]['x']) for bp in selected_bodyparts]) - 1
    end_var.set(str(max_frames))
    
    # Initial update
    update_analysis()
    
    # Add close button
    close_button = tk.Button(analysis_window, text="Close", command=analysis_window.destroy, width=10)
    close_button.pack(pady=10)
    
    log_message(f"X displacement analysis completed - Analyzed {len(selected_bodyparts)} bodyparts", "INFO")

# Reserved space for adding more analysis algorithms
# TODO: Add more analysis functions here
# For example:
# - Velocity analysis
# - Acceleration analysis
# - Trajectory analysis
# - Behavioral pattern recognition
# - Statistical analysis
# - Machine learning analysis