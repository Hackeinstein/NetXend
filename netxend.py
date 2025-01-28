import shutil
import subprocess
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
import hashlib

# Theme and appearance settings
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Constants
PORT = 65432
DISCOVERY_PORT = 65433
BUFFER_SIZE = 4096
DISCOVERY_MSG = "NETXEND_DISCOVERY"
DISCOVERY_RESPONSE = "NETXEND_HERE"
CONFIG_FILE = "netxend_config.json"
BROADCAST_ADDR = '255.255.255.255'

PEER_TIMEOUT = 30  # Seconds before a peer is considered offline
AUTO_SCAN_INTERVAL = 10000  # Milliseconds between automatic scans

# Default user settings
DEFAULT_CONFIG = {
    "display_name": "",
    "avatar_color": "#3498db"  # Default avatar color
}

def load_config():
    """Load user configuration from file"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(config):
    """Save user configuration to file"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

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

class UserFrame(ctk.CTkFrame):
    def __init__(self, master, username, is_self=False, avatar_color=None, **kwargs):
        super().__init__(master, **kwargs)
        self.username = username
        self.is_self = is_self
        self.avatar_color = avatar_color or "#3498db"
        self.setup_ui()

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
       
        # Avatar frame
        self.avatar_size = 40
        self.avatar_frame = ctk.CTkFrame(
            self,
            width=self.avatar_size,
            height=self.avatar_size,
            corner_radius=20,
            fg_color=self.avatar_color
        )
        self.avatar_frame.grid(row=0, column=0, padx=(10, 10), pady=10)
        self.avatar_frame.grid_propagate(False)
        
        # Avatar initial
        initial = self.username[0].upper() if self.username else "?"
        avatar_label = ctk.CTkLabel(
            self.avatar_frame,
            text=initial,
            font=("Helvetica", 16, "bold"),
            text_color="white"
        )
        avatar_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # Username frame with edit option for self
        self.name_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.name_frame.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        self.name_frame.grid_columnconfigure(0, weight=1)
        
        # Username label
        self.name_label = ctk.CTkLabel(
            self.name_frame,
            text=self.username,
            font=("Helvetica", 14),
            anchor="w"
        )
        self.name_label.grid(row=0, column=0, sticky="w", pady=2)
        
        if self.is_self:
            # Status label (online)
            self.status_label = ctk.CTkLabel(
                self.name_frame,
                text="You",
                font=("Helvetica", 12),
                text_color="gray70",
                anchor="w"
            )
            self.status_label.grid(row=1, column=0, sticky="w")
            
            # Edit button
            self.edit_btn = ctk.CTkButton(
                self.name_frame,
                text="Edit",
                width=50,
                height=24,
                font=("Helvetica", 12),
                command=self.edit_name
            )
            self.edit_btn.grid(row=0, column=1, padx=5)
        
        # Highlight self user
        if self.is_self:
            self.configure(fg_color=("gray85", "gray25"))

    def edit_name(self):
        dialog = EditNameDialog(self)
        self.wait_window(dialog)
        if dialog.result:
            self.username = dialog.result
            self.name_label.configure(text=self.username)
            # Update configuration
            config = load_config()
            config['display_name'] = self.username
            save_config(config)
            # Update avatar initial
            self.avatar_frame.winfo_children()[0].configure(text=self.username[0].upper())
            # Trigger peer list update
            self.master.master.master.update_discovery_info()

class EditNameDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Edit Display Name")
        self.geometry("300x150")
        self.result = None
        
        # Make dialog modal
        self.transient(parent)
        self.grab_set()
        
        # Center dialog
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'+{x}+{y}')
        
        self.setup_ui()

    def setup_ui(self):
        # Name entry
        self.name_entry = ctk.CTkEntry(
            self,
            placeholder_text="Enter display name"
        )
        self.name_entry.pack(padx=20, pady=(20, 10), fill="x")
        
        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            width=80,
            command=self.cancel
        ).pack(side="right", padx=5)
        
        ctk.CTkButton(
            btn_frame,
            text="Save",
            width=80,
            command=self.save
        ).pack(side="right", padx=5)

    def save(self):
        name = self.name_entry.get().strip()
        if name:
            self.result = name
            self.destroy()

    def cancel(self):
        self.destroy()

class NetXendApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Window setup
        self.peers_list = None
        self.title("NetXend")
        self.geometry("1000x600")
        self.minsize(800, 500)
        
        # Load icon
        self.load_icon()
        self.setup_ui()
        self.start_network_services()
         # Add peer timestamps dictionary
        self.peer_timestamps = {}
        
        # Start automatic scanning
        self.start_auto_scan()

    def load_icon(self):
        try:
            icon_path = "netxend.png"
            if os.path.exists(icon_path):
                # For Windows and Linux
                icon_image = Image.open(icon_path)
                # Convert to PhotoImage for Tkinter
                photo = ImageTk.PhotoImage(icon_image)
                self.wm_iconphoto(True, photo)
        except Exception as e:
            print(f"Could not load icon: {e}")

    def setup_ui(self):
        self.grid_rowconfigure(1, weight=1)  # Main content row
        self.grid_rowconfigure(0, weight=0)  # Top bar row
        self.grid_columnconfigure(1, weight=1)

        # Top bar
        self.top_bar = ctk.CTkFrame(self, height=40, corner_radius=0, fg_color=("gray80", "gray30"))
        self.top_bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=0, pady=0)
        self.top_bar.grid_propagate(False)
        self.top_bar.grid_columnconfigure(1, weight=1)
        
        # App title
        self.title_label = ctk.CTkLabel(
            self.top_bar,
            text="NetXend",
            font=("Helvetica", 16, "bold")
        )
        self.title_label.grid(row=0, column=0, padx=20, pady=8)
        
        # Update button
        self.update_button = ctk.CTkButton(
            self.top_bar,
            text="Update",
            width=80,
            height=28,
            command=self.update_codebase
        )
        self.update_button.grid(row=0, column=2, padx=20, pady=6)
        self.grid_columnconfigure(1, weight=1)
        
        # Main container
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left panel (Peers)
        self.left_panel = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray90", "gray20"))
        self.left_panel.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        
        # Panel title
        self.peers_label = ctk.CTkLabel(
            self.left_panel, 
            text="Active Users",
            font=("Helvetica", 16, "bold")
        )
        self.peers_label.pack(pady=20)
        
        # Users container
        self.users_container = ctk.CTkFrame(
            self.left_panel,
            fg_color="transparent"
        )
        self.users_container.pack(fill="both", expand=True, padx=10)
        
        # Load user config
        self.config = load_config()
        if not self.config['display_name']:
            self.config['display_name'] = socket.gethostname()
            save_config(self.config)
        
        # Create self user frame
        self.self_user = UserFrame(
            self.users_container,
            self.config['display_name'],
            is_self=True,
            avatar_color=self.config['avatar_color'],
            fg_color=("gray85", "gray25"),
            corner_radius=10
        )
        self.self_user.pack(fill="x", padx=5, pady=5)
        
        # Separator
        separator = ctk.CTkFrame(self.users_container, height=2, fg_color="gray50")
        separator.pack(fill="x", padx=15, pady=10)
        
        # Peers container
        self.peers_container = ctk.CTkFrame(
            self.users_container,
            fg_color="transparent"
        )
        self.peers_container.pack(fill="both", expand=True)

        # Add this after the peers_container setup in setup_ui method

        # Right panel
        self.right_panel = ctk.CTkFrame(self)
        self.right_panel.grid(row=1, column=1, sticky="nsew", padx=10, pady=10)
        self.right_panel.grid_rowconfigure(0, weight=1)
        self.right_panel.grid_columnconfigure(0, weight=1)

        # Drop zone
        self.drop_zone = ctk.CTkFrame(
            self.right_panel,
            corner_radius=10,
            border_width=2,
            fg_color=("gray85", "gray25")
        )
        self.drop_zone.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        
        # Drop zone label
        self.drop_label = ctk.CTkLabel(
            self.drop_zone,
            text="Click to Select Files",
            font=("Helvetica", 18)
        )
        self.drop_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # Make drop zone clickable
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

       

       

    def select_peer(self, event):
        global selected_peer
        try:
            # Get clicked line
            index = self.peers_list.index(f"@{event.x},{event.y}")
            line = self.peers_list.get(f"{index} linestart", f"{index} lineend")
            # Extract IP address from line (assuming format "name (ip)")
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
    
    # Add this method for the update button:
    def update_codebase(self):
        """Update the codebase from GitHub repository"""
        try:
            self.update_button.configure(state="disabled", text="Updating...")
            
            # Function to run shell commands
            def run_command(command):
                try:
                    result = subprocess.run(
                        command,
                        shell=True,
                        check=True,
                        capture_output=True,
                        text=True
                    )
                    return result.stdout.strip()
                except subprocess.CalledProcessError as e:
                    raise Exception(f"Command failed: {e.stderr}")

            # Check if git is installed
            try:
                run_command("git --version")
            except:
                messagebox.showerror("Error", "Git is not installed. Please install Git first.")
                return

            # Check if we're in a git repository
            if not os.path.exists(".git"):
                if messagebox.askyesno("Initialize Git", 
                    "This doesn't appear to be a Git repository. Initialize it?"):
                    run_command("git init")
                    run_command("git remote add origin https://github.com/Hackeinstein/NetXend.git")
                else:
                    return

            # Create backup of current file
            backup_name = f"netxend_backup_{int(time.time())}.py"
            shutil.copy2(__file__, backup_name)

            try:
                # Fetch latest changes
                run_command("git fetch origin main")
                
                # Check for changes
                current = run_command("git rev-parse HEAD")
                latest = run_command("git rev-parse origin/main")
                
                if current == latest:
                    messagebox.showinfo("Update", "Already up to date!")
                    return

                # Stash any local changes
                run_command("git stash")
                
                # Pull updates
                result = run_command("git pull origin main")
                
                messagebox.showinfo("Success", 
                    f"Update successful!\nBackup saved as: {backup_name}\n\nPlease restart the application.")
                
                # Exit application
                self.quit()
                
            except Exception as e:
                # Restore from backup if update failed
                shutil.copy2(backup_name, __file__)
                messagebox.showerror("Error", f"Update failed: {str(e)}\nRestored from backup.")
                
        except Exception as e:
            messagebox.showerror("Error", f"Update failed: {str(e)}")
        
        finally:
            self.update_button.configure(state="normal", text="Update")

    def start_auto_scan(self):
        """Start automatic periodic scanning"""
        self.scan_network(quiet=True)  # Initial scan quietly
        self.after(AUTO_SCAN_INTERVAL, self.start_auto_scan)  # Schedule next scan
    
    def scan_network(self, quiet=False):
        """Broadcast discovery message to find peers"""
        if not quiet:
            self.status_label.configure(text="Scanning network...")
        
        def send_broadcast():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    
                    discovery_data = {
                        "type": DISCOVERY_MSG,
                        "hostname": self.config['display_name']
                    }
                    msg = json.dumps(discovery_data).encode()
                    
                    # Send multiple times to improve reliability
                    for _ in range(2):
                        for addr in [BROADCAST_ADDR, '<broadcast>']:
                            try:
                                sock.sendto(msg, (addr, DISCOVERY_PORT))
                            except:
                                continue
                        time.sleep(0.1)  # Small delay between attempts
                    
                if not quiet:
                    self.after(100, lambda: self.status_label.configure(text="Ready"))
                    
            except Exception as e:
                if not quiet:
                    self.status_label.configure(text=f"Scan error: {str(e)}")
                print(f"Scan error: {e}")

        threading.Thread(target=send_broadcast, daemon=True).start()
            
    def update_peers_list(self):
            """Update the peers list and remove timed-out peers"""
            current_time = time.time()
            
            # Remove timed-out peers
            peers_to_remove = []
            for ip in peers.keys():
                if current_time - self.peer_timestamps.get(ip, 0) > PEER_TIMEOUT:
                    peers_to_remove.append(ip)
            
            for ip in peers_to_remove:
                peers.pop(ip, None)
                self.peer_timestamps.pop(ip, None)
            
            # Clear existing peer frames
            for widget in self.peers_container.winfo_children():
                widget.destroy()
                
            # Add peer frames
            for ip, peer_info in peers.items():
                color_hash = hashlib.md5(ip.encode()).hexdigest()[:6]
                avatar_color = f"#{color_hash}"
                
                peer_frame = UserFrame(
                    self.peers_container,
                    peer_info['hostname'],
                    avatar_color=avatar_color,
                    corner_radius=10
                )
                peer_frame.pack(fill="x", padx=5, pady=5)
                peer_frame.bind("<Button-1>", lambda e, ip=ip: self.select_peer_by_frame(ip))

    def select_peer_by_frame(self, ip):
        global selected_peer
        selected_peer = ip
        self.status_label.configure(text=f"Selected: {peers[ip]['hostname']}")
        
        # Highlight selected peer
        for frame in self.peers_container.winfo_children():
            if isinstance(frame, UserFrame):
                if frame.username == peers[ip]['hostname']:
                    frame.configure(fg_color=("gray85", "gray25"))
                else:
                    frame.configure(fg_color=("transparent", "transparent"))

    def update_discovery_info(self):
        """Update discovery response with current display name"""
        self.hostname = self.config['display_name']
            
