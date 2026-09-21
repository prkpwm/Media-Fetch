"""Desktop presentation. Downloading and browser messaging stay in app/core."""
import tkinter as tk
from tkinter import ttk

BG = '#10151d'
CARD = '#19212c'
INSET = '#121a24'
LINE = '#2b3746'
TEXT = '#eef4fa'
MUTED = '#9aaabd'
ACCENT = '#80e4bc'


def label(parent, text='', style='TLabel', **kwargs):
    return ttk.Label(parent, text=text, style=style, **kwargs)


def setup_theme(app):
    app.configure(background=BG)
    app.option_add('*insertBackground', TEXT)
    style = ttk.Style(app)
    style.theme_use('clam')
    style.configure('.', background=BG, foreground=TEXT, font=('Segoe UI', 10))
    style.configure('TFrame', background=BG)
    style.configure('Card.TFrame', background=CARD)
    style.configure('TLabel', background=BG, foreground=TEXT)
    for name, bg, color, font in [
        ('Muted', BG, MUTED, ('Segoe UI', 10)),
        ('Brand', BG, TEXT, ('Segoe UI Semibold', 17)),
        ('Title', BG, TEXT, ('Segoe UI Semibold', 27)),
        ('Kicker', BG, ACCENT, ('Segoe UI Semibold', 9)),
        ('Card', CARD, TEXT, ('Segoe UI', 10)),
        ('CardMuted', CARD, MUTED, ('Segoe UI', 9)),
        ('CardHeading', CARD, TEXT, ('Segoe UI Semibold', 12)),
        ('Quality', CARD, TEXT, ('Segoe UI Semibold', 30)),
        ('Accent', CARD, ACCENT, ('Segoe UI Semibold', 10)),
        ('Badge', INSET, ACCENT, ('Segoe UI Semibold', 9)),
        ('Percent', CARD, TEXT, ('Segoe UI Semibold', 19)),
    ]:
        style.configure(f'{name}.TLabel', background=bg, foreground=color, font=font)
    style.configure('Badge.TLabel', padding=(12, 7))
    style.configure('TButton', background='#273443', foreground=TEXT, borderwidth=0,
                    padding=(15, 11), font=('Segoe UI Semibold', 10), focuscolor=ACCENT)
    style.map('TButton', background=[('disabled', '#202a35'), ('pressed', '#3b4d60'), ('active', '#33465a')],
              foreground=[('disabled', '#8392a5')])
    style.configure('Primary.TButton', background=ACCENT, foreground='#102820', padding=(16, 13))
    style.map('Primary.TButton', background=[('disabled', '#293e3b'), ('pressed', '#57c49a'), ('active', '#a1f3d3')],
              foreground=[('disabled', '#91b2a8'), ('!disabled', '#102820')])
    style.configure('Quiet.TButton', background=BG, foreground=MUTED)
    style.map('Quiet.TButton', background=[('active', '#243142')], foreground=[('active', TEXT)])
    style.configure('TEntry', fieldbackground=INSET, foreground=TEXT, insertcolor=TEXT,
                    bordercolor=LINE, lightcolor=LINE, darkcolor=LINE, padding=(12, 11))
    style.map('TEntry', bordercolor=[('focus', ACCENT)], lightcolor=[('focus', ACCENT)],
              darkcolor=[('focus', ACCENT)], foreground=[('disabled', MUTED)])
    style.configure('Treeview', background=CARD, fieldbackground=CARD, foreground=TEXT,
                    borderwidth=0, bordercolor=CARD, lightcolor=CARD, darkcolor=CARD, rowheight=44, font=('Segoe UI', 10), relief='flat')
    style.layout('Treeview', [('Treeview.treearea', {'sticky': 'nswe'})])
    style.configure('Treeview.Heading', background=INSET, foreground=MUTED, borderwidth=0,
                    padding=(10, 12), font=('Segoe UI Semibold', 9), relief='flat')
    style.map('Treeview', background=[('selected', '#24463e')], foreground=[('selected', '#bdffe2')])
    style.map('Treeview.Heading', background=[('active', INSET)])
    style.configure('Horizontal.TProgressbar', background=ACCENT, troughcolor=INSET,
                    borderwidth=0, bordercolor=INSET, lightcolor=ACCENT, darkcolor=ACCENT, thickness=6)
    style.configure('Vertical.TScrollbar', background=LINE, troughcolor=CARD, borderwidth=0,
                    bordercolor=CARD, lightcolor=LINE, darkcolor=LINE, arrowcolor=MUTED, arrowsize=12)


