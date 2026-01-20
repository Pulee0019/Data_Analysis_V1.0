from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
from matplotlib.figure import Figure
from tkinter import filedialog, ttk
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import tkinter as tk
import pandas as pd
import numpy as np
import threading
import traceback
import fnmatch
import signal
import json
import glob
import time
import os
import re

from Behavior_analysis import position_analysis, displacement_analysis, x_displacement_analysis
from Fiber_analysis import apply_preprocessing, calculate_dff, calculate_zscore
from Running_analysis import running_bout_analysis_classify, preprocess_running_data
from Running_induced_activity_analysis import show_running_induced_analysis
from Drug_induced_activity_analysis import show_drug_induced_analysis
from Optogenetic_induced_activity_analysis import show_optogenetic_induced_analysis
from Multimodal_analysis import identify_optogenetic_events, identify_drug_events, calculate_optogenetic_pulse_info, group_optogenetic_sessions

from logger import log_message, set_log_widget

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    log_message("OpenCV not installed, video export function unavailable. Please run 'pip install opencv-python' to install.", "WARNING")

# Global channel memory
CHANNEL_MEMORY_FILE = "channel_memory.json"
EVENT_CONFIG_FILE = "event_config.json"
OPTO_POWER_CONFIG_FILE = "opto_power_config.json"

channel_memory = {}
event_config = {}
opto_power_config = {}

def load_channel_memory():
    """Load channel memory from file"""
    global channel_memory
    if os.path.exists(CHANNEL_MEMORY_FILE):
        try:
            with open(CHANNEL_MEMORY_FILE, 'r') as f:
                channel_memory = json.load(f)
        except:
            channel_memory = {}

def save_channel_memory():
    """Save channel memory to file"""
    try:
        with open(CHANNEL_MEMORY_FILE, 'w') as f:
            json.dump(channel_memory, f)
    except:
        pass

def load_event_config():
    """Load event configuration from file"""
    global event_config
    if os.path.exists(EVENT_CONFIG_FILE):
        try:
            with open(EVENT_CONFIG_FILE, 'r') as f:
                event_config = json.load(f)
        except:
            event_config = {
                'drug_event': 'Event1',
                'opto_event': 'Input3',
                'running_start': 'Input2'
            }

def save_event_config():
    """Save event configuration to file"""
    try:
        with open(EVENT_CONFIG_FILE, 'w') as f:
            json.dump(event_config, f)
    except:
        pass

def load_opto_power_config():
    """Load optogenetic power configuration from file"""
    global opto_power_config
    if os.path.exists(OPTO_POWER_CONFIG_FILE):
        try:
            with open(OPTO_POWER_CONFIG_FILE, 'r') as f:
                opto_power_config = json.load(f)
        except:
            opto_power_config = {}

def save_opto_power_config():
    """Save optogenetic power configuration to file"""
    try:
        with open(OPTO_POWER_CONFIG_FILE, 'w') as f:
            json.dump(opto_power_config, f)
    except:
        pass

