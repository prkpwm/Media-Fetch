"""Launch with python desktop/app.py. UI work stays on the Tk main thread."""
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from core import DownloadJob, fetch_playlist, find_ffmpeg, import_har, redact, default_destination
from ui import build_ui, refresh_selection, add_task_widget, update_task_widget


import sys

APP_ID = 'MediaFetch.Desktop.App.0.2'
if sys.platform == 'win32':
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass


def is_same_media(choice_a, choice_b):
    if not choice_a or not choice_b:
        return False
    if choice_a.url == choice_b.url:
        return True
    from urllib.parse import urlsplit
    try:
        p_a = urlsplit(choice_a.url)
        p_b = urlsplit(choice_b.url)
        if p_a.hostname and p_b.hostname and p_a.hostname == p_b.hostname and p_a.path == p_b.path and p_a.path:
            return True
    except Exception:
        pass
    return False


class App(tk.Tk):
    def __init__(self, native_reply=None):
        super().__init__()
        self.title('Media Fetch — Desktop')
        icon_path = Path(__file__).parent / 'app.ico'
        if icon_path.is_file():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass
        self.events = queue.Queue()
        self.choices = []
        self.tasks = {}
        self.task_sequence = 0
        self.inspecting = False
        self.native_reply = native_reply
        self.native_disconnected = False
        self.url = tk.StringVar()
        self.ffmpeg = tk.StringVar(value=find_ffmpeg())
        self.destination = tk.StringVar(value=default_destination())
        self.status = tk.StringVar(value='Import a HAR capture or inspect an HLS playlist URL.')
        build_ui(self)
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.after(100, self.poll)

    def get_current_media_status(self):
        selection = self.table.selection()
        if not selection or int(selection[0]) >= len(self.choices):
            return None
        current_choice = self.choices[int(selection[0])]
        dest_name = Path(self.destination.get()).name if self.destination.get() else ''

        for task in reversed(list(self.tasks.values())):
            task_choice = task.get('choice')
            task_status = task.get('status')
            matches = False
            if is_same_media(task_choice, current_choice):
                matches = True
            elif task.get('name') and dest_name and task.get('name') == dest_name:
                matches = True

            if matches:
                if task_status in ('Preparing', 'Downloading'):
                    return 'in_progress'
                elif task_status == 'Done':
                    return 'done'
        return None

    def update_download_button_state(self):
        if not hasattr(self, 'download_button'):
            return
        if self.inspecting:
            self.download_button.configure(state='disabled')
            return

        selection = self.table.selection()
        if not selection or int(selection[0]) >= len(self.choices):
            self.download_button.configure(text='↓  Download MP4', state='disabled')
            return

        media_status = self.get_current_media_status()
        if media_status == 'in_progress':
            self.download_button.configure(text='Downloading…', state='disabled')
        elif media_status == 'done':
            self.download_button.configure(text='✓  Downloaded', state='disabled')
        else:
            self.download_button.configure(text='↓  Download MP4', state='normal')

    def update_clear_button_state(self):
        if not hasattr(self, 'clear_button'):
            return
        has_finished = any(t.get('status') in ('Done', 'Failed', 'Cancelled') for t in self.tasks.values())
        self.clear_button.configure(state='normal' if has_finished else 'disabled')

    @property
    def busy(self):
        return self.inspecting

    @busy.setter
    def busy(self, value):
        self.inspecting = bool(value)

    @property
    def job(self):
        active = [t['job'] for t in self.tasks.values() if t['status'] in ('Preparing', 'Downloading')]
        return active[-1] if active else None

    @job.setter
    def job(self, value):
        pass

    @property
    def active_jobs_count(self):
        return sum(1 for t in self.tasks.values() if t['status'] in ('Preparing', 'Downloading'))

    def emit(self, kind, value):
        self.events.put((kind, value))

    def handle_native(self, message):
        from native_protocol import parse_open
        request_id = message.get('id')
        if type(request_id) is not int:
            self.native_reply({'id': None, 'ok': False, 'error': 'Invalid request ID.'})
            return
        try:
            if message.get('action') == 'ping':
                self.native_reply({'id': request_id, 'ok': True, 'version': '0.2.0'})
                return
            if message.get('action') != 'open':
                raise ValueError('Unknown desktop action.')
            if self.busy:
                raise ValueError('The desktop app is busy reading media information.')
            url, headers, title, choice = parse_open(message)
            self.url.set(url)
            self.title('Media Fetch — ' + (title or 'From browser'))
            if title:
                downloads_dir = Path(self.destination.get()).parent if self.destination.get() else None
                self.destination.set(default_destination(title, folder=downloads_dir))
            self.deiconify()
            self.lift()
            if choice:
                self.emit('choices', [choice])
            else:
                self.discover(lambda source: fetch_playlist(source, headers), url)
            self.native_reply({'id': request_id, 'ok': True, 'opened': True})
        except Exception as error:
            self.native_reply({'id': request_id, 'ok': False, 'error': redact(error)})

    def set_busy(self, value):
        self.inspecting = value
        for button in (self.inspect_button, self.import_button):
            button.configure(state='disabled' if value else 'normal')
        for widget in (self.url_entry, self.destination_entry, self.browse_button):
            widget.configure(state='disabled' if value else 'normal')
        self.update_download_button_state()
        if not value:
            if str(self.progress['mode']) == 'indeterminate':
                self.progress.stop()
                self.progress.configure(mode='determinate', value=0)

    def discover(self, function, argument):
        if self.inspecting:
            return
        self.set_busy(True)
        self.status.set('Reading media information…')
        self.phase.set('Finding your media')
        self.percent.set('…')
        self.progress.configure(mode='indeterminate')
        self.progress.start(15)
        def work():
            try:
                self.emit('choices', function(argument))
            except Exception as error:
                self.emit('error', redact(error))
            finally:
                self.emit('finished', None)
        threading.Thread(target=work, daemon=True).start()

    def inspect(self):
        self.discover(fetch_playlist, self.url.get().strip())

    def load_har(self):
        path = filedialog.askopenfilename(filetypes=[('HAR captures', '*.har')])
        if path:
            self.discover(import_har, path)

    def browse_output(self):
        initial_file = Path(self.destination.get()).name if self.destination.get() else 'video.mp4'
        initial_dir = str(Path(self.destination.get()).parent) if self.destination.get() else str(Path.home() / 'Downloads')
        path = filedialog.asksaveasfilename(initialdir=initial_dir, initialfile=initial_file, defaultextension='.mp4', filetypes=[('MP4 video', '*.mp4')])
        if path:
            self.destination.set(path)

    def browse_ffmpeg(self):
        path = filedialog.askopenfilename(filetypes=[('FFmpeg', '*.exe'), ('All files', '*')])
        if path:
            self.ffmpeg.set(path)

    def download(self):
        selection = self.table.selection()
        if self.inspecting or not selection:
            return
        executable = Path(self.ffmpeg.get())
        destination = Path(self.destination.get())
        if not executable.is_file():
            messagebox.showerror('FFmpeg missing', 'Run setup.cmd or browse to your ffmpeg.exe.'); return
        if destination.suffix.lower() != '.mp4' or not destination.parent.is_dir():
            messagebox.showerror('Choose an output file', 'Choose a valid .mp4 filename inside an existing folder.'); return
        if destination.exists():
            destination = Path(default_destination(title=destination.stem, folder=destination.parent))
            self.destination.set(str(destination))

        choice = self.choices[int(selection[0])]
        self.task_sequence += 1
        task_id = self.task_sequence

        def notify(kind, value):
            self.emit(f'task_{kind}', (task_id, value))

        job = DownloadJob(str(executable), choice, destination, notify)
        widgets = add_task_widget(self, task_id, destination.name, f'{choice.height}p · {destination.parent}')
        self.tasks[task_id] = {
            'id': task_id,
            'job': job,
            'destination': destination,
            'name': destination.name,
            'choice': choice,
            'status': 'Preparing',
            'seconds': 0,
            'duration': choice.duration or 0,
            'percent': 0,
            'widgets': widgets
        }

        self.update_download_button_state()
        self.cancel_button.configure(state='normal')
        self.phase.set(f'{self.active_jobs_count} download(s) in progress')
        self.percent.set('…')
        self.status.set(f'Started download #{task_id}: {destination.name}')

        next_name = default_destination(title=destination.stem, folder=destination.parent)
        self.destination.set(next_name)

        threading.Thread(target=job.run, daemon=True).start()

    def cancel(self, task_id=None):
        if task_id is not None:
            task = self.tasks.get(task_id)
            if task and task['status'] in ('Preparing', 'Downloading'):
                task['status'] = 'Cancelling'
                task['widgets']['meta_var'].set('Cancelling…')
                task['widgets']['cancel_btn'].configure(state='disabled')
                threading.Thread(target=task['job'].cancel, daemon=True).start()
        else:
            for tid, task in reversed(list(self.tasks.items())):
                if task['status'] in ('Preparing', 'Downloading'):
                    self.cancel(tid)
                    break

    def cancel_all(self):
        for tid in list(self.tasks.keys()):
            self.cancel(tid)

    def clear_task(self, task_id):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            if task['status'] in ('Preparing', 'Downloading'):
                self.cancel(task_id)
            widgets = task.get('widgets')
            if widgets and 'frame' in widgets:
                try:
                    widgets['frame'].destroy()
                except Exception:
                    pass
            del self.tasks[task_id]
            self._update_after_clear()

    def clear_tasks(self, only_finished=True):
        tids = list(self.tasks.keys())
        for tid in tids:
            task = self.tasks.get(tid)
            if not task:
                continue
            if only_finished and task['status'] in ('Preparing', 'Downloading'):
                continue
            self.clear_task(tid)

    def _update_after_clear(self):
        active_tasks = [t for t in self.tasks.values() if t['status'] in ('Preparing', 'Downloading')]
        if not self.tasks:
            self.phase.set('Ready when you are')
            self.percent.set('—')
            self.status.set('All cleared.')
            self.progress['value'] = 0
            self.cancel_button.configure(state='disabled')
        elif not active_tasks:
            self.phase.set('All downloads completed')
            self.percent.set('100%')
            self.cancel_button.configure(state='disabled')
        else:
            avg_pct = sum(t['percent'] for t in active_tasks) / len(active_tasks)
            self.progress['value'] = avg_pct
            self.percent.set(f'{avg_pct:.0f}%')
            self.phase.set(f'{len(active_tasks)} download(s) in progress')

        self.update_download_button_state()
        self.update_clear_button_state()

    def poll(self):
        from urllib.parse import urlsplit
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'native_request':
                    self.handle_native(value)
                elif kind == 'native_disconnect':
                    self.native_disconnected = True
                    if self.active_jobs_count > 0:
                        self.cancel_all()
                    elif not self.busy:
                        self.destroy()
                        return
                elif kind == 'choices':
                    self.choices = value
                    self.empty_state.place_forget()
                    self.count_text.set(f'{len(value)} available')
                    self.table.delete(*self.table.get_children())
                    for index, choice in enumerate(value):
                        self.table.insert('', 'end', iid=str(index), tags=('alternate',) if index % 2 else (), values=(f'{choice.height}p' if choice.height else 'Original', choice.audio_name or ('Separate' if choice.audio_url else 'From source'), choice.encryption or 'HLS', urlsplit(choice.url).hostname))
                    self.table.selection_set(str(len(value) - 1))
                    self.table.see(str(len(value) - 1))
                    refresh_selection(self)
                    self.update_download_button_state()
                    self.phase.set('Ready to download' if self.active_jobs_count == 0 else f'{self.active_jobs_count} download(s) in progress')
                    self.status.set(f'{len(value)} quality options detected. Select one and click Download.')
                    if not self.busy:
                        self.set_busy(False)
                elif kind == 'task_status':
                    task_id, text = value
                    if task_id in self.tasks:
                        self.tasks[task_id]['widgets']['meta_var'].set(text)
                elif kind == 'task_progress':
                    task_id, (seconds, duration) = value
                    if task_id in self.tasks:
                        task = self.tasks[task_id]
                        pct = min(99, seconds / duration * 100) if duration else 0
                        task['percent'] = pct
                        task['status'] = 'Downloading'
                        task['seconds'] = seconds
                        task['duration'] = duration
                        update_task_widget(task['widgets'], pct, f'Processed {seconds:.0f} / {duration:.0f}s ({pct:.0f}%)', state='active')
                        active_tasks = [t for t in self.tasks.values() if t['status'] in ('Preparing', 'Downloading')]
                        if active_tasks:
                            avg_pct = sum(t['percent'] for t in active_tasks) / len(active_tasks)
                            self.progress['value'] = avg_pct
                            self.percent.set(f'{avg_pct:.0f}%')
                            self.phase.set(f'{len(active_tasks)} download(s) in progress')
                elif kind == 'task_done':
                    task_id, destination = value
                    if task_id in self.tasks:
                        task = self.tasks[task_id]
                        task['status'] = 'Done'
                        task['percent'] = 100
                        update_task_widget(task['widgets'], 100, f'Saved: {destination}', state='done')
                        self.status.set(f'Saved #{task_id}: {Path(destination).name}')
                        if self.active_jobs_count == 0:
                            self.progress['value'] = 100
                            self.phase.set('All downloads completed')
                            self.percent.set('100%')
                            self.cancel_button.configure(state='disabled')
                        self.update_download_button_state()
                        self.update_clear_button_state()
                elif kind == 'task_error':
                    task_id, error_msg = value
                    if task_id in self.tasks:
                        task = self.tasks[task_id]
                        task['status'] = 'Failed'
                        update_task_widget(task['widgets'], task['percent'], f'Failed: {error_msg}', state='error')
                        self.status.set(f'Download #{task_id} failed.')
                        messagebox.showerror('Media Fetch', error_msg)
                        self.update_download_button_state()
                        self.update_clear_button_state()
                elif kind == 'task_cancelled':
                    task_id, _ = value
                    if task_id in self.tasks:
                        task = self.tasks[task_id]
                        task['status'] = 'Cancelled'
                        update_task_widget(task['widgets'], 0, 'Cancelled', state='cancelled')
                        self.status.set(f'Download #{task_id} cancelled.')
                        self.update_download_button_state()
                        self.update_clear_button_state()
                elif kind == 'task_finished':
                    if self.active_jobs_count == 0:
                        self.cancel_button.configure(state='disabled')
                        if self.native_disconnected:
                            self.destroy()
                            return
                    self.update_download_button_state()
                    self.update_clear_button_state()
                elif kind == 'progress':
                    seconds, duration = value
                    self.progress['value'] = min(99, seconds / duration * 100) if duration else 0
                    self.percent.set(f'{min(99, seconds / duration * 100):.0f}%' if duration else '…')
                elif kind == 'done':
                    self.progress['value'] = 100
                    self.percent.set('100%')
                    self.status.set(f'Saved: {value}')
                elif kind == 'error':
                    self.status.set('Failed.')
                    messagebox.showerror('Media Fetch', value)
                elif kind == 'finished':
                    self.set_busy(False)
                    if self.active_jobs_count == 0:
                        self.cancel_button.configure(state='disabled')
                        if self.native_disconnected:
                            self.destroy()
                            return
                else:
                    self.status.set(str(value))
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def close(self):
        if self.inspecting:
            messagebox.showinfo('Work in progress', 'Wait for inspection to finish before closing.'); return
        if self.active_jobs_count > 0:
            if messagebox.askyesno('Downloads in progress', f'There are {self.active_jobs_count} active download(s). Cancel them and exit?'):
                self.cancel_all()
                self.destroy()
            return
        self.destroy()


if __name__ == '__main__':
    App().mainloop()