def card(parent, padding=20):
    border = tk.Frame(parent, bg=LINE, bd=0, highlightthickness=0)
    body = ttk.Frame(border, style='Card.TFrame', padding=padding)
    body.pack(fill='both', expand=True, padx=1, pady=1)
    return border, body


def build_ui(app):
    setup_theme(app)
    app.geometry('1120x800')
    app.minsize(920, 600)
    outer = ttk.Frame(app, padding=(24, 16))
    outer.pack(fill='both', expand=True)
    outer.columnconfigure(0, weight=1)
    outer.rowconfigure(2, weight=1)

    header = ttk.Frame(outer)
    header.grid(row=0, column=0, sticky='ew', pady=(0, 14))
    logo = tk.Canvas(header, width=42, height=42, bg=BG, highlightthickness=0)
    logo.pack(side='left', padx=(0, 12))
    logo.create_polygon(11, 1, 31, 1, 41, 11, 41, 31, 31, 41, 11, 41, 1, 31, 1, 11, fill=ACCENT, outline='')
    logo.create_line(21, 10, 21, 28, fill='#102820', width=3)
    logo.create_line(14, 22, 21, 29, 28, 22, fill='#102820', width=3)
    logo.create_line(12, 33, 30, 33, fill='#102820', width=2)
    label(header, 'media fetch', 'Brand.TLabel').pack(side='left')
    label(header, 'DESKTOP', 'Kicker.TLabel').pack(side='left', padx=14)
    ttk.Button(header, text='Settings', style='Quiet.TButton', command=lambda: settings(app)).pack(side='right')
    label(header, '●  Browser connected' if app.native_reply else '●  Desktop mode', 'Badge.TLabel').pack(side='right', padx=12)

    hero = ttk.Frame(outer)
    hero.grid(row=1, column=0, sticky='ew', pady=(0, 12))
    label(hero, 'Make it yours.', 'Title.TLabel').pack(anchor='w')
    label(hero, 'Choose a stream. Pick your quality. Save a complete video.', 'Muted.TLabel').pack(anchor='w', pady=(3, 0))

    # Main vertical paned window allowing vertical resizing of Zone 01, Middle, and Zone 04
    v_paned = tk.PanedWindow(
        outer,
        orient='vertical',
        bg=BG,
        bd=0,
        sashwidth=8,
        sashpad=2,
        sashrelief='flat',
        sashcursor='size_ns',
        opaqueresize=True
    )
    v_paned.grid(row=2, column=0, sticky='nsew')

    # Zone 01: Add Your Media
    source_border, source = card(v_paned, 14)
    label(source, '01   ADD YOUR MEDIA', 'Accent.TLabel').pack(anchor='w', pady=(0, 7))
    source_row = ttk.Frame(source, style='Card.TFrame')
    source_row.pack(fill='x')
    app.url_entry = ttk.Entry(source_row, textvariable=app.url)
    app.url_entry.pack(side='left', fill='x', expand=True)
    app.url_entry.bind('<Return>', lambda event: app.inspect())
    app.inspect_button = ttk.Button(source_row, text='Find qualities', style='Primary.TButton', command=app.inspect)
    app.inspect_button.pack(side='left', padx=(10, 8))
    app.import_button = ttk.Button(source_row, text='Import HAR', command=app.load_har)
    app.import_button.pack(side='left')
    label(source, 'Paste an HLS playlist URL, import a browser capture, or send a stream from the extension.', 'CardMuted.TLabel').pack(anchor='w', pady=(7, 0))
    v_paned.add(source_border, minsize=80, height=95, stretch='never')

    # Horizontal paned window allowing horizontal resizing between Zone 02 and Zone 03
    h_paned = tk.PanedWindow(
        v_paned,
        orient='horizontal',
        bg=BG,
        bd=0,
        sashwidth=8,
        sashpad=2,
        sashrelief='flat',
        sashcursor='size_we',
        opaqueresize=True
    )

    # Zone 02: Available Qualities
    left_border, left = card(h_paned, 14)
    heading = ttk.Frame(left, style='Card.TFrame')
    heading.pack(fill='x', pady=(0, 10))
    label(heading, '02   AVAILABLE QUALITIES', 'Accent.TLabel').pack(side='left')
    app.count_text = tk.StringVar(value='No streams yet')
    label(heading, style='CardMuted.TLabel', textvariable=app.count_text).pack(side='right')
    table_area = ttk.Frame(left, style='Card.TFrame')
    table_area.pack(fill='both', expand=True)
    columns = ('quality', 'audio', 'encryption', 'source')
    app.table = ttk.Treeview(table_area, columns=columns, show='headings', height=5, selectmode='browse')
    for name, title, width in [('quality', 'QUALITY', 90), ('audio', 'AUDIO', 105), ('encryption', 'FORMAT', 95), ('source', 'SOURCE', 170)]:
        app.table.heading(name, text=title, anchor='w')
        app.table.column(name, width=width, minwidth=65, anchor='w', stretch=name == 'source')
    scrollbar = ttk.Scrollbar(table_area, orient='vertical', command=app.table.yview)
    app.table.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side='right', fill='y')
    app.table.pack(fill='both', expand=True)
    app.table.tag_configure('alternate', background='#1c2733')
    app.table.bind('<<TreeviewSelect>>', lambda event: refresh_selection(app))
    app.empty_state = ttk.Frame(table_area, style='Card.TFrame', padding=16)
    app.empty_state.place(relx=0.5, rely=0.53, anchor='center')
    label(app.empty_state, '↓', 'Quality.TLabel').pack()
    label(app.empty_state, 'A little space for your next video', 'CardHeading.TLabel').pack(pady=(8, 6))
    label(app.empty_state, 'Add a playlist above to see its available qualities.', 'CardMuted.TLabel').pack()
    label(left, 'Select a row to choose your download quality.', 'CardMuted.TLabel').pack(anchor='w', pady=(8, 0))

    # Zone 03: Your Download
    right_border, right = card(h_paned, (18, 14))
    label(right, '03   YOUR DOWNLOAD', 'Accent.TLabel').pack(anchor='w')
    app.selected_quality = tk.StringVar(value='—')
    label(right, style='Quality.TLabel', textvariable=app.selected_quality).pack(anchor='w', pady=(4, 0))
    app.selected_detail = tk.StringVar(value='Select a quality to get started')
    label(right, style='CardMuted.TLabel', textvariable=app.selected_detail, wraplength=255).pack(anchor='w', pady=(2, 8))
    facts = ttk.Frame(right, style='Card.TFrame')
    facts.pack(fill='x', pady=(0, 10))
    label(facts, 'OUTPUT', 'CardMuted.TLabel').pack(side='left')
    label(facts, 'MP4  ·  Original quality', 'Card.TLabel').pack(side='right')
    label(right, 'SAVE LOCATION', 'CardMuted.TLabel').pack(anchor='w', pady=(0, 4))
    location = ttk.Frame(right, style='Card.TFrame')
    location.pack(fill='x', pady=(0, 14))
    app.destination_entry = ttk.Entry(location, textvariable=app.destination, width=22)
    app.destination_entry.pack(side='left', fill='x', expand=True)
    app.browse_button = ttk.Button(location, text='…', width=2, command=app.browse_output)
    app.browse_button.pack(side='left', padx=(5, 0))
    action_area = ttk.Frame(right, style='Card.TFrame')
    action_area.pack(fill='x')
    app.download_button = ttk.Button(action_area, text='↓  Download MP4', style='Primary.TButton', command=app.download, state='disabled')
    app.download_button.pack(side='left', fill='x', expand=True)
    app.cancel_button = ttk.Button(action_area, text='Cancel', command=app.cancel, state='disabled')
    app.cancel_button.pack(side='left', padx=(7, 0))

    h_paned.add(left_border, minsize=320, width=650, stretch='always')
    h_paned.add(right_border, minsize=280, width=340, stretch='never')
    v_paned.add(h_paned, minsize=220, height=330, stretch='always')

    # Zone 04: Active Activity and Multi-task Downloads
    activity_border, activity = card(v_paned, (18, 12))
    activity.columnconfigure(0, weight=1)
    activity.rowconfigure(3, weight=1)
    app.phase = tk.StringVar(value='Ready when you are')
    app.percent = tk.StringVar(value='—')
    label(activity, style='CardHeading.TLabel', textvariable=app.phase).grid(row=0, column=0, sticky='w')

    act_top_right = ttk.Frame(activity, style='Card.TFrame')
    act_top_right.grid(row=0, column=1, rowspan=2, sticky='e', padx=(15, 0))
    label(act_top_right, style='Percent.TLabel', textvariable=app.percent).pack(side='right')
    app.clear_button = ttk.Button(act_top_right, text='Clear', style='Quiet.TButton', command=lambda: app.clear_tasks() if hasattr(app, 'clear_tasks') else None, state='disabled')
    app.clear_button.pack(side='right', padx=(0, 12))

    app.status_label = label(activity, style='CardMuted.TLabel', textvariable=app.status, wraplength=850)
    app.status_label.grid(row=1, column=0, sticky='w', pady=(3, 10))
    app.progress = ttk.Progressbar(activity, maximum=100)
    app.progress.grid(row=2, column=0, columnspan=2, sticky='ew')

    tasks_canvas = tk.Canvas(activity, bg=CARD, highlightthickness=0)
    tasks_scrollbar = ttk.Scrollbar(activity, orient='vertical', command=tasks_canvas.yview)
    tasks_canvas.configure(yscrollcommand=tasks_scrollbar.set)
    tasks_canvas.grid(row=3, column=0, sticky='nsew', pady=(8, 0))

    app.tasks_container = ttk.Frame(tasks_canvas, style='Card.TFrame')
    tasks_window = tasks_canvas.create_window((0, 0), window=app.tasks_container, anchor='nw')

    def _sync_tasks_scroll(event=None):
        tasks_canvas.configure(scrollregion=tasks_canvas.bbox('all'))
        req_h = app.tasks_container.winfo_reqheight()
        vis_h = tasks_canvas.winfo_height()
        if req_h > vis_h and vis_h > 20:
            tasks_scrollbar.grid(row=3, column=1, sticky='ns', pady=(8, 0))
        else:
            tasks_scrollbar.grid_remove()

    def _sync_canvas_width(event):
        tasks_canvas.itemconfig(tasks_window, width=event.width)
        _sync_tasks_scroll()

    def _on_mousewheel(event):
        if tasks_canvas.winfo_height() < app.tasks_container.winfo_reqheight():
            tasks_canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

    app.tasks_container.bind('<Configure>', _sync_tasks_scroll)
    tasks_canvas.bind('<Configure>', _sync_canvas_width)
    tasks_canvas.bind('<MouseWheel>', _on_mousewheel)
    app.tasks_container.bind('<MouseWheel>', _on_mousewheel)

    v_paned.add(activity_border, minsize=140, height=190, stretch='always')

    footer = ttk.Frame(outer)
    footer.grid(row=3, column=0, sticky='ew', pady=(12, 0))
    label(footer, 'HLS video  /  Audio + video merging  /  MP4 export', 'Muted.TLabel').pack(side='left')
    label(footer, 'MEDIA FETCH  ·  0.2', 'Kicker.TLabel').pack(side='right')
    app.bind('<Configure>', lambda event: app.status_label.configure(wraplength=max(500, app.winfo_width() - 210)) if event.widget is app else None)