load_channel_memory()
load_event_config()
load_opto_power_config()

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
        resize_frame.config(cursor="size_nw_se")
        
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
        resize_frame.config(cursor="size_nw_se")
        
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
            '410': {'main': "#0019fd", 'light': '#5dade2', 'lighter': '#85c1e9'},  # Blue family
            '470': {'main': "#06b720", 'light': '#58d68d', 'lighter': '#82e0aa'},  # Green family
            '560': {'main': "#f3b312", 'light': '#f8b24c', 'lighter': '#fad7a0'}   # Yellow family
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
        ast2_data = self.animal_data.get('ast2_data_adjusted')
        fs = ast2_data['header']['inputRate']/ast2_data['header']['saveEvery']
        for idx, (start, end) in enumerate(self.animal_data['running_bouts'][analysis_type]):
            lbl = analysis_type if idx == 0 else '_nolegend_'
            self.ax.axvspan(start/fs, end/fs,
                            color='orange',
                            alpha=0.1,
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
                                alpha=0.1,
                                label=lbl)
    
    def _plot_drug_markers(self):
        """Plot drug administration events"""
        if "fiber_events" in self.animal_data:
            fiber_events = self.animal_data['fiber_events']
            drug_events = identify_drug_events(fiber_events)
            for idx in range(0, len(drug_events), 2):
                (start, _), (end, _) = drug_events[idx], drug_events[idx+1]
                lbl = "Drug Administration" if idx == 0 else '_nolegend_'
                self.ax.axvspan(int(start), int(end),
                                color='red',
                                alpha=0.1,
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
        resize_frame.config(cursor="size_nw_se")
        
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
                speed = processed_data['bout_speed']
            else:
                speed = ast2_data['data']['speed']
            
            # Plot speed data
            self.ax.plot(timestamps, speed, 'b-', label='Running Speed', linewidth=1, alpha=0.7)
            
            # Plot analysis data if available
            if self.animal_data.get('running_processed_data'):
                self.plot_analysis_data()
            
            # Set title based on current analysis
            if self.animal_data.get('running_processed_data'):
                title = f"Running Data - {disp_var.get()}"
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
        ast2_data = self.animal_data.get('ast2_data_adjusted')
        fs = ast2_data['header']['inputRate']/ast2_data['header']['saveEvery']
        for idx, (start, end) in enumerate(self.animal_data['running_bouts'][analysis_type]):
            lbl = analysis_type if idx == 0 else '_nolegend_'
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

def import_multi_animals():
    """Modified to create separate entries for each channel"""
    global selected_files, multi_animal_data, current_experiment_mode

    base_dir = filedialog.askdirectory(title="Select Free Moving/Behavioural directory")
    if not base_dir:
        return

    try:
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
                            speed = h_AST2_raw2Speed(raw_data[running_channel], header, voltageRange=None)
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

        if not selected_files:
            log_message("No valid animal data found in the selected directory", "WARNING")
        else:
            mode_name = "Fiber+AST2" if current_experiment_mode == EXPERIMENT_MODE_FIBER_AST2 else "Fiber+AST2+DLC"
            log_message(f"Found {len(selected_files)} channel entries in {mode_name} mode", "INFO")
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
                    speed = h_AST2_raw2Speed(raw_data[running_channel], header, voltageRange=None)
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

        if added_channels:
            show_channel_selection_dialog()
            mode_name = "Fiber+AST2" if current_experiment_mode == EXPERIMENT_MODE_FIBER_AST2 else "Fiber+AST2+DLC"
            log_message(f"Added {base_animal_id} with {len(added_channels)} channels ({mode_name} mode)", "INFO")
        else:
            log_message(f"No new channels added for {base_animal_id}", "WARNING")

    except Exception as e:
        log_message(f"Failed to add single animal: {str(e)}", "ERROR")

def load_fiber_data(file_path=None):
    """Modified to return data structure for channel splitting"""
    path = file_path
    try:
        fiber_data = pd.read_csv(path, skiprows=1, delimiter=',', low_memory=False)
        fiber_data = fiber_data.loc[:, ~fiber_data.columns.str.contains('^Unnamed')]
        fiber_data.columns = fiber_data.columns.str.strip()

        time_col = None
        possible_time_columns = ['timestamp', 'time', 'time(ms)']
        for col in fiber_data.columns:
            col_lower = col.lower()
            if any(keyword in col_lower for keyword in possible_time_columns):
                time_col = col
                break
        
        if not time_col:
            numeric_cols = fiber_data.select_dtypes(include=np.number).columns
            if len(numeric_cols) > 0:
                time_col = numeric_cols[0]
        
        fiber_data[time_col] = fiber_data[time_col] / 1000
        
        events_col = None
        for col in fiber_data.columns:
            if 'event' in col.lower():
                events_col = col
                break
        
        channels = {'time': time_col, 'events': events_col}
        
        # Parse channel data
        channel_data = {}
        channel_pattern = re.compile(r'CH(\d+)-(\d+)', re.IGNORECASE)
        
        for col in fiber_data.columns:
            match = channel_pattern.match(col)
            if match:
                channel_num = int(match.group(1))
                wavelength = int(match.group(2))
                
                if channel_num not in channel_data:
                    channel_data[channel_num] = {'410': None, '470': None, '560': None}
                
                if wavelength == 410:
                    channel_data[channel_num]['410'] = col
                elif wavelength == 470:
                    channel_data[channel_num]['470'] = col
                elif wavelength == 560:
                    channel_data[channel_num]['560'] = col
        
        log_message(f"Fiber data loaded, {len(channel_data)} channels detected", "INFO")
        
        return {
            'fiber_data': fiber_data,
            'channels': channels,
            'channel_data': channel_data
        }
    except Exception as e:
        log_message(f"Failed to load fiber data: {str(e)}", "ERROR")
        return None
    
def load_fiber_events(file_path):
    """Load fiber events from Events.csv file"""
    path = file_path
    try:
        events_data = pd.read_csv(path, delimiter=',', low_memory=False)
        log_message("Fiber events data loaded", "INFO")

        return events_data
    except Exception as e:
        log_message(f"Failed to load fiber events data: {str(e)}", "ERROR")
        return None

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
        saved_diameter = channel_memory.get(f"{animal_single_channel_id}_diameter", threadmill_diameter)
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
            invert_value = invert_running_vars[animal_single_channel_id].get()
            animal_data['invert_running'] = invert_value
            channel_memory[f"{animal_single_channel_id}_invert_running"] = invert_value
        
        # Diameter setting
        if animal_single_channel_id in diameter_vars:
            try:
                diameter_value = float(diameter_vars[animal_single_channel_id].get())
                if diameter_value <= 0:
                    raise ValueError("Diameter must be positive")
                animal_data['threadmill_diameter'] = diameter_value
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
                    old_diameter = globals().get('threadmill_diameter', 22)
                    
                    globals()['invert_running'] = animal_data.get('invert_running', False)
                    globals()['threadmill_diameter'] = animal_data.get('threadmill_diameter', 22)
                    
                    speed = h_AST2_raw2Speed(raw_data[selected_channel], header, voltageRange=None)
                    ast2_data = {
                        'header': header,
                        'data': speed
                    }
                    animal_data['ast2_data'] = ast2_data
                    
                    # Restore global settings
                    globals()['invert_running'] = old_invert
                    globals()['threadmill_diameter'] = old_diameter
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
        drug_event_name = event_config.get('drug_event', 'Event1')

        # Find Input2 events (running markers) - running start time
        input2_events = fiber_data[fiber_data[events_col].str.contains(running_start_name, na=False)]
        if len(input2_events) < 1:
            log_message("Could not find Input2 events for running start", "ERROR")
            return False
        
        global input3_events, drug_events

        input3_events = fiber_data[fiber_data[events_col].str.contains(opto_event_name, na=False)]
        if len(input3_events) < 1:
            multimodal_menu.entryconfig("Optogenetics-Induced Activity Analysis", state="disabled")
            log_message("Could not find Input3 events for optogenetic analysis", "INFO")
            running_induced_menu.entryconfig("Running + Optogenetics", state="disabled")
            setting_menu.entryconfig("Optogenetic Power Configuration", state="disabled")
        else:
            multimodal_menu.entryconfig("Optogenetics-Induced Activity Analysis", state="normal")
            running_induced_menu.entryconfig("Running + Optogenetics", state="normal")
            setting_menu.entryconfig("Optogenetic Power Configuration", state="normal")
        
        drug_events = fiber_data[fiber_data[events_col].str.contains(drug_event_name, na=False)]
        if len(drug_events) < 1:
            multimodal_menu.entryconfig("Drug-Induced Activity Analysis", state="disabled")
            running_induced_menu.entryconfig("Running + Drug", state="disabled")
            log_message("Could not find Event2 events for drug analysis", "INFO")
        else:
            multimodal_menu.entryconfig("Drug-Induced Activity Analysis", state="normal")
            running_induced_menu.entryconfig("Running + Drug", state="normal")

        if len(input3_events) < 1 or len(drug_events) < 1:
            optogenetics_induced_menu.entryconfig("Optogenetics + Drug", state="disabled")
            running_induced_menu.entryconfig("Running + Optogenetics + Drug", state="disabled")
        elif len(input3_events) >= 1 and len(drug_events) >= 1:
            optogenetics_induced_menu.entryconfig("Optogenetics + Drug", state="normal")
            running_induced_menu.entryconfig("Running + Optogenetics + Drug", state="normal") 

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

def read_dlc_file(file_path):
    """Read dlc CSV file and parse bodyparts data"""
    if file_path:
        log_message(f"Selected: {file_path}")
        try:
            # Read CSV file, don't use first row as header
            df = pd.read_csv(file_path, header=None, low_memory=False)
            
            # Check if file has enough rows
            if len(df) < 4:
                log_message("CSV file doesn't have enough rows, at least 4 rows needed", "ERROR")
                return
            
            # Get bodyparts information from second row (index 1)
            if len(df) > 1:
                bodyparts_row = df.iloc[1].values
            else:
                log_message("Cannot find bodyparts information in second row", "ERROR")
                return
            
            # Find all unique bodyparts
            global unique_bodyparts
            unique_bodyparts = []
            for i in range(1, len(bodyparts_row), 3):  # Start from index 1, skip "bodyparts" title
                if i < len(bodyparts_row):
                    part = bodyparts_row[i]
                    if pd.notna(part) and str(part).strip() != '':
                        bodypart_name = str(part).strip()
                        if bodypart_name not in unique_bodyparts:
                            unique_bodyparts.append(bodypart_name)
            
            if not unique_bodyparts:
                log_message("No valid bodyparts information found", "ERROR")
                return
                
            log_message(f"Detected bodyparts: {unique_bodyparts}")
            log_message(f"CSV file total columns: {df.shape[1]}")
            
            # Create dictionary to store x, y, likelihood data for each bodypart
            bodypart_data = {}
            
            # Extract data starting from fourth row (index 3)
            data_start_row = 3
            if len(df) <= data_start_row:
                log_message("Not enough data rows, cannot extract data from fourth row", "ERROR")
                return
                
            data_rows = df.iloc[data_start_row:]
            
            # Check if there are enough columns
            expected_cols = len(unique_bodyparts) * 3
            if df.shape[1] < expected_cols:
                log_message(f"Not enough columns, expected {expected_cols}, got {df.shape[1]}", "ERROR")
                return
            
            # Create data vectors for each bodypart
            col_index = 1  # Start from second column, skip "bodyparts" title
            for bodypart in unique_bodyparts:
                try:
                    # Each bodypart occupies 3 columns: x, y, likelihood
                    if col_index + 2 < df.shape[1]:
                        x_data = data_rows.iloc[:, col_index].dropna().astype(float).values
                        y_data = data_rows.iloc[:, col_index + 1].dropna().astype(float).values
                        likelihood_data = data_rows.iloc[:, col_index + 2].dropna().astype(float).values
                        
                        bodypart_data[bodypart] = {
                            'x': x_data,
                            'y': y_data,
                            'likelihood': likelihood_data
                        }
                    else:
                        log_message("Bodypart '{bodypart}' column index out of range", "WARNING")
                        break
                except Exception as col_error:
                    log_message(f"Error processing bodypart '{bodypart}': {col_error}", "ERROR")
                    continue
                
                col_index += 3
            
            # Display parsing results
            result_info = f"File parsed successfully!\n"
            result_info += f"Found {len(unique_bodyparts)} bodyparts: {', '.join(unique_bodyparts)}\n"
            result_info += f"Data rows: {len(data_rows)}\n"
            
            for bodypart, data in bodypart_data.items():
                result_info += f"{bodypart}: x({len(data['x'])}), y({len(data['y'])}), likelihood({len(data['likelihood'])})"
            log_message(result_info, "INFO")
            
            # Print first few rows for verification
            log_message(f"Bodyparts found: {unique_bodyparts}")
            for bodypart, data in bodypart_data.items():
                log_message(f"\n{bodypart}:")
                log_message(f"  X (first 5): {data['x'][:5]}")
                log_message(f"  Y (first 5): {data['y'][:5]}")
                log_message(f"  Likelihood (first 5): {data['likelihood'][:5]}")
            
            # Store data as global variable for later use
            global parsed_data
            parsed_data = bodypart_data

            return parsed_data
        
        except Exception as e:
            log_message(f"Failed to read file: {e}", "ERROR")
            return None

def convert_num(s):
    s = s.strip()
    try:
        if '.' in s or 'e' in s or 'E' in s:
            return float(s)
        else:
            return int(s)
    except ValueError:
        return s

def h_AST2_readData(filename):
    header = {}
    
    with open(filename, 'rb') as fid:
        header_lines = []
        while True:
            line = fid.readline().decode('utf-8').strip()
            if line == 'header_end':
                break
            header_lines.append(line)
        
        for line in header_lines:
            match = re.match(r"header\.(\w+)\s*=\s*(.*);$", line)
            if not match:
                continue
            key = match.group(1)
            value_str = match.group(2).strip()
            
            if value_str.startswith("'") and value_str.endswith("'"):
                header[key] = value_str[1:-1]
            elif value_str.startswith('[') and value_str.endswith(']'):
                inner = value_str[1:-1].strip()
                if not inner:
                    header[key] = []
                else:
                    if ';' in inner:
                        rows = inner.split(';')
                        array = []
                        for row in rows:
                            row = row.strip()
                            if row:
                                elements = row.split()
                                array.append([convert_num(x) for x in elements])
                        header[key] = array
                    else:
                        elements = inner.split()
                        header[key] = [convert_num(x) for x in elements]
            else:
                header[key] = convert_num(value_str)
        
        binary_data = np.fromfile(fid, dtype=np.int16)
    
    if 'activeChIDs' in header and 'scale' in header:
        if isinstance(header['activeChIDs'], list):
            numOfCh = len(header['activeChIDs'])
        elif isinstance(header['activeChIDs'], int):
            numOfCh = 1
        data = binary_data.reshape((numOfCh, -1), order='F') / header['scale']
    else:
        data = None

    return header, data

def h_AST2_raw2Speed(rawData, info, voltageRange=None):
    if voltageRange is None or len(voltageRange) == 0:
        voltageRange = h_calibrateVoltageRange(rawData)
    
    speedDownSampleFactor = info['saveEvery']
    
    rawDataLength = len(rawData)
    segmentLength = speedDownSampleFactor
    speedDataLength = rawDataLength // segmentLength
    
    if rawDataLength % segmentLength != 0:
        log_message(f"SpeedDataLength is not integer!  speedDataLength = {rawDataLength}, speedDownSampleFactor = {segmentLength}", "ERROR")
        rawData = rawData[:speedDataLength * segmentLength]
    
    t = ((np.arange(speedDataLength) + 1) * speedDownSampleFactor) / info['inputRate']
    time_segment = (np.arange(segmentLength) + 1) / info['inputRate']
    reshapedData = rawData.reshape(segmentLength, speedDataLength, order='F')
    speedData2 = h_computeSpeed2(time_segment, reshapedData, voltageRange)
    
    if invert_running:
        speedData2 = -speedData2
    
    speedData = {
        'timestamps': t,
        'speed': speedData2
    }
    
    return speedData

def h_calibrateVoltageRange(rawData):
    peakValue, peakPos = h_AST2_findPeaks(rawData)
    valleyValue, valleyPos = h_AST2_findPeaks(-rawData)
    valleyValue = [-x for x in valleyValue]
    
    if len(peakValue) > 0 and len(valleyValue) > 0:
        voltageRange = [np.mean(valleyValue), np.mean(peakValue)]
        if np.diff(voltageRange) > 3:
            log_message(f"Calibrated voltage range is {voltageRange}")
        else:
            log_message("Calibration error. Range too small")
            voltageRange = [0, 5]
    else:
        voltageRange = [0, 5]
        log_message("Calibration fail! Return default: [0 5].")
    
    return voltageRange

def h_AST2_findPeaks(data):
    transitionPos = np.where(np.abs(np.diff(data)) > 2)[0]
    
    transitionPos = transitionPos[(transitionPos > 50) & (transitionPos < len(data) - 50)]
    
    if len(transitionPos) >= 1:
        peakValue = np.zeros(len(transitionPos))
        peakPos = np.zeros(len(transitionPos))
        
        for i, pos in enumerate(transitionPos):
            segment = data[pos-50:pos+51]
            peakValue[i] = np.max(segment)
            peakPos[i] = pos - 50 + np.argmax(segment)
    else:
        return [], []
    
    avg = np.mean(data)
    maxData = np.max(data)
    thresh = avg + 0.8 * (maxData - avg)
    
    mask = peakValue > thresh
    peakValue = peakValue[mask]
    peakPos = peakPos[mask]
    
    return peakValue, peakPos

def h_computeSpeed2(time, data, voltageRange):
    deltaVoltage = voltageRange[1] - voltageRange[0]
    thresh = 3/5 * deltaVoltage
    
    diffData = np.diff(data, axis=0)
    I = np.abs(diffData) > thresh
    
    data = data.copy()
    for j in range(data.shape[1]):
        if np.any(I[:, j]):
            ind = np.where(I[:, j])[0]
            for i in ind:
                if diffData[i, j] < thresh:
                    data[i+1:, j] = data[i+1:, j] + deltaVoltage
                elif diffData[i, j] > thresh:
                    data[i+1:, j] = data[i+1:, j] - deltaVoltage
    
    dataInDegree = (data / deltaVoltage) * 360
    
    deltaDegree = np.mean(dataInDegree[-11:, :], axis=0) - np.mean(dataInDegree[:11, :], axis=0)
    
    I1 = deltaDegree > 200
    I2 = deltaDegree < -200
    deltaDegree[I1] = deltaDegree[I1] - 360
    deltaDegree[I2] = deltaDegree[I2] + 360
    
    duration = np.mean(time[-11:]) - np.mean(time[:11])
    speed = deltaDegree / duration
    
    diameter = threadmill_diameter
    speed2 = speed / 360 * diameter * np.pi
    
    return speed2

def create_visualization_window():
    """Create the bodyparts location visualization window"""
    global visualization_window, parsed_data, central_label
    
    if 'parsed_data' not in globals() or not parsed_data:
        log_message("Please load the behavior data file first", "WARNING")
        return
    
    # If the window already exists, close it first
    if visualization_window:
        visualization_window.close_window()
    
    # Hide the default label in the central display area
    if 'central_label' in globals():
        try:
            # Check if central_label still exists
            if hasattr(central_label, 'winfo_exists') and central_label.winfo_exists():
                central_label.pack_forget()
        except tk.TclError:
            # If central_label has been destroyed, create a new one
            central_label = tk.Label(central_display_frame, text="Central Display Area\nThe bodyparts location visualization window will be displayed after loading the CSV file", bg="#f8f8f8", fg="#666666")
    
    # Create a new visualization window
    visualization_window = BodypartVisualizationWindow(central_display_frame, parsed_data)

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

def create_bodypart_buttons(bodyparts):
    """Create bodypart toggle buttons"""
    # Clear existing buttons
    for widget in left_frame.winfo_children():
        widget.destroy()
    
    bodypart_buttons.clear()
    selected_bodyparts.clear()
    
    # Define color configuration (consistent with visualization window)
    colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', 
             '#1abc9c', '#e67e22', '#34495e', '#f1c40f', '#95a5a6']
    
    # Add title
    title_label = tk.Label(left_frame, text="🎯 Bodyparts:", font=("Microsoft YaHei", 12, "bold"), 
                          bg="#e0e0e0", fg="#2c3e50")
    title_label.pack(pady=(10, 5))
    
    # Create toggle button for each bodypart
    for i, bodypart in enumerate(bodyparts):
        color = colors[i % len(colors)]
        button_text = f"{i+1}. {bodypart}"  # Add numbering
        button = tk.Button(
            left_frame,
            text=button_text,
            width=15,
            relief=tk.RAISED,
            bg=color,
            fg="white",
            font=("Microsoft YaHei", 9, "bold"),
            activebackground=color,
            activeforeground="white",
            cursor="hand2",
            command=lambda bp=bodypart: toggle_bodypart(bp, bodypart_buttons[bp])
        )
        button.pack(pady=3, padx=8, fill=tk.X)
        bodypart_buttons[bodypart] = button
    
    # Add separator
    separator = tk.Frame(left_frame, height=2, bg="#bdc3c7")
    separator.pack(fill=tk.X, padx=10, pady=10)
    
    # Add skeleton function title
    skeleton_title = tk.Label(left_frame, text="🦴 Skeleton Building:", font=("Microsoft YaHei", 12, "bold"), 
                             bg="#e0e0e0", fg="#2c3e50")
    skeleton_title.pack(pady=(5, 5))
    
    # Add skeleton buttons
    add_skeleton_btn = tk.Button(
        left_frame,
        text="Add Skeleton",
        width=15,
        relief=tk.RAISED,
        bg="#3498db",
        fg="white",
        font=("Microsoft YaHei", 9, "bold"),
        activebackground="#2980b9",
        activeforeground="white",
        cursor="hand2",
        command=start_skeleton_building
    )
    add_skeleton_btn.pack(pady=3, padx=8, fill=tk.X)
    
    confirm_skeleton_btn = tk.Button(
        left_frame,
        text="Confirm",
        width=15,
        relief=tk.RAISED,
        bg="#27ae60",
        fg="white",
        font=("Microsoft YaHei", 9, "bold"),
        activebackground="#229954",
        activeforeground="white",
        cursor="hand2",
        command=confirm_skeleton,
        state=tk.DISABLED
    )
    confirm_skeleton_btn.pack(pady=3, padx=8, fill=tk.X)
    
    # Store buttons as global variables for later access
    global add_skeleton_button, confirm_skeleton_button
    add_skeleton_button = add_skeleton_btn
    confirm_skeleton_button = confirm_skeleton_btn
    
    # Add separator
    separator2 = tk.Frame(left_frame, height=2, bg="#bdc3c7")
    separator2.pack(fill=tk.X, padx=10, pady=10)
    
    # Add FPS conversion function title
    fps_title = tk.Label(left_frame, text="⏱️ FPS Conversion:", font=("Microsoft YaHei", 12, "bold"), 
                        bg="#e0e0e0", fg="#2c3e50")
    fps_title.pack(pady=(5, 5))
    
    # FPS setting frame
    fps_frame = tk.Frame(left_frame, bg="#e0e0e0")
    fps_frame.pack(pady=3, padx=8, fill=tk.X)
    
    fps_label = tk.Label(fps_frame, text="FPS:", font=("Microsoft YaHei", 9), 
                        bg="#e0e0e0", fg="#2c3e50")
    fps_label.pack(side=tk.LEFT)
    
    global fps_var
    fps_var = tk.StringVar(value="30")
    fps_entry = tk.Entry(fps_frame, textvariable=fps_var, width=8, 
                        font=("Microsoft YaHei", 9))
    fps_entry.pack(side=tk.RIGHT)
    
    time_unit_frame = tk.Frame(left_frame, bg="#e0e0e0")
    time_unit_frame.pack(pady=3, padx=8, fill=tk.X)
    
    time_unit_label = tk.Label(time_unit_frame, text="Time Unit:", font=("Microsoft YaHei", 9), 
                              bg="#e0e0e0", fg="#2c3e50")
    time_unit_label.pack(side=tk.LEFT)
    
    global time_unit_var
    time_unit_var = tk.StringVar(value="seconds")
    time_unit_combo = ttk.Combobox(time_unit_frame, textvariable=time_unit_var, 
                                  values=["seconds", "minutes"], width=6, state="readonly")
    time_unit_combo.pack(side=tk.RIGHT)
    
    # Enable FPS conversion checkbox
    global fps_conversion_var
    fps_conversion_var = tk.BooleanVar()
    fps_checkbox = tk.Checkbutton(left_frame, text="Enable FPS Conversion", 
                                 variable=fps_conversion_var,
                                 font=("Microsoft YaHei", 9),
                                 bg="#e0e0e0", fg="#2c3e50",
                                 activebackground="#e0e0e0",
                                 command=apply_fps_conversion)
    fps_checkbox.pack(pady=3, padx=8)
    
    # Apply button
    apply_fps_btn = tk.Button(
        left_frame,
        text="Apply Settings",
        width=15,
        relief=tk.RAISED,
        bg="#e67e22",
        fg="white",
        font=("Microsoft YaHei", 9, "bold"),
        activebackground="#d35400",
        activeforeground="white",
        cursor="hand2",
        command=apply_fps_conversion
    )
    apply_fps_btn.pack(pady=3, padx=8, fill=tk.X)

