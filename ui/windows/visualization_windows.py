import threading
import time
import tkinter as tk
from tkinter import filedialog, ttk

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from infrastructure.logger import log_message
from analysis_multimodal.Multimodal_analysis import identify_drug_sessions, identify_optogenetic_events

EXPERIMENT_MODE_FIBER_AST2_DLC = "fiber+ast2+dlc"

_deps = {}

def bind_window_dependencies(deps):
    _deps.clear()
    _deps.update(deps)
    globals().update(deps)

class BodypartVisualizationWindow:
    def __init__(self, parent_frame, data):
        self.parent_frame = parent_frame
        self.data = data
        self.current_frame = 0
        self.total_frames = 0
        self.is_playing = False
        self.fps = 10
        self.play_thread = None
        
        if current_experiment_mode == EXPERIMENT_MODE_FIBER_AST2_DLC:
            self.window_width = 800
            self.window_height = 870
        else:
            self.window_width = 0
            self.window_height = 0

        self.is_minimized = False
        
        self.pan_start = None
        self.zoom_factor = 1.0
        self.original_xlim = None
        self.original_ylim = None
        self.is_panning = False
        
        if data:
            self.total_frames = min([len(bodypart_data['x']) for bodypart_data in data.values()])
        
        self.create_window()
        
    def create_window(self):
        self.window_frame = tk.Frame(self.parent_frame, bg="#f5f5f5", relief=tk.RAISED, bd=1)
        self.window_frame.place(x=0, y=0, width=self.window_width, height=self.window_height)
        
        self.window_frame.bind("<Button-1>", self.start_move)
        self.window_frame.bind("<B1-Motion>", self.do_move)
        
        title_frame = tk.Frame(self.window_frame, bg="#f5f5f5", height=25)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        title_frame.bind("<Button-1>", self.start_move)
        title_frame.bind("<B1-Motion>", self.do_move)
        
        title_label = tk.Label(title_frame, text="Bodyparts Position Visualization", bg="#f5f5f5", fg="#666666", 
                              font=("Microsoft YaHei", 10, "bold"))
        title_label.pack(side=tk.LEFT, padx=10, pady=3)
        title_label.bind("<Button-1>", self.start_move)
        title_label.bind("<B1-Motion>", self.do_move)
        
        # Window control buttons
        btn_frame = tk.Frame(title_frame, bg="#f5f5f5")
        btn_frame.pack(side=tk.RIGHT, padx=5, pady=2)
        
        # Minimize button
        minimize_btn = tk.Button(btn_frame, text="−", bg="#f5f5f5", fg="#999999", bd=0, 
                               font=("Arial", 8), width=2, height=1,
                               command=self.minimize_window, relief=tk.FLAT)
        minimize_btn.pack(side=tk.LEFT, padx=1)
        
        # Close button
        close_btn = tk.Button(btn_frame, text="×", bg="#f5f5f5", fg="#999999", bd=0, 
                             font=("Arial", 8), width=2, height=1,
                             command=self.close_window, relief=tk.FLAT)
        close_btn.pack(side=tk.LEFT, padx=1)

        reset_view_btn = tk.Button(btn_frame, text="🗘", bg="#f5f5f5", fg="#999999", bd=0,
                                 font=("Arial", 8), width=2, height=1,
                                 command=self.reset_view, relief=tk.FLAT)
        reset_view_btn.pack(side=tk.LEFT, padx=1)
        
        # Add window resize control point
        resize_frame = tk.Frame(self.window_frame, bg="#bdc3c7", width=15, height=15)
        resize_frame.place(relx=1.0, rely=1.0, anchor="se")
        resize_frame.bind("<Button-1>", self.start_resize)
        resize_frame.bind("<B1-Motion>", self.do_resize)
        resize_frame.config(cursor="sizing")
        
        # Create matplotlib figure - with better color scheme
        self.fig = Figure(figsize=(7, 4.5), dpi=90, facecolor='#f8f9fa')
        self.ax = self.fig.add_subplot(111, facecolor='#ffffff')
        
        # Create canvas frame - add shadow effect
        canvas_frame = tk.Frame(self.window_frame, bg="#f5f5f5", relief=tk.SUNKEN, bd=1)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        
        self.canvas = FigureCanvasTkAgg(self.fig, canvas_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        self.canvas.mpl_connect('button_press_event', self.on_press)
        self.canvas.mpl_connect('button_release_event', self.on_release)
        self.canvas.mpl_connect('motion_notify_event', self.on_motion)
        self.canvas.mpl_connect('scroll_event', self.on_scroll)
        
        # Control panel - modern design
        control_frame = tk.Frame(self.window_frame, bg="#ecf0f1", height=130, relief=tk.RAISED, bd=1)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        control_frame.pack_propagate(False)
        
        # Progress bar - modern style (moved to top)
        progress_frame = tk.Frame(control_frame, bg="#ecf0f1")
        progress_frame.pack(fill=tk.X, pady=(8, 5))
        
        tk.Label(progress_frame, text="📊 Progress:", bg="#ecf0f1", 
                font=("Microsoft YaHei", 10, "bold"), fg="#2c3e50").pack(side=tk.LEFT, padx=10)
        self.progress_var = tk.DoubleVar()
        self.progress_scale = tk.Scale(progress_frame, from_=0, to=self.total_frames-1, 
                                      orient=tk.HORIZONTAL, variable=self.progress_var,
                                      command=self.on_progress_change, font=("Microsoft YaHei", 9),
                                      bg="#ecf0f1", fg="#2c3e50", highlightthickness=0,
                                      troughcolor="#bdc3c7", activebackground="#3498db",
                                      length=200)
        self.progress_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        
        self.frame_label = tk.Label(progress_frame, text=f"0/{self.total_frames}", bg="#ecf0f1", 
                                   width=12, font=("Microsoft YaHei", 10, "bold"), fg="#2c3e50")
        self.frame_label.pack(side=tk.RIGHT, padx=10)
        
        # Buttons and FPS control on the same line
        control_row_frame = tk.Frame(control_frame, bg="#ecf0f1")
        control_row_frame.pack(pady=(5, 8))
        
        # Play control buttons - modern button style
        btn_frame = tk.Frame(control_row_frame, bg="#ecf0f1")
        btn_frame.pack(side=tk.LEFT, padx=(10, 20))
        
        self.play_btn = tk.Button(btn_frame, text="▶ Play", command=self.toggle_play,
                                 bg="#27ae60", fg="white", font=("Microsoft YaHei", 10, "bold"),
                                 relief=tk.FLAT, padx=15, pady=5, cursor="hand2", width=8)
        self.play_btn.pack(side=tk.LEFT, padx=3)
        
        self.pause_btn = tk.Button(btn_frame, text="⏸ Pause", command=self.pause,
                                  bg="#f39c12", fg="white", font=("Microsoft YaHei", 10, "bold"),
                                  relief=tk.FLAT, padx=15, pady=5, cursor="hand2", width=8)
        self.pause_btn.pack(side=tk.LEFT, padx=3)
        
        self.reset_btn = tk.Button(btn_frame, text="🔄 Reset", command=self.reset,
                                  bg="#3498db", fg="white", font=("Microsoft YaHei", 10, "bold"),
                                  relief=tk.FLAT, padx=15, pady=5, cursor="hand2", width=8)
        self.reset_btn.pack(side=tk.LEFT, padx=3)
        
        # Video export button
        self.export_btn = tk.Button(btn_frame, text="🎬 Export Video", command=self.export_video,
                                   bg="#e74c3c", fg="white", font=("Microsoft YaHei", 10, "bold"),
                                   relief=tk.FLAT, padx=15, pady=5, cursor="hand2", width=10)
        self.export_btn.pack(side=tk.LEFT, padx=3)
        
        # FPS setting - modern style (same line as buttons)
        fps_frame = tk.Frame(control_row_frame, bg="#ecf0f1")
        fps_frame.pack(side=tk.RIGHT, padx=(20, 10))
        
        tk.Label(fps_frame, text="⚡ FPS:", bg="#ecf0f1", 
                font=("Microsoft YaHei", 10, "bold"), fg="#2c3e50").pack(side=tk.LEFT, padx=(0, 5))
        self.fps_var = tk.StringVar(value=str(self.fps))
        fps_spinbox = tk.Spinbox(fps_frame, from_=1, to=120, width=6, textvariable=self.fps_var,
                                command=self.update_fps, font=("Microsoft YaHei", 10), relief=tk.FLAT,
                                bg="white", fg="#2c3e50", buttonbackground="#bdc3c7")
        fps_spinbox.pack(side=tk.LEFT, padx=5)
        tk.Label(fps_frame, text="FPS", bg="#ecf0f1", 
                font=("Microsoft YaHei", 10, "bold"), fg="#2c3e50").pack(side=tk.LEFT, padx=(5, 0))
        
        # Show first frame
        self.update_plot()
        
    def on_press(self, event):
        if event.inaxes != self.ax:
            return
            
        if event.button == 1:
            self.pan_start = (event.xdata, event.ydata)
            self.is_panning = True
            
        elif event.button == 3:
            self.on_select(event)

    def on_release(self, event):
        if event.button == 1:
            self.pan_start = None
            self.is_panning = False

    def on_motion(self, event):
        if not self.is_panning or event.inaxes != self.ax or self.pan_start is None:
            return
            
        if event.xdata is None or event.ydata is None:
            return
            
        dx = event.xdata - self.pan_start[0]
        dy = event.ydata - self.pan_start[1]
        
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        
        new_xlim = (xlim[0] - dx, xlim[1] - dx)
        new_ylim = (ylim[0] - dy, ylim[1] - dy)
        
        self.ax.set_xlim(new_xlim)
        self.ax.set_ylim(new_ylim)
        
        self.canvas.draw_idle()
        
    def on_scroll(self, event):
        if event.inaxes != self.ax:
            log_message("Scroll event outside axes, ignoring.", "WARNING")
            return
            
        try:
            current_time = getattr(self, '_last_scroll_time', 0)
            if time.time() - current_time < 0.05:
                return
            self._last_scroll_time = time.time()
            
            if event.xdata is None or event.ydata is None:
                return
                
            x, y = event.xdata, event.ydata
            xlim = self.ax.get_xlim()
            ylim = self.ax.get_ylim()
            
            if not self._is_valid_range(xlim, ylim):
                self.reset_view()
                return
            
            zoom_factor = 1.1 if event.button == 'up' else 0.9
            
            new_xlim = (x - (x - xlim[0]) * zoom_factor, 
                    x + (xlim[1] - x) * zoom_factor)
            new_ylim = (y - (y - ylim[0]) * zoom_factor, 
                    y + (ylim[1] - y) * zoom_factor)
            
            if self._is_valid_range(new_xlim, new_ylim):
                self.ax.set_xlim(new_xlim)
                self.ax.set_ylim(new_ylim)
                self.canvas.draw_idle()
                
        except Exception as e:
            log_message(f"Scroll error: {str(e)}", "WARNING")
            self.reset_view()

    def _is_valid_range(self, xlim, ylim):
        try:
            return (all(np.isfinite(xlim)) and all(np.isfinite(ylim)) and
                    xlim[1] > xlim[0] and ylim[1] > ylim[0] and
                    abs(xlim[1] - xlim[0]) > 1e-10 and
                    abs(ylim[1] - ylim[0]) > 1e-10 and
                    abs(xlim[1] - xlim[0]) < 1e10 and
                    abs(ylim[1] - ylim[0]) < 1e10)
        except:
            return False

    def on_select(self, event):
        click_x, click_y = event.xdata, event.ydata
        if click_x is None or click_y is None:
            return
        
        min_distance = float('inf')
        closest_bodypart = None
        
        for i, (bodypart, data) in enumerate(self.data.items()):
            if self.current_frame < len(data['x']) and self.current_frame < len(data['y']):
                x = data['x'][self.current_frame]
                y = data['y'][self.current_frame]
                
                distance = ((click_x - x) ** 2 + (click_y - y) ** 2) ** 0.5
                
                click_threshold = 30
                
                if distance < click_threshold and distance < min_distance:
                    min_distance = distance
                    closest_bodypart = bodypart
        
        if closest_bodypart and closest_bodypart in bodypart_buttons:
            button = bodypart_buttons[closest_bodypart]
            toggle_bodypart(closest_bodypart, button)
        
    def reset_view(self):
        """Reset the view to original zoom and pan"""
        if self.original_xlim and self.original_ylim:
            self.ax.set_xlim(self.original_xlim)
            self.ax.set_ylim(self.original_ylim)
            self.zoom_factor = 1.0
            self.canvas.draw_idle()
            log_message("DLC view reset to original", "INFO")

    def update_fps(self):
        try:
            self.fps = int(self.fps_var.get())
            # Limit FPS range to avoid performance issues with high values
            if self.fps > 120:
                self.fps = 120
                self.fps_var.set("120")
            elif self.fps < 1:
                self.fps = 1
                self.fps_var.set("1")
        except ValueError:
            self.fps = 10
            self.fps_var.set("10")
    
    def toggle_play(self):
        if self.is_playing:
            self.pause()
        else:
            self.play()
    
    def play(self):
        if not self.is_playing and self.current_frame < self.total_frames - 1:
            self.is_playing = True
            self.play_btn.config(text="Playing...")
            self.schedule_next_frame()
    
    def pause(self):
        self.is_playing = False
        try:
            self.play_btn.config(text="▶ Play")
        except tk.TclError:
            pass
        if hasattr(self, 'after_id'):
            try:
                self.window_frame.after_cancel(self.after_id)
            except tk.TclError:
                pass
    
    def reset(self):
        self.pause()
        self.current_frame = 0
        self.progress_var.set(0)
        self.update_plot()
    
    def schedule_next_frame(self):
        if not self.window_frame.winfo_exists():
            return
            
        if self.is_playing and self.current_frame < self.total_frames - 1:
            self.current_frame += 1
            self.progress_var.set(self.current_frame)
            self.update_plot_optimized()
            
            delay_ms = max(1, int(1000.0 / self.fps))
            self.after_id = self.window_frame.after(delay_ms, self.schedule_next_frame)
        else:
            self.is_playing = False
            try:
                self.play_btn.config(text="▶ Play")
            except tk.TclError:
                pass
    
    def play_animation(self):
        """Keep original method as backup, but no longer used"""
        pass
    
    def on_progress_change(self, value):
        self.current_frame = int(float(value))
        self.update_plot()
    
    def update_plot(self):
        """Original update method, keep for compatibility"""
        self.update_plot_optimized()
    
    def update_plot_optimized(self):
        """Optimized plot update method, reduce unnecessary redraw operations"""
        # Only clear data points, keep axis settings
        if not hasattr(self, '_plot_initialized'):
            self._initialize_plot()
            self._plot_initialized = True
        
        # Clear previous scatter plots
        if hasattr(self, '_scatter_plots'):
            for scatter in self._scatter_plots:
                scatter.remove()
        
        self._scatter_plots = []
        
        # Use predefined colors
        colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', 
                 '#1abc9c', '#e67e22', '#34495e', '#f1c40f', '#95a5a6']
        
        # Draw current frame data points
        for i, (bodypart, data) in enumerate(self.data.items()):
            if self.current_frame < len(data['x']) and self.current_frame < len(data['y']):
                x = data['x'][self.current_frame]
                y = data['y'][self.current_frame]
                
                # Draw point
                color = colors[i % len(colors)]
                scatter = self.ax.scatter(x, y, s=200, alpha=0.8, 
                                        color=color, edgecolors='black', linewidth=2)
                self._scatter_plots.append(scatter)
                
                # Add number inside circle
                text = self.ax.text(x, y, str(i+1), ha='center', va='center', 
                                   fontsize=8, fontweight='bold', color='black')
                self._scatter_plots.append(text)
        
        # Draw skeleton connections
        self._draw_skeleton()
        
        # Update title to show time or frame number
        if fps_conversion_enabled:
            current_time = frame_to_time(self.current_frame)
            total_time = frame_to_time(self.total_frames - 1)
            time_label = get_time_label()
            
            if time_unit_var and time_unit_var.get() == "Minutes":
                title_text = f"Bodyparts Position - {time_label}: {current_time:.2f}/{total_time:.2f}"
            else:
                title_text = f"Bodyparts Position - {time_label}: {current_time:.1f}/{total_time:.1f}"
        else:
            title_text = f"Bodyparts Position - Frame {self.current_frame + 1}/{self.total_frames}"
        
        self.ax.set_title(title_text, fontsize=12, fontweight='bold', color='#2c3e50', pad=15)
        
        # Update frame label
        if fps_conversion_enabled:
            current_time = frame_to_time(self.current_frame)
            total_time = frame_to_time(self.total_frames - 1)
            
            if time_unit_var and time_unit_var.get() == "Minutes":
                frame_text = f"{current_time:.2f}/{total_time:.2f}"
            else:
                frame_text = f"{current_time:.1f}/{total_time:.1f}"
        else:
            frame_text = f"{self.current_frame + 1}/{self.total_frames}"
        
        self.frame_label.config(text=frame_text)
        
        # Use blit for fast redraw (if supported)
        try:
            self.canvas.draw_idle()
        except:
            self.canvas.draw()
    
    def _draw_skeleton(self):
        """Draw skeleton connections"""
        global skeleton_connections
        
        if not skeleton_connections or not self.data:
            return
        
        # Draw skeleton connections
        for connection in skeleton_connections:
            bodypart1, bodypart2 = connection
            
            # Check if both bodyparts are in data
            if bodypart1 in self.data and bodypart2 in self.data:
                data1 = self.data[bodypart1]
                data2 = self.data[bodypart2]
                
                # Check if current frame is valid
                if (self.current_frame < len(data1['x']) and self.current_frame < len(data1['y']) and
                    self.current_frame < len(data2['x']) and self.current_frame < len(data2['y'])):
                    
                    x1, y1 = data1['x'][self.current_frame], data1['y'][self.current_frame]
                    x2, y2 = data2['x'][self.current_frame], data2['y'][self.current_frame]
                    
                    # Draw connection
                    line = self.ax.plot([x1, x2], [y1, y2], 'k-', linewidth=2, alpha=0.8)[0]
                    self._scatter_plots.append(line)
    
    def _initialize_plot(self):
        """Initialize static elements of the plot area"""
        self.ax.clear()
        
        # Set graph properties
        self.ax.set_xlabel("X Coordinate", fontsize=11, fontweight='bold', color='#2c3e50')
        self.ax.set_ylabel("Y Coordinate", fontsize=11, fontweight='bold', color='#2c3e50')
        
        # Set grid and background
        self.ax.grid(True, alpha=0.3, linestyle='--', color='#bdc3c7')
        self.ax.set_facecolor('#ffffff')
        
        # Set axis range and save original limits
        if self.data:
            all_x = []
            all_y = []
            for data in self.data.values():
                all_x.extend(data['x'])
                all_y.extend(data['y'])
            
            if all_x and all_y:
                margin_x = (max(all_x) - min(all_x)) * 0.1
                margin_y = (max(all_y) - min(all_y)) * 0.1
                self.original_xlim = (min(all_x) - margin_x, max(all_x) + margin_x)
                self.original_ylim = (min(all_y) - margin_y, max(all_y) + margin_y)
                self.ax.set_xlim(self.original_xlim)
                self.ax.set_ylim(self.original_ylim)
        
        # Set axis style
        self.ax.tick_params(colors='#2c3e50', labelsize=9)
        for spine in self.ax.spines.values():
            spine.set_color('#bdc3c7')
            spine.set_linewidth(1)
        
        self._scatter_plots = []
    
    def start_move(self, event):
        """Start dragging window"""
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.start_win_x = self.window_frame.winfo_x()
        self.start_win_y = self.window_frame.winfo_y()
    
    def do_move(self, event):
        """Drag window"""
        x = self.start_win_x + (event.x_root - self.start_x)
        y = self.start_win_y + (event.y_root - self.start_y)
        # Limit window from being dragged out of parent window
        parent_width = self.parent_frame.winfo_width()
        parent_height = self.parent_frame.winfo_height()
        window_width = self.window_frame.winfo_width()
        window_height = self.window_frame.winfo_height()
        
        x = max(0, min(x, parent_width - window_width))
        y = max(0, min(y, parent_height - window_height))
        
        self.window_frame.place(x=x, y=y)
    
    def minimize_window(self):
        """Minimize window"""
        if hasattr(self, 'is_minimized') and self.is_minimized:
            # Restore window
            self.window_frame.place(width=self.window_width, height=self.window_height)
            self.is_minimized = False
        else:
            # Save current window size
            self.window_width = self.window_frame.winfo_width()
            self.window_height = self.window_frame.winfo_height()
            # Minimize window
            self.window_frame.place(width=self.window_width, height=35)
            self.is_minimized = True
    
    def start_resize(self, event):
        """Start resizing window"""
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.start_width = self.window_frame.winfo_width()
        self.start_height = self.window_frame.winfo_height()
    
    def do_resize(self, event):
        """Resize window"""
        new_width = self.start_width + (event.x_root - self.start_x)
        new_height = self.start_height + (event.y_root - self.start_y)
        
        # Set minimum and maximum dimensions
        min_width, min_height = 400, 300
        max_width = self.parent_frame.winfo_width() - self.window_frame.winfo_x()
        max_height = self.parent_frame.winfo_height() - self.window_frame.winfo_y()
        
        new_width = max(min_width, min(new_width, max_width))
        new_height = max(min_height, min(new_height, max_height))
        
        self.window_frame.place(width=new_width, height=new_height)
        
        # Update matplotlib figure size
        if hasattr(self, 'fig'):
            self.fig.set_size_inches((new_width-100)/100, (new_height-200)/100)
            self.canvas.draw()
    
    def export_video(self):
        """Export animation as MP4 video file"""
        if not CV2_AVAILABLE:
            log_message("OpenCV not installed, cannot export video.\nPlease run 'pip install opencv-python' to install.", "ERROR")
            return
        
        # Select save path
        file_path = filedialog.asksaveasfilename(
            title="Save Video File",
            defaultextension=".mp4",
            filetypes=[("MP4 Video", "*.mp4"), ("AVI Video", "*.avi")]
        )
        
        if not file_path:
            return
        
        try:
            # Disable export button to prevent repeated clicks
            self.export_btn.config(state="disabled", text="Exporting...")
            
            # Create progress dialog
            progress_window = tk.Toplevel(self.window_frame)
            progress_window.title("Export Progress")
            progress_window.geometry("300x100")
            progress_window.resizable(False, False)
            progress_window.grab_set()  # Modal dialog
            
            progress_label = tk.Label(progress_window, text="Exporting video, please wait...")
            progress_label.pack(pady=10)
            
            progress_bar = ttk.Progressbar(progress_window, length=250, mode='determinate')
            progress_bar.pack(pady=10)
            progress_bar['maximum'] = self.total_frames
            
            # Execute export in separate thread
            def export_thread():
                try:
                    # Set video parameters
                    fps = min(self.fps, 30)  # Limit max FPS to 30
                    width, height = 800, 600
                    
                    # Create video writer
                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                    out = cv2.VideoWriter(file_path, fourcc, fps, (width, height))
                    
                    # Save current frame position
                    original_frame = self.current_frame
                    
                    # Generate video frame by frame
                    for frame_idx in range(self.total_frames):
                        self.current_frame = frame_idx
                        
                        # Create temporary figure for export
                        temp_fig = plt.figure(figsize=(10, 7.5), dpi=80)
                        temp_ax = temp_fig.add_subplot(111)
                        
                        # Draw current frame
                        self._draw_frame_for_export(temp_ax, frame_idx)
                        
                        # Convert matplotlib figure to numpy array
                        temp_fig.canvas.draw()
                        buf = np.frombuffer(temp_fig.canvas.tostring_rgb(), dtype=np.uint8)
                        buf = buf.reshape(temp_fig.canvas.get_width_height()[::-1] + (3,))
                        
                        # Resize image and convert color format
                        frame = cv2.resize(buf, (width, height))
                        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                        
                        # Write video frame
                        out.write(frame)
                        
                        # Update progress bar
                        progress_bar['value'] = frame_idx + 1
                        progress_window.update()
                        
                        plt.close(temp_fig)
                    
                    # Release resources
                    out.release()
                    
                    # Restore original frame position
                    self.current_frame = original_frame
                    self.progress_var.set(self.current_frame)
                    self.update_plot()
                    
                    # Close progress dialog
                    progress_window.destroy()
                    
                    # Show success message
                    log_message(f"Video successfully exported to:\n{file_path}", "INFO")
                    
                except Exception as e:
                    progress_window.destroy()
                    log_message(f"Video export failed:\n{str(e)}", "ERROR")
                
                finally:
                    # Re-enable export button
                    self.export_btn.config(state="normal", text="🎬 Export Video")
            
            # Start export thread
            export_thread_obj = threading.Thread(target=export_thread)
            export_thread_obj.daemon = True
            export_thread_obj.start()
            
        except Exception as e:
            log_message(f"Export initialization failed:\n{str(e)}", "ERROR")
            self.export_btn.config(state="normal", text="🎬 Export Video")
    
    def _draw_frame_for_export(self, ax, frame_idx):
        """Draw single frame for video export"""
        ax.clear()
        
        # Set graph properties
        ax.set_title(f"Bodyparts Position - Frame {frame_idx + 1}/{self.total_frames}", 
                    fontsize=14, fontweight='bold', color='#2c3e50', pad=20)
        ax.set_xlabel("X Coordinate", fontsize=12, fontweight='bold', color='#2c3e50')
        ax.set_ylabel("Y Coordinate", fontsize=12, fontweight='bold', color='#2c3e50')
        
        # Set grid and background
        ax.grid(True, alpha=0.3, linestyle='--', color='#bdc3c7')
        ax.set_facecolor('#ffffff')
        
        # Use predefined colors
        colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', 
                 '#1abc9c', '#e67e22', '#34495e', '#f1c40f', '#95a5a6']
        
        # Draw skeleton connections (draw before points to avoid occlusion)
        global skeleton_connections
        if skeleton_connections and self.data:
            for connection in skeleton_connections:
                bodypart1, bodypart2 = connection
                
                # Check if both bodyparts are in data
                if bodypart1 in self.data and bodypart2 in self.data:
                    data1 = self.data[bodypart1]
                    data2 = self.data[bodypart2]
                    
                    # Check if current frame is valid
                    if (frame_idx < len(data1['x']) and frame_idx < len(data1['y']) and
                        frame_idx < len(data2['x']) and frame_idx < len(data2['y'])):
                        
                        x1, y1 = data1['x'][frame_idx], data1['y'][frame_idx]
                        x2, y2 = data2['x'][frame_idx], data2['y'][frame_idx]
                        
                        # Draw connection
                        ax.plot([x1, x2], [y1, y2], 'k-', linewidth=2, alpha=0.8)
        
        # Draw current frame data points
        for i, (bodypart, data) in enumerate(self.data.items()):
            if frame_idx < len(data['x']) and frame_idx < len(data['y']):
                x = data['x'][frame_idx]
                y = data['y'][frame_idx]
                
                # Draw point
                color = colors[i % len(colors)]
                ax.scatter(x, y, s=120, alpha=0.8, 
                          color=color, edgecolors='black', linewidth=2)
                
                # Add number inside circle
                ax.text(x, y, str(i+1), ha='center', va='center', 
                       fontsize=8, fontweight='bold', color='white')
                
                # Add label
                ax.annotate(f"{i+1}. {bodypart}", (x, y), xytext=(5, 5), textcoords='offset points',
                           fontsize=9, color=color, fontweight='bold')
        
        # Set axis range
        if self.data:
            all_x = []
            all_y = []
            for data in self.data.values():
                all_x.extend(data['x'])
                all_y.extend(data['y'])
            
            if all_x and all_y:
                margin_x = (max(all_x) - min(all_x)) * 0.1
                margin_y = (max(all_y) - min(all_y)) * 0.1
                ax.set_xlim(min(all_x) - margin_x, max(all_x) + margin_x)
                ax.set_ylim(min(all_y) - margin_y, max(all_y) + margin_y)
        
        # Set axis style
        ax.tick_params(colors='#2c3e50', labelsize=10)
        for spine in ax.spines.values():
            spine.set_color('#bdc3c7')
            spine.set_linewidth(1)
    
    def close_window(self):
        global visualization_window, central_label
        
        self.pause()
        
        if hasattr(self, 'after_id'):
            try:
                self.window_frame.after_cancel(self.after_id)
            except:
                pass
        
        self.window_frame.destroy()
        visualization_window = None

        if 'central_label' in globals():
            try:
                if hasattr(central_label, 'winfo_exists') and central_label.winfo_exists():
                    central_label.pack(pady=20)
                else:
                    central_label = tk.Label(central_display_frame, text="Central Display Area\nBodyparts position visualization will be shown after reading CSV file", bg="#f8f8f8", fg="#666666")
                    central_label.pack(pady=20)
            except tk.TclError:
                central_label = tk.Label(central_display_frame, text="Central Display Area\nBodyparts position visualization will be shown after reading CSV file", bg="#f8f8f8", fg="#666666")
                central_label.pack(pady=20)

