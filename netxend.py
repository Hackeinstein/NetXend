import customtkinter as ctk
import socket
import threading
import os
import platform
from pathlib import Path
import time
from PIL import Image, ImageTk
import json
from tkinter import filedialog, messagebox
import tkinter as tk

# Theme and appearance settings
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Constants
PORT = 65432
DISCOVERY_PORT = 65433
BUFFER_SIZE = 4096
DISCOVERY_MSG = "NETXEND_DISCOVERY"
DISCOVERY_RESPONSE = "NETXEND_HERE"

# Cross-platform setup
def get_downloads_path():
    system = platform.system()
    if system == "Windows":
        return Path(os.environ['USERPROFILE']) / 'Downloads'
    return Path.home() / 'Downloads'

SAVE_FOLDER = get_downloads_path() / "netxend"
if not SAVE_FOLDER.exists():
    SAVE_FOLDER.mkdir(parents=True)

# Network state
peers = {}
selected_peer = None
transfer_queue = []

class DropZoneFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.setup_ui()

    def setup_ui(self):
        self.label = ctk.CTkLabel(
            self,
            text="Click to Select Files",
            font=("Helvetica", 18)
        )
        self.label.place(relx=0.5, rely=0.5, anchor="center")
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)

    def on_enter(self, event):
        self.configure(fg_color=("gray75", "gray35"))
        self.label.configure(text="Select Files...")

    def on_leave(self, event):
        self.configure(fg_color=("gray85", "gray25"))
        self.label.configure(text="Click to Select Files")

class NetXendApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("NetXend")
        self.geometry("1000x600")
        self.minsize(800, 500)
        
        self.hostname = socket.gethostname()
        self.discovery_socket = None
        self.discover_thread = None
        self.discovery_running = False
        
        self.load_icon()
        self.setup_ui()
        self.start_network_services()

    def load_icon(self):
        try:
            icon_path = "netxend.png"
            if os.path.exists(icon_path):
                icon_image = Image.open(icon_path)
                photo = ImageTk.PhotoImage(icon_image)
                self.wm_iconphoto(True, photo)
        except Exception as e:
            print(f"Could not load icon: {e}")

    def setup_ui(self):
        # Main container
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left panel (Peers)
        self.left_panel = ctk.CTkFrame(self, corner_radius=0)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        # Peers list label
        self.peers_label = ctk.CTkLabel(
            self.left_panel, 
            text="Online Users",
            font=("Helvetica", 16, "bold")
        )
        self.peers_label.pack(pady=10)
        
        # Peers listbox with selection
        self.peers_list = ctk.CTkTextbox(self.left_panel, width=200)
        self.peers_list.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.peers_list.bind("<Button-1>", self.select_peer)
        
        # Right panel
        self.right_panel = ctk.CTkFrame(self)
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.right_panel.grid_rowconfigure(0, weight=1)
        self.right_panel.grid_columnconfigure(0, weight=1)

        # Drop zone
        self.drop_zone = DropZoneFrame(
            self.right_panel,
            corner_radius=10,
            border_width=2,
            fg_color=("gray85", "gray25")
        )
        self.drop_zone.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.drop_zone.bind("<Button-1>", self.select_files)
        
        # Bottom controls
        self.controls_frame = ctk.CTkFrame(self.right_panel)
        self.controls_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 20))
        
        # File status label
        self.status_label = ctk.CTkLabel(
            self.controls_frame,
            text="Ready",
            font=("Helvetica", 12)
        )
        self.status_label.grid(row=0, column=0, sticky="w", padx=10, pady=5)
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(self.controls_frame)
        self.progress_bar.grid(row=1, column=0, sticky="ew", padx=(10, 10), pady=5)
        self.progress_bar.set(0)
        
        # Scan button
        self.scan_button = ctk.CTkButton(
            self.controls_frame,
            text="Scan Network",
            width=120,
            command=self.scan_network
        )
        self.scan_button.grid(row=1, column=1, padx=10, pady=5)

    def start_discovery_service(self):
        """Start the discovery service to listen for peer broadcasts"""
        try:
            self.discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.discovery_socket.bind(('', DISCOVERY_PORT))
            
            self.discovery_running = True
            
            def discovery_listener():
                while self.discovery_running:
                    try:
                        data, addr = self.discovery_socket.recvfrom(1024)
                        msg = data.decode()
                        
                        if msg == DISCOVERY_MSG:
                            # Send response with hostname
                            response = json.dumps({
                                "type": DISCOVERY_RESPONSE,
                                "hostname": self.hostname
                            })
                            self.discovery_socket.sendto(response.encode(), addr)
                        
                        elif msg.startswith("{"):
                            try:
                                data = json.loads(msg)
                                if data.get("type") == DISCOVERY_RESPONSE:
                                    peers[addr[0]] = data.get("hostname", "Unknown")
                                    self.after(100, self.update_peers_list)
                            except json.JSONDecodeError:
                                pass
                                
                    except Exception as e:
                        print(f"Discovery error: {e}")
                        time.sleep(1)
            
            self.discover_thread = threading.Thread(target=discovery_listener, daemon=True)
            self.discover_thread.start()
            
        except Exception as e:
            print(f"Could not start discovery service: {e}")

    def select_peer(self, event):
        global selected_peer
        try:
            index = self.peers_list.index(f"@{event.x},{event.y}")
            line = self.peers_list.get(f"{index} linestart", f"{index} lineend")
            ip_start = line.find("(") + 1
            ip_end = line.find(")")
            if ip_start > 0 and ip_end > ip_start:
                selected_peer = line[ip_start:ip_end]
                self.status_label.configure(text=f"Selected: {selected_peer}")
        except Exception as e:
            print(f"Peer selection error: {e}")

    def select_files(self, event=None):
        files = filedialog.askopenfilenames()
        if files:
            self.handle_files(files)

    def handle_files(self, files):
        if not selected_peer:
            messagebox.showwarning("No Peer Selected", "Please select a peer first!")
            return
            
        for file_path in files:
            transfer_queue.append((file_path, selected_peer))
            threading.Thread(
                target=self.send_file,
                args=(file_path, selected_peer),
                daemon=True
            ).start()

    def update_progress(self, value, status_text=""):
        self.progress_bar.set(value / 100)
        if status_text:
            self.status_label.configure(text=status_text)
        
    def scan_network(self):
        """Broadcast discovery message to find peers"""
        self.status_label.configure(text="Scanning network...")
        peers.clear()
        self.update_peers_list()
        
        try:
            # Send broadcast message
            msg = DISCOVERY_MSG.encode()
            self.discovery_socket.sendto(msg, ('<broadcast>', DISCOVERY_PORT))
            self.after(2000, lambda: self.status_label.configure(text="Ready"))
        except Exception as e:
            self.status_label.configure(text=f"Scan error: {str(e)}")
            print(f"Scan error: {e}")
            
    def update_peers_list(self):
        self.peers_list.delete("1.0", "end")
        for ip, name in peers.items():
            self.peers_list.insert("end", f"{name} ({ip})\n")

    def receive_file(self, conn):
        try:
            file_info = conn.recv(1024).decode()
            file_info = json.loads(file_info)
            file_name = file_info['name']
            total_size = file_info['size']
            
            save_path = SAVE_FOLDER / file_name
            received = 0
            
            with open(save_path, 'wb') as f:
                while received < total_size:
                    data = conn.recv(BUFFER_SIZE)
                    if not data:
                        break
                    f.write(data)
                    received += len(data)
                    progress = received / total_size * 100
                    self.after(10, lambda: self.update_progress(
                        progress,
                        f"Receiving: {file_name} ({progress:.1f}%)"
                    ))

            conn.sendall(b'ACK')
            self.status_label.configure(text=f"Received: {file_name}")
            
        except Exception as e:
            self.status_label.configure(text=f"Error receiving file: {str(e)}")
            print(f"Receive error: {e}")
        finally:
            conn.close()

    def send_file(self, file_path, ip):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((ip, PORT))
                file_name = os.path.basename(file_path)
                file_size = os.path.getsize(file_path)
                
                file_info = {
                    'name': file_name,
                    'size': file_size
                }
                sock.sendall(json.dumps(file_info).encode())
                time.sleep(0.1)

                sent = 0
                with open(file_path, 'rb') as f:
                    while sent < file_size:
                        data = f.read(BUFFER_SIZE)
                        sock.sendall(data)
                        sent += len(data)
                        progress = sent / file_size * 100
                        self.after(10, lambda: self.update_progress(
                            progress,
                            f"Sending: {file_name} ({progress:.1f}%)"
                        ))

                if sock.recv(3) == b'ACK':
                    self.status_label.configure(text=f"Sent: {file_name}")
                    
        except Exception as e:
            self.status_label.configure(text=f"Error sending file: {str(e)}")
            print(f"Send error: {e}")

    def start_network_services(self):
        def receiver():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(('0.0.0.0', PORT))
                sock.listen()
                while True:
                    conn, addr = sock.accept()
                    threading.Thread(
                        target=self.receive_file,
                        args=(conn,),
                        daemon=True
                    ).start()

        # Start file receiver
        threading.Thread(target=receiver, daemon=True).start()
        
        # Start discovery service
        self.start_discovery_service()
        
        # Initial network scan
        self.after(1000, self.scan_network)

if __name__ == "__main__":
    app = NetXendApp()
    app.mainloop()