def main_visualization(animal_data=None):
    """Modified to handle different experiment modes"""
    global parsed_data, visualization_window, fiber_plot_window, running_plot_window
    global current_experiment_mode
    
    for widget in central_display_frame.winfo_children():
        widget.destroy()
    
    if animal_data is None:
        # Using global data
        if current_experiment_mode == EXPERIMENT_MODE_FIBER_AST2_DLC:
            if not hasattr(globals(), 'parsed_data') or not parsed_data:
                log_message("No DLC data available for visualization", "WARNING")
                return
            
            create_bodypart_buttons(list(parsed_data.keys()))
            create_visualization_window()
        
        create_fiber_visualization()
        create_running_visualization()
    else:
        # Using animal_data
        animal_mode = animal_data.get('experiment_mode', EXPERIMENT_MODE_FIBER_AST2_DLC)
        
        if animal_mode == EXPERIMENT_MODE_FIBER_AST2_DLC:
            if 'dlc_data' not in animal_data or not animal_data['dlc_data']:
                log_message("No DLC data available for visualization", "WARNING")
            else:
                parsed_data = animal_data['dlc_data']
                create_bodypart_buttons(list(parsed_data.keys()))
                create_visualization_window()
        else:
            # Fiber+AST2 mode: show info message
            info_label = tk.Label(central_display_frame, 
                                 text="Fiber + AST2 Mode\n\nBodypart visualization not available\nSee fiber and running plots on the right",
                                 bg="#f8f8f8", fg="#666666",
                                 font=("Arial", 12))
            info_label.pack(pady=100)
        
        create_fiber_visualization(animal_data)
        create_running_visualization(animal_data)