def add_task_widget(app, task_id, title_text, detail_text):
    card_frame = ttk.Frame(app.tasks_container, style='Card.TFrame', padding=(0, 4))
    card_frame.pack(fill='x', expand=True, pady=(4, 4))
    card_frame.columnconfigure(0, weight=1)

    header = ttk.Frame(card_frame, style='Card.TFrame')
    header.pack(fill='x')

    task_title = label(header, f'#{task_id}  {title_text}', 'CardHeading.TLabel')
    task_title.pack(side='left')

    cancel_btn = ttk.Button(header, text='✕ Cancel', style='Quiet.TButton', command=lambda: app.cancel(task_id))
    cancel_btn.pack(side='right')

    pct_var = tk.StringVar(value='0%')
    pct_lbl = label(header, style='Percent.TLabel', textvariable=pct_var)
    pct_lbl.pack(side='right', padx=(0, 10))

    meta_var = tk.StringVar(value=detail_text)
    meta_lbl = label(card_frame, style='CardMuted.TLabel', textvariable=meta_var)
    meta_lbl.pack(anchor='w', pady=(1, 4))

    prog = ttk.Progressbar(card_frame, maximum=100)
    prog.pack(fill='x', expand=True)

    return {
        'app': app,
        'task_id': task_id,
        'frame': card_frame,
        'pct_var': pct_var,
        'meta_var': meta_var,
        'progress': prog,
        'cancel_btn': cancel_btn
    }


