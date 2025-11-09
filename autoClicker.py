"""
autoclicker.py - Simple recorder/replayer for mouse & keyboard using pynput.
Usage:
    python autoclicker.py
Requirements:
    pip install pynput
Notes:
    - Run as admin on Windows for some games.
    - For macOS, grant Accessibility permissions.
Edit: 
    - Working on adding an option to ignore mouse input. 
"""

import json
import threading
import time
import random
from pathlib import Path
from tkinter import Tk, Button, Label, Entry, Checkbutton, IntVar, DoubleVar, filedialog, StringVar
from pynput import mouse, keyboard

# ---------- Data structures ----------
events = []  # list of {"type": "mouse"|"key", "subtype": "...", "time": <float>, ...}
recording = False
play_thread = None
playback_paused = False
stop_playback_flag = False

# ---------- Recording ----------
start_time = None
mouse_listener = None
keyboard_listener = None

def now():
    return time.perf_counter()

def record_event(e: dict):
    events.append(e)

def on_move(x, y):
    if not recording: return
    record_event({"type": "mouse", "subtype": "move", "x": x, "y": y, "time": now() - start_time})

def on_click(x, y, button, pressed):
    if not recording: return
    record_event({"type": "mouse", "subtype": "click", "x": x, "y": y, "button": button.name, "pressed": pressed, "time": now() - start_time})

def on_scroll(x, y, dx, dy):
    if not recording: return
    record_event({"type": "mouse", "subtype": "scroll", "x": x, "y": y, "dx": dx, "dy": dy, "time": now() - start_time})

def on_press(key):
    if not recording: return
    try:
        k = key.char
    except AttributeError:
        k = str(key)  # special keys
    record_event({"type": "key", "subtype": "press", "key": k, "time": now() - start_time})

def on_release(key):
    if not recording: return
    try:
        k = key.char
    except AttributeError:
        k = str(key)
    record_event({"type": "key", "subtype": "release", "key": k, "time": now() - start_time})

def start_recording():
    global recording, start_time, mouse_listener, keyboard_listener, events
    events = []
    recording = True
    start_time = now()
    # start listeners
    mouse_bool = bool(mouse_var.get())
    if mouse_bool == True:
        mouse_listener = mouse.Listener(on_move=on_move, on_click=on_click, on_scroll=on_scroll)
    else: 
        pass
    keyboard_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    mouse_listener.start()
    keyboard_listener.start()
    print("Recording started.")

def stop_recording():
    global recording, mouse_listener, keyboard_listener
    recording = False
    if mouse_listener:
        mouse_listener.stop()
        mouse_listener = None
    if keyboard_listener:
        keyboard_listener.stop()
        keyboard_listener = None
    print(f"Recording stopped. {len(events)} events captured.")

# ---------- Playback ----------
mouse_controller = mouse.Controller()
keyboard_controller = keyboard.Controller()

def _press_key_from_repr(k):
    """Turn stored key string back into pynput Key or char. Stored special keys are like 'Key.space' or 'Key.shift'."""
    if k.startswith("Key."):
        name = k.split(".", 1)[1]
        return getattr(keyboard.Key, name)
    else:
        # a character
        return k

def play_events(loop=False, speed=1.0, jitter_ms=0):
    """Play recorded events in a new thread. Options:
       loop: bool -> repeat forever until stopped
       speed: float -> multiply speed (2.0 == twice as fast)
       jitter_ms: int -> random +/- milliseconds added to each delay (makes playback less robotic) EDIT: i have removed the jitter feature and will replace with mouse input selection
    """
    global play_thread, playback_paused, stop_playback_flag
    playback_paused = False
    stop_playback_flag = False

    def runner():
        global playback_paused, stop_playback_flag
        if not events:
            print("No events to play.")
            return
        print("Playback started.")
        while True:
            base_t0 = time.perf_counter()
            prev_time = 0.0
            for ev in events:
                if stop_playback_flag:
                    print("Playback stopped by user.")
                    return
                # handle pause
                while playback_paused and not stop_playback_flag:
                    time.sleep(0.05)
                # compute delay
                target_delay = (ev["time"] - prev_time) / speed

                if jitter_ms:
                    jitter = random.uniform(-jitter_ms, jitter_ms) / 1000.0
                else:
                    jitter = 0.0
                if target_delay + jitter > 0:
                    time.sleep(max(0, target_delay + jitter))
                
                prev_time = ev["time"]
                # play event
                try:
                    if ev["type"] == "mouse":
                        mouse_bool = bool(mouse_var.get())
                        if mouse_bool == True:
                            if ev["subtype"] == "move":
                                mouse_controller.position = (ev["x"], ev["y"])
                            elif ev["subtype"] == "click":
                                # button -> mouse.Button.left/right/middle
                                btn = getattr(mouse.Button, ev["button"])
                                if ev["pressed"]:
                                    mouse_controller.press(btn)
                                else:
                                    mouse_controller.release(btn)
                            elif ev["subtype"] == "scroll":
                                mouse_controller.scroll(ev["dx"], ev["dy"])
                            else: pass
                    elif ev["type"] == "key":
                        k = ev["key"]
                        if k.startswith("Key."):
                            keyobj = getattr(keyboard.Key, k.split(".",1)[1])
                            if ev["subtype"] == "press":
                                keyboard_controller.press(keyobj)
                            else:
                                keyboard_controller.release(keyobj)
                        else:
                            # printable char
                            if ev["subtype"] == "press":
                                keyboard_controller.press(k)
                            else:
                                keyboard_controller.release(k)
                except Exception as e:
                    print("Playback error:", e)
            if not loop:
                print("Playback finished.")
                return
            # loop: continue to next iteration
    play_thread = threading.Thread(target=runner, daemon=True)
    play_thread.start()