def create_fiber_visualization(animal_data=None):
    global fiber_plot_window, input3_events, drug_events
    
    if fiber_plot_window:
        fiber_plot_window.close_window()
    
    target_signal = target_signal_var.get() if 'target_signal_var' in globals() else "470"
    
    if animal_data:
        if 'preprocessed_data' in animal_data:
            fiber_plot_window = FiberVisualizationWindow(central_display_frame, animal_data, target_signal, input3_events, drug_events)
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
                
            fiber_plot_window = FiberVisualizationWindow(central_display_frame, animal_data, target_signal, input3_events, drug_events)

def create_running_visualization(animal_data=None):
    global running_plot_window
    
    if running_plot_window:
        running_plot_window.close_window()
    
    running_plot_window = RunningVisualizationWindow(central_display_frame, animal_data)

def display_analysis_results(analysis_type, animal_data):
    """Display analysis results for current animal"""
    if analysis_type == 'running_analysis':
        display_running_analysis_for_animal(animal_data)
    elif analysis_type == 'fiber_preprocessing':
        display_fiber_results_for_animal(animal_data)

def display_running_analysis_for_animal(animal_data):
    """Display running analysis results for specific animal"""
    analysis_type = disp_var.get()
    bouts = animal_data.get('bouts', {})
    
    # Update running plot window
    if running_plot_window:
        running_plot_window.update_plot()
    
    # Update fiber plot window if exists
    if fiber_plot_window:
        fiber_plot_window.update_plot()

