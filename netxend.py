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
import struct
import netifaces  # Better network interface detection for macOS
from typing import Optional, Dict, List, Tuple

# Theme and appearance settings
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# UI Color Palette
COLORS = {
    "bg_dark": "#1a1a2e",
    "bg_medium": "#16213e",
    "bg_light": "#0f3460",
    "accent": "#e94560",
    "accent_hover": "#ff6b6b",
    "success": "#00d9a5",
    "text_primary": "#ffffff",
    "text_secondary": "#a0a0a0",
    "border": "#2a2a4a",
    "card_bg": "#1e1e3f",
    "online_dot": "#00d9a5",
    "selected": "#2a2a5a",
}

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

def get_local_ips() -> List[str]:
    """Get all local IP addresses - works reliably on macOS, Windows, Linux"""
    local_ips = []
    try:
        for interface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(interface)
            if netifaces.AF_INET in addrs:
                for addr in addrs[netifaces.AF_INET]:
                    ip = addr.get('addr')
                    if ip and not ip.startswith('127.'):
                        local_ips.append(ip)
    except Exception:
        # Fallback method
        try:
            hostname = socket.gethostname()
            local_ips = socket.gethostbyname_ex(hostname)[2]
            local_ips = [ip for ip in local_ips if not ip.startswith('127.')]
        except Exception:
            pass
    return local_ips

def get_broadcast_addresses() -> List[str]:
    """Get broadcast addresses for all network interfaces"""
    broadcasts = [BROADCAST_ADDR]
    try:
        for interface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(interface)
            if netifaces.AF_INET in addrs:
                for addr in addrs[netifaces.AF_INET]:
                    broadcast = addr.get('broadcast')
                    if broadcast and broadcast not in broadcasts:
                        broadcasts.append(broadcast)
    except Exception:
        pass
    return broadcasts

def format_speed(bytes_per_sec: float) -> str:
    """Format transfer speed in human readable format"""
    if bytes_per_sec < 1024:
        return f"{bytes_per_sec:.0f} B/s"
    elif bytes_per_sec < 1024 * 1024:
        return f"{bytes_per_sec / 1024:.1f} KB/s"
    else:
        return f"{bytes_per_sec / (1024 * 1024):.1f} MB/s"

def format_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

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

