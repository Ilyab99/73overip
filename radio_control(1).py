import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import json
import os
import threading

CONFIG_FILE = os.path.join(os.path.expanduser("~"), "radio_config.json")

DEFAULT_CONFIG = {
    "vlc_path": "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe",
    "ffmpeg_path": "C:\\hereisuers\\Desktop\\stuff\\Binaries\\Win64\\ffmpeg.exe",
    "pi_ip": "192.168.0.91",
    "pi_user": "freebsd",
    "pi_script": "./final.sh",
    "rigctld_cmd": "rigctld -m 3073 -s 9600 -r /dev/cuaU0",
    "rx_port": "9000",
    "tx_port": "8766",
    "rx_cable": "CABLE Input (VB-Audio Virtual Cable)",
    "tx_cable": "CABLE-C Output (VB-Audio Cable C)",
    "network_caching": "200",
    "tx_gain": 1.0,
}

class RadioControl:
    def __init__(self, root):
        self.root = root
        self.root.title("IC-7300 Remote Audio Control")
        self.root.resizable(False, False)
        self.root.configure(bg="#1a1a2e")

        self.rx_process = None
        self.tx_process = None
        self.ssh_audio_process = None
        self.ssh_rigctld_process = None
        self.config = self.load_config()

        self.build_ui()
        self.monitor_processes()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE) as f:
                    return {**DEFAULT_CONFIG, **json.load(f)}
            except:
                pass
        return DEFAULT_CONFIG.copy()

    def save_config(self):
        config = {
            "vlc_path": self.vlc_path.get(),
            "ffmpeg_path": self.ffmpeg_path.get(),
            "pi_ip": self.pi_ip.get(),
            "pi_user": self.pi_user.get(),
            "pi_script": self.pi_script.get(),
            "rigctld_cmd": self.rigctld_cmd.get(),
            "rx_port": self.rx_port.get(),
            "tx_port": self.tx_port.get(),
            "rx_cable": self.rx_cable.get(),
            "tx_cable": self.tx_cable.get(),
            "network_caching": self.network_caching.get(),
            "tx_gain": self.tx_gain.get(),
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)

    def update_gain_label(self, val):
        self.tx_gain_label.config(text=f"{float(val):.1f}x")

    def build_ui(self):
        # Title
        title_frame = tk.Frame(self.root, bg="#1a1a2e")
        title_frame.pack(fill="x", padx=20, pady=(20, 5))

        tk.Label(title_frame, text="IC-7300 REMOTE AUDIO",
                 font=("Courier New", 18, "bold"), fg="#00d4ff", bg="#1a1a2e").pack()
        tk.Label(title_frame, text="Raspberry Pi Audio Bridge",
                 font=("Courier New", 9), fg="#4a4a8a", bg="#1a1a2e").pack()

        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=20, pady=10)

        main = tk.Frame(self.root, bg="#1a1a2e")
        main.pack(padx=20, pady=5, fill="both")

        # Network settings
        self.section_label(main, "NETWORK")
        net_frame = self.card_frame(main)
        self.pi_ip = self.labeled_entry(net_frame, "Pi IP Address:", self.config["pi_ip"], 0)
        self.rx_port = self.labeled_entry(net_frame, "RX Port:", self.config["rx_port"], 1)
        self.tx_port = self.labeled_entry(net_frame, "TX Port:", self.config["tx_port"], 2)
        self.network_caching = self.labeled_entry(net_frame, "VLC Caching (ms):", self.config["network_caching"], 3)

        # SSH settings
        self.section_label(main, "SSH / PI CONTROL")
        ssh_frame = self.card_frame(main)
        self.pi_user = self.labeled_entry(ssh_frame, "Pi Username:", self.config["pi_user"], 0)
        self.pi_script = self.labeled_entry(ssh_frame, "Audio Script:", self.config["pi_script"], 1)
        self.rigctld_cmd = self.labeled_entry(ssh_frame, "rigctld Command:", self.config["rigctld_cmd"], 2)

        # SSH controls
        ssh_ctrl_frame = tk.Frame(ssh_frame, bg="#16213e")
        ssh_ctrl_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=6)

        # rigctld row
        rig_row = tk.Frame(ssh_ctrl_frame, bg="#16213e")
        rig_row.pack(fill="x", pady=2)
        tk.Label(rig_row, text="rigctld:", font=("Courier New", 9, "bold"),
                 fg="#8888cc", bg="#16213e", width=12, anchor="w").pack(side="left")
        self.rigctld_status = tk.Label(rig_row, text="● STOPPED",
                                        font=("Courier New", 9), fg="#ff4444", bg="#16213e")
        self.rigctld_status.pack(side="left", padx=10)
        tk.Button(rig_row, text="STOP", font=("Courier New", 8, "bold"),
                  bg="#3a0000", fg="#ff4444", relief="flat", padx=8,
                  command=self.stop_rigctld, cursor="hand2").pack(side="right", padx=3)
        tk.Button(rig_row, text="START", font=("Courier New", 8, "bold"),
                  bg="#003a1a", fg="#00ff88", relief="flat", padx=8,
                  command=self.start_rigctld, cursor="hand2").pack(side="right", padx=3)

        # audio script row
        script_row = tk.Frame(ssh_ctrl_frame, bg="#16213e")
        script_row.pack(fill="x", pady=2)
        tk.Label(script_row, text="Audio Script:", font=("Courier New", 9, "bold"),
                 fg="#8888cc", bg="#16213e", width=12, anchor="w").pack(side="left")
        self.ssh_audio_status = tk.Label(script_row, text="● STOPPED",
                                          font=("Courier New", 9), fg="#ff4444", bg="#16213e")
        self.ssh_audio_status.pack(side="left", padx=10)
        tk.Button(script_row, text="STOP", font=("Courier New", 8, "bold"),
                  bg="#3a0000", fg="#ff4444", relief="flat", padx=8,
                  command=self.stop_ssh_audio, cursor="hand2").pack(side="right", padx=3)
        tk.Button(script_row, text="START", font=("Courier New", 8, "bold"),
                  bg="#003a1a", fg="#00ff88", relief="flat", padx=8,
                  command=self.start_ssh_audio, cursor="hand2").pack(side="right", padx=3)

        # Paths
        self.section_label(main, "PATHS")
        path_frame = self.card_frame(main)
        self.vlc_path = self.labeled_entry_browse(path_frame, "VLC Path:", self.config["vlc_path"], 0)
        self.ffmpeg_path = self.labeled_entry_browse(path_frame, "FFmpeg Path:", self.config["ffmpeg_path"], 1)

        # Audio devices
        self.section_label(main, "AUDIO DEVICES")
        audio_frame = self.card_frame(main)
        self.rx_cable = self.labeled_entry(audio_frame, "RX Output Device:", self.config["rx_cable"], 0)
        self.tx_cable = self.labeled_entry(audio_frame, "TX Input Device:", self.config["tx_cable"], 1)

        # TX Gain slider
        tk.Label(audio_frame, text="TX Gain:", font=("Courier New", 9),
                 fg="#8888cc", bg="#16213e", width=22, anchor="w").grid(row=2, column=0, sticky="w", pady=2)
        gain_frame = tk.Frame(audio_frame, bg="#16213e")
        gain_frame.grid(row=2, column=1, sticky="ew", padx=5)
        self.tx_gain = tk.DoubleVar(value=float(self.config.get("tx_gain", 1.0)))
        self.tx_gain_label = tk.Label(gain_frame, text=f"{self.tx_gain.get():.1f}x",
                                       font=("Courier New", 9), fg="#ff6b35", bg="#16213e", width=5)
        self.tx_gain_label.pack(side="right")
        tk.Scale(gain_frame, variable=self.tx_gain, from_=0.5, to=5.0, resolution=0.1,
                 orient="horizontal", bg="#16213e", fg="#ff6b35", troughcolor="#0d0d1a",
                 highlightthickness=0, relief="flat", length=200,
                 command=self.update_gain_label).pack(side="left")

        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=20, pady=10)

        # RX/TX controls
        ctrl_frame = tk.Frame(self.root, bg="#1a1a2e")
        ctrl_frame.pack(padx=20, pady=5, fill="x")

        # RX controls
        rx_frame = tk.Frame(ctrl_frame, bg="#16213e", relief="flat", bd=0)
        rx_frame.pack(fill="x", pady=4)
        rx_frame.configure(highlightbackground="#00d4ff", highlightthickness=1)
        tk.Label(rx_frame, text="RX  (Pi → PC)", font=("Courier New", 10, "bold"),
                 fg="#00d4ff", bg="#16213e", width=18, anchor="w").pack(side="left", padx=10, pady=8)
        self.rx_status = tk.Label(rx_frame, text="● STOPPED", font=("Courier New", 9),
                                   fg="#ff4444", bg="#16213e")
        self.rx_status.pack(side="left", padx=10)
        self.rx_stop_btn = tk.Button(rx_frame, text="STOP", font=("Courier New", 9, "bold"),
                                      bg="#3a0000", fg="#ff4444", relief="flat", padx=12,
                                      command=self.stop_rx, state="disabled", cursor="hand2")
        self.rx_stop_btn.pack(side="right", padx=5, pady=5)
        self.rx_start_btn = tk.Button(rx_frame, text="START", font=("Courier New", 9, "bold"),
                                       bg="#003a1a", fg="#00ff88", relief="flat", padx=12,
                                       command=self.start_rx, cursor="hand2")
        self.rx_start_btn.pack(side="right", padx=5, pady=5)

        # TX controls
        tx_frame = tk.Frame(ctrl_frame, bg="#16213e", relief="flat", bd=0)
        tx_frame.pack(fill="x", pady=4)
        tx_frame.configure(highlightbackground="#ff6b35", highlightthickness=1)
        tk.Label(tx_frame, text="TX  (PC → Pi)", font=("Courier New", 10, "bold"),
                 fg="#ff6b35", bg="#16213e", width=18, anchor="w").pack(side="left", padx=10, pady=8)
        self.tx_status = tk.Label(tx_frame, text="● STOPPED", font=("Courier New", 9),
                                   fg="#ff4444", bg="#16213e")
        self.tx_status.pack(side="left", padx=10)
        self.tx_stop_btn = tk.Button(tx_frame, text="STOP", font=("Courier New", 9, "bold"),
                                      bg="#3a0000", fg="#ff4444", relief="flat", padx=12,
                                      command=self.stop_tx, state="disabled", cursor="hand2")
        self.tx_stop_btn.pack(side="right", padx=5, pady=5)
        self.tx_start_btn = tk.Button(tx_frame, text="START", font=("Courier New", 9, "bold"),
                                       bg="#003a1a", fg="#00ff88", relief="flat", padx=12,
                                       command=self.start_tx, cursor="hand2")
        self.tx_start_btn.pack(side="right", padx=5, pady=5)

        # Bottom buttons
        btn_frame = tk.Frame(self.root, bg="#1a1a2e")
        btn_frame.pack(padx=20, pady=(10, 10), fill="x")
        tk.Button(btn_frame, text="START ALL", font=("Courier New", 10, "bold"),
                  bg="#00d4ff", fg="#1a1a2e", relief="flat", padx=20, pady=6,
                  command=self.start_all, cursor="hand2").pack(side="left", padx=5)
        tk.Button(btn_frame, text="STOP ALL", font=("Courier New", 10, "bold"),
                  bg="#ff4444", fg="#ffffff", relief="flat", padx=20, pady=6,
                  command=self.stop_all, cursor="hand2").pack(side="left", padx=5)
        tk.Button(btn_frame, text="SAVE SETTINGS", font=("Courier New", 10, "bold"),
                  bg="#4a4a8a", fg="#ffffff", relief="flat", padx=20, pady=6,
                  command=self.save_and_confirm, cursor="hand2").pack(side="right", padx=5)

        # Log
        self.section_label(self.root, "LOG")
        log_frame = tk.Frame(self.root, bg="#1a1a2e")
        log_frame.pack(padx=20, pady=(0, 20), fill="x")
        self.log = tk.Text(log_frame, height=6, bg="#0d0d1a", fg="#00d4ff",
                           font=("Courier New", 8), relief="flat", state="disabled",
                           insertbackground="#00d4ff")
        self.log.pack(fill="x")
        scrollbar = tk.Scrollbar(log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)

    def section_label(self, parent, text):
        tk.Label(parent, text=text, font=("Courier New", 8, "bold"),
                 fg="#4a4a8a", bg="#1a1a2e").pack(anchor="w", pady=(8, 2))

    def card_frame(self, parent):
        frame = tk.Frame(parent, bg="#16213e", padx=10, pady=8)
        frame.pack(fill="x", pady=2)
        frame.configure(highlightbackground="#2a2a5a", highlightthickness=1)
        return frame

    def labeled_entry(self, parent, label, default, row):
        tk.Label(parent, text=label, font=("Courier New", 9),
                 fg="#8888cc", bg="#16213e", width=22, anchor="w").grid(
            row=row, column=0, sticky="w", pady=2)
        var = tk.StringVar(value=default)
        tk.Entry(parent, textvariable=var, font=("Courier New", 9),
                 bg="#0d0d1a", fg="#ffffff", insertbackground="#00d4ff",
                 relief="flat", width=35).grid(row=row, column=1, sticky="ew", padx=5)
        return var

    def labeled_entry_browse(self, parent, label, default, row):
        tk.Label(parent, text=label, font=("Courier New", 9),
                 fg="#8888cc", bg="#16213e", width=22, anchor="w").grid(
            row=row, column=0, sticky="w", pady=2)
        var = tk.StringVar(value=default)
        tk.Entry(parent, textvariable=var, font=("Courier New", 9),
                 bg="#0d0d1a", fg="#ffffff", insertbackground="#00d4ff",
                 relief="flat", width=30).grid(row=row, column=1, sticky="ew", padx=5)
        tk.Button(parent, text="...", font=("Courier New", 8),
                  bg="#2a2a5a", fg="#ffffff", relief="flat", padx=6,
                  command=lambda v=var: self.browse_file(v),
                  cursor="hand2").grid(row=row, column=2, padx=2)
        return var

    def browse_file(self, var):
        path = filedialog.askopenfilename(filetypes=[("Executables", "*.exe"), ("All files", "*.*")])
        if path:
            var.set(path.replace("/", "\\"))

    def log_message(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", f"{msg}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def ssh_cmd(self, remote_cmd):
        user = self.pi_user.get()
        ip = self.pi_ip.get()
        return ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes",
                f"{user}@{ip}", remote_cmd]

    def start_rigctld(self):
        if self.ssh_rigctld_process and self.ssh_rigctld_process.poll() is None:
            self.log_message("rigctld already running")
            return
        cmd = self.ssh_cmd(f"sudo {self.rigctld_cmd.get()}")
        try:
            self.ssh_rigctld_process = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.log_message("rigctld started on Pi")
        except Exception as e:
            self.log_message(f"rigctld SSH failed: {e}")
            self.log_message("Tip: Set up SSH keys with ssh-copy-id")

    def stop_rigctld(self):
        if self.ssh_rigctld_process:
            self.ssh_rigctld_process.terminate()
            self.ssh_rigctld_process = None
        subprocess.Popen(self.ssh_cmd("sudo killall -9 rigctld 2>/dev/null"),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.log_message("rigctld stopped")

    def start_ssh_audio(self):
        if self.ssh_audio_process and self.ssh_audio_process.poll() is None:
            self.log_message("Audio script already running")
            return
        script = self.pi_script.get()
        cmd = self.ssh_cmd(f"sudo {script}")
        try:
            self.ssh_audio_process = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.log_message(f"Audio script started: {script}")
        except Exception as e:
            self.log_message(f"Audio script SSH failed: {e}")
            self.log_message("Tip: Set up SSH keys with ssh-copy-id")

    def stop_ssh_audio(self):
        if self.ssh_audio_process:
            self.ssh_audio_process.terminate()
            self.ssh_audio_process = None
        subprocess.Popen(
            self.ssh_cmd("sudo killall -9 virtual_oss sox nc play rec 2>/dev/null"),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.log_message("Audio script stopped on Pi")

    def start_rx(self):
        if self.rx_process and self.rx_process.poll() is None:
            self.log_message("RX already running")
            return
        vlc = self.vlc_path.get()
        ip = self.pi_ip.get()
        port = self.rx_port.get()
        caching = self.network_caching.get()
        if not os.path.exists(vlc):
            messagebox.showerror("Error", f"VLC not found at:\n{vlc}")
            return
        cmd = [vlc, "-I", "dummy", f"--network-caching={caching}", f"tcp://{ip}:{port}"]
        try:
            self.rx_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.log_message(f"RX started → tcp://{ip}:{port}")
        except Exception as e:
            self.log_message(f"RX failed: {e}")

    def stop_rx(self):
        if self.rx_process:
            self.rx_process.terminate()
            self.rx_process = None
            self.log_message("RX stopped")

    def start_tx(self):
        if self.tx_process and self.tx_process.poll() is None:
            self.log_message("TX already running")
            return
        ffmpeg = self.ffmpeg_path.get()
        ip = self.pi_ip.get()
        port = self.tx_port.get()
        cable = self.tx_cable.get()
        if not os.path.exists(ffmpeg):
            messagebox.showerror("Error", f"FFmpeg not found at:\n{ffmpeg}")
            return
        gain = self.tx_gain.get()
        cmd = [ffmpeg, "-f", "dshow", "-thread_queue_size", "512",
               "-i", f"audio={cable}",
               "-af", f"volume={gain:.1f}",
               "-ar", "48000", "-ac", "1", "-f", "s16le",
               f"tcp://{ip}:{port}"]
        try:
            self.tx_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.log_message(f"TX started → tcp://{ip}:{port}")
        except Exception as e:
            self.log_message(f"TX failed: {e}")

    def stop_tx(self):
        if self.tx_process:
            self.tx_process.terminate()
            self.tx_process = None
            self.log_message("TX stopped")

    def start_all(self):
        self.log_message("Starting all services...")
        self.start_rigctld()
        self.root.after(1000, self.start_ssh_audio)
        self.root.after(3000, self.start_rx)
        self.root.after(3000, self.start_tx)

    def stop_all(self):
        self.stop_rx()
        self.stop_tx()
        self.stop_ssh_audio()
        self.stop_rigctld()

    def save_and_confirm(self):
        self.save_config()
        self.log_message("Settings saved")

    def monitor_processes(self):
        # RX
        if self.rx_process and self.rx_process.poll() is None:
            self.rx_status.config(text="● RUNNING", fg="#00ff88")
            self.rx_start_btn.config(state="disabled")
            self.rx_stop_btn.config(state="normal")
        else:
            self.rx_status.config(text="● STOPPED", fg="#ff4444")
            self.rx_start_btn.config(state="normal")
            self.rx_stop_btn.config(state="disabled")
            if self.rx_process and self.rx_process.poll() is not None:
                self.log_message("RX process ended unexpectedly")
                self.rx_process = None

        # TX
        if self.tx_process and self.tx_process.poll() is None:
            self.tx_status.config(text="● RUNNING", fg="#00ff88")
            self.tx_start_btn.config(state="disabled")
            self.tx_stop_btn.config(state="normal")
        else:
            self.tx_status.config(text="● STOPPED", fg="#ff4444")
            self.tx_start_btn.config(state="normal")
            self.tx_stop_btn.config(state="disabled")
            if self.tx_process and self.tx_process.poll() is not None:
                self.log_message("TX process ended unexpectedly")
                self.tx_process = None

        # rigctld
        if self.ssh_rigctld_process and self.ssh_rigctld_process.poll() is None:
            self.rigctld_status.config(text="● RUNNING", fg="#00ff88")
        else:
            self.rigctld_status.config(text="● STOPPED", fg="#ff4444")
            if self.ssh_rigctld_process and self.ssh_rigctld_process.poll() is not None:
                self.ssh_rigctld_process = None

        # Audio script
        if self.ssh_audio_process and self.ssh_audio_process.poll() is None:
            self.ssh_audio_status.config(text="● RUNNING", fg="#00ff88")
        else:
            self.ssh_audio_status.config(text="● STOPPED", fg="#ff4444")
            if self.ssh_audio_process and self.ssh_audio_process.poll() is not None:
                self.ssh_audio_process = None

        self.root.after(1000, self.monitor_processes)

    def on_close(self):
        self.stop_all()
        self.save_config()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = RadioControl(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