def display_fiber_results_for_animal(animal_data):
    """Display fiber preprocessing results for specific animal"""
    if fiber_plot_window:
        fiber_plot_window.animal_data = animal_data
        
        # Determine which plot type to show based on available data
        if 'zscore_data' in animal_data and animal_data['zscore_data']:
            fiber_plot_window.set_plot_type("zscore")
        elif 'dff_data' in animal_data and animal_data['dff_data']:
            fiber_plot_window.set_plot_type("dff")
        elif 'preprocessed_data' in animal_data:
            fiber_plot_window.set_plot_type("motion_corrected")
        else:
            fiber_plot_window.set_plot_type("raw")

def create_animal_list():
    for widget in right_frame.winfo_children():
        widget.destroy()

    multi_animal_frame = ttk.LabelFrame(right_frame, text="Multi Animal Analysis")
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
                              height=5)
    file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    xscroll.config(command=file_listbox.xview)
    yscroll.config(command=file_listbox.yview)
    
    list_frame.columnconfigure(0, weight=1)
    list_frame.rowconfigure(0, weight=1)
    
    file_listbox.bind('<<ListboxSelect>>', on_animal_select)

    btn_frame = ttk.Frame(multi_animal_frame)
    btn_frame.pack(fill="both", padx=5, pady=5)

    style = ttk.Style()
    style.configure("Accent.TButton", 
                    font=("Microsoft YaHei", 10),
                    padding=(10, 5))

    clear_selected_btn = ttk.Button(btn_frame, 
                                text="Clear Selected", 
                                command=clear_selected,
                                style="Accent.TButton")
    clear_selected_btn.pack(fill="x", padx=2, pady=(2, 1))

    clear_all_btn = ttk.Button(btn_frame, 
                            text="Clear All", 
                            command=clear_all,
                            style="Accent.TButton")
    clear_all_btn.pack(fill="x", padx=2, pady=(1, 2))

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
    global selected_files, multi_animal_data
    selected_files = []
    multi_animal_data = []
    
    # Reset analysis manager
    analysis_manager.last_analysis_type = None