class FiberVisualizationWindow:
    def __init__(self, parent_frame, animal_data=None, target_signal="470", input3_events=None, drug_events=None):
        self.parent_frame = parent_frame
        self.animal_data = animal_data
        self.is_minimized = False
        self.input3_events = input3_events
        self.drug_events = drug_events

        if current_experiment_mode == EXPERIMENT_MODE_FIBER_AST2_DLC:
            self.window_width = 615
            self.window_height = 470
        else:
            self.window_width = 1415
            self.window_height = 470

        self.plot_type = "raw"
        self.target_signal = target_signal
        
        self.pan_start = None
        self.zoom_factor = 1.0
        self._plot_initialized = False
        self.original_xlim = None
        self.original_ylim = None
        self.is_panning = False

        self.running_analysis_results = {}
        self.current_analysis_type = None
        
        self.create_window()
        self.update_plot()
        self.create_preprocessing_controls()
        
    def create_window(self):
        self.window_frame = tk.Frame(self.parent_frame, bg="#f5f5f5", relief=tk.RAISED, bd=1)
        if current_experiment_mode == EXPERIMENT_MODE_FIBER_AST2_DLC:
            self.window_frame.place(x=800, y=0, width=self.window_width, height=self.window_height)
        else:
            self.window_frame.place(x=0, y=0, width=self.window_width, height=self.window_height)
        
        self.window_frame.bind("<Button-1>", self.start_move)
        self.window_frame.bind("<B1-Motion>", self.do_move)
        
        title_frame = tk.Frame(self.window_frame, bg="#f5f5f5", height=25)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        title_frame.bind("<Button-1>", self.start_move)
        title_frame.bind("<B1-Motion>", self.do_move)
        
        title_label = tk.Label(title_frame, text="Fiber Photometry Data", bg="#f5f5f5", fg="#666666", 
                              font=("Microsoft YaHei", 9))
        title_label.pack(side=tk.LEFT, padx=10, pady=3)
        title_label.bind("<Button-1>", self.start_move)
        title_label.bind("<B1-Motion>", self.do_move)
        
        btn_frame = tk.Frame(title_frame, bg="#f5f5f5")
        btn_frame.pack(side=tk.RIGHT, padx=5, pady=2)
        
        minimize_btn = tk.Button(btn_frame, text="−", bg="#f5f5f5", fg="#999999", bd=0, 
                               font=("Arial", 8), width=2, height=1,
                               command=self.minimize_window, relief=tk.FLAT)
        minimize_btn.pack(side=tk.LEFT, padx=1)
        
        close_btn = tk.Button(btn_frame, text="×", bg="#f5f5f5", fg="#999999", bd=0, 
                             font=("Arial", 8), width=2, height=1,
                             command=self.close_window, relief=tk.FLAT)
        close_btn.pack(side=tk.LEFT, padx=1)

        reset_view_btn = tk.Button(btn_frame, text="🗘", bg="#f5f5f5", fg="#999999", bd=0,
                                 font=("Arial", 8), width=2, height=1,
                                 command=self.reset_view, relief=tk.FLAT)
        reset_view_btn.pack(side=tk.LEFT, padx=1)
        
        resize_frame = tk.Frame(self.window_frame, bg="#bdc3c7", width=15, height=15)
        resize_frame.place(relx=1.0, rely=1.0, anchor="se")
        resize_frame.bind("<Button-1>", self.start_resize)
        resize_frame.bind("<B1-Motion>", self.do_resize)
        resize_frame.config(cursor="sizing")
        
        self.fig = Figure(figsize=(3, 1), dpi=90, facecolor='#f8f9fa')
        self.ax = self.fig.add_subplot(111, facecolor='#ffffff')
        
        canvas_frame = tk.Frame(self.window_frame, bg="#f5f5f5", relief=tk.SUNKEN, bd=1)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        
        self.canvas = FigureCanvasTkAgg(self.fig, canvas_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        toolbar_frame = tk.Frame(canvas_frame, bg="#f5f5f5")
        toolbar_frame.pack(fill=tk.X, padx=2, pady=(0,2))
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        for child in toolbar_frame.winfo_children():
            if isinstance(child, tk.Button):
                child.config(bg="#f5f5f5", fg="#666666", bd=0, padx=4, pady=2,
                            activebackground="#e0e0e0", activeforeground="#000000")

        self.canvas.mpl_connect('button_press_event', self.on_click)
        self.canvas.mpl_connect('button_release_event', self.on_release)
        # self.canvas.mpl_connect('motion_notify_event', self.on_motion)
        self.canvas.mpl_connect('scroll_event', self.on_scroll)
    
    def create_preprocessing_controls(self):
        control_frame = tk.Frame(self.window_frame, bg="#ecf0f1")
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        button_width = 12
        button_height = 1

        tk.Button(control_frame, text="Raw", command=lambda: self.set_plot_type("raw"),
                bg="#3498db", fg="white", font=("Microsoft YaHei", 8), width=button_width, height=button_height).pack(side=tk.LEFT, padx=2, pady=2)
        tk.Button(control_frame, text="Smoothed", command=lambda: self.set_plot_type("smoothed"),
                bg="#e67e22", fg="white", font=("Microsoft YaHei", 8), width=button_width, height=button_height).pack(side=tk.LEFT, padx=2, pady=2)
        tk.Button(control_frame, text="Baseline Corr", command=lambda: self.set_plot_type("baseline_corrected"),
                bg="#2ecc71", fg="white", font=("Microsoft YaHei", 8), width=button_width, height=button_height).pack(side=tk.LEFT, padx=2, pady=2)
        tk.Button(control_frame, text="Motion Corr", command=lambda: self.set_plot_type("motion_corrected"),
                bg="#9b59b6", fg="white", font=("Microsoft YaHei", 8), width=button_width, height=button_height).pack(side=tk.LEFT, padx=2, pady=2)
        tk.Button(control_frame, text="ΔF/F", command=lambda: self.set_plot_type("dff"),
                bg="#f39c12", fg="white", font=("Microsoft YaHei", 8), width=button_width, height=button_height).pack(side=tk.LEFT, padx=2, pady=2)
        tk.Button(control_frame, text="Z-Score", command=lambda: self.set_plot_type("zscore"),
                bg="#e74c3c", fg="white", font=("Microsoft YaHei", 8), width=button_width, height=button_height).pack(side=tk.LEFT, padx=2, pady=2)
        
    def on_click(self, event):
        """Handle mouse click event for panning"""
        if event.inaxes == self.ax and event.button == 1:
            self.pan_start = (event.xdata, event.ydata)
            self.is_panning = True
            
    def on_release(self, event):
        """Handle mouse release event"""
        if event.button == 1:
            self.pan_start = None
            self.is_panning = False
            
    def on_motion(self, event):
        """Handle mouse motion for panning"""
        if not self.is_panning or event.inaxes != self.ax or self.pan_start is None:
            return
            
        if event.xdata is None or event.ydata is None:
            return
            
        dx = event.xdata - self.pan_start[0]
        dy = event.ydata - self.pan_start[1]
        
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        
        new_xlim = (xlim[0] - dx, xlim[1] - dx)
        new_ylim = (ylim[0] - dy, ylim[1] - dy)
        
        self.ax.set_xlim(new_xlim)
        self.ax.set_ylim(new_ylim)
        
        self.canvas.draw_idle()
        
    def on_scroll(self, event):
        if event.inaxes != self.ax:
            log_message("Scroll event outside axes, ignoring.", "WARNING")
            return
            
        try:
            current_time = getattr(self, '_last_scroll_time', 0)
            if time.time() - current_time < 0.05:
                return
            self._last_scroll_time = time.time()
            
            if event.xdata is None or event.ydata is None:
                return
                
            x, y = event.xdata, event.ydata
            xlim = self.ax.get_xlim()
            ylim = self.ax.get_ylim()
            
            if not self._is_valid_range(xlim, ylim):
                self.reset_view()
                return
            
            zoom_factor = 1.1 if event.button == 'up' else 0.9
            
            new_xlim = (x - (x - xlim[0]) * zoom_factor, 
                    x + (xlim[1] - x) * zoom_factor)
            new_ylim = (y - (y - ylim[0]) * zoom_factor, 
                    y + (ylim[1] - y) * zoom_factor)
            
            if self._is_valid_range(new_xlim, new_ylim):
                self.ax.set_xlim(new_xlim)
                self.ax.set_ylim(new_ylim)
                self.canvas.draw_idle()
                
        except Exception as e:
            log_message(f"Scroll error: {str(e)}", "WARNING")
            self.reset_view()

    def _is_valid_range(self, xlim, ylim):
        try:
            return (all(np.isfinite(xlim)) and all(np.isfinite(ylim)) and
                    xlim[1] > xlim[0] and ylim[1] > ylim[0] and
                    abs(xlim[1] - xlim[0]) > 1e-10 and
                    abs(ylim[1] - ylim[0]) > 1e-10 and
                    abs(xlim[1] - xlim[0]) < 1e10 and
                    abs(ylim[1] - ylim[0]) < 1e10)
        except:
            return False
        
    def reset_view(self):
        """Reset the view to original zoom and pan"""
        if self.original_xlim and self.original_ylim:
            self.ax.set_xlim(self.original_xlim)
            self.ax.set_ylim(self.original_ylim)
            self.zoom_factor = 1.0
            self.canvas.draw_idle()
            log_message("Fiber view reset to original", "INFO")

    def update_plot(self):
        """Updated plot method with color management and enhanced visualization"""
        self.ax.clear()
        
        if self.animal_data:
            fiber_data = self.animal_data.get('fiber_data_trimmed') if 'fiber_data_trimmed' in self.animal_data else self.animal_data.get('fiber_data')
            channels = self.animal_data.get('channels', {})
            active_channels = self.animal_data.get('active_channels', [])
            channel_data = self.animal_data.get('channel_data', {})
            preprocessed_data = self.animal_data.get('preprocessed_data', {})
            dff_data = self.animal_data.get('dff_data', {})
            zscore_data = self.animal_data.get('zscore_data', {})
            target_signal = self.animal_data.get('target_signal', self.target_signal)
        else:
            fiber_data = globals().get('fiber_data_trimmed') or globals().get('fiber_data')
            channels = globals().get('channels', {})
            active_channels = globals().get('active_channels', [])
            channel_data = globals().get('channel_data', {})
            preprocessed_data = globals().get('preprocessed_data', {})
            dff_data = globals().get('dff_data', {})
            zscore_data = globals().get('zscore_data', {})
            target_signal = self.target_signal
        
        if fiber_data is None or not active_channels:
            self.ax.text(0.5, 0.5, "No fiber data available\nPlease load fiber data first", ha='center', va='center', transform=self.ax.transAxes, fontsize=12)
            self.ax.set_title("Fiber Photometry Data - No Data Available")
            self.canvas.draw()
            return
        
        time_col = channels.get('time')
        if time_col is None or time_col not in fiber_data.columns:
            self.ax.text(0.5, 0.5, f"Time column '{time_col}' not found in fiber data", ha='center', va='center', transform=self.ax.transAxes, fontsize=10)
            self.ax.set_title("Fiber Photometry Data - Error")
            self.canvas.draw()
            return
        
        time_data = fiber_data[time_col]
        
        # Color scheme for wavelengths
        wavelength_colors = {
            '410': {'main': "#285DFF", 'light': '#5dade2', 'lighter': '#85c1e9'},  # Blue family
            '470': {'main': "#44B444", 'light': '#58d68d', 'lighter': '#82e0aa'},  # Green family
            '560': {'main': "#FF0000", 'light': "#d55858", 'lighter': "#faa0a0"},  # Red family
            '640': {'main': "#FF9900", 'light': '#e59866', 'lighter': '#f5cba7'}   # Orange family
        }
        
        all_time_data = []
        all_value_data = []
        has_plotted_data = False
        
        target_wavelengths = target_signal.split('+') if '+' in target_signal else [target_signal]
        
        if self.plot_type == "raw":
            # Plot raw data with 410nm included
            has_data = False
            for i, channel_num in enumerate(active_channels):
                if channel_num in channel_data:
                    # Plot target wavelengths
                    for wl_idx, wavelength in enumerate(target_wavelengths):
                        col_name = channel_data[channel_num].get(wavelength)
                        if col_name and col_name in fiber_data.columns:
                            color_scheme = wavelength_colors.get(wavelength, wavelength_colors['470'])
                            color = color_scheme['main'] if wl_idx == 0 else (color_scheme['light'] if wl_idx == 1 else color_scheme['lighter'])
                            
                            alpha = 0.8
                            linewidth = 1.5
                            label = f'CH{channel_num} {wavelength}nm'
                            
                            self.ax.plot(time_data, fiber_data[col_name], color=color, alpha=alpha, 
                                    linewidth=linewidth, label=label)
                            all_time_data.extend(time_data)
                            all_value_data.extend(fiber_data[col_name].values)
                            has_data = True
                            has_plotted_data = True
                    
                    # Plot 410nm reference
                    ref_410 = channel_data[channel_num].get('410')
                    if ref_410 and ref_410 in fiber_data.columns:
                        self.ax.plot(time_data, fiber_data[ref_410], 
                                color=wavelength_colors['410']['main'], alpha=0.5, 
                                linewidth=1.0, linestyle='--', label=f'CH{channel_num} 410nm (ref)')
                        all_time_data.extend(time_data)
                        all_value_data.extend(fiber_data[ref_410].values)
            
            if not has_data:
                self.ax.text(0.5, 0.5, "No raw data columns found\nCheck channel configuration", 
                            ha='center', va='center', transform=self.ax.transAxes, fontsize=10)
            
            title_suffix = f" ({target_signal}nm)" if target_signal else ""
            self.ax.set_title(f"Fiber Photometry Data - Raw Signals{title_suffix}", fontsize=14, fontweight='bold')

        elif self.plot_type == "smoothed":
            if self.animal_data:
                data_source = self.animal_data.get('preprocessed_data', pd.DataFrame())
            else:
                data_source = globals().get('preprocessed_data', pd.DataFrame())
            
            for i, channel_num in enumerate(active_channels):
                if channel_num in channel_data:
                    for wl_idx, wavelength in enumerate(target_wavelengths):
                        # Plot raw data first (lighter)
                        raw_col = channel_data[channel_num].get(wavelength)
                        if raw_col and raw_col in fiber_data.columns:
                            color_scheme = wavelength_colors.get(wavelength, wavelength_colors['470'])
                            raw_color = color_scheme['lighter']
                            self.ax.plot(time_data, fiber_data[raw_col], color=raw_color, alpha=0.4, linewidth=1.0, linestyle=':', 
                                    label=f'CH{channel_num} {wavelength}nm Raw')
                        
                        # Plot smoothed data (main color)
                        smoothed_col = f"CH{channel_num}_{wavelength}_smoothed"
                        if smoothed_col in data_source.columns:
                            color_scheme = wavelength_colors.get(wavelength, wavelength_colors['470'])
                            main_color = color_scheme['main'] if wl_idx == 0 else color_scheme['light']
                            
                            label = f'CH{channel_num} {wavelength}nm Smoothed'
                            line = self.ax.plot(time_data, data_source[smoothed_col], color=main_color, linewidth=1.8, label=label)[0]
                            all_time_data.extend(time_data)
                            all_value_data.extend(data_source[smoothed_col].values)
                            has_plotted_data = True
            
            title_suffix = f" ({target_signal}nm)" if target_signal else ""
            self.ax.set_title(f"Fiber Photometry Data - Smoothed{title_suffix}", fontsize=14, fontweight='bold')

        elif self.plot_type == "baseline_corrected":
            if self.animal_data:
                data_source = self.animal_data.get('preprocessed_data', pd.DataFrame())
            else:
                data_source = globals().get('preprocessed_data', pd.DataFrame())
            
            for i, channel_num in enumerate(active_channels):
                for wl_idx, wavelength in enumerate(target_wavelengths):
                    color_scheme = wavelength_colors.get(wavelength, wavelength_colors['470'])
                    
                    # Determine which data was used for baseline correction
                    smoothed_col = f"CH{channel_num}_{wavelength}_smoothed"
                    raw_col = channel_data[channel_num].get(wavelength)
                    
                    if smoothed_col in data_source.columns:
                        source_col = smoothed_col
                        source_label = "Smoothed"
                        source_color = color_scheme['lighter']
                    elif raw_col and raw_col in fiber_data.columns:
                        source_col = raw_col
                        source_label = "Raw"
                        source_color = color_scheme['lighter']
                    else:
                        continue
                    
                    # Plot source data
                    if source_col in data_source.columns:
                        self.ax.plot(time_data, data_source[source_col], color=source_color, 
                                alpha=0.4, linewidth=1.0, linestyle=':', 
                                label=f'CH{channel_num} {wavelength}nm {source_label}')
                    elif source_col in fiber_data.columns:
                        self.ax.plot(time_data, fiber_data[source_col], color=source_color, 
                                alpha=0.4, linewidth=1.0, linestyle=':', 
                                label=f'CH{channel_num} {wavelength}nm {source_label}')
                    
                    # Plot fitted baseline curve
                    baseline_pred_col = f"CH{channel_num}_{wavelength}_baseline_pred"
                    if baseline_pred_col in data_source.columns:
                        # fitted_color = color_scheme['light']
                        self.ax.plot(time_data, data_source[baseline_pred_col], 
                                color='k', alpha=0.6, linewidth=1.2, 
                                linestyle='--', label=f'CH{channel_num} {wavelength}nm Baseline Fit')
                    
                    # Plot baseline corrected data
                    baseline_col = f"CH{channel_num}_{wavelength}_baseline_corrected"
                    if baseline_col in data_source.columns:
                        main_color = color_scheme['main'] if wl_idx == 0 else color_scheme['light']
                        label = f'CH{channel_num} {wavelength}nm Baseline Corrected'
                        line = self.ax.plot(time_data, data_source[baseline_col], color=main_color,
                                        linewidth=1.8, label=label)[0]
                        all_time_data.extend(time_data)
                        all_value_data.extend(data_source[baseline_col].values)
                        has_plotted_data = True
            
            title_suffix = f" ({target_signal}nm)" if target_signal else ""
            self.ax.set_title(f"Fiber Photometry Data - Baseline Corrected{title_suffix}", fontsize=14, fontweight='bold')

        elif self.plot_type == "motion_corrected":
            if self.animal_data:
                data_source = self.animal_data.get('preprocessed_data', pd.DataFrame())
            else:
                data_source = globals().get('preprocessed_data', pd.DataFrame())
            
            for i, channel_num in enumerate(active_channels):
                for wl_idx, wavelength in enumerate(target_wavelengths):
                    color_scheme = wavelength_colors.get(wavelength, wavelength_colors['470'])
                    
                    # Determine which data was used for motion correction
                    baseline_col = f"CH{channel_num}_{wavelength}_baseline_corrected"
                    smoothed_col = f"CH{channel_num}_{wavelength}_smoothed"
                    raw_col = channel_data[channel_num].get(wavelength)
                    
                    if baseline_col in data_source.columns:
                        source_col = baseline_col
                        source_label = "Baseline Corrected"
                        source_color = color_scheme['lighter']
                    elif smoothed_col in data_source.columns:
                        source_col = smoothed_col
                        source_label = "Smoothed"
                        source_color = color_scheme['lighter']
                    elif raw_col and raw_col in fiber_data.columns:
                        source_col = raw_col
                        source_label = "Raw"
                        source_color = color_scheme['lighter']
                    else:
                        continue
                    
                    # Plot source data
                    if source_col in data_source.columns:
                        self.ax.plot(time_data, data_source[source_col], color=source_color, 
                                alpha=0.4, linewidth=1.0, linestyle=':', 
                                label=f'CH{channel_num} {wavelength}nm {source_label}')
                    elif source_col in fiber_data.columns:
                        self.ax.plot(time_data, fiber_data[source_col], color=source_color, 
                                alpha=0.4, linewidth=1.0, linestyle=':', 
                                label=f'CH{channel_num} {wavelength}nm {source_label}')
                    
                    # Plot fitted reference curve
                    fitted_ref_col = f"CH{channel_num}_{wavelength}_fitted_ref"
                    if fitted_ref_col in data_source.columns:
                        # fitted_color = color_scheme['light']
                        self.ax.plot(time_data, data_source[fitted_ref_col], 
                                color='k', alpha=0.6, linewidth=1.2, 
                                linestyle='--', label=f'CH{channel_num} {wavelength}nm Fitted Ref')
                    
                    # Plot motion corrected data
                    motion_col = f"CH{channel_num}_{wavelength}_motion_corrected"
                    if motion_col in data_source.columns:
                        main_color = color_scheme['main'] if wl_idx == 0 else color_scheme['light']
                        label = f'CH{channel_num} {wavelength}nm Motion Corrected'
                        line = self.ax.plot(time_data, data_source[motion_col], color=main_color,
                                        linewidth=1.8, label=label)[0]
                        all_time_data.extend(time_data)
                        all_value_data.extend(data_source[motion_col].values)
                        has_plotted_data = True
            
            title_suffix = f" ({target_signal}nm)" if target_signal else ""
            self.ax.set_title(f"Fiber Photometry Data - Motion Corrected{title_suffix}", fontsize=14, fontweight='bold')

        elif self.plot_type == "dff":
            for i, channel_num in enumerate(active_channels):
                for wl_idx, wavelength in enumerate(target_wavelengths):
                    color_scheme = wavelength_colors.get(wavelength, wavelength_colors['470'])
                    key = f"{channel_num}_{wavelength}"
                    dff_col = f"CH{channel_num}_{wavelength}_dff"
                    
                    # Try to get from dff_data dict first
                    if isinstance(dff_data, dict) and key in dff_data:
                        data_to_plot = dff_data[key]
                        if isinstance(data_to_plot, pd.Series):
                            data_to_plot = data_to_plot.values
                        
                        main_color = color_scheme['main'] if wl_idx == 0 else (color_scheme['light'] if wl_idx == 1 else color_scheme['lighter'])
                        label = f'CH{channel_num} {wavelength}nm ΔF/F'
                        
                        line = self.ax.plot(time_data, data_to_plot, color=main_color,
                                        linewidth=1.8, label=label)[0]
                        all_time_data.extend(time_data)
                        all_value_data.extend(data_to_plot)
                        has_plotted_data = True
                    # Otherwise try preprocessed_data
                    elif preprocessed_data is not None and dff_col in preprocessed_data.columns:
                        main_color = color_scheme['main'] if wl_idx == 0 else (color_scheme['light'] if wl_idx == 1 else color_scheme['lighter'])
                        label = f'CH{channel_num} {wavelength}nm ΔF/F'
                        
                        line = self.ax.plot(time_data, preprocessed_data[dff_col], color=main_color,
                                        linewidth=1.8, label=label)[0]
                        all_time_data.extend(time_data)
                        all_value_data.extend(preprocessed_data[dff_col].values)
                        has_plotted_data = True
            
            title_suffix = f" ({target_signal}nm)" if target_signal else ""
            self.ax.set_title(f"Fiber Photometry Data - ΔF/F{title_suffix}", fontsize=14, fontweight='bold')

        elif self.plot_type == "zscore":
            for i, channel_num in enumerate(active_channels):
                for wl_idx, wavelength in enumerate(target_wavelengths):
                    color_scheme = wavelength_colors.get(wavelength, wavelength_colors['470'])
                    key = f"{channel_num}_{wavelength}"
                    zscore_col = f"CH{channel_num}_{wavelength}_zscore"
                    
                    # Try to get from zscore_data dict first
                    if isinstance(zscore_data, dict) and key in zscore_data:
                        data_to_plot = zscore_data[key]
                        if isinstance(data_to_plot, pd.Series):
                            data_to_plot = data_to_plot.values
                        
                        main_color = color_scheme['main'] if wl_idx == 0 else (color_scheme['light'] if wl_idx == 1 else color_scheme['lighter'])
                        label = f'CH{channel_num} {wavelength}nm Z-Score'
                        
                        line = self.ax.plot(time_data, data_to_plot, color=main_color,
                                        linewidth=1.8, label=label)[0]
                        all_time_data.extend(time_data)
                        all_value_data.extend(data_to_plot)
                        has_plotted_data = True
                    # Otherwise try preprocessed_data
                    elif preprocessed_data is not None and zscore_col in preprocessed_data.columns:
                        main_color = color_scheme['main'] if wl_idx == 0 else (color_scheme['light'] if wl_idx == 1 else color_scheme['lighter'])
                        label = f'CH{channel_num} {wavelength}nm Z-Score'
                        
                        line = self.ax.plot(time_data, preprocessed_data[zscore_col], color=main_color,
                                        linewidth=1.8, label=label)[0]
                        all_time_data.extend(time_data)
                        all_value_data.extend(preprocessed_data[zscore_col].values)
                        has_plotted_data = True
            
            title_suffix = f" ({target_signal}nm)" if target_signal else ""
            self.ax.set_title(f"Fiber Photometry Data - Z-Score{title_suffix}", fontsize=14, fontweight='bold')

        # Plot running analysis markers if available
        if self.animal_data.get('running_processed_data'):
            self._plot_running_analysis_markers()

        # Plot optogenetic stimulation markers if available
        if self.input3_events is not None:
            self._plot_optogenetic_markers()

        # Plot drug administration markers if available
        if self.drug_events is not None:
            self._plot_drug_markers()

        self.ax.set_xlabel("Time (s)", fontsize=12)
        self.ax.set_ylabel("ΔF/F" if self.plot_type == "dff" else "Z-Score" if self.plot_type == "zscore" else "Fluorescence", fontsize=12)
        if has_plotted_data:
            self.ax.legend(loc='best', fontsize=8, framealpha=0.9)
        self.ax.grid(False)

        # Set axis limits
        if all_time_data and all_value_data:
            min_time = min(all_time_data)
            max_time = max(all_time_data)
            min_value = min(all_value_data)
            max_value = max(all_value_data)
            
            time_margin = (max_time - min_time) * 0.05
            value_margin = (max_value - min_value) * 0.1
            
            self.original_xlim = (min_time - time_margin, max_time + time_margin)
            self.original_ylim = (min_value - value_margin, max_value + value_margin)
            
            if not hasattr(self, '_plot_initialized') or not self._plot_initialized:
                self.ax.set_xlim(self.original_xlim)
                self.ax.set_ylim(self.original_ylim)
                self._plot_initialized = True

        self.canvas.draw()

    def _plot_running_analysis_markers(self):
        """Plot different types of analysis data"""
        analysis_type = disp_var.get()
        bout_direction = direction_var.get()
        ast2_data = self.animal_data.get('ast2_data_adjusted')
        fs = ast2_data['header']['inputRate']/ast2_data['header']['saveEvery']
        for idx, (start, end) in enumerate(self.animal_data['bouts_with_direction'][analysis_type][bout_direction]):
            lbl = f"{analysis_type}-{bout_direction}" if idx == 0 else '_nolegend_'
            self.ax.axvspan(start/fs, end/fs,
                            color='orange',
                            alpha=0.3,
                            label=lbl)
    
    def _plot_optogenetic_markers(self):
        """Plot optogenetic stimulation periods"""
        if 'fiber_events' in self.animal_data:
            fiber_events = self.animal_data['fiber_events']
            optogenetic_events = identify_optogenetic_events(fiber_events)
            for idx in range(0, len(optogenetic_events), 2):
                (start, _), (end, _) = optogenetic_events[idx], optogenetic_events[idx+1]
                lbl = "Optogenetic Stimulation" if idx == 0 else '_nolegend_'
                self.ax.axvspan(int(start), int(end),
                                color='blue',
                                alpha=0.3,
                                label=lbl)
    
    def _plot_drug_markers(self):
        """Plot drug administration events"""
        if "fiber_events" in self.animal_data:
            fiber_events = self.animal_data['fiber_events']
            drug_sessions = identify_drug_sessions(fiber_events)
            for idx in range(0, len(drug_sessions)):
                start_time = drug_sessions[idx]['time']
                lbl = "Drug Administration" if idx == 0 else '_nolegend_'
                self.ax.axvline(int(start_time),
                                color='purple',
                                alpha=0.3,
                                label=lbl)

    def set_plot_type(self, plot_type):
        self.plot_type = plot_type
        self.update_plot()

    def start_move(self, event):
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.start_win_x = self.window_frame.winfo_x()
        self.start_win_y = self.window_frame.winfo_y()
    
    def do_move(self, event):
        x = self.start_win_x + (event.x_root - self.start_x)
        y = self.start_win_y + (event.y_root - self.start_y)
        parent_width = self.parent_frame.winfo_width()
        parent_height = self.parent_frame.winfo_height()
        window_width = self.window_frame.winfo_width()
        window_height = self.window_frame.winfo_height()
        
        x = max(0, min(x, parent_width - window_width))
        y = max(0, min(y, parent_height - window_height))
        
        self.window_frame.place(x=x, y=y)
    
    def minimize_window(self):
        if self.is_minimized:
            self.window_frame.place(width=self.window_width, height=self.window_height)
            self.is_minimized = False
        else:
            self.window_width = self.window_frame.winfo_width()
            self.window_height = self.window_frame.winfo_height()
            self.window_frame.place(width=self.window_width, height=35)
            self.is_minimized = True
    
    def start_resize(self, event):
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.start_width = self.window_frame.winfo_width()
        self.start_height = self.window_frame.winfo_height()
    
    def do_resize(self, event):
        new_width = self.start_width + (event.x_root - self.start_x)
        new_height = self.start_height + (event.y_root - self.start_y)
        
        min_width, min_height = 400, 300
        max_width = self.parent_frame.winfo_width() - self.window_frame.winfo_x()
        max_height = self.parent_frame.winfo_height() - self.window_frame.winfo_y()
        
        new_width = max(min_width, min(new_width, max_width))
        new_height = max(min_height, min(new_height, max_height))
        
        self.window_frame.place(width=new_width, height=new_height)
        
        if hasattr(self, 'fig'):
            self.fig.set_size_inches((new_width-100)/100, (new_height-200)/100)
            self.canvas.draw()
    
    def close_window(self):
        global fiber_plot_window
        self.window_frame.destroy()
        fiber_plot_window = None

class RunningVisualizationWindow:
    def __init__(self, parent_frame, animal_data=None):
        self.parent_frame = parent_frame
        self.animal_data = animal_data
        self.is_minimized = False
        self.movement_bouts = []

        if current_experiment_mode == EXPERIMENT_MODE_FIBER_AST2_DLC:
            self.window_width = 615
            self.window_height = 400
        else:
            self.window_width = 1415
            self.window_height = 400

        self.current_analysis_type = None
        self.analysis_data = None
        self.pan_start = None
        self.zoom_factor = 1.0
        self._plot_initialized = False
        self.original_xlim = None
        self.original_ylim = None
        self.is_panning = False
        
        self.create_window()
        self.update_plot()
        
    def create_window(self):
        self.window_frame = tk.Frame(self.parent_frame, bg="#f5f5f5", relief=tk.RAISED, bd=1)
        if current_experiment_mode == EXPERIMENT_MODE_FIBER_AST2_DLC:
            self.window_frame.place(x=800, y=470, width=self.window_width, height=self.window_height)
        else:
            self.window_frame.place(x=0, y=470, width=self.window_width, height=self.window_height)

        self.window_frame.bind("<Button-1>", self.start_move)
        self.window_frame.bind("<B1-Motion>", self.do_move)
        
        title_frame = tk.Frame(self.window_frame, bg="#f5f5f5", height=25)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        title_frame.bind("<Button-1>", self.start_move)
        title_frame.bind("<B1-Motion>", self.do_move)
        
        title_label = tk.Label(title_frame, text="Threadmill Data", bg="#f5f5f5", fg="#666666", 
                              font=("Microsoft YaHei", 9))
        title_label.pack(side=tk.LEFT, padx=10, pady=3)
        title_label.bind("<Button-1>", self.start_move)
        title_label.bind("<B1-Motion>", self.do_move)
        
        btn_frame = tk.Frame(title_frame, bg="#f5f5f5")
        btn_frame.pack(side=tk.RIGHT, padx=5, pady=2)
        
        minimize_btn = tk.Button(btn_frame, text="−", bg="#f5f5f5", fg="#999999", bd=0, 
                               font=("Arial", 8), width=2, height=1,
                               command=self.minimize_window, relief=tk.FLAT)
        minimize_btn.pack(side=tk.LEFT, padx=1)
        
        close_btn = tk.Button(btn_frame, text="×", bg="#f5f5f5", fg="#999999", bd=0, 
                             font=("Arial", 8), width=2, height=1,
                             command=self.close_window, relief=tk.FLAT)
        close_btn.pack(side=tk.LEFT, padx=1)
        
        reset_view_btn = tk.Button(btn_frame, text="🗘", bg="#f5f5f5", fg="#999999", bd=0,
                                 font=("Arial", 8), width=2, height=1,
                                 command=self.reset_view, relief=tk.FLAT)
        reset_view_btn.pack(side=tk.LEFT, padx=1)
        
        resize_frame = tk.Frame(self.window_frame, bg="#bdc3c7", width=15, height=15)
        resize_frame.place(relx=1.0, rely=1.0, anchor="se")
        resize_frame.bind("<Button-1>", self.start_resize)
        resize_frame.bind("<B1-Motion>", self.do_resize)
        resize_frame.config(cursor="sizing")
        
        self.fig = Figure(figsize=(3, 1), dpi=90, facecolor='#f8f9fa')
        self.ax = self.fig.add_subplot(111, facecolor='#ffffff')
        
        canvas_frame = tk.Frame(self.window_frame, bg="#f5f5f5", relief=tk.SUNKEN, bd=1)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        
        self.canvas = FigureCanvasTkAgg(self.fig, canvas_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        toolbar_frame = tk.Frame(canvas_frame, bg="#f5f5f5")
        toolbar_frame.pack(fill=tk.X, padx=2, pady=(0,2))
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        for child in toolbar_frame.winfo_children():
            if isinstance(child, tk.Button):
                child.config(bg="#f5f5f5", fg="#666666", bd=0, padx=4, pady=2,
                            activebackground="#e0e0e0", activeforeground="#000000")

        self.canvas.mpl_connect('button_press_event', self.on_click)
        self.canvas.mpl_connect('button_release_event', self.on_release)
        # self.canvas.mpl_connect('motion_notify_event', self.on_motion)
        self.canvas.mpl_connect('scroll_event', self.on_scroll)
    
    def on_click(self, event):
        """Handle mouse click event for panning"""
        if event.inaxes == self.ax and event.button == 1:
            self.pan_start = (event.xdata, event.ydata)
            self.is_panning = True
            
    def on_release(self, event):
        """Handle mouse release event"""
        if event.button == 1:
            self.pan_start = None
            self.is_panning = False
            
    def on_motion(self, event):
        """Handle mouse motion for panning"""
        if not self.is_panning or event.inaxes != self.ax or self.pan_start is None:
            return
            
        if event.xdata is None or event.ydata is None:
            return
            
        dx = event.xdata - self.pan_start[0]
        dy = event.ydata - self.pan_start[1]
        
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        
        new_xlim = (xlim[0] - dx, xlim[1] - dx)
        new_ylim = (ylim[0] - dy, ylim[1] - dy)
        
        self.ax.set_xlim(new_xlim)
        self.ax.set_ylim(new_ylim)
        
        self.canvas.draw_idle()
        
    def on_scroll(self, event):
        if event.inaxes != self.ax:
            log_message("Scroll event outside axes, ignoring.", "WARNING")
            return
            
        try:
            current_time = getattr(self, '_last_scroll_time', 0)
            if time.time() - current_time < 0.05:
                return
            self._last_scroll_time = time.time()
            
            if event.xdata is None or event.ydata is None:
                return
                
            x, y = event.xdata, event.ydata
            xlim = self.ax.get_xlim()
            ylim = self.ax.get_ylim()
            
            if not self._is_valid_range(xlim, ylim):
                self.reset_view()
                return
            
            zoom_factor = 1.1 if event.button == 'up' else 0.9
            
            new_xlim = (x - (x - xlim[0]) * zoom_factor, 
                    x + (xlim[1] - x) * zoom_factor)
            new_ylim = (y - (y - ylim[0]) * zoom_factor, 
                    y + (ylim[1] - y) * zoom_factor)
            
            if self._is_valid_range(new_xlim, new_ylim):
                self.ax.set_xlim(new_xlim)
                self.ax.set_ylim(new_ylim)
                self.canvas.draw_idle()
                
        except Exception as e:
            log_message(f"Scroll error: {str(e)}", "WARNING")
            self.reset_view()

    def _is_valid_range(self, xlim, ylim):
        try:
            return (all(np.isfinite(xlim)) and all(np.isfinite(ylim)) and
                    xlim[1] > xlim[0] and ylim[1] > ylim[0] and
                    abs(xlim[1] - xlim[0]) > 1e-10 and
                    abs(ylim[1] - ylim[0]) > 1e-10 and
                    abs(xlim[1] - xlim[0]) < 1e10 and
                    abs(ylim[1] - ylim[0]) < 1e10)
        except:
            return False
        
    def reset_view(self):
        """Reset the view to original zoom and pan"""
        if self.original_xlim and self.original_ylim:
            self.ax.set_xlim(self.original_xlim)
            self.ax.set_ylim(self.original_ylim)
            self.zoom_factor = 1.0
            self.canvas.draw_idle()
            log_message("Running view reset to original", "INFO")
    
    def update_plot(self):
        self.ax.clear()
        
        if self.animal_data:
            ast2_data = self.animal_data.get('ast2_data_adjusted')
            processed_data = self.animal_data.get('running_processed_data')
            bouts = self.animal_data.get('bouts', {})
        else:
            ast2_data = globals().get('ast2_data_adjusted')
            processed_data = globals().get('running_processed_data')
            bouts = globals().get('bouts', {})
        if ast2_data is None:
            self.ax.text(0.5, 0.5, "No running data available", ha='center', va='center', transform=self.ax.transAxes)
            self.ax.set_title("Running Wheel Data - No Data")
        else:
            timestamps = ast2_data['data']['timestamps']
            
            if processed_data:
                speed = processed_data['filtered_speed']
            else:
                speed = ast2_data['data']['speed']
            
            # Plot speed data
            self.ax.plot(timestamps, speed, 'b-', label='Running Speed', linewidth=1, alpha=0.7)
            
            # Plot analysis data if available
            if self.animal_data.get('running_processed_data'):
                self.plot_analysis_data()
            
            # Set title based on current analysis
            if self.animal_data.get('running_processed_data'):
                title = f"Running Data - {disp_var.get()} - {direction_var.get()}"
            else:
                title = f"Running Data"
                
            self.ax.set_title(title, fontsize=14, fontweight='bold')
            self.ax.set_xlabel("Time (s)", fontsize=12)
            self.ax.set_ylabel("Speed (cm/s)", fontsize=12)
            self.ax.legend()
            self.ax.grid(False)
            
            if len(speed) > 0 and len(timestamps) > 0:
                min_speed = min(speed)
                max_speed = max(speed)
                min_time = min(timestamps)
                max_time = max(timestamps)
                
                speed_margin = (max_speed - min_speed) * 0.1
                time_margin = (max_time - min_time) * 0.05
                
                if speed_margin < 0.1:
                    speed_margin = 0.1
                
                self.original_xlim = (min_time - time_margin, max_time + time_margin)
                self.original_ylim = (min_speed - speed_margin, max_speed + speed_margin)
                
                if not hasattr(self, '_plot_initialized') or not self._plot_initialized:
                    self.ax.set_xlim(self.original_xlim)
                    self.ax.set_ylim(self.original_ylim)
                    self._plot_initialized = True

        self.canvas.draw()
    
    def plot_analysis_data(self):
        """Plot different types of analysis data"""
        analysis_type = disp_var.get()
        bout_direction = direction_var.get()
        ast2_data = self.animal_data.get('ast2_data_adjusted')
        fs = ast2_data['header']['inputRate']/ast2_data['header']['saveEvery']
        for idx, (start, end) in enumerate(self.animal_data['bouts_with_direction'][analysis_type][bout_direction]):
            lbl = f"{analysis_type}-{bout_direction}" if idx == 0 else '_nolegend_'
            self.ax.axvspan(start/fs, end/fs,
                            color='orange',
                            alpha=0.3,
                            label=lbl)

    def start_move(self, event):
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.start_win_x = self.window_frame.winfo_x()
        self.start_win_y = self.window_frame.winfo_y()
    
    def do_move(self, event):
        x = self.start_win_x + (event.x_root - self.start_x)
        y = self.start_win_y + (event.y_root - self.start_y)
        parent_width = self.parent_frame.winfo_width()
        parent_height = self.parent_frame.winfo_height()
        window_width = self.window_frame.winfo_width()
        window_height = self.window_frame.winfo_height()
        
        x = max(0, min(x, parent_width - window_width))
        y = max(0, min(y, parent_height - window_height))
        
        self.window_frame.place(x=x, y=y)
    
    def minimize_window(self):
        if self.is_minimized:
            self.window_frame.place(width=self.window_width, height=self.window_height)
            self.is_minimized = False
        else:
            self.window_width = self.window_frame.winfo_width()
            self.window_height = self.window_frame.winfo_height()
            self.window_frame.place(width=self.window_width, height=35)
            self.is_minimized = True
    
    def start_resize(self, event):
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.start_width = self.window_frame.winfo_width()
        self.start_height = self.window_frame.winfo_height()
    
    def do_resize(self, event):
        new_width = self.start_width + (event.x_root - self.start_x)
        new_height = self.start_height + (event.y_root - self.start_y)
        
        min_width, min_height = 400, 300
        max_width = self.parent_frame.winfo_width() - self.window_frame.winfo_x()
        max_height = self.parent_frame.winfo_height() - self.window_frame.winfo_y()
        
        new_width = max(min_width, min(new_width, max_width))
        new_height = max(min_height, min(new_height, max_height))
        
        self.window_frame.place(width=new_width, height=new_height)
        
        if hasattr(self, 'fig'):
            self.fig.set_size_inches((new_width-100)/100, (new_height-200)/100)
            self.canvas.draw()
    
    def close_window(self):
        global running_plot_window
        self.window_frame.destroy()
        running_plot_window = None