# Replace discover_peers method with this:
    def discover_peers(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(DISCOVERY_MSG.encode(), ('<broadcast>', DISCOVERY_PORT))
            time.sleep(1)
            self.after(100, self.update_peers_list)

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
                
                # Send file metadata
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
        def discovery_listener():
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.bind(('', DISCOVERY_PORT))
                
                while True:
                    try:
                        data, addr = sock.recvfrom(1024)
                        try:
                            msg_data = json.loads(data.decode())
                            
                            if msg_data.get("type") == DISCOVERY_MSG:
                                # Don't add ourselves
                                my_ips = [ip for ip in socket.gethostbyname_ex(socket.gethostname())[2]]
                                if addr[0] not in my_ips:
                                    # Update peer info and timestamp
                                    peers[addr[0]] = {
                                        'hostname': msg_data.get("hostname", "Unknown")
                                    }
                                    self.peer_timestamps[addr[0]] = time.time()
                                    self.after(100, self.update_peers_list)
                                    
                                    # Always send response back
                                    response = json.dumps({
                                        "type": DISCOVERY_MSG,
                                        "hostname": self.config['display_name']
                                    })
                                    sock.sendto(response.encode(), addr)
                            
                        except json.JSONDecodeError:
                            pass
                            
                    except Exception as e:
                        print(f"Discovery error: {e}")
                        time.sleep(1)

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
        threading.Thread(target=discovery_listener, daemon=True).start()
        
        # Initial network scan
        self.after(1000, self.scan_network)  # Scan network after 1 second

if __name__ == "__main__":
    app = NetXendApp()
    app.mainloop()