def fiber_preprocessing():
    global preprocess_frame, multi_animal_data
    
    # Detect available wavelengths from loaded data
    available_wavelengths = []
    if multi_animal_data:
        for animal_data in multi_animal_data:
            if 'channel_data' in animal_data:
                wavelength_combos = detect_wavelengths_and_generate_combinations(animal_data['channel_data'])
                available_wavelengths.extend(wavelength_combos)
                break  # Use first animal's wavelengths as reference
    
    # Remove duplicates and sort
    available_wavelengths = sorted(list(set(available_wavelengths)))
    
    if not available_wavelengths:
        available_wavelengths = ["470", "560"]  # Fallback default
    
    prep_window = tk.Toplevel(root)
    prep_window.title("Fiber Data Preprocessing")
    prep_window.geometry("320x600")
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
    ref_options = ["410", "baseline"]
    ref_menu = ttk.OptionMenu(signal_frame, reference_signal_var, "410", *ref_options)
    ref_menu.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
    
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
              command=prep_window.destroy).pack(side=tk.RIGHT, padx=5)

def toggle_motion_correction():
        if reference_signal_var.get() != "410":
            apply_motion.set(False)
            log_message("Motion correction requires 410nm as reference signal", "WARNING")

def detect_wavelengths_and_generate_combinations(channel_data):
    """Detect available wavelengths and generate all possible combinations"""
    # Get all available wavelengths (excluding 410)
    all_wavelengths = set()
    for channel_num, wavelengths in channel_data.items():
        for wl in wavelengths.keys():
            if wl not in ['410', '415']:  # Exclude reference wavelengths
                all_wavelengths.add(wl)
    
    all_wavelengths = sorted(list(all_wavelengths))
    
    if not all_wavelengths:
        return []
    
    # Generate all combinations
    from itertools import combinations
    
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
    global multi_animal_data, current_animal_index, threadmill_diameter
    
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
    disp_frame = ttk.Frame(filter_disp_frame)
    disp_frame.pack(fill=tk.X, pady=(0, 10))
    ttk.Label(disp_frame, text="Display Bouts:").pack(side=tk.LEFT)
    
    bout_menu = ttk.Combobox(disp_frame, textvariable=disp_var,
                                values=bouts_param, state="readonly", width=20)
    bout_menu.pack(side=tk.RIGHT, padx=(10, 0))
    disp_var.set(bouts_param[1])

    bout_param_frame = ttk.LabelFrame(top_row,
                                    text="Bout Detection Parameters",
                                    padding=10)
    bout_param_frame.grid(row=0, column=1, sticky='ew', padx=(5, 0), pady=(0, 10))

    bout_param_defs = [
        ("Smooth window (frames)",     "smooth_window",       "float", 5,    1,  (2, 50)),
        ("General threshold (cm/s)",   "threshold",           "float", 0.5,  0.1, (0.1, 10)),
        ("General min duration (s)",   "gen_min_dur",         "float", 0.5,  0.1, (0.1, 20)),
        ("Min rest duration (s)",      "rest_dur",            "float", 4.0,  0.5, (0.5, 30)),
        ("Pre-locomotion buffer (s)",  "pre_buffer",          "float", 5.0,  0.5, (0, 20)),
        ("Post-locomotion buffer (s)", "post_buffer",         "float", 5.0,  0.5, (0, 20)),
        ("Locomotion duration (s)",    "locomotion_duration", "float", 2.0,  0.5, (0, 10))
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
        
        smooth_window       = bout_vars["smooth_window"].get()
        threshold           = bout_vars["threshold"].get()
        gen_min_dur         = bout_vars["gen_min_dur"].get()
        rest_dur            = bout_vars["rest_dur"].get()
        pre_buf             = bout_vars["pre_buffer"].get()
        post_buf            = bout_vars["post_buffer"].get()
        locomotion_duration = bout_vars["locomotion_duration"].get()
        processed_data = preprocess_running_data(ast2_data, filter_settings)
        if not processed_data:
            canvas.draw(); return
        
        fs = ast2_data['header']['inputRate'] / ast2_data['header']['saveEvery']
        bouts, bout_speed = running_bout_analysis_classify(
            processed_data,
            smooth_window=smooth_window,
            general_threshold=threshold,
            general_min_duration=gen_min_dur,
            rest_min_duration=rest_dur,
            pre_locomotion_buffer=pre_buf,
            post_locomotion_buffer=post_buf,
            locomotion_duration=locomotion_duration)
        processed_data['bout_speed'] = bout_speed
        
        if processed_data:
            timestamps = processed_data['timestamps']
            original_speed = processed_data['original_speed']
            filtered_speed = processed_data['filtered_speed']
            bout_speed = processed_data['bout_speed']
            
            ax1.plot(timestamps, original_speed, 'k-', alpha=0.7, label='Original', linewidth=1)
            ax1.plot(timestamps, filtered_speed, 'r-', label='Filtered', linewidth=1)
            ax1.plot(timestamps, bout_speed, 'g-', label='Bout Speed', linewidth=1)
            
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

            smooth_window       = bout_vars["smooth_window"].get()
            threshold           = bout_vars["threshold"].get()
            gen_min_dur         = bout_vars["gen_min_dur"].get()
            rest_dur            = bout_vars["rest_dur"].get()
            pre_buf             = bout_vars["pre_buffer"].get()
            post_buf            = bout_vars["post_buffer"].get()
            locomotion_duration = bout_vars["locomotion_duration"].get()

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

                    bouts, bout_speed = running_bout_analysis_classify(
                        processed_data,
                        smooth_window=smooth_window,
                        general_threshold=threshold,
                        general_min_duration=gen_min_dur,
                        rest_min_duration=rest_dur,
                        pre_locomotion_buffer=pre_buf,
                        post_locomotion_buffer=post_buf,
                        locomotion_duration=locomotion_duration
                    )
                    processed_data['bout_speed'] = bout_speed
                    animal_data['running_processed_data'] = processed_data
                    animal_data['running_bouts'] = bouts
                    successful += 1
                    log_message(f"Processed {animal_single_channel_id}", "INFO")
                except Exception as e:
                    log_message(f"Error processing {animal_single_channel_id}: {e}", "ERROR")
                    failed += 1

            if current_animal_index < len(multi_animal_data) and running_plot_window:
                running_plot_window.animal_data = multi_animal_data[current_animal_index]
                running_plot_window.update_plot()

            log_message(f"Running preprocessing completed: "
                        f"Diameter {threadmill_diameter} cm, "
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
                if 'preprocessed_data' not in animal_data or animal_data['preprocessed_data'] is None:
                    log_message(f"Skipping {animal_single_channel_id}: No preprocessed data", "WARNING")
                    failed_calculations += 1
                    continue
                
                calculate_dff(
                    animal_data, 
                    target_signal,
                    reference_signal,
                    (baseline_start_val, baseline_end_val),
                    apply_baseline_val
                )
                
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

# Global analysis results manager
class AnalysisResultsManager:
    """Manage analysis results for all animals"""
    def __init__(self):
        self.last_analysis_type = None  # Track last analysis type
    
    def set_last_analysis(self, analysis_type):
        """Set the last performed analysis type"""
        self.last_analysis_type = analysis_type
        log_message(f"Last analysis type set to: {analysis_type}", "INFO")
    
    def get_last_analysis(self):
        """Get the last performed analysis type"""
        return self.last_analysis_type

# Initialize global analysis manager (add this near the top of the file)
analysis_manager = AnalysisResultsManager()

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
    mode_window.geometry("400x400")
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
    
    # Mode 1: Fiber + AST2
    mode1_radio = tk.Radiobutton(
        mode_frame,
        text="Fiber + AST2 (Running Only)",
        variable=mode_var,
        value=EXPERIMENT_MODE_FIBER_AST2,
        font=("Arial", 10),
        justify=tk.LEFT
    )
    mode1_radio.pack(anchor="w", pady=5)
    
    mode1_desc = tk.Label(mode_frame, 
                         text="  • Fiber photometry data\n  • Running wheel data (AST2)",
                         font=("Arial", 9), fg="gray", justify=tk.LEFT)
    mode1_desc.pack(anchor="w", padx=20)
    
    # Mode 2: Fiber + AST2 + DLC
    mode2_radio = tk.Radiobutton(
        mode_frame,
        text="Fiber + AST2 + DLC (Full Analysis)",
        variable=mode_var,
        value=EXPERIMENT_MODE_FIBER_AST2_DLC,
        font=("Arial", 10),
        justify=tk.LEFT
    )
    mode2_radio.pack(anchor="w", pady=(15, 5))
    
    mode2_desc = tk.Label(mode_frame, 
                         text="  • Fiber photometry data\n  • Running wheel data (AST2)\n  • DeepLabCut behavioral tracking",
                         font=("Arial", 9), fg="gray", justify=tk.LEFT)
    mode2_desc.pack(anchor="w", padx=20)
    
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
        
        # Update UI based on mode
        update_ui_for_mode()
        
        mode_name = "Fiber + AST2" if new_mode == EXPERIMENT_MODE_FIBER_AST2 else "Fiber + AST2 + DLC"
        log_message(f"Experiment mode set to: {mode_name}", "INFO")
        
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
    if current_experiment_mode == EXPERIMENT_MODE_FIBER_AST2:
        # Disable DLC-related menu items
        behaviour_analysis_menu.entryconfig("Position Analysis", state="disabled")
        behaviour_analysis_menu.entryconfig("Displacement Analysis", state="disabled")
        behaviour_analysis_menu.entryconfig("X Displacement Analysis", state="disabled")
        behaviour_analysis_menu.entryconfig("Trajectory Point Cloud", state="disabled")
        
    else:  # FIBER_AST2_DLC mode
        # Enable all menu items
        behaviour_analysis_menu.entryconfig("Position Analysis", state="normal")
        behaviour_analysis_menu.entryconfig("Displacement Analysis", state="normal")
        behaviour_analysis_menu.entryconfig("X Displacement Analysis", state="normal")
        behaviour_analysis_menu.entryconfig("Trajectory Point Cloud", state="normal")
    
    # Clear left panel if in Fiber+AST2 mode
    if current_experiment_mode == EXPERIMENT_MODE_FIBER_AST2:
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
    
    def save_config():
        event_config['drug_event'] = drug_var.get().strip()
        event_config['opto_event'] = opto_var.get().strip()
        event_config['running_start'] = running_var.get().strip()
        save_event_config()
        log_message("Event configuration saved", "INFO")
        dialog.destroy()
    
    # Buttons
    btn_frame = tk.Frame(main_frame, bg="#f8f8f8")
    btn_frame.pack(pady=(20, 0))
    
    tk.Button(btn_frame, text="Save", command=save_config,
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
                base_id = f"{animal_id}_Session{session_idx+1}_{freq:.1f}Hz_{pulse_width*1000:.0f}ms_{duration:.1f}s"
                
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

    # def apply_power():
    #     """Apply power values and create final IDs"""
    #     try:
    #         for base_id, power_var in power_vars.items():
    #             power = float(power_var.get())
    #             if power <= 0:
    #                 raise ValueError(f"Power must be positive for {base_id}")
                
    #             # Create final ID with power
    #             final_id = f"{base_id}_{power:.1f}mW"
    #             opto_power_config[final_id] = power
            
    #         save_opto_power_config()
    #         log_message(f"Power values applied for {len(opto_power_config)} sessions")
    #         dialog.destroy()
            
    #     except ValueError as e:
    #         log_message(f"Invalid power value: {str(e)}", "ERROR")
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
                final_id = f"{base_id}_{power:.1f}mW"
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

def save_path_setting():
    print(1)

def export_now_result():
    print(1)

def on_closing():
    log_message("Main window closed, exiting the program...", "INFO")
    root.quit()
    root.destroy()
    os.kill(os.getpid(), signal.SIGTERM)

root = tk.Tk()
root.title("Behavior Syllable Analysis")
root.state('zoomed')

root.protocol("WM_DELETE_WINDOW", on_closing)

# Experiment mode settings
EXPERIMENT_MODE_FIBER_AST2 = "fiber+ast2"
EXPERIMENT_MODE_FIBER_AST2_DLC = "fiber+ast2+dlc"
current_experiment_mode = EXPERIMENT_MODE_FIBER_AST2  # Default mode

target_signal_var = tk.StringVar(value="470")
reference_signal_var = tk.StringVar(value="410")
baseline_start = tk.DoubleVar(value=0)
baseline_end = tk.DoubleVar(value=60)
apply_smooth = tk.BooleanVar(value=False)
smooth_window = tk.IntVar(value=11)
smooth_order = tk.IntVar(value=5)
apply_baseline = tk.BooleanVar(value=False)
baseline_model = tk.StringVar(value="Polynomial")
apply_motion = tk.BooleanVar(value=False)
preprocess_frame = None
multimodal_analyzer = None
accrossday_analyzer = None

current_animal_index = 0
fiber_plot_window = None
running_plot_window = None
bodypart_buttons = {}
selected_bodyparts = set()
visualization_window = None

disp_var = tk.StringVar()

skeleton_connections = []
skeleton_building = False
skeleton_sequence = []

fps_var = None
time_unit_var = None
fps_conversion_var = None
fps_conversion_enabled = False
current_fps = 30

show_data_points_var = None

running_channel = 2
invert_running = False
threadmill_diameter = 22

log_text_widget = None

main_container = tk.Frame(root)
main_container.pack(fill=tk.BOTH, expand=True)

left_frame = tk.Frame(main_container, width=200, bg="#e0e0e0")
left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(5, 0), pady=5)
left_frame.pack_propagate(False)

middle_frame = tk.Frame(main_container)
middle_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0), pady=5)