def update_task_widget(widgets, percent, status_text, state='active'):
    if not widgets:
        return
    widgets['progress']['value'] = percent
    widgets['pct_var'].set(f'{percent:.0f}%' if state == 'active' else ('100%' if state == 'done' else '—'))
    widgets['meta_var'].set(status_text)
    if state in ('done', 'error', 'cancelled'):
        app = widgets.get('app')
        task_id = widgets.get('task_id')
        if app and hasattr(app, 'clear_task') and task_id is not None:
            widgets['cancel_btn'].configure(text='✕ Clear', state='normal', command=lambda: app.clear_task(task_id))
        else:
            widgets['cancel_btn'].configure(state='disabled')


def refresh_selection(app):
    selected = app.table.selection()
    if not selected or int(selected[0]) >= len(app.choices):
        app.selected_quality.set('—')
        app.selected_detail.set('Select a quality to get started')
        if hasattr(app, 'update_download_button_state'):
            app.update_download_button_state()
        elif hasattr(app, 'download_button'):
            app.download_button.configure(state='disabled')
        return
    choice = app.choices[int(selected[0])]
    app.selected_quality.set(f'{choice.height}p' if choice.height else 'Original')
    parts = [f'{round(choice.bandwidth / 1000):,} kbps'] if choice.bandwidth else []
    parts.append((choice.audio_name or 'Audio') + ' · separate track' if choice.audio_url else 'Audio from source')
    app.selected_detail.set('  /  '.join(parts))
    if hasattr(app, 'update_download_button_state'):
        app.update_download_button_state()


