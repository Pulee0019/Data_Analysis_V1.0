import platform
import sys

import tkinter as tk

try:
    from analysis_core.Behavior_analysis import displacement_analysis, position_analysis, x_displacement_analysis
    from analysis_multimodal.Drug_induced_activity_analysis import show_drug_induced_analysis
    from analysis_multimodal.Optogenetic_induced_activity_analysis import show_optogenetic_induced_analysis
    from analysis_multimodal.Running_induced_activity_analysis import show_running_induced_analysis
    from analysis_multimodal.Bout_analysis import show_bout_analysis
    from core.analysis_results import AnalysisResultsManager
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
    from ui.bodypart_controller import create_trajectory_pointcloud
    from ui.settings_dialogs import (
        export_now_result,
        on_closing,
        select_experiment_mode,
        setup_log_display,
        show_drug_name_config_dialog,
        show_event_config_dialog,
        show_opto_power_config_dialog,
        update_ui_for_mode,
    )
    from ui.view_controller import create_animal_list
    from workflows.analysis_workflows import (
        calculate_and_plot_dff_wrapper,
        calculate_and_plot_zscore_wrapper,
        fiber_preprocessing,
        running_data_analysis,
    )
    from workflows.data_workflows import import_multi_animals, import_single_animal

    import ui.bodypart_controller as bodypart_controller
    import ui.settings_dialogs as settings_dialogs
    import ui.view_controller as view_controller
    import ui.windows.visualization_windows as visualization_windows
    import workflows.analysis_workflows as analysis_workflows
    import workflows.data_workflows as data_workflows
except ModuleNotFoundError as exc:
    missing_name = exc.name or str(exc)
    print(
        f"Dependency missing: {missing_name}\n"
        "Please install required packages with:\n"
        "  pip install -r requirements.txt",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc


def bootstrap_globals(root):
    state = {
        "root": root,
        "analysis_manager": AnalysisResultsManager(),
        "EXPERIMENT_MODE_AST2": "ast2",
        "EXPERIMENT_MODE_FIBER_AST2": "fiber+ast2",
        "EXPERIMENT_MODE_FIBER_AST2_DLC": "fiber+ast2+dlc",
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
        "show_data_points_var": None,
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
        "create_fiber_visualization": view_controller.create_fiber_visualization,
        "update_file_listbox": view_controller.update_file_listbox,
        "display_analysis_results": view_controller.display_analysis_results,
        "display_running_analysis_for_animal": view_controller.display_running_analysis_for_animal,
        "display_fiber_results_for_animal": view_controller.display_fiber_results_for_animal,
    }
    return state


def build_layout(root, state):
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

    state.update(
        {
            "main_container": main_container,
            "left_frame": left_frame,
            "middle_frame": middle_frame,
            "central_display_frame": central_display_frame,
            "bottom_display_frame": bottom_display_frame,
            "right_frame": right_frame,
            "left_label": left_label,
            "central_label": central_label,
            "bottom_label": bottom_label,
            "right_label": right_label,
        }
    )


def bind_modules(state):
    visualization_windows.bind_window_dependencies(state)
    data_workflows.bind_workflow_dependencies(state)
    analysis_workflows.bind_analysis_dependencies(state)
    bodypart_controller.bind_bodypart_dependencies(state)
    view_controller.bind_view_dependencies(state)
    settings_dialogs.bind_settings_dependencies(state)


def build_menu(root, state):
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
        command=lambda: position_analysis(state.get("parsed_data"), state["selected_bodyparts"], root),
    )
    behaviour_analysis_menu.add_command(
        label="Displacement Analysis",
        command=lambda: displacement_analysis(state.get("parsed_data"), state["selected_bodyparts"], root),
    )
    behaviour_analysis_menu.add_command(
        label="X Displacement Analysis",
        command=lambda: x_displacement_analysis(state.get("parsed_data"), state["selected_bodyparts"], root),
    )
    behaviour_analysis_menu.add_command(label="Trajectory Point Cloud", command=create_trajectory_pointcloud)

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

    setting_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Settings", menu=setting_menu)
    setting_menu.add_command(label="Experiment Type", command=select_experiment_mode)
    setting_menu.add_command(label="Event Configuration", command=show_event_config_dialog)
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
        }
    )


def create_root():
    root = tk.Tk()
    root.title("Fiber Photometry with Running Analysis")
    if platform.system() == "Windows":
        root.state("zoomed")
    else:
        root.attributes("-zoomed", True)
    return root


def bootstrap():
    root = create_root()
    state = bootstrap_globals(root)
    build_layout(root, state)
    build_menu(root, state)
    bind_modules(state)
    root.protocol("WM_DELETE_WINDOW", on_closing)
    update_ui_for_mode()
    create_animal_list()
    setup_log_display()
    return root


def main():
    app = bootstrap()
    app.mainloop()


if __name__ == "__main__":
    main()