central_display_frame = tk.Frame(middle_frame, bg="#f8f8f8", relief=tk.SUNKEN, bd=1)
central_display_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

bottom_display_frame = tk.Frame(middle_frame, bg="#f0f0f0", relief=tk.SUNKEN, bd=1, height=170)
bottom_display_frame.pack(fill=tk.X, pady=(0, 0))
bottom_display_frame.pack_propagate(False)

right_frame = tk.Frame(main_container, width=200, bg="#e8e8e8")
right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 5), pady=5)
right_frame.pack_propagate(False)

left_label = tk.Label(left_frame, text="Left Button Area", bg="#f8f8f8", fg="#666666")
left_label.pack(pady=20)

central_label = tk.Label(central_display_frame, text="Central Display Area", bg="#f8f8f8", fg="#666666")
central_label.pack(pady=20)

bottom_label = tk.Label(bottom_display_frame, text="Bottom Log Area", bg="#f0f0f0", fg="#666666")
bottom_label.pack(pady=10)

right_label = tk.Label(right_frame, text="Right List Area", bg="#e8e8e8", fg="#666666")
right_label.pack(pady=20)

menubar = tk.Menu(root)
root.config(menu=menubar)

file_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="File", menu=file_menu)
import_animals_menu = tk.Menu(file_menu, tearoff=0)
file_menu.add_cascade(label="Import Animals", menu=import_animals_menu, state="normal")
import_animals_menu.add_command(label="Import Single Animal", command=import_single_animal)
import_animals_menu.add_command(label="Import Multiple Animals", command=import_multi_animals)
file_menu.add_command(label="Export", command=export_now_result)
file_menu.add_command(label="Exit", command=root.quit)