def settings(app):
    existing = getattr(app, 'settings_window', None)
    if existing and existing.winfo_exists():
        existing.lift(); return
    window = tk.Toplevel(app)
    app.settings_window = window
    window.title('Media Fetch — Settings')
    window.configure(bg=BG)
    window.geometry('620x300')
    window.resizable(False, False)
    window.transient(app)
    body = ttk.Frame(window, padding=24); body.pack(fill='both', expand=True)
    label(body, 'Download engine', 'Brand.TLabel').pack(anchor='w')
    label(body, 'FFmpeg combines your video and audio without re-encoding.', 'Muted.TLabel').pack(anchor='w', pady=(6, 18))
    label(body, 'FFmpeg executable', 'Muted.TLabel').pack(anchor='w', pady=(0, 6))
    entry = ttk.Entry(body, textvariable=app.ffmpeg)
    entry.pack(fill='x')
    if app.busy:
        entry.configure(state='disabled')
    row = ttk.Frame(body); row.pack(fill='x', pady=14)
    ttk.Button(row, text='Browse…', command=app.browse_ffmpeg, state='disabled' if app.busy else 'normal').pack(side='left')
    ttk.Button(row, text='Done', style='Primary.TButton', command=window.destroy).pack(side='right')
    label(body, 'Browser-linked downloads require the browser to remain open.', 'Muted.TLabel').pack(anchor='w', pady=(8, 0))
    window.bind('<Escape>', lambda event: window.destroy())
