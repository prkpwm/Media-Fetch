import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_protocol import MAX_MESSAGE, parse_open, read_message, write_message
from register_host import prepare


class NativeTests(unittest.TestCase):
    def payload(self):
        return {'id': 1, 'action': 'open', 'url': 'https://cdn.invalid/master.m3u8',
                'pageUrl': 'https://player.invalid/watch', 'title': 'Thai episode', 'userAgent': 'Test browser',
                'selection': {'url': 'https://cdn.invalid/720.m3u8?token=video',
                              'audioUrl': 'https://cdn.invalid/th.m3u8?token=audio', 'audioName': 'Thai',
                              'height': 720, 'bandwidth': 2426000}}

    def test_wire_encoding_roundtrip(self):
        data = {'id': 1, 'title': 'ไทย'}
        stream = io.BytesIO(); write_message(stream, data); stream.seek(0)
        self.assertEqual(read_message(stream), data)
        self.assertIsNone(read_message(stream))

    def test_rejects_oversize_truncated_nonobject(self):
        for raw in [struct.pack('<I', MAX_MESSAGE + 1), b'\x10', struct.pack('<I', 2) + b'[]', struct.pack('<I', 4) + b'{}']:
            with self.assertRaises((ValueError, UnicodeError)):
                read_message(io.BytesIO(raw))

    def test_selection_preserves_both_tracks_and_context(self):
        url, headers, title, choice = parse_open(self.payload())
        self.assertEqual(choice.height, 720)
        self.assertTrue(choice.audio_url.endswith('token=audio'))
        self.assertEqual(headers['Origin'], 'https://player.invalid')
        self.assertEqual(headers['Referer'], 'https://player.invalid/watch')
        self.assertEqual(choice.source, url)

    def test_rejects_local_files_and_header_injection(self):
        for field, bad in [('url', 'file:///C:/secret'), ('userAgent', 'test\r\nCookie: secret')]:
            payload = self.payload(); payload[field] = bad
            with self.assertRaises(ValueError):
                parse_open(payload)
        payload = self.payload(); payload['selection']['audioUrl'] = 'file:///C:/secret'
        with self.assertRaises(ValueError):
            parse_open(payload)

    def test_manifest_allows_only_supplied_extension(self):
        extension_id = 'nifpgklpooghhmdclpkkcdkgbnekfnge'
        with tempfile.TemporaryDirectory() as directory:
            path = prepare(extension_id, directory)
            manifest = json.loads(path.read_text())
            self.assertEqual(manifest['allowed_origins'], [f'chrome-extension://{extension_id}/'])
            self.assertTrue(Path(manifest['path']).exists())
        with self.assertRaises(ValueError):
            prepare('*')

    def test_native_selection_reaches_desktop_table_without_starting_download(self):
        from app import App
        replies = []
        app = App(native_reply=replies.append); app.withdraw()
        try:
            with patch.object(app, 'deiconify'), patch.object(app, 'lift'):
                app.handle_native(self.payload())
                app.poll()
                app.update_idletasks()
            self.assertEqual(replies[-1], {'id': 1, 'ok': True, 'opened': True})
            self.assertEqual(app.choices[0].height, 720)
            self.assertEqual(Path(app.destination.get()).name, 'Thai episode.mp4')
            self.assertEqual(len(app.table.get_children()), 1)
            self.assertEqual(str(app.download_button['state']), 'normal')
            self.assertIsNone(app.job)
            app.busy = True
            app.handle_native(self.payload())
            self.assertFalse(replies[-1]['ok'])
        finally:
            app.destroy()

    def test_multiple_concurrent_downloads_tracked(self):
        from app import App
        replies = []
        app = App(native_reply=replies.append); app.withdraw()
        try:
            with patch.object(app, 'deiconify'), patch.object(app, 'lift'):
                app.handle_native(self.payload())
                app.poll()
            self.assertEqual(replies[-1], {'id': 1, 'ok': True, 'opened': True})
            # Start job 1
            with patch('threading.Thread'):
                app.download()
            self.assertEqual(app.active_jobs_count, 1)
            task1 = app.tasks[1]
            self.assertEqual(task1['status'], 'Preparing')

            # Send second stream from browser - should NOT be rejected
            payload2 = self.payload()
            payload2['id'] = 2
            payload2['title'] = 'Second Episode'
            with patch.object(app, 'deiconify'), patch.object(app, 'lift'):
                app.handle_native(payload2)
                app.poll()
            self.assertEqual(replies[-1], {'id': 2, 'ok': True, 'opened': True})
            # Start job 2
            with patch('threading.Thread'):
                app.download()
            self.assertEqual(app.active_jobs_count, 2)
            self.assertIn(1, app.tasks)
            self.assertIn(2, app.tasks)

            # Test progress updates per task
            app.emit('task_progress', (1, (10, 100)))
            app.emit('task_progress', (2, (20, 100)))
            app.poll()
            self.assertEqual(app.tasks[1]['percent'], 10)
            self.assertEqual(app.tasks[2]['percent'], 20)

            # Cancel task 1 specifically
            with patch('threading.Thread'):
                app.cancel(1)
            self.assertEqual(app.tasks[1]['status'], 'Cancelling')
            self.assertEqual(app.tasks[2]['status'], 'Downloading')
        finally:
            app.destroy()

    def test_download_button_disabled_when_in_progress_or_done(self):
        from app import App
        replies = []
        app = App(native_reply=replies.append)
        app.withdraw()
        try:
            with patch.object(app, 'deiconify'), patch.object(app, 'lift'):
                app.handle_native(self.payload())
                app.poll()
            self.assertEqual(str(app.download_button['state']), 'normal')

            # Click download -> in progress -> disabled
            with patch('threading.Thread'):
                app.download()
            self.assertEqual(str(app.download_button['state']), 'disabled')
            self.assertIn('Downloading', app.download_button['text'])

            # New stream arrives while old one runs -> enabled for new stream
            payload2 = self.payload()
            payload2['id'] = 2
            payload2['title'] = 'New Episode'
            payload2['selection']['url'] = 'https://cdn.invalid/new_stream.m3u8'
            with patch.object(app, 'deiconify'), patch.object(app, 'lift'):
                app.handle_native(payload2)
                app.poll()
            self.assertEqual(str(app.download_button['state']), 'normal')

            # Switch back to first stream which completes -> done -> disabled
            app.emit('task_done', (1, 'C:\\Users\\acer\\Downloads\\Thai episode.mp4'))
            app.poll()
            with patch.object(app, 'deiconify'), patch.object(app, 'lift'):
                app.handle_native(self.payload())
                app.poll()
            self.assertEqual(str(app.download_button['state']), 'disabled')
            self.assertIn('Downloaded', app.download_button['text'])
        finally:
            app.destroy()

    def test_clear_completed_tasks_and_individual_task(self):
        from app import App
        replies = []
        app = App(native_reply=replies.append)
        app.withdraw()
        try:
            with patch.object(app, 'deiconify'), patch.object(app, 'lift'):
                app.handle_native(self.payload())
                app.poll()

            with patch('threading.Thread'):
                app.download()

            self.assertEqual(str(app.clear_button['state']), 'disabled')

            app.emit('task_done', (1, 'C:\\Users\\acer\\Downloads\\Thai episode.mp4'))
            app.poll()

            self.assertEqual(str(app.clear_button['state']), 'normal')
            self.assertIn('Clear', app.tasks[1]['widgets']['cancel_btn']['text'])

            app.clear_task(1)
            self.assertEqual(len(app.tasks), 0)
            self.assertEqual(str(app.clear_button['state']), 'disabled')
            self.assertEqual(app.phase.get(), 'Ready when you are')
        finally:
            app.destroy()


if __name__ == '__main__':
    unittest.main()

