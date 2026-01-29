import os
import time
import argparse
import subprocess
from watchdog.events import FileModifiedEvent, FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer

parser = argparse.ArgumentParser(description='Expander')
parser.add_argument('project_path', help='Project file path')
parser.add_argument('commit_msg_path', help="Commit messages file path")
opts = parser.parse_args()
print(f"Listening at: {opts.commit_msg_path}")
print(f"Target project path: {opts.project_path}")

class EventHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_content = None

    def on_modified(self, event) -> None:
        #print(f"File modified: {event.src_path}")
        if not event.is_directory and event.src_path.endswith(os.path.basename(opts.commit_msg_path)):
            with open(event.src_path, "r", encoding='utf-8') as f:
                commit_msg = f.read()
                if commit_msg != self.last_content:
                    try:
                        print(f"Commit changes: {commit_msg}")
                        subprocess.run(["git", "add", "-A"], cwd=opts.project_path, check=True)
                        subprocess.run(["git", "commit", "-m", commit_msg, "-q"], cwd=opts.project_path, check=True)
                    except Exception as e:
                        print(f"Commit failed with error: {e}")
                self.last_content = commit_msg
                
event_handler = EventHandler()
observer = Observer()
observer.schedule(event_handler, os.path.dirname(opts.commit_msg_path), recursive=True)
observer.start()
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    observer.stop()
observer.join()