# Analysis menu
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
behaviour_analysis_menu.add_command(label="Position Analysis", command=lambda: position_analysis(parsed_data, selected_bodyparts, root))
behaviour_analysis_menu.add_command(label="Displacement Analysis", command=lambda: displacement_analysis(parsed_data, selected_bodyparts, root))
behaviour_analysis_menu.add_command(label="X Displacement Analysis", command=lambda: x_displacement_analysis(parsed_data, selected_bodyparts, root))
behaviour_analysis_menu.add_command(label="Trajectory Point Cloud", command=create_trajectory_pointcloud)

multimodal_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Multimodal Analysis", menu=multimodal_menu)

# Running-Induced Activity Analysis submenu
running_induced_menu = tk.Menu(multimodal_menu, tearoff=0)
multimodal_menu.add_cascade(label="Running-Induced Activity Analysis", menu=running_induced_menu)
running_induced_menu.add_command(
    label="Running", 
    command=lambda: show_running_induced_analysis(root, multi_animal_data, "running")
)
running_induced_menu.add_command(
    label="Running + Drug", 
    command=lambda: show_running_induced_analysis(root, multi_animal_data, "running+drug")
)
running_induced_menu.add_command(
    label="Running + Optogenetics", 
    command=lambda: show_running_induced_analysis(root, multi_animal_data, "running+optogenetics")
)
running_induced_menu.add_command(
    label="Running + Optogenetics + Drug", 
    command=lambda: show_running_induced_analysis(root, multi_animal_data, "running+optogenetics+drug")
)

# Drug-Induced Activity Analysis
multimodal_menu.add_command(label="Drug-Induced Activity Analysis", 
                             command=lambda: show_drug_induced_analysis(root, multi_animal_data))

# Optogenetics-Induced Activity Analysis
optogenetics_induced_menu = tk.Menu(multimodal_menu, tearoff=0)
multimodal_menu.add_cascade(label="Optogenetics-Induced Activity Analysis", menu=optogenetics_induced_menu)
optogenetics_induced_menu.add_command(
    label="Optogenetics", 
    command=lambda: show_optogenetic_induced_analysis(root, multi_animal_data, "optogenetics")
)
optogenetics_induced_menu.add_command(
    label="Optogenetics + Drug", 
    command=lambda: show_optogenetic_induced_analysis(root, multi_animal_data, "optogenetics+drug")
)

setting_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Settings", menu=setting_menu)
setting_menu.add_command(label="Experiment Type", command=select_experiment_mode)
setting_menu.add_command(label="Event Configuration", command=show_event_config_dialog)
global opto_config_menu_item
opto_config_menu_item = setting_menu.add_command(
    label="Optogenetic Power Configuration", 
    command=show_opto_power_config_dialog,
    state="disabled"
)

if __name__ == "__main__":
    selected_files = []
    multi_animal_data = []
    create_animal_list()
    setup_log_display()
    root.mainloop()