def stop_playback():
    global stop_playback_flag, playback_paused
    stop_playback_flag = True
    playback_paused = False
    print("Stopping playback...")

def pause_playback():
    global playback_paused
    playback_paused = True
    print("Playback paused.")

def resume_playback():
    global playback_paused
    playback_paused = False
    print("Playback resumed.")

# ---------- Save / Load ----------
def save_to_file(path: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2)
    print(f"Saved {len(events)} events to {path}")

def load_from_file(path: str):
    global events
    with open(path, "r", encoding="utf-8") as f:
        events = json.load(f)
    print(f"Loaded {len(events)} events from {path}")

# ---------- GUI ----------
def make_gui():
    global mouse_var
    root = Tk()
    root.title("Simple AutoClicker Recorder")

    # buttons
    lbl_status = Label(root, text="Idle")
    lbl_status.grid(row=0, column=0, columnspan=4, padx=6, pady=6)

    def on_record():
        if not recording:
            start_recording()
            lbl_status.config(text="Recording...")
            btn_record.config(state="disabled")
            btn_stop.config(state="normal")
        else:
            pass

    def on_stop():
        if recording:
            stop_recording()
            lbl_status.config(text=f"Recorded {len(events)} events")
            btn_record.config(state="normal")
            btn_stop.config(state="disabled")

    def on_play():
        if not events:
            lbl_status.config(text="No events to play")
            return
        loop = bool(loop_var.get())
        try:
            speed = float(speed_var.get())
        except:
            speed = 1.0
        """
        try:
            #jitter = int(jitter_var.get())
        #except:
            #jitter = 0
        """
        play_events(loop=loop, speed=speed)
        lbl_status.config(text="Playing")

    def on_pause():
        pause_playback()
        lbl_status.config(text="Paused")

    def on_resume():
        resume_playback()
        lbl_status.config(text="Playing")

    def on_stop_play():
        stop_playback()
        lbl_status.config(text="Stopped")

    def on_save():
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files","*.json")])
        if path:
            save_to_file(path)
            lbl_status.config(text=f"Saved {len(events)} events")

    def on_load():
        path = filedialog.askopenfilename(filetypes=[("JSON files","*.json")])
        if path:
            load_from_file(path)
            lbl_status.config(text=f"Loaded {len(events)} events")

    btn_record = Button(root, text="Record", width=12, command=on_record)
    btn_record.grid(row=1, column=0, padx=6, pady=6)

    btn_stop = Button(root, text="Stop (Record)", width=12, command=on_stop, state="disabled")
    btn_stop.grid(row=1, column=1, padx=6, pady=6)

    btn_play = Button(root, text="Play", width=12, command=on_play)
    btn_play.grid(row=1, column=2, padx=6, pady=6)

    btn_pause = Button(root, text="Pause", width=12, command=on_pause)
    btn_pause.grid(row=1, column=3, padx=6, pady=6)

    btn_resume = Button(root, text="Resume", width=12, command=on_resume)
    btn_resume.grid(row=2, column=0, padx=6, pady=6)

    btn_stopplay = Button(root, text="Stop (Play)", width=12, command=on_stop_play)
    btn_stopplay.grid(row=2, column=1, padx=6, pady=6)

    btn_save = Button(root, text="Save", width=12, command=on_save)
    btn_save.grid(row=2, column=2, padx=6, pady=6)

    btn_load = Button(root, text="Load", width=12, command=on_load)
    btn_load.grid(row=2, column=3, padx=6, pady=6)

    # options
    loop_var = IntVar(value=0)
    chk_loop = Checkbutton(root, text="Loop", variable=loop_var)
    chk_loop.grid(row=3, column=0, padx=6, pady=6)

    # new mouse input option
    mouse_var = IntVar(value=1)
    chk_loop = Checkbutton(root, text="Mouse Input", variable=mouse_var)
    chk_loop.grid(row=3, column=1)

    speed_var = StringVar(value="1.0")
    Label(root, text="Speed:").grid(row=3, column=2)
    Entry(root, textvariable=speed_var, width=6).grid(row=3, column=3)

    

    """
    jitter_var = StringVar(value="0")
    Label(root, text="Jitter ms").grid(row=3, column=3)
    Entry(root, textvariable=jitter_var, width=6).grid(row=3, column=4)
    """
    root.mainloop()

if __name__ == "__main__":
    make_gui()
