import numpy as np
import tkinter as tk
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from tkinter import ttk, colorchooser

class PlotParameterController:
    """Global controller for real-time plot parameter adjustment across all result windows."""

    def __init__(self, figure_pairs):
        """
        Parameters
        ----------
        figure_pairs : list of (Figure, FigureCanvasTkAgg, window_title)
        """
        self._pairs = figure_pairs
        self._win = None
        self._current_fig_idx = 0
        self._current_ax_idx = 0
        self._defaults = {}
        self._ax_store = {}
        self._filtered_axes = []

        self._fig_var = tk.StringVar()
        self._ax_var = tk.StringVar()

        self._notebook = None
        self._common_tab = None
        self._lines_tab = None
        self._heatmap_tab = None
        self._labels_tab = None

        self._build_window()

    @property
    def _current_fig(self):
        if 0 <= self._current_fig_idx < len(self._pairs):
            return self._pairs[self._current_fig_idx][0]
        return None

    @property
    def _current_canvas(self):
        if 0 <= self._current_fig_idx < len(self._pairs):
            return self._pairs[self._current_fig_idx][1]
        return None

    # ── Window building ───────────────────────────────────────────

    def _build_window(self):
        self._win = tk.Toplevel()
        self._win.title("Plot Parameter Control")
        self._win.geometry("680x750")
        self._win.configure(bg="#f8f8f8")

        tk.Label(self._win, text="Select Figure:", bg="#f8f8f8",
                 font=("Microsoft YaHei", 9, "bold")).pack(anchor=tk.W, padx=10, pady=(10, 2))

        fig_names = []
        for fig, canvas, win_title in self._pairs:
            st = fig._suptitle.get_text() if fig._suptitle else "Untitled"
            fig_names.append(f"{win_title} - {st}")

        self._fig_combo = ttk.Combobox(self._win, textvariable=self._fig_var,
                                       values=fig_names, state="readonly", width=80)
        self._fig_combo.pack(padx=10, pady=(0, 5), fill=tk.X)
        if fig_names:
            self._fig_combo.current(0)
        self._fig_combo.bind("<<ComboboxSelected>>", self._on_fig_selected)

        tk.Label(self._win, text="Select Subplot:", bg="#f8f8f8",
                 font=("Microsoft YaHei", 9, "bold")).pack(anchor=tk.W, padx=10, pady=(5, 2))

        self._ax_combo = ttk.Combobox(self._win, textvariable=self._ax_var,
                                      state="readonly", width=80)
        self._ax_combo.pack(padx=10, pady=(0, 5), fill=tk.X)
        self._ax_combo.bind("<<ComboboxSelected>>", self._on_ax_selected)

        self._notebook = ttk.Notebook(self._win)
        self._notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        self._common_tab = ttk.Frame(self._notebook)
        self._lines_tab = ttk.Frame(self._notebook)
        self._heatmap_tab = ttk.Frame(self._notebook)
        self._labels_tab = ttk.Frame(self._notebook)

        self._notebook.add(self._common_tab, text="Common")
        self._notebook.add(self._lines_tab, text="Lines")
        self._notebook.add(self._heatmap_tab, text="Heatmap")
        self._notebook.add(self._labels_tab, text="Labels")

        btn_frame = tk.Frame(self._win, bg="#f8f8f8")
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        tk.Button(btn_frame, text="Reset to Defaults", command=self._reset_defaults,
                  bg="#e0e0e0", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        tk.Button(btn_frame, text="Close", command=self._win.destroy,
                  bg="#e0e0e0", font=("Microsoft YaHei", 9)).pack(side=tk.RIGHT)

        self._update_ax_list()
        self._rebuild_controls()

    # ── Figure / Subplot selection ─────────────────────────────────

    def _on_fig_selected(self, event=None):
        idx = self._fig_combo.current()
        if idx >= 0 and idx != self._current_fig_idx:
            self._current_fig_idx = idx
            self._update_ax_list()
            self._rebuild_controls()

    def _update_ax_list(self):
        fig = self._current_fig
        if fig is None or not fig.axes:
            self._ax_combo['values'] = []
            self._filtered_axes = []
            return
        self._filtered_axes = [ax for ax in fig.axes
                               if not self._is_colorbar_ax(ax)]
        ncols = len(self._filtered_axes) // 2
        if ncols < 1:
            ncols = 1
        ax_names = []
        for idx, ax in enumerate(self._filtered_axes):
            t = self._detect_ax_type(ax)
            pos = idx + 1
            row = (pos - 1) // ncols + 1
            col = (pos - 1) % ncols + 1
            title = ax.get_title() or ax.get_ylabel() or "Untitled"
            ax_names.append(f"Row {row}, Col {col} - {title} ({t})")
        self._ax_combo['values'] = ax_names
        if ax_names:
            self._ax_combo.current(0)
            self._current_ax_idx = 0

    def _on_ax_selected(self, event=None):
        idx = self._ax_combo.current()
        if idx >= 0:
            self._current_ax_idx = idx
            self._rebuild_controls()

    def _get_current_ax(self):
        if 0 <= self._current_ax_idx < len(self._filtered_axes):
            return self._filtered_axes[self._current_ax_idx]
        return None

    @staticmethod
    def _detect_ax_type(ax):
        if ax.get_images():
            return "Heatmap"
        if ax.get_lines():
            return "Trace"
        return "Empty"

    @staticmethod
    def _is_colorbar_ax(ax):
        from matplotlib.colorbar import Colorbar as _MplCb
        cb = getattr(ax, '_colorbar', None)
        return cb is not None and isinstance(cb, _MplCb)

    # ── Control rebuild ────────────────────────────────────────────

    def _rebuild_controls(self):
        ax = self._get_current_ax()
        if ax is None:
            return
        t = self._detect_ax_type(ax)

        for tab in (self._common_tab, self._lines_tab, self._heatmap_tab, self._labels_tab):
            for w in tab.winfo_children():
                w.destroy()

        self._build_common_controls(self._common_tab, ax)
        self._build_labels_controls(self._labels_tab, ax)

        is_trace = t == "Trace"
        is_heatmap = t == "Heatmap"

        if is_trace:
            self._build_trace_controls(self._lines_tab, ax)
        else:
            tk.Label(self._lines_tab, text="Not applicable — current subplot is not a Trace plot.",
                     bg="#f8f8f8", fg="#999999").pack(padx=20, pady=30)

        if is_heatmap:
            self._build_heatmap_controls(self._heatmap_tab, ax)
        else:
            tk.Label(self._heatmap_tab, text="Not applicable — current subplot is not a Heatmap.",
                     bg="#f8f8f8", fg="#999999").pack(padx=20, pady=30)

        self._notebook.select(0)
        self._save_defaults(ax)

    def _save_defaults(self, ax):
        key = id(ax)
        self._defaults[key] = {
            'xlabel': ax.get_xlabel(),
            'ylabel': ax.get_ylabel(),
            'xlim': ax.get_xlim(),
            'ylim': ax.get_ylim(),
            'grid': bool(ax.get_xgridlines() and ax.get_xgridlines()[0].get_visible()) if ax.get_xgridlines() else False,
            'title': ax.get_title(),
            'trace_defaults': {'linespace': 0.0, 'downsample': 1,
                               'smooth_method': 'none', 'smooth_param': 5.0},
        }

    def _redraw(self):
        fig = self._current_fig
        canvas = self._current_canvas
        if fig and canvas:
            try:
                fig.tight_layout(rect=[0, 0, 1, 0.96])
            except Exception:
                pass
            canvas.draw_idle()

    # ── Common controls ────────────────────────────────────────────

    def _build_common_controls(self, parent, ax):
        inner = tk.Frame(parent, bg="#f8f8f8")
        inner.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        grid_var = tk.BooleanVar(
            value=bool(ax.get_xgridlines() and ax.get_xgridlines()[0].get_visible()) if ax.get_xgridlines() else False
        )
        def _toggle_grid():
            ax.grid(grid_var.get())
            self._redraw()
        tk.Checkbutton(inner, text="Show Grid", variable=grid_var,
                       command=_toggle_grid, bg="#f8f8f8").pack(anchor=tk.W, padx=5, pady=(5, 8))

        tk.Label(inner, text="X Label:", bg="#f8f8f8", anchor=tk.W).pack(fill=tk.X, padx=5, pady=(5, 1))
        xlv = tk.StringVar(value=ax.get_xlabel())
        tk.Entry(inner, textvariable=xlv).pack(fill=tk.X, padx=5)
        def _sxl(*a):
            ax.set_xlabel(xlv.get())
            self._redraw()
        xlv.trace_add("write", _sxl)

        tk.Label(inner, text="Y Label:", bg="#f8f8f8", anchor=tk.W).pack(fill=tk.X, padx=5, pady=(8, 1))
        ylv = tk.StringVar(value=ax.get_ylabel())
        tk.Entry(inner, textvariable=ylv).pack(fill=tk.X, padx=5)
        def _syl(*a):
            ax.set_ylabel(ylv.get())
            self._redraw()
        ylv.trace_add("write", _syl)

        xlim_f = tk.Frame(inner, bg="#f8f8f8")
        xlim_f.pack(fill=tk.X, padx=5, pady=(10, 2))
        tk.Label(xlim_f, text="X Limit:", bg="#f8f8f8").pack(side=tk.LEFT)
        xmn, xmx = ax.get_xlim()
        xmnv = tk.DoubleVar(value=xmn)
        xmxv = tk.DoubleVar(value=xmx)
        tk.Label(xlim_f, text="from", bg="#f8f8f8").pack(side=tk.LEFT, padx=(8, 2))
        xmn_s = tk.Spinbox(xlim_f, from_=-99999, to=99999, textvariable=xmnv, width=8, increment=0.1)
        xmn_s.pack(side=tk.LEFT)
        tk.Label(xlim_f, text="to", bg="#f8f8f8").pack(side=tk.LEFT, padx=(5, 2))
        xmx_s = tk.Spinbox(xlim_f, from_=-99999, to=99999, textvariable=xmxv, width=8, increment=0.1)
        xmx_s.pack(side=tk.LEFT)
        def _sxl2(*a):
            try:
                ax.set_xlim(xmnv.get(), xmxv.get())
                self._redraw()
            except Exception:
                pass
        xmn_s.bind("<KeyRelease>", _sxl2)
        xmx_s.bind("<KeyRelease>", _sxl2)

        ylim_f = tk.Frame(inner, bg="#f8f8f8")
        ylim_f.pack(fill=tk.X, padx=5, pady=(5, 2))
        tk.Label(ylim_f, text="Y Limit:", bg="#f8f8f8").pack(side=tk.LEFT)
        ymn, ymx = ax.get_ylim()
        ymnv = tk.DoubleVar(value=ymn)
        ymxv = tk.DoubleVar(value=ymx)
        tk.Label(ylim_f, text="from", bg="#f8f8f8").pack(side=tk.LEFT, padx=(8, 2))
        ymn_s = tk.Spinbox(ylim_f, from_=-99999, to=99999, textvariable=ymnv, width=8, increment=0.1)
        ymn_s.pack(side=tk.LEFT)
        tk.Label(ylim_f, text="to", bg="#f8f8f8").pack(side=tk.LEFT, padx=(5, 2))
        ymx_s = tk.Spinbox(ylim_f, from_=-99999, to=99999, textvariable=ymxv, width=8, increment=0.1)
        ymx_s.pack(side=tk.LEFT)
        def _syl2(*a):
            try:
                ax.set_ylim(ymnv.get(), ymxv.get())
                self._redraw()
            except Exception:
                pass
        ymn_s.bind("<KeyRelease>", _syl2)
        ymx_s.bind("<KeyRelease>", _syl2)

    # ── Trace / Line controls ──────────────────────────────────────

    def _build_trace_controls(self, parent, ax):
        from matplotlib.collections import PolyCollection
        lines = self._trace_lines(ax)
        if not lines:
            tk.Label(parent, text="No labeled lines found.", bg="#f8f8f8",
                     fg="#666666").pack(padx=10, pady=20)
            return

        fills = [c for c in ax.collections if isinstance(c, PolyCollection)]

        container = tk.Frame(parent, bg="#f8f8f8")
        container.pack(fill=tk.BOTH, expand=True)

        self._build_trace_processing_controls(container, ax)

        hdr = tk.Frame(container, bg="#e8e8e8")
        hdr.pack(fill=tk.X, pady=(0, 2))
        for i, txt in enumerate(["Color", "Group", "Width", "Alpha", "Visible"]):
            tk.Label(hdr, text=txt, bg="#e8e8e8",
                     font=("Microsoft YaHei", 8, "bold"),
                     width=12 if i else 6).pack(side=tk.LEFT, padx=2)

        cv = tk.Canvas(container, bg="#f8f8f8", highlightthickness=0)
        sb = tk.Scrollbar(container, orient=tk.VERTICAL, command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = tk.Frame(cv, bg="#f8f8f8")
        cid = cv.create_window((0, 0), window=inner, anchor="nw")
        cv.bind("<Configure>", lambda e: cv.itemconfig(cid, width=e.width))
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))

        def _on_mw(event):
            cv.yview_scroll(int(-1 * (event.delta / 120)), "units")
        cv.bind_all("<MouseWheel>", _on_mw)
        inner.bind("<Destroy>", lambda e: cv.unbind_all("<MouseWheel>"))

        for idx, line in enumerate(lines):
            fill = fills[idx] if idx < len(fills) else None
            self._add_line_row(inner, line, fill, ax)

    # ── Trace processing (linespace / downsample / smooth) ────────

    @staticmethod
    def _trace_lines(ax):
        """Labeled data traces only (excludes axvline/axhline and legend proxies).

        axvline/axhline use blended transforms, so requiring the plain
        ``ax.transData`` transform keeps them and any other non-trace lines out
        of the processing pipeline and control list.
        """
        return [l for l in ax.get_lines()
                if l.get_label() and not l.get_label().startswith("_")
                and l.get_transform() == ax.transData]

    def _ensure_trace_store(self, ax):
        from matplotlib.collections import PolyCollection
        key = id(ax)
        store = self._ax_store.get(key)
        if store is not None:
            return store
        lines = self._trace_lines(ax)
        fills = [c for c in ax.collections if isinstance(c, PolyCollection)]
        orig_fills = {id(c): self._split_fill(c) for c in fills}
        store = {
            'linespace': 0.0,
            'downsample': 1,
            'smooth_method': 'none',
            'smooth_param': 5.0,
            'orig': {id(l): (np.array(l.get_xdata()), np.array(l.get_ydata()))
                     for l in lines},
            'orig_fills': orig_fills,
        }
        self._ax_store[key] = store
        return store

    @staticmethod
    def _split_fill(fill):
        """Reconstruct per-region (t, f1, f2) curves from fill_between vertices.

        Returns a list of (t, f1, f2) arrays, or None if the vertex layout is
        not the plain fill_between polygon and cannot be reconstructed safely.
        """
        regions = []
        for p in fill.get_paths():
            v = p.vertices
            m = len(v)
            if m < 6 or (m - 3) % 2 != 0:
                return None
            n = (m - 3) // 2
            t = v[1:n + 1, 0]
            t_rev = v[n + 2:2 * n + 2, 0][::-1]
            if not np.allclose(t, t_rev):
                return None
            regions.append((t.copy(), v[1:n + 1, 1].copy(),
                            v[n + 2:2 * n + 2, 1][::-1].copy()))
        return regions if regions else None

    @staticmethod
    def _smooth(y, method, param):
        y = np.asarray(y, dtype=float)
        if method == 'moving_average':
            from scipy.ndimage import uniform_filter1d
            w = max(1, min(int(round(param)), len(y)))
            return uniform_filter1d(y, size=w, mode='nearest')
        if method == 'savgol':
            from scipy.signal import savgol_filter
            w = max(3, int(round(param)))
            if w % 2 == 0:
                w += 1
            if w > len(y):
                w = len(y) if len(y) % 2 == 1 else len(y) - 1
            if w < 3:
                return y
            return savgol_filter(y, w, polyorder=2)
        if method == 'gaussian':
            from scipy.ndimage import gaussian_filter1d
            return gaussian_filter1d(y, sigma=param, mode='nearest')
        return y

    def _apply_trace_processing(self, ax):
        from matplotlib.collections import PolyCollection
        store = self._ax_store.get(id(ax))
        if store is None:
            return
        try:
            spacing = float(store['linespace'])
            ds = max(1, int(store['downsample']))
            method = store['smooth_method']
            param = float(store['smooth_param'])
        except (TypeError, ValueError):
            return

        try:
            lines = self._trace_lines(ax)
            for idx, line in enumerate(lines):
                orig = store['orig'].get(id(line))
                if orig is None:
                    continue
                x = np.asarray(orig[0])
                y = np.asarray(orig[1])
                if ds > 1 and len(x) > ds:
                    x = x[::ds]
                    y = y[::ds]
                y = self._smooth(y, method, param)
                if spacing:
                    y = y + idx * spacing
                line.set_data(x, y)

            fills = [c for c in ax.collections if isinstance(c, PolyCollection)]
            for idx, fill in enumerate(fills):
                regions = store['orig_fills'].get(id(fill))
                if regions is None:
                    continue
                offset = idx * spacing if spacing else 0.0
                verts = []
                for t, f1, f2 in regions:
                    if ds > 1 and len(t) > ds:
                        t = t[::ds]
                        f1 = f1[::ds]
                        f2 = f2[::ds]
                    f1 = self._smooth(f1, method, param)
                    f2 = self._smooth(f2, method, param)
                    if offset:
                        f1 = f1 + offset
                        f2 = f2 + offset
                    n = len(t)
                    pts = np.empty((2 * n + 2, 2))
                    pts[0] = (t[0], f2[0])
                    pts[1:n + 1, 0] = t
                    pts[1:n + 1, 1] = f1
                    pts[n + 1] = (t[-1], f2[-1])
                    pts[n + 2:, 0] = t[::-1]
                    pts[n + 2:, 1] = f2[::-1]
                    verts.append(pts)
                fill.set_verts(verts)
        except Exception:
            return
        self._redraw()

    def _build_trace_processing_controls(self, container, ax):
        store = self._ensure_trace_store(ax)

        title = tk.Frame(container, bg="#e8e8e8")
        title.pack(fill=tk.X, pady=(0, 4))
        tk.Label(title, text="Trace Processing (applies to all lines)",
                 bg="#e8e8e8", font=("Microsoft YaHei", 8, "bold")).pack(side=tk.LEFT, padx=4)

        cfg = tk.Frame(container, bg="#f8f8f8")
        cfg.pack(fill=tk.X, padx=6, pady=(0, 6))

        row1 = tk.Frame(cfg, bg="#f8f8f8")
        row1.pack(fill=tk.X, pady=1)

        tk.Label(row1, text="Linespace:", bg="#f8f8f8").pack(side=tk.LEFT)
        ls_v = tk.DoubleVar(value=float(store['linespace']))
        ls_s = tk.Spinbox(row1, from_=0, to=100, increment=0.05, textvariable=ls_v, width=6)
        ls_s.pack(side=tk.LEFT, padx=(4, 14))

        tk.Label(row1, text="Downsample:", bg="#f8f8f8").pack(side=tk.LEFT)
        ds_v = tk.IntVar(value=int(store['downsample']))
        ds_s = tk.Spinbox(row1, from_=1, to=100000, increment=1, textvariable=ds_v, width=6)
        ds_s.pack(side=tk.LEFT, padx=(4, 0))

        row2 = tk.Frame(cfg, bg="#f8f8f8")
        row2.pack(fill=tk.X, pady=1)

        tk.Label(row2, text="Smooth:", bg="#f8f8f8").pack(side=tk.LEFT)
        sm_v = tk.StringVar(value=str(store['smooth_method']))
        sm_c = ttk.Combobox(row2, textvariable=sm_v,
                            values=["none", "moving_average", "savgol", "gaussian"],
                            state="readonly", width=16)
        sm_c.pack(side=tk.LEFT, padx=(4, 14))

        tk.Label(row2, text="Param:", bg="#f8f8f8").pack(side=tk.LEFT)
        sp_v = tk.DoubleVar(value=float(store['smooth_param']))
        sp_s = tk.Spinbox(row2, from_=0.1, to=1000, increment=0.5, textvariable=sp_v, width=6)
        sp_s.pack(side=tk.LEFT, padx=(4, 0))

        def _set_smooth_state(*_):
            if sm_v.get() == 'none':
                sp_s.configure(state='disabled')
            else:
                sp_s.configure(state='normal')
        _set_smooth_state()

        def _commit(*_):
            try:
                store['linespace'] = float(ls_v.get())
                store['downsample'] = int(ds_v.get())
                store['smooth_method'] = sm_v.get()
                store['smooth_param'] = float(sp_v.get())
            except (ValueError, tk.TclError):
                return
            self._apply_trace_processing(ax)

        ls_s.bind("<KeyRelease>", _commit)
        ds_s.bind("<KeyRelease>", _commit)
        sm_c.bind("<<ComboboxSelected>>", lambda e: (_set_smooth_state(), _commit()))
        sp_s.bind("<KeyRelease>", _commit)

    def _add_line_row(self, parent, line, fill, ax):
        row = tk.Frame(parent, bg="#f8f8f8")
        row.pack(fill=tk.X, pady=1)

        color = mcolors.to_hex(line.get_color())
        swatch = tk.Frame(row, width=20, height=20, bg=color,
                          relief=tk.RAISED, bd=2, cursor="hand2")
        swatch.pack(side=tk.LEFT, padx=(15, 5))
        swatch.pack_propagate(False)

        label = line.get_label()
        tk.Label(row, text=label, bg="#f8f8f8", width=12,
                 anchor=tk.W, font=("Microsoft YaHei", 8)).pack(side=tk.LEFT, padx=(40, 5))

        lw_v = tk.DoubleVar(value=line.get_linewidth())
        lw_s = tk.Spinbox(row, from_=0.1, to=10, textvariable=lw_v, width=5, increment=0.5)
        lw_s.pack(side=tk.LEFT, padx=(0, 5))

        line_alpha = line.get_alpha() if line.get_alpha() is not None else 1.0
        fill_alpha = fill.get_alpha() if fill is not None else 0.3
        alpha_ratio = (fill_alpha / line_alpha) if line_alpha > 0 else 0.3

        al_v = tk.DoubleVar(value=line_alpha)
        al_s = tk.Scale(row, from_=0, to=1, resolution=0.05, orient=tk.HORIZONTAL,
                        variable=al_v, showvalue=False, length=100, bg="#f8f8f8")
        al_s.pack(side=tk.LEFT, padx=(5, 5))

        vis_v = tk.BooleanVar(value=line.get_visible())
        vis_c = tk.Checkbutton(row, variable=vis_v, bg="#f8f8f8")
        vis_c.pack(side=tk.LEFT, padx=(20, 5))

        def _sync_legend():
            leg = ax.get_legend()
            if leg is None:
                return
            data_lines = self._trace_lines(ax)
            for proxy, dl in zip(leg.get_lines(), data_lines):
                proxy.set_color(dl.get_color())
                proxy.set_alpha(dl.get_alpha() if dl.get_alpha() is not None else 1.0)
                proxy.set_linewidth(dl.get_linewidth())

        def _pick_color():
            c = colorchooser.askcolor(color=color, title=f"Color - {label}")
            if c and c[1]:
                swatch.config(bg=c[1])
                line.set_color(c[1])
                if fill is not None:
                    fill.set_facecolor(c[1])
                    fill.set_edgecolor(c[1])
                _sync_legend()
                self._redraw()
        swatch.bind("<Double-Button-1>", lambda e: _pick_color())

        def _upd(*a):
            try:
                line.set_linewidth(lw_v.get())
                _sync_legend()
                self._redraw()
            except Exception:
                pass
        lw_s.bind("<KeyRelease>", _upd)

        def _upd_a(*a):
            new_alpha = al_v.get()
            line.set_alpha(new_alpha)
            if fill is not None:
                fill.set_alpha(new_alpha * alpha_ratio)
            _sync_legend()
            self._redraw()
        al_v.trace_add("write", _upd_a)

        def _upd_v():
            line.set_visible(vis_v.get())
            if fill is not None:
                fill.set_visible(vis_v.get())
            leg = ax.get_legend()
            # If the legend exists, find the corresponding text, line and set its visibility
            if leg is not None:
                for text, proxy in zip(leg.get_texts(), leg.get_lines()):
                    if text.get_text() == label:
                        text.set_visible(vis_v.get())
                        proxy.set_visible(vis_v.get())
                        break
            self._redraw()
        vis_c.config(command=_upd_v)

    # ── Heatmap controls ───────────────────────────────────────────

    def _build_heatmap_controls(self, parent, ax):
        images = ax.get_images()
        if not images:
            tk.Label(parent, text="No heatmap image found.", bg="#f8f8f8",
                     fg="#666666").pack(padx=10, pady=20)
            return

        im = images[0]
        inner = tk.Frame(parent, bg="#f8f8f8")
        inner.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Colormap
        cf = tk.Frame(inner, bg="#f8f8f8")
        cf.pack(fill=tk.X, pady=(10, 5))
        tk.Label(cf, text="Colormap:", bg="#f8f8f8").pack(side=tk.LEFT)

        cm_v = tk.StringVar(value=im.get_cmap().name)
        all_cmaps = sorted([m for m in plt.colormaps() if not m.endswith("_r")])
        cm_c = ttk.Combobox(cf, textvariable=cm_v, values=all_cmaps,
                            state="readonly", width=22)
        cm_c.pack(side=tk.LEFT, padx=(5, 10))

        prev = tk.Canvas(cf, width=120, height=22, bg="white",
                         relief=tk.SUNKEN, bd=1)
        prev.pack(side=tk.LEFT)

        def _draw_preview(*_):
            prev.delete("all")
            try:
                cmap = plt.colormaps[cm_v.get()]
                w = prev.winfo_width() or 120
                h = prev.winfo_height() or 22
                for i in range(w):
                    rgba = cmap(i / max(w - 1, 1))
                    hx = '#{:02x}{:02x}{:02x}'.format(
                        int(rgba[0] * 255), int(rgba[1] * 255), int(rgba[2] * 255))
                    prev.create_line(i, 0, i, h, fill=hx)
            except Exception:
                pass
        prev.after(50, _draw_preview)

        def _set_cmap(*_):
            im.set_cmap(cm_v.get())
            _draw_preview()
            self._redraw()
        cm_c.bind("<<ComboboxSelected>>", _set_cmap)

        # Interpolation
        ipf = tk.Frame(inner, bg="#f8f8f8")
        ipf.pack(fill=tk.X, pady=(5, 5))
        tk.Label(ipf, text="Interpolation:", bg="#f8f8f8").pack(side=tk.LEFT)
        ip_v = tk.StringVar(value=im.get_interpolation() or "nearest")
        ip_c = ttk.Combobox(ipf, textvariable=ip_v,
                            values=["nearest", "bilinear", "bicubic", "spline16",
                                    "spline36", "hanning", "hamming", "hermite",
                                    "kaiser", "quadric", "catrom", "gaussian",
                                    "bessel", "mitchell", "sinc", "lanczos"],
                            state="readonly", width=15)
        ip_c.pack(side=tk.LEFT, padx=(5, 0))
        def _set_ip(*_):
            im.set_interpolation(ip_v.get())
            self._redraw()
        ip_c.bind("<<ComboboxSelected>>", _set_ip)

        # Clim
        clf = tk.Frame(inner, bg="#f8f8f8")
        clf.pack(fill=tk.X, pady=(10, 5))
        vmin, vmax = im.get_clim()
        vmn_v = tk.DoubleVar(value=vmin)
        vmx_v = tk.DoubleVar(value=vmax)
        tk.Label(clf, text="Colorbar Min:", bg="#f8f8f8").pack(side=tk.LEFT)
        vmn_s = tk.Spinbox(clf, from_=-99999, to=99999, textvariable=vmn_v,
                           width=10, increment=0.1)
        vmn_s.pack(side=tk.LEFT, padx=(5, 15))
        tk.Label(clf, text="Max:", bg="#f8f8f8").pack(side=tk.LEFT)
        vmx_s = tk.Spinbox(clf, from_=-99999, to=99999, textvariable=vmx_v,
                           width=10, increment=0.1)
        vmx_s.pack(side=tk.LEFT, padx=(5, 0))
        def _set_cl(*_):
            try:
                new_vmin = vmn_v.get()
                new_vmax = vmx_v.get()
                im.set_clim(new_vmin, new_vmax)
                if hasattr(im, 'colorbar') and im.colorbar is not None:
                    try:
                        im.colorbar.draw_all()
                    except AttributeError:
                        pass
                self._redraw()
            except (ValueError, tk.TclError):
                pass
        vmn_v.trace_add("write", _set_cl)
        vmx_v.trace_add("write", _set_cl)

        # Colorbar label
        lbf = tk.Frame(inner, bg="#f8f8f8")
        lbf.pack(fill=tk.X, pady=(5, 5))
        tk.Label(lbf, text="Colorbar Label:", bg="#f8f8f8").pack(side=tk.LEFT)

        cbar_label = ""
        if hasattr(im, 'colorbar') and im.colorbar is not None:
            cb = im.colorbar
            if hasattr(cb, 'ax'):
                cbar_label = cb.ax.get_ylabel() or cb.ax.get_xlabel() or ""
        if not cbar_label:
            for cax in ax.figure.axes:
                if cax is not ax:
                    lbl = cax.get_ylabel() or cax.get_xlabel() or ""
                    if lbl:
                        cbar_label = lbl
                        break

        cbl_v = tk.StringVar(value=cbar_label)
        cbl_e = tk.Entry(lbf, textvariable=cbl_v, width=30)
        cbl_e.pack(side=tk.LEFT, padx=(5, 0))
        def _set_cbl(*_):
            if hasattr(im, 'colorbar') and im.colorbar is not None:
                cb = im.colorbar
                if hasattr(cb, 'ax'):
                    cb.ax.set_ylabel(cbl_v.get())
            else:
                for cax in ax.figure.axes:
                    if cax is not ax:
                        lbl = cax.get_ylabel() or cax.get_xlabel() or ""
                        if lbl:
                            cax.set_ylabel(cbl_v.get())
                            break
            self._redraw()
        cbl_v.trace_add("write", _set_cbl)

    # ── Labels / Font controls ─────────────────────────────────────

    def _build_labels_controls(self, parent, ax):
        inner = tk.Frame(parent, bg="#f8f8f8")
        inner.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        tk.Label(inner, text="Title:", bg="#f8f8f8", anchor=tk.W).pack(fill=tk.X, padx=5, pady=(8, 1))
        tv = tk.StringVar(value=ax.get_title())
        te = tk.Entry(inner, textvariable=tv)
        te.pack(fill=tk.X, padx=5)
        def _st(*a):
            ax.set_title(tv.get())
            self._redraw()
        tv.trace_add("write", _st)

        ff = tk.Frame(inner, bg="#f8f8f8")
        ff.pack(fill=tk.X, padx=5, pady=(12, 5))

        r = 0
        tk.Label(ff, text="Title Font Size:", bg="#f8f8f8", anchor=tk.W).grid(row=r, column=0, sticky=tk.W, pady=3)
        tfs_v = tk.IntVar(value=ax.title.get_fontsize() or 12)
        tfs_s = tk.Spinbox(ff, from_=6, to=40, textvariable=tfs_v, width=5)
        tfs_s.grid(row=r, column=1, padx=(8, 20), pady=3)

        r += 1
        tk.Label(ff, text="Label Font Size:", bg="#f8f8f8", anchor=tk.W).grid(row=r, column=0, sticky=tk.W, pady=3)
        lfs_v = tk.IntVar(value=ax.xaxis.label.get_fontsize() or 10)
        lfs_s = tk.Spinbox(ff, from_=6, to=40, textvariable=lfs_v, width=5)
        lfs_s.grid(row=r, column=1, padx=(8, 20), pady=3)

        r += 1
        tk.Label(ff, text="Tick Font Size:", bg="#f8f8f8", anchor=tk.W).grid(row=r, column=0, sticky=tk.W, pady=3)
        tks = ax.xaxis.get_ticklabels()
        tfs2_v = tk.IntVar(value=tks[0].get_fontsize() if tks else 9)
        tfs2_s = tk.Spinbox(ff, from_=6, to=40, textvariable=tfs2_v, width=5)
        tfs2_s.grid(row=r, column=1, padx=(8, 20), pady=3)

        legend = ax.get_legend()
        if legend:
            r += 1
            tk.Label(ff, text="Legend Font Size:", bg="#f8f8f8", anchor=tk.W).grid(row=r, column=0, sticky=tk.W, pady=3)
            lg_fs_v = tk.IntVar(value=legend.get_texts()[0].get_fontsize() if legend.get_texts() else 7)
            lg_fs_s = tk.Spinbox(ff, from_=4, to=30, textvariable=lg_fs_v, width=5)
            lg_fs_s.grid(row=r, column=1, padx=(8, 20), pady=3)

            tk.Label(ff, text="Location:", bg="#f8f8f8", anchor=tk.W).grid(row=r, column=2, sticky=tk.W, padx=(10, 5), pady=3)
            loc_v = tk.StringVar(value=legend._loc if hasattr(legend, '_loc') else "best")
            loc_c = ttk.Combobox(ff, textvariable=loc_v,
                                 values=["best", "upper right", "upper left", "lower left",
                                         "lower right", "right", "center left", "center right",
                                         "lower center", "upper center", "center"],
                                 state="readonly", width=14)
            loc_c.grid(row=r, column=3, pady=3)

            def _set_leg(*_):
                leg = ax.get_legend()
                if leg:
                    for t in leg.get_texts():
                        t.set_fontsize(lg_fs_v.get())
                    leg.set_loc(loc_v.get())
                    self._redraw()
            lg_fs_s.bind("<KeyRelease>", _set_leg)
            loc_c.bind("<<ComboboxSelected>>", _set_leg)

        def _set_fonts(*_):
            ax.title.set_fontsize(tfs_v.get())
            ax.xaxis.label.set_fontsize(lfs_v.get())
            ax.yaxis.label.set_fontsize(lfs_v.get())
            for t in ax.xaxis.get_ticklabels():
                t.set_fontsize(tfs2_v.get())
            for t in ax.yaxis.get_ticklabels():
                t.set_fontsize(tfs2_v.get())
            self._redraw()
        tfs_s.bind("<KeyRelease>", _set_fonts)
        lfs_s.bind("<KeyRelease>", _set_fonts)
        tfs2_s.bind("<KeyRelease>", _set_fonts)

    # ── Reset ──────────────────────────────────────────────────────

    def _reset_defaults(self):
        ax = self._get_current_ax()
        if ax is None:
            return
        d = self._defaults.get(id(ax), {})
        if 'xlabel' in d:
            ax.set_xlabel(d['xlabel'])
        if 'ylabel' in d:
            ax.set_ylabel(d['ylabel'])
        if 'xlim' in d:
            ax.set_xlim(d['xlim'])
        if 'ylim' in d:
            ax.set_ylim(d['ylim'])
        if 'grid' in d:
            ax.grid(d['grid'])
        if 'title' in d:
            ax.set_title(d['title'])
        td = d.get('trace_defaults')
        if td is not None:
            store = self._ax_store.get(id(ax))
            if store is not None:
                store.update(dict(td))
                self._apply_trace_processing(ax)
        self._rebuild_controls()
        self._redraw()