class UserFrame(ctk.CTkFrame):
    def __init__(self, master, username, is_self=False, avatar_color=None, ip_address=None, **kwargs):
        # Override default colors
        kwargs.setdefault('fg_color', 'transparent')
        kwargs.setdefault('corner_radius', 12)
        super().__init__(master, **kwargs)
        self.username = username
        self.is_self = is_self
        self.ip_address = ip_address
        self.avatar_color = avatar_color or COLORS["accent"]
        self.is_selected = False
        self.setup_ui()
        
        # Hover effects
        self.bind("<Enter>", self.on_hover_enter)
        self.bind("<Leave>", self.on_hover_leave)

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        
        # Container for avatar + online indicator
        self.avatar_container = ctk.CTkFrame(self, fg_color="transparent", width=50, height=50)
        self.avatar_container.grid(row=0, column=0, padx=(12, 8), pady=12)
        self.avatar_container.grid_propagate(False)
       
        # Avatar frame with gradient-like effect
        self.avatar_size = 44
        self.avatar_frame = ctk.CTkFrame(
            self.avatar_container,
            width=self.avatar_size,
            height=self.avatar_size,
            corner_radius=22,
            fg_color=self.avatar_color,
            border_width=2,
            border_color=self._adjust_color(self.avatar_color, 1.2)
        )
        self.avatar_frame.place(relx=0.5, rely=0.5, anchor="center")
        self.avatar_frame.grid_propagate(False)
        
        # Avatar initial with better font
        initial = self.username[0].upper() if self.username else "?"
        self.avatar_label = ctk.CTkLabel(
            self.avatar_frame,
            text=initial,
            font=("SF Pro Display", 18, "bold") if platform.system() == "Darwin" else ("Segoe UI", 18, "bold"),
            text_color="white"
        )
        self.avatar_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # Online indicator dot
        self.online_dot = ctk.CTkFrame(
            self.avatar_container,
            width=14,
            height=14,
            corner_radius=7,
            fg_color=COLORS["online_dot"],
            border_width=2,
            border_color=COLORS["bg_dark"]
        )
        self.online_dot.place(relx=1.0, rely=1.0, anchor="se", x=-2, y=-2)
        
        # Username frame with edit option for self
        self.name_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.name_frame.grid(row=0, column=1, sticky="ew", padx=(0, 12))
        self.name_frame.grid_columnconfigure(0, weight=1)
        
        # Username label with better typography
        self.name_label = ctk.CTkLabel(
            self.name_frame,
            text=self.username,
            font=("SF Pro Display", 14, "bold") if platform.system() == "Darwin" else ("Segoe UI", 14, "bold"),
            text_color=COLORS["text_primary"],
            anchor="w"
        )
        self.name_label.grid(row=0, column=0, sticky="w", pady=(0, 2))
        
        # Subtitle (IP or "You")
        subtitle_text = "You" if self.is_self else (self.ip_address or "")
        self.status_label = ctk.CTkLabel(
            self.name_frame,
            text=subtitle_text,
            font=("SF Pro Display", 11) if platform.system() == "Darwin" else ("Segoe UI", 11),
            text_color=COLORS["text_secondary"],
            anchor="w"
        )
        self.status_label.grid(row=1, column=0, sticky="w")
        
        if self.is_self:
            # Edit button with icon-like appearance
            self.edit_btn = ctk.CTkButton(
                self.name_frame,
                text="✎",
                width=32,
                height=32,
                corner_radius=16,
                font=("SF Pro Display", 14) if platform.system() == "Darwin" else ("Segoe UI", 14),
                fg_color="transparent",
                hover_color=COLORS["border"],
                command=self.edit_name
            )
            self.edit_btn.grid(row=0, column=1, rowspan=2, padx=5)
            self.configure(fg_color=COLORS["selected"])
    
    def _adjust_color(self, hex_color: str, factor: float) -> str:
        """Lighten or darken a hex color"""
        try:
            hex_color = hex_color.lstrip('#')
            r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:], 16)
            r = min(255, int(r * factor))
            g = min(255, int(g * factor))
            b = min(255, int(b * factor))
            return f"#{r:02x}{g:02x}{b:02x}"
        except:
            return hex_color
    
    def on_hover_enter(self, event=None):
        if not self.is_self and not self.is_selected:
            self.configure(fg_color=COLORS["border"])
    
    def on_hover_leave(self, event=None):
        if not self.is_self and not self.is_selected:
            self.configure(fg_color="transparent")
    
    def set_selected(self, selected: bool):
        self.is_selected = selected
        if selected:
            self.configure(fg_color=COLORS["selected"])
        elif not self.is_self:
            self.configure(fg_color="transparent")

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
        self.geometry("360x180")
        self.result = None
        self.configure(fg_color=COLORS["bg_dark"])
        
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
        # Title
        title = ctk.CTkLabel(
            self,
            text="Enter your display name",
            font=("SF Pro Display", 16, "bold") if platform.system() == "Darwin" else ("Segoe UI", 16, "bold"),
            text_color=COLORS["text_primary"]
        )
        title.pack(padx=24, pady=(24, 16))
        
        # Name entry with modern styling
        self.name_entry = ctk.CTkEntry(
            self,
            placeholder_text="Your name...",
            height=44,
            corner_radius=10,
            border_width=2,
            border_color=COLORS["border"],
            fg_color=COLORS["bg_medium"],
            font=("SF Pro Display", 14) if platform.system() == "Darwin" else ("Segoe UI", 14)
        )
        self.name_entry.pack(padx=24, pady=(0, 20), fill="x")
        self.name_entry.focus()
        self.name_entry.bind("<Return>", lambda e: self.save())
        
        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=24, pady=(0, 24))
        
        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            width=100,
            height=40,
            corner_radius=10,
            fg_color="transparent",
            border_width=2,
            border_color=COLORS["border"],
            hover_color=COLORS["border"],
            command=self.cancel
        ).pack(side="right", padx=(8, 0))
        
        ctk.CTkButton(
            btn_frame,
            text="Save",
            width=100,
            height=40,
            corner_radius=10,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self.save
        ).pack(side="right")

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
        
        # Instance variables for network state (not globals)
        self.peers: Dict[str, dict] = {}
        self.selected_peer: Optional[str] = None
        self.transfer_queue: List[Tuple[str, str]] = []
        self.peer_timestamps: Dict[str, float] = {}
        self.transfer_history: List[dict] = []  # Track transfer history
        self.running = True  # For clean shutdown
        
        # Configure window
        self.configure(fg_color=COLORS["bg_dark"])
        self.title("NetXend")
        self.geometry("1100x700")
        self.minsize(900, 600)
        
        # Load icon (platform-aware)
        self.load_icon()
        self.setup_ui()
        self.setup_drag_and_drop()
        self.start_network_services()
        
        # Start automatic scanning
        self.start_auto_scan()
        
        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def load_icon(self):
        """Load application icon - platform aware"""
        try:
            icon_path = Path(__file__).parent / "netxend.png"
            if not icon_path.exists():
                icon_path = Path("netxend.png")
            
            if icon_path.exists():
                icon_image = Image.open(icon_path)
                
                if platform.system() == "Darwin":  # macOS
                    # macOS handles icons differently - use iconphoto with specific size
                    # Also set the dock icon
                    icon_resized = icon_image.resize((128, 128), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(icon_resized)
                    self.iconphoto(True, photo)
                    self._icon_photo = photo  # Keep reference to prevent garbage collection
                else:
                    # Windows and Linux
                    photo = ImageTk.PhotoImage(icon_image)
                    self.wm_iconphoto(True, photo)
                    self._icon_photo = photo
        except Exception as e:
            print(f"Could not load icon: {e}")
    
    def on_closing(self):
        """Clean shutdown handler"""
        self.running = False
        self.destroy()

    def setup_ui(self):
        # Configure main grid
        self.grid_rowconfigure(0, weight=0)  # Header
        self.grid_rowconfigure(1, weight=1)  # Main content
        self.grid_columnconfigure(0, weight=0)  # Sidebar
        self.grid_columnconfigure(1, weight=1)  # Main area

        # ========== HEADER ==========
        self.header = ctk.CTkFrame(
            self, 
            height=60, 
            corner_radius=0, 
            fg_color=COLORS["bg_medium"]
        )
        self.header.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.header.grid_propagate(False)
        self.header.grid_columnconfigure(1, weight=1)
        
        # Logo/Title with icon
        logo_frame = ctk.CTkFrame(self.header, fg_color="transparent")
        logo_frame.grid(row=0, column=0, padx=20, pady=10)
        
        # App icon placeholder (colored circle)
        icon_frame = ctk.CTkFrame(
            logo_frame,
            width=36,
            height=36,
            corner_radius=8,
            fg_color=COLORS["accent"]
        )
        icon_frame.pack(side="left", padx=(0, 12))
        icon_frame.pack_propagate(False)
        
        icon_label = ctk.CTkLabel(
            icon_frame,
            text="⚡",
            font=("SF Pro Display", 18) if platform.system() == "Darwin" else ("Segoe UI", 18),
            text_color="white"
        )
        icon_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # Title
        self.title_label = ctk.CTkLabel(
            logo_frame,
            text="NetXend",
            font=("SF Pro Display", 22, "bold") if platform.system() == "Darwin" else ("Segoe UI", 22, "bold"),
            text_color=COLORS["text_primary"]
        )
        self.title_label.pack(side="left")
        
        # Subtitle
        subtitle = ctk.CTkLabel(
            logo_frame,
            text="  Local File Sharing",
            font=("SF Pro Display", 12) if platform.system() == "Darwin" else ("Segoe UI", 12),
            text_color=COLORS["text_secondary"]
        )
        subtitle.pack(side="left", padx=(8, 0), pady=(4, 0))
        
        # Header buttons
        header_btns = ctk.CTkFrame(self.header, fg_color="transparent")
        header_btns.grid(row=0, column=2, padx=20)
        
        # Open folder button
        self.folder_button = ctk.CTkButton(
            header_btns,
            text="📁 Open Folder",
            width=120,
            height=36,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            border_color=COLORS["border"],
            hover_color=COLORS["border"],
            font=("SF Pro Display", 12) if platform.system() == "Darwin" else ("Segoe UI", 12),
            command=self.open_downloads_folder
        )
        self.folder_button.pack(side="left", padx=(0, 8))
        
        # Update button
        self.update_button = ctk.CTkButton(
            header_btns,
            text="↻ Update",
            width=100,
            height=36,
            corner_radius=8,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            font=("SF Pro Display", 12, "bold") if platform.system() == "Darwin" else ("Segoe UI", 12, "bold"),
            command=self.update_codebase
        )
        self.update_button.pack(side="left")

        # ========== SIDEBAR ==========
        self.sidebar = ctk.CTkFrame(
            self, 
            width=280, 
            corner_radius=0, 
            fg_color=COLORS["bg_medium"]
        )
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        
        # Sidebar header
        sidebar_header = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        sidebar_header.pack(fill="x", padx=16, pady=(20, 12))
        
        peers_title = ctk.CTkLabel(
            sidebar_header,
            text="Devices",
            font=("SF Pro Display", 13, "bold") if platform.system() == "Darwin" else ("Segoe UI", 13, "bold"),
            text_color=COLORS["text_secondary"]
        )
        peers_title.pack(side="left")
        
        # Scan button (icon)
        self.scan_btn = ctk.CTkButton(
            sidebar_header,
            text="⟳",
            width=32,
            height=32,
            corner_radius=16,
            fg_color="transparent",
            hover_color=COLORS["border"],
            font=("SF Pro Display", 16) if platform.system() == "Darwin" else ("Segoe UI", 16),
            command=self.scan_network
        )
        self.scan_btn.pack(side="right")
        
        # Users container with scroll
        self.users_scroll = ctk.CTkScrollableFrame(
            self.sidebar,
            fg_color="transparent",
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent"]
        )
        self.users_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        
        # Load user config
        self.config = load_config()
        if not self.config['display_name']:
            self.config['display_name'] = socket.gethostname()
            save_config(self.config)
        
        # Create self user frame
        self.self_user = UserFrame(
            self.users_scroll,
            self.config['display_name'],
            is_self=True,
            avatar_color=self.config['avatar_color'],
            corner_radius=12
        )
        self.self_user.pack(fill="x", pady=(0, 4))
        
        # Separator
        separator = ctk.CTkFrame(self.users_scroll, height=1, fg_color=COLORS["border"])
        separator.pack(fill="x", padx=8, pady=12)
        
        # Peers label
        peers_label = ctk.CTkLabel(
            self.users_scroll,
            text="NEARBY",
            font=("SF Pro Display", 11, "bold") if platform.system() == "Darwin" else ("Segoe UI", 11, "bold"),
            text_color=COLORS["text_secondary"]
        )
        peers_label.pack(anchor="w", padx=12, pady=(0, 8))
        
        # Peers container
        self.peers_container = ctk.CTkFrame(
            self.users_scroll,
            fg_color="transparent"
        )
        self.peers_container.pack(fill="both", expand=True)
        
        # No peers placeholder
        self.no_peers_label = ctk.CTkLabel(
            self.peers_container,
            text="No devices found\nMake sure NetXend is running\non other computers",
            font=("SF Pro Display", 12) if platform.system() == "Darwin" else ("Segoe UI", 12),
            text_color=COLORS["text_secondary"],
            justify="center"
        )
        self.no_peers_label.pack(pady=40)

        # ========== MAIN CONTENT ==========
        self.main_content = ctk.CTkFrame(self, fg_color=COLORS["bg_dark"], corner_radius=0)
        self.main_content.grid(row=1, column=1, sticky="nsew", padx=0, pady=0)
        self.main_content.grid_rowconfigure(0, weight=1)
        self.main_content.grid_rowconfigure(1, weight=0)
        self.main_content.grid_columnconfigure(0, weight=1)

        # ========== DROP ZONE ==========
        self.drop_zone = ctk.CTkFrame(
            self.main_content,
            corner_radius=20,
            border_width=3,
            border_color=COLORS["border"],
            fg_color=COLORS["card_bg"]
        )
        self.drop_zone.grid(row=0, column=0, sticky="nsew", padx=40, pady=40)
        
        # Drop zone content container
        drop_content = ctk.CTkFrame(self.drop_zone, fg_color="transparent")
        drop_content.place(relx=0.5, rely=0.5, anchor="center")
        
        # Upload icon
        self.upload_icon_label = ctk.CTkLabel(
            drop_content,
            text="📤",
            font=("SF Pro Display", 64) if platform.system() == "Darwin" else ("Segoe UI", 64)
        )
        self.upload_icon_label.pack(pady=(0, 16))
        
        # Main drop text
        self.drop_title = ctk.CTkLabel(
            drop_content,
            text="Drop files here to send",
            font=("SF Pro Display", 20, "bold") if platform.system() == "Darwin" else ("Segoe UI", 20, "bold"),
            text_color=COLORS["text_primary"]
        )
        self.drop_title.pack(pady=(0, 8))
        
        # Subtitle
        self.drop_subtitle = ctk.CTkLabel(
            drop_content,
            text="or click to browse files",
            font=("SF Pro Display", 14) if platform.system() == "Darwin" else ("Segoe UI", 14),
            text_color=COLORS["text_secondary"]
        )
        self.drop_subtitle.pack(pady=(0, 24))
        
        # Select files button
        self.select_btn = ctk.CTkButton(
            drop_content,
            text="Select Files",
            width=160,
            height=48,
            corner_radius=24,
            font=("SF Pro Display", 14, "bold") if platform.system() == "Darwin" else ("Segoe UI", 14, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self.select_files
        )
        self.select_btn.pack()
        
        # Make drop zone clickable
        for widget in [self.drop_zone, drop_content, self.upload_icon_label, self.drop_title, self.drop_subtitle]:
            widget.bind("<Button-1>", self.select_files)
        
        # Hover effects for drop zone
        self.drop_zone.bind("<Enter>", self.on_drop_zone_enter)
        self.drop_zone.bind("<Leave>", self.on_drop_zone_leave)
        
        # ========== STATUS BAR ==========
        self.status_bar = ctk.CTkFrame(
            self.main_content,
            height=80,
            fg_color=COLORS["bg_medium"],
            corner_radius=16
        )
        self.status_bar.grid(row=1, column=0, sticky="ew", padx=40, pady=(0, 24))
        self.status_bar.grid_propagate(False)
        self.status_bar.grid_columnconfigure(0, weight=1)
        
        # Status content
        status_content = ctk.CTkFrame(self.status_bar, fg_color="transparent")
        status_content.pack(fill="both", expand=True, padx=20, pady=12)
        status_content.grid_columnconfigure(0, weight=1)
        
        # Status row
        status_row = ctk.CTkFrame(status_content, fg_color="transparent")
        status_row.pack(fill="x", pady=(0, 8))
        
        # Status icon and text
        self.status_icon = ctk.CTkLabel(
            status_row,
            text="●",
            font=("SF Pro Display", 10) if platform.system() == "Darwin" else ("Segoe UI", 10),
            text_color=COLORS["success"]
        )
        self.status_icon.pack(side="left")
        
        self.status_label = ctk.CTkLabel(
            status_row,
            text="Ready to send files",
            font=("SF Pro Display", 13) if platform.system() == "Darwin" else ("Segoe UI", 13),
            text_color=COLORS["text_primary"]
        )
        self.status_label.pack(side="left", padx=(8, 0))
        
        # Scan button in status bar
        self.scan_button = ctk.CTkButton(
            status_row,
            text="Scan Network",
            width=120,
            height=32,
            corner_radius=8,
            font=("SF Pro Display", 12) if platform.system() == "Darwin" else ("Segoe UI", 12),
            fg_color="transparent",
            border_width=1,
            border_color=COLORS["border"],
            hover_color=COLORS["border"],
            command=self.scan_network
        )
        self.scan_button.pack(side="right")
        
        # Progress bar with custom styling
        self.progress_bar = ctk.CTkProgressBar(
            status_content,
            height=6,
            corner_radius=3,
            fg_color=COLORS["border"],
            progress_color=COLORS["accent"]
        )
        self.progress_bar.pack(fill="x")
        self.progress_bar.set(0)
    
    def open_downloads_folder(self):
        """Open the NetXend downloads folder"""
        try:
            if platform.system() == "Darwin":  # macOS
                subprocess.run(["open", str(SAVE_FOLDER)])
            elif platform.system() == "Windows":
                subprocess.run(["explorer", str(SAVE_FOLDER)])
            else:  # Linux
                subprocess.run(["xdg-open", str(SAVE_FOLDER)])
        except Exception as e:
            print(f"Could not open folder: {e}")
    
    def setup_drag_and_drop(self):
        """Setup native drag and drop support"""
        # Try to use tkinterdnd2 if available (best cross-platform drag-drop)
        try:
            from tkinterdnd2 import DND_FILES, TkinterDnD
            # If we get here, tkinterdnd2 is available
            self.drop_zone.drop_target_register(DND_FILES)
            self.drop_zone.dnd_bind('<<Drop>>', self.handle_drop)
            self.drop_zone.dnd_bind('<<DragEnter>>', lambda e: self.on_drop_zone_enter(e))
            self.drop_zone.dnd_bind('<<DragLeave>>', lambda e: self.on_drop_zone_leave(e))
            self.drop_title.configure(text="Drop files here to send")
            self.drop_subtitle.configure(text="or drag & drop anywhere in this area")
        except ImportError:
            # tkinterdnd2 not available - just use click to select
            pass
    
    def handle_drop(self, event):
        """Handle dropped files"""
        files = self.parse_drop_data(event.data)
        if files:
            self.handle_files(files)
    
    def parse_drop_data(self, data: str) -> List[str]:
        """Parse dropped file data - handles different formats"""
        files = []
        # Handle different drop data formats
        if data.startswith('{'):
            # macOS/Windows format with braces for paths with spaces
            import re
            files = re.findall(r'\{([^}]+)\}|([^\s]+)', data)
            files = [f[0] or f[1] for f in files if f[0] or f[1]]
        else:
            files = data.split()
        return [f for f in files if os.path.exists(f)]
    
    def on_drop_zone_enter(self, event=None):
        """Visual feedback when hovering over drop zone"""
        self.drop_zone.configure(
            fg_color=COLORS["bg_light"], 
            border_color=COLORS["accent"]
        )
    
    def on_drop_zone_leave(self, event=None):
        """Reset drop zone appearance"""
        self.drop_zone.configure(
            fg_color=COLORS["card_bg"], 
            border_color=COLORS["border"]
        )

    def select_files(self, event=None):
        files = filedialog.askopenfilenames()
        if files:
            self.handle_files(files)

    def handle_files(self, files):
        if not self.selected_peer:
            messagebox.showwarning("No Peer Selected", "Please select a peer first!")
            return
        
        if not self.peers.get(self.selected_peer):
            messagebox.showwarning("Peer Offline", "Selected peer is no longer available.")
            self.selected_peer = None
            return
            
        for file_path in files:
            self.transfer_queue.append((file_path, self.selected_peer))
            threading.Thread(
                target=self.send_file,
                args=(file_path, self.selected_peer),
                daemon=True
            ).start()

    def update_progress(self, value: float, status_text: str = "", status_type: str = "info"):
        """Thread-safe progress update with status icon color"""
        def _update():
            self.progress_bar.set(value / 100)
            if status_text:
                self.status_label.configure(text=status_text)
            
            # Update status icon color based on type
            if hasattr(self, 'status_icon'):
                if status_type == "success":
                    self.status_icon.configure(text_color=COLORS["success"])
                elif status_type == "error":
                    self.status_icon.configure(text_color=COLORS["accent"])
                elif status_type == "progress":
                    self.status_icon.configure(text_color="#ffd93d")  # Yellow for in-progress
                else:
                    self.status_icon.configure(text_color=COLORS["success"])
        
        if threading.current_thread() is threading.main_thread():
            _update()
        else:
            self.after(0, _update)
    
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
                        # Send to all broadcast addresses (better for macOS with multiple interfaces)
                        for addr in get_broadcast_addresses():
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
        for ip in list(self.peers.keys()):
            if current_time - self.peer_timestamps.get(ip, 0) > PEER_TIMEOUT:
                peers_to_remove.append(ip)
        
        for ip in peers_to_remove:
            self.peers.pop(ip, None)
            self.peer_timestamps.pop(ip, None)
            # Clear selection if selected peer went offline
            if self.selected_peer == ip:
                self.selected_peer = None
                self.status_label.configure(text="Peer went offline")
        
        # Clear existing peer frames (except the no_peers_label placeholder)
        for widget in self.peers_container.winfo_children():
            if widget != getattr(self, 'no_peers_label', None):
                widget.destroy()
        
        # Show/hide no peers message
        if not self.peers:
            if not hasattr(self, 'no_peers_label') or not self.no_peers_label.winfo_exists():
                self.no_peers_label = ctk.CTkLabel(
                    self.peers_container,
                    text="No devices found\nMake sure NetXend is running\non other computers",
                    font=("SF Pro Display", 12) if platform.system() == "Darwin" else ("Segoe UI", 12),
                    text_color=COLORS["text_secondary"],
                    justify="center"
                )
                self.no_peers_label.pack(pady=40)
        else:
            if hasattr(self, 'no_peers_label') and self.no_peers_label.winfo_exists():
                self.no_peers_label.destroy()
            
        # Add peer frames
        for ip, peer_info in self.peers.items():
            color_hash = hashlib.md5(ip.encode()).hexdigest()[:6]
            avatar_color = f"#{color_hash}"
            
            peer_frame = UserFrame(
                self.peers_container,
                peer_info['hostname'],
                avatar_color=avatar_color,
                ip_address=ip,
                corner_radius=12
            )
            peer_frame.pack(fill="x", pady=2)
            
            # Set selected state
            if ip == self.selected_peer:
                peer_frame.set_selected(True)
            
            # Bind click events to all children too
            def make_click_handler(frame, pip):
                def handler(e):
                    self.select_peer_by_frame(pip)
                    frame.set_selected(True)
                return handler
            
            peer_frame.bind("<Button-1>", make_click_handler(peer_frame, ip))
            for child in peer_frame.winfo_children():
                child.bind("<Button-1>", make_click_handler(peer_frame, ip))
                for grandchild in child.winfo_children():
                    grandchild.bind("<Button-1>", make_click_handler(peer_frame, ip))

    def select_peer_by_frame(self, ip: str):
        """Handle peer selection from the UI"""
        self.selected_peer = ip
        peer_info = self.peers.get(ip, {})
        hostname = peer_info.get('hostname', ip)
        self.status_label.configure(text=f"Selected: {hostname}")
        self.status_icon.configure(text_color=COLORS["accent"])
        
        # Update selection state for all peer frames
        for frame in self.peers_container.winfo_children():
            if isinstance(frame, UserFrame):
                # Find which IP this frame belongs to
                is_selected = frame.ip_address == ip if hasattr(frame, 'ip_address') else False
                frame.set_selected(is_selected)

    def update_discovery_info(self):
        """Update discovery response with current display name"""
        self.hostname = self.config['display_name']
            
    def discover_peers(self):
        """Send discovery broadcast to find peers"""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            for addr in get_broadcast_addresses():
                try:
                    sock.sendto(DISCOVERY_MSG.encode(), (addr, DISCOVERY_PORT))
                except Exception:
                    pass
            time.sleep(1)
            self.after(100, self.update_peers_list)

    def receive_file(self, conn, addr):
        """Receive a file from a peer"""
        try:
            file_info = conn.recv(1024).decode()
            file_info = json.loads(file_info)
            file_name = file_info['name']
            total_size = file_info['size']
            
            # Handle duplicate filenames
            save_path = SAVE_FOLDER / file_name
            if save_path.exists():
                base, ext = os.path.splitext(file_name)
                counter = 1
                while save_path.exists():
                    save_path = SAVE_FOLDER / f"{base}_{counter}{ext}"
                    counter += 1
            
            received = 0
            start_time = time.time()
            last_update = start_time
            
            with open(save_path, 'wb') as f:
                while received < total_size:
                    data = conn.recv(BUFFER_SIZE)
                    if not data:
                        break
                    f.write(data)
                    received += len(data)
                    
                    # Update progress (throttled to avoid UI lag)
                    current_time = time.time()
                    if current_time - last_update >= 0.1:  # Update every 100ms
                        elapsed = current_time - start_time
                        speed = received / elapsed if elapsed > 0 else 0
                        progress = received / total_size * 100
                        # Capture values for lambda
                        p, s, fn = progress, speed, file_name
                        self.after(0, lambda p=p, s=s, fn=fn: self.update_progress(
                            p, f"⬇ Receiving: {fn} ({p:.1f}%) - {format_speed(s)}", "progress"
                        ))
                        last_update = current_time

            conn.sendall(b'ACK')
            
            # Final status
            elapsed = time.time() - start_time
            avg_speed = total_size / elapsed if elapsed > 0 else 0
            self.after(0, lambda: self.update_progress(
                100, f"✓ Received: {save_path.name} ({format_size(total_size)})", "success"
            ))
            
            # Show notification on macOS
            if platform.system() == "Darwin":
                self.show_notification("File Received", f"{save_path.name}")
            
        except Exception as e:
            self.after(0, lambda: self.update_progress(0, f"✗ Error receiving: {str(e)}", "error"))
            print(f"Receive error: {e}")
        finally:
            conn.close()
    
    def show_notification(self, title: str, message: str):
        """Show system notification (macOS)"""
        try:
            if platform.system() == "Darwin":
                os.system(f'''osascript -e 'display notification "{message}" with title "{title}"' ''')
        except Exception:
            pass

    def send_file(self, file_path: str, ip: str):
        """Send a file to a peer"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(30)  # Connection timeout
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
                start_time = time.time()
                last_update = start_time
                
                with open(file_path, 'rb') as f:
                    while sent < file_size:
                        data = f.read(BUFFER_SIZE)
                        sock.sendall(data)
                        sent += len(data)
                        
                        # Update progress (throttled)
                        current_time = time.time()
                        if current_time - last_update >= 0.1:
                            elapsed = current_time - start_time
                            speed = sent / elapsed if elapsed > 0 else 0
                            progress = sent / file_size * 100
                            # Capture values for lambda to fix closure bug
                            p, s, fn = progress, speed, file_name
                            self.after(0, lambda p=p, s=s, fn=fn: self.update_progress(
                                p, f"⬆ Sending: {fn} ({p:.1f}%) - {format_speed(s)}", "progress"
                            ))
                            last_update = current_time

                sock.settimeout(10)  # Timeout for ACK
                if sock.recv(3) == b'ACK':
                    elapsed = time.time() - start_time
                    avg_speed = file_size / elapsed if elapsed > 0 else 0
                    self.after(0, lambda: self.update_progress(
                        100, f"✓ Sent: {file_name} ({format_size(file_size)})", "success"
                    ))
                    
        except socket.timeout:
            self.after(0, lambda: self.update_progress(0, f"✗ Timeout sending to {ip}", "error"))
        except ConnectionRefusedError:
            self.after(0, lambda: self.update_progress(0, f"✗ Connection refused by {ip}", "error"))
        except Exception as e:
            self.after(0, lambda: self.update_progress(0, f"✗ Error: {str(e)}", "error"))
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
                                # Don't add ourselves - use better IP detection for macOS
                                my_ips = get_local_ips()
                                if addr[0] not in my_ips:
                                    # Update peer info and timestamp
                                    self.peers[addr[0]] = {
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
                # macOS needs SO_REUSEPORT for some cases
                if platform.system() == "Darwin":
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                sock.bind(('0.0.0.0', PORT))
                sock.listen(5)  # Allow queue of 5 connections
                while self.running:
                    try:
                        sock.settimeout(1.0)  # Check running flag periodically
                        conn, addr = sock.accept()
                        threading.Thread(
                            target=self.receive_file,
                            args=(conn, addr),
                            daemon=True
                        ).start()
                    except socket.timeout:
                        continue
                    except Exception as e:
                        if self.running:
                            print(f"Receiver error: {e}")

        # Start file receiver
        threading.Thread(target=receiver, daemon=True).start()
        
        # Start discovery service
        threading.Thread(target=discovery_listener, daemon=True).start()
        
        # Initial network scan
        self.after(1000, self.scan_network)  # Scan network after 1 second

if __name__ == "__main__":
    app = NetXendApp()
    app.mainloop()
