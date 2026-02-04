import shutil
import subprocess
import customtkinter as ctk
import socket
import threading
import os
import platform
from pathlib import Path
import time
from PIL import Image, ImageTk, ImageDraw
import json
from tkinter import filedialog, messagebox
import hashlib
import struct
import netifaces  # Better network interface detection for macOS
from typing import Optional, Dict, List, Tuple
import zipfile
import tempfile

# System tray support (optional)
try:
    import pystray
    from pystray import MenuItem as TrayItem
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

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

# Light theme colors
COLORS_LIGHT = {
    "bg_dark": "#f5f5f7",
    "bg_medium": "#e8e8ed",
    "bg_light": "#d1d1d6",
    "accent": "#e94560",
    "accent_hover": "#ff6b6b",
    "success": "#00b894",
    "text_primary": "#1a1a2e",
    "text_secondary": "#666666",
    "border": "#c7c7cc",
    "card_bg": "#ffffff",
    "online_dot": "#00b894",
    "selected": "#d8d8e0",
}

# Constants
PORT = 65432
DISCOVERY_PORT = 65433
BUFFER_SIZE = 4096
DISCOVERY_MSG = "NETXEND_DISCOVERY"
DISCOVERY_RESPONSE = "NETXEND_HERE"
CONFIG_FILE = "netxend_config.json"
HISTORY_FILE = "transfer_history.json"
BROADCAST_ADDR = '255.255.255.255'

PEER_TIMEOUT = 30  # Seconds before a peer is considered offline
AUTO_SCAN_INTERVAL = 10000  # Milliseconds between automatic scans

# Default user settings
DEFAULT_CONFIG = {
    "display_name": "",
    "avatar_color": "#3498db",
    "save_location": "",  # Empty means use default ~/Downloads/netxend
    "sound_enabled": True,
    "notifications_enabled": True,
    "auto_accept_files": False,
    "minimize_to_tray": True,  # Minimize to tray on close
    "theme": "dark"  # "dark" or "light"
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

def calculate_file_checksum(file_path: str, algorithm: str = "sha256") -> str:
    """Calculate checksum of a file"""
    hash_func = hashlib.new(algorithm)
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(BUFFER_SIZE), b''):
            hash_func.update(chunk)
    return hash_func.hexdigest()

# File type icon mapping
FILE_TYPE_ICONS = {
    # Images
    '.jpg': '🖼️', '.jpeg': '🖼️', '.png': '🖼️', '.gif': '🖼️', 
    '.bmp': '🖼️', '.svg': '🖼️', '.webp': '🖼️', '.ico': '🖼️',
    # Videos
    '.mp4': '🎬', '.mov': '🎬', '.avi': '🎬', '.mkv': '🎬',
    '.wmv': '🎬', '.flv': '🎬', '.webm': '🎬',
    # Audio
    '.mp3': '🎵', '.wav': '🎵', '.flac': '🎵', '.aac': '🎵',
    '.ogg': '🎵', '.wma': '🎵', '.m4a': '🎵',
    # Documents
    '.pdf': '📄', '.doc': '📝', '.docx': '📝', '.txt': '📝',
    '.rtf': '📝', '.odt': '📝',
    # Spreadsheets
    '.xls': '📊', '.xlsx': '📊', '.csv': '📊', '.ods': '📊',
    # Presentations
    '.ppt': '📽️', '.pptx': '📽️', '.odp': '📽️',
    # Archives
    '.zip': '📦', '.rar': '📦', '.7z': '📦', '.tar': '📦',
    '.gz': '📦', '.bz2': '📦',
    # Code
    '.py': '🐍', '.js': '📜', '.html': '🌐', '.css': '🎨',
    '.json': '📋', '.xml': '📋', '.yaml': '📋', '.yml': '📋',
    '.java': '☕', '.cpp': '⚙️', '.c': '⚙️', '.h': '⚙️',
    '.swift': '🍎', '.kt': '🤖', '.rs': '🦀', '.go': '🐹',
    # Executables
    '.exe': '⚡', '.app': '📱', '.dmg': '💿', '.pkg': '📦',
    '.deb': '📦', '.rpm': '📦',
}

def get_file_icon(file_name: str, is_folder: bool = False) -> str:
    """Get emoji icon for a file based on extension"""
    if is_folder:
        return '📁'
    
    ext = os.path.splitext(file_name.lower())[1]
    return FILE_TYPE_ICONS.get(ext, '📄')

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


def load_transfer_history() -> List[dict]:
    """Load transfer history from file"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return []


def save_transfer_history(history: List[dict]):
    """Save transfer history to file"""
    # Keep only last 100 transfers
    history = history[-100:]
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)


def transfer_to_dict(transfer: 'Transfer') -> dict:
    """Convert Transfer object to dictionary for saving"""
    return {
        'id': transfer.id,
        'file_name': transfer.file_name,
        'file_size': transfer.file_size,
        'peer_name': transfer.peer_name,
        'peer_ip': transfer.peer_ip,
        'direction': transfer.direction,
        'status': transfer.status,
        'start_time': transfer.start_time,
        'end_time': transfer.end_time,
        'error_message': transfer.error_message,
        'is_folder': transfer.is_folder,
        'checksum': transfer.checksum,
        'checksum_verified': transfer.checksum_verified
    }

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


# ============================================================================
# TRANSFER QUEUE CLASSES (Phase 1)
# ============================================================================

class TransferStatus:
    """Transfer status constants"""
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Transfer:
    """Represents a single file transfer"""
    def __init__(self, file_path: str, file_name: str, file_size: int, 
                 peer_ip: str, peer_name: str, direction: str, transfer_id: str = None,
                 is_folder: bool = False):
        self.id = transfer_id or f"{time.time()}_{file_name}"
        self.file_path = file_path
        self.file_name = file_name
        self.file_size = file_size
        self.peer_ip = peer_ip
        self.peer_name = peer_name
        self.direction = direction  # "send" or "receive"
        self.status = TransferStatus.PENDING
        self.progress = 0.0
        self.speed = 0.0
        self.bytes_transferred = 0
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.error_message: Optional[str] = None
        self.cancelled = False  # Flag for cancellation
        self.is_folder = is_folder  # True if this is a zipped folder
        self.checksum: Optional[str] = None  # File checksum for verification
        self.checksum_verified: Optional[bool] = None  # None=not checked, True=match, False=mismatch


class TransferItemWidget(ctk.CTkFrame):
    """UI widget for a single transfer in the queue"""
    def __init__(self, master, transfer: Transfer, on_cancel=None, on_retry=None, **kwargs):
        kwargs.setdefault('fg_color', COLORS["card_bg"])
        kwargs.setdefault('corner_radius', 12)
        super().__init__(master, **kwargs)
        
        self.transfer = transfer
        self.on_cancel = on_cancel
        self.on_retry = on_retry
        self.setup_ui()
    
    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        
        # Left: Icon based on direction and status
        self.icon_label = ctk.CTkLabel(
            self,
            text=self._get_icon(),
            font=("SF Pro Display", 24) if platform.system() == "Darwin" else ("Segoe UI", 24),
            width=40
        )
        self.icon_label.grid(row=0, column=0, rowspan=2, padx=(12, 8), pady=12)
        
        # Middle: File info
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(12, 0))
        info_frame.grid_columnconfigure(0, weight=1)
        
        # File name
        self.name_label = ctk.CTkLabel(
            info_frame,
            text=self._truncate_name(self.transfer.file_name, 30),
            font=("SF Pro Display", 13, "bold") if platform.system() == "Darwin" else ("Segoe UI", 13, "bold"),
            text_color=COLORS["text_primary"],
            anchor="w"
        )
        self.name_label.grid(row=0, column=0, sticky="w")
        
        # Status/peer info
        self.status_label = ctk.CTkLabel(
            info_frame,
            text=self._get_status_text(),
            font=("SF Pro Display", 11) if platform.system() == "Darwin" else ("Segoe UI", 11),
            text_color=COLORS["text_secondary"],
            anchor="w"
        )
        self.status_label.grid(row=1, column=0, sticky="w")
        
        # Progress bar (only for active transfers)
        self.progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.progress_frame.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(4, 12))
        
        self.progress_bar = ctk.CTkProgressBar(
            self.progress_frame,
            height=4,
            corner_radius=2,
            fg_color=COLORS["border"],
            progress_color=self._get_progress_color()
        )
        self.progress_bar.pack(fill="x")
        self.progress_bar.set(self.transfer.progress / 100)
        
        # Right: Size and cancel/retry button
        right_frame = ctk.CTkFrame(self, fg_color="transparent")
        right_frame.grid(row=0, column=2, rowspan=2, padx=(0, 12), pady=12)
        
        # File size
        self.size_label = ctk.CTkLabel(
            right_frame,
            text=format_size(self.transfer.file_size),
            font=("SF Pro Display", 11) if platform.system() == "Darwin" else ("Segoe UI", 11),
            text_color=COLORS["text_secondary"]
        )
        self.size_label.pack()
        
        # Cancel button (only for pending/active)
        if self.transfer.status in [TransferStatus.PENDING, TransferStatus.ACTIVE]:
            self.cancel_btn = ctk.CTkButton(
                right_frame,
                text="✕",
                width=24,
                height=24,
                corner_radius=12,
                fg_color="transparent",
                hover_color=COLORS["accent"],
                font=("SF Pro Display", 12) if platform.system() == "Darwin" else ("Segoe UI", 12),
                command=self._on_cancel_click
            )
            self.cancel_btn.pack(pady=(4, 0))
        
        # Retry button (only for failed transfers that were sends)
        if self.transfer.status == TransferStatus.FAILED and self.transfer.direction == "send":
            self.retry_btn = ctk.CTkButton(
                right_frame,
                text="↻",
                width=24,
                height=24,
                corner_radius=12,
                fg_color="transparent",
                hover_color=COLORS["success"],
                font=("SF Pro Display", 14) if platform.system() == "Darwin" else ("Segoe UI", 14),
                command=self._on_retry_click
            )
            self.retry_btn.pack(pady=(4, 0))
    
    def _on_retry_click(self):
        """Handle retry button click"""
        if hasattr(self, 'on_retry') and self.on_retry:
            self.on_retry(self.transfer)
    
    def _get_icon(self) -> str:
        """Get icon based on transfer direction, status, and file type"""
        if self.transfer.status == TransferStatus.COMPLETED:
            return "✓"
        elif self.transfer.status == TransferStatus.FAILED:
            return "✗"
        elif self.transfer.status == TransferStatus.CANCELLED:
            return "⊘"
        elif self.transfer.is_folder:
            return "📁"
        else:
            # Use file type icon with direction indicator
            file_icon = get_file_icon(self.transfer.file_name)
            return file_icon
    
    def _get_status_text(self) -> str:
        """Get status text for display"""
        direction = "To" if self.transfer.direction == "send" else "From"
        
        if self.transfer.status == TransferStatus.PENDING:
            return f"{direction} {self.transfer.peer_name} • Waiting..."
        elif self.transfer.status == TransferStatus.ACTIVE:
            speed = format_speed(self.transfer.speed) if self.transfer.speed > 0 else "Starting..."
            return f"{direction} {self.transfer.peer_name} • {speed}"
        elif self.transfer.status == TransferStatus.COMPLETED:
            return f"{direction} {self.transfer.peer_name} • Complete"
        elif self.transfer.status == TransferStatus.FAILED:
            return f"Failed: {self.transfer.error_message or 'Unknown error'}"
        elif self.transfer.status == TransferStatus.CANCELLED:
            return "Cancelled"
        return ""
    
    def _get_progress_color(self) -> str:
        """Get progress bar color based on status"""
        if self.transfer.status == TransferStatus.COMPLETED:
            return COLORS["success"]
        elif self.transfer.status == TransferStatus.FAILED:
            return COLORS["accent"]
        elif self.transfer.status == TransferStatus.CANCELLED:
            return COLORS["text_secondary"]
        return COLORS["accent"]
    
    def _truncate_name(self, name: str, max_len: int) -> str:
        """Truncate filename if too long"""
        if len(name) <= max_len:
            return name
        ext = Path(name).suffix
        base = name[:-len(ext)] if ext else name
        return base[:max_len - len(ext) - 3] + "..." + ext
    
    def _on_cancel_click(self):
        """Handle cancel button click"""
        if self.on_cancel:
            self.on_cancel(self.transfer)
    
    def update_display(self):
        """Update the widget to reflect current transfer state"""
        self.icon_label.configure(text=self._get_icon())
        self.status_label.configure(text=self._get_status_text())
        self.progress_bar.configure(progress_color=self._get_progress_color())
        self.progress_bar.set(self.transfer.progress / 100)
        
        # Update icon color based on status
        if self.transfer.status == TransferStatus.COMPLETED:
            self.icon_label.configure(text_color=COLORS["success"])
        elif self.transfer.status == TransferStatus.FAILED:
            self.icon_label.configure(text_color=COLORS["accent"])
        elif self.transfer.status == TransferStatus.ACTIVE:
            self.icon_label.configure(text_color="#ffd93d")  # Yellow for active


class TransferQueuePanel(ctk.CTkFrame):
    """Panel showing all transfers"""
    def __init__(self, master, **kwargs):
        kwargs.setdefault('fg_color', 'transparent')
        super().__init__(master, **kwargs)
        
        self.transfers: Dict[str, Transfer] = {}
        self.transfer_widgets: Dict[str, TransferItemWidget] = {}
        self.on_cancel_callback = None
        
        self.setup_ui()
    
    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 12))
        
        title = ctk.CTkLabel(
            header,
            text="Transfers",
            font=("SF Pro Display", 14, "bold") if platform.system() == "Darwin" else ("Segoe UI", 14, "bold"),
            text_color=COLORS["text_primary"]
        )
        title.pack(side="left")
        
        # Transfer count badge
        self.count_label = ctk.CTkLabel(
            header,
            text="0",
            font=("SF Pro Display", 11) if platform.system() == "Darwin" else ("Segoe UI", 11),
            text_color=COLORS["text_secondary"],
            fg_color=COLORS["border"],
            corner_radius=10,
            width=24,
            height=20
        )
        self.count_label.pack(side="left", padx=(8, 0))
        
        # Clear completed button
        self.clear_btn = ctk.CTkButton(
            header,
            text="Clear",
            width=60,
            height=28,
            corner_radius=8,
            font=("SF Pro Display", 11) if platform.system() == "Darwin" else ("Segoe UI", 11),
            fg_color="transparent",
            hover_color=COLORS["border"],
            command=self.clear_completed
        )
        self.clear_btn.pack(side="right")
        
        # Scrollable transfer list
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent"]
        )
        self.scroll_frame.grid(row=1, column=0, sticky="nsew")
        
        # Empty state message
        self.empty_label = ctk.CTkLabel(
            self.scroll_frame,
            text="No transfers yet\nSelect a device and send files",
            font=("SF Pro Display", 12) if platform.system() == "Darwin" else ("Segoe UI", 12),
            text_color=COLORS["text_secondary"],
            justify="center"
        )
        self.empty_label.pack(pady=40)
    
    def add_transfer(self, transfer: Transfer) -> None:
        """Add a new transfer to the queue"""
        self.transfers[transfer.id] = transfer
        
        # Hide empty state
        if self.empty_label.winfo_exists():
            self.empty_label.pack_forget()
        
        # Create widget
        widget = TransferItemWidget(
            self.scroll_frame,
            transfer,
            on_cancel=self._handle_cancel,
            on_retry=self._handle_retry
        )
        widget.pack(fill="x", pady=(0, 8))
        self.transfer_widgets[transfer.id] = widget
        
        self._update_count()
    
    def update_transfer(self, transfer_id: str) -> None:
        """Update an existing transfer's display"""
        if transfer_id in self.transfer_widgets:
            self.transfer_widgets[transfer_id].update_display()
    
    def remove_transfer(self, transfer_id: str) -> None:
        """Remove a transfer from the queue"""
        if transfer_id in self.transfer_widgets:
            self.transfer_widgets[transfer_id].destroy()
            del self.transfer_widgets[transfer_id]
        if transfer_id in self.transfers:
            del self.transfers[transfer_id]
        
        self._update_count()
        self._check_empty()
    
    def clear_completed(self) -> None:
        """Remove all completed transfers"""
        to_remove = [
            tid for tid, t in self.transfers.items() 
            if t.status in [TransferStatus.COMPLETED, TransferStatus.FAILED, TransferStatus.CANCELLED]
        ]
        for tid in to_remove:
            self.remove_transfer(tid)
    
    def _handle_cancel(self, transfer: Transfer) -> None:
        """Handle cancel button click"""
        if self.on_cancel_callback:
            self.on_cancel_callback(transfer)
    
    def _handle_retry(self, transfer: Transfer) -> None:
        """Handle retry button click"""
        if self.on_retry_callback:
            self.on_retry_callback(transfer)
    
    def _update_count(self) -> None:
        """Update the transfer count badge"""
        active_count = len([t for t in self.transfers.values() 
                          if t.status in [TransferStatus.PENDING, TransferStatus.ACTIVE]])
        self.count_label.configure(text=str(active_count))
    
    def _check_empty(self) -> None:
        """Show empty state if no transfers"""
        if not self.transfers:
            self.empty_label.pack(pady=40)


class SettingsDialog(ctk.CTkToplevel):
    """Settings configuration dialog"""
    def __init__(self, parent, config: dict, on_save=None):
        super().__init__(parent)
        self.config = config.copy()
        self.on_save = on_save
        
        self.title("Settings")
        self.geometry("500x680")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg_dark"])
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        self.setup_ui()
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def setup_ui(self):
        # Header
        header = ctk.CTkLabel(
            self,
            text="⚙️ Settings",
            font=("SF Pro Display", 24, "bold") if platform.system() == "Darwin" else ("Segoe UI", 24, "bold"),
            text_color=COLORS["text_primary"]
        )
        header.pack(pady=(24, 20))
        
        # Settings container
        container = ctk.CTkFrame(self, fg_color=COLORS["bg_medium"], corner_radius=16)
        container.pack(fill="both", expand=True, padx=24, pady=(0, 24))
        
        # Display Name
        self._create_setting_row(container, "Display Name", "display_name", "text", 
                                 "How you appear to other devices")
        
        # Save Location
        save_frame = ctk.CTkFrame(container, fg_color="transparent")
        save_frame.pack(fill="x", padx=20, pady=(20, 0))
        
        ctk.CTkLabel(
            save_frame,
            text="Save Location",
            font=("SF Pro Display", 14, "bold") if platform.system() == "Darwin" else ("Segoe UI", 14, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            save_frame,
            text="Where received files are saved",
            font=("SF Pro Display", 11) if platform.system() == "Darwin" else ("Segoe UI", 11),
            text_color=COLORS["text_secondary"]
        ).pack(anchor="w")
        
        path_frame = ctk.CTkFrame(save_frame, fg_color="transparent")
        path_frame.pack(fill="x", pady=(8, 0))
        
        current_path = self.config.get("save_location", "") or str(SAVE_FOLDER)
        self.save_location_var = ctk.StringVar(value=current_path)
        self.save_location_entry = ctk.CTkEntry(
            path_frame,
            textvariable=self.save_location_var,
            width=300,
            height=36,
            fg_color=COLORS["card_bg"],
            border_color=COLORS["border"]
        )
        self.save_location_entry.pack(side="left", padx=(0, 8))
        
        browse_btn = ctk.CTkButton(
            path_frame,
            text="Browse",
            width=80,
            height=36,
            fg_color=COLORS["bg_light"],
            hover_color=COLORS["accent"],
            command=self.browse_save_location
        )
        browse_btn.pack(side="left")
        
        # Separator
        sep = ctk.CTkFrame(container, height=1, fg_color=COLORS["border"])
        sep.pack(fill="x", padx=20, pady=20)
        
        # Toggle settings
        self._create_toggle_row(container, "Notifications", "notifications_enabled",
                               "Show system notifications for transfers")
        
        self._create_toggle_row(container, "Sound Effects", "sound_enabled",
                               "Play sounds on transfer events")
        
        self._create_toggle_row(container, "Auto-Accept Files", "auto_accept_files",
                               "Accept incoming files without confirmation")
        
        if TRAY_AVAILABLE:
            self._create_toggle_row(container, "Minimize to Tray", "minimize_to_tray",
                                   "Minimize to menu bar on close")
        
        # Theme selector
        theme_frame = ctk.CTkFrame(container, fg_color="transparent")
        theme_frame.pack(fill="x", padx=20, pady=(16, 0))
        
        theme_text_frame = ctk.CTkFrame(theme_frame, fg_color="transparent")
        theme_text_frame.pack(side="left", fill="x", expand=True)
        
        ctk.CTkLabel(
            theme_text_frame,
            text="Theme",
            font=("SF Pro Display", 14, "bold") if platform.system() == "Darwin" else ("Segoe UI", 14, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            theme_text_frame,
            text="Choose dark or light appearance",
            font=("SF Pro Display", 11) if platform.system() == "Darwin" else ("Segoe UI", 11),
            text_color=COLORS["text_secondary"]
        ).pack(anchor="w")
        
        self.theme_var = ctk.StringVar(value=self.config.get("theme", "dark"))
        theme_menu = ctk.CTkSegmentedButton(
            theme_frame,
            values=["dark", "light"],
            variable=self.theme_var,
            fg_color=COLORS["bg_dark"],
            selected_color=COLORS["accent"],
            selected_hover_color=COLORS["accent_hover"]
        )
        theme_menu.pack(side="right", padx=(0, 8))
        
        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=(0, 24))
        
        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            width=100,
            height=40,
            fg_color=COLORS["bg_medium"],
            hover_color=COLORS["bg_light"],
            command=self.destroy
        )
        cancel_btn.pack(side="left", padx=(0, 12))
        
        save_btn = ctk.CTkButton(
            btn_frame,
            text="Save Settings",
            width=140,
            height=40,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self.save_settings
        )
        save_btn.pack(side="left")
    
    def _create_setting_row(self, parent, label: str, key: str, input_type: str, description: str):
        """Create a text input setting row"""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=20, pady=(20, 0))
        
        ctk.CTkLabel(
            frame,
            text=label,
            font=("SF Pro Display", 14, "bold") if platform.system() == "Darwin" else ("Segoe UI", 14, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            frame,
            text=description,
            font=("SF Pro Display", 11) if platform.system() == "Darwin" else ("Segoe UI", 11),
            text_color=COLORS["text_secondary"]
        ).pack(anchor="w")
        
        entry = ctk.CTkEntry(
            frame,
            width=300,
            height=36,
            fg_color=COLORS["card_bg"],
            border_color=COLORS["border"]
        )
        entry.insert(0, self.config.get(key, ""))
        entry.pack(anchor="w", pady=(8, 0))
        setattr(self, f"{key}_entry", entry)
    
    def _create_toggle_row(self, parent, label: str, key: str, description: str):
        """Create a toggle switch setting row"""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=20, pady=(16, 0))
        
        text_frame = ctk.CTkFrame(frame, fg_color="transparent")
        text_frame.pack(side="left", fill="x", expand=True)
        
        ctk.CTkLabel(
            text_frame,
            text=label,
            font=("SF Pro Display", 14, "bold") if platform.system() == "Darwin" else ("Segoe UI", 14, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            text_frame,
            text=description,
            font=("SF Pro Display", 11) if platform.system() == "Darwin" else ("Segoe UI", 11),
            text_color=COLORS["text_secondary"]
        ).pack(anchor="w")
        
        switch_var = ctk.BooleanVar(value=self.config.get(key, False))
        switch = ctk.CTkSwitch(
            frame,
            text="",
            variable=switch_var,
            onvalue=True,
            offvalue=False,
            fg_color=COLORS["border"],
            progress_color=COLORS["accent"]
        )
        switch.pack(side="right", padx=(0, 8))
        setattr(self, f"{key}_var", switch_var)
    
    def browse_save_location(self):
        """Open folder picker for save location"""
        folder = filedialog.askdirectory(
            title="Select Save Location",
            initialdir=self.save_location_var.get()
        )
        if folder:
            self.save_location_var.set(folder)
    
    def save_settings(self):
        """Save settings and close dialog"""
        self.config["display_name"] = self.display_name_entry.get()
        self.config["save_location"] = self.save_location_var.get()
        self.config["notifications_enabled"] = self.notifications_enabled_var.get()
        self.config["sound_enabled"] = self.sound_enabled_var.get()
        self.config["auto_accept_files"] = self.auto_accept_files_var.get()
        self.config["theme"] = self.theme_var.get()
        
        # Save tray setting if available
        if hasattr(self, 'minimize_to_tray_var'):
            self.config["minimize_to_tray"] = self.minimize_to_tray_var.get()
        
        if self.on_save:
            self.on_save(self.config)
        
        self.destroy()


class NetXendApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Instance variables for network state (not globals)
        self.peers: Dict[str, dict] = {}
        self.selected_peer: Optional[str] = None
        self.peer_timestamps: Dict[str, float] = {}
        self.transfer_history: List[dict] = load_transfer_history()  # Load persisted history
        self.active_transfers: Dict[str, Transfer] = {}  # Active transfer objects
        self.running = True  # For clean shutdown
        
        # Configure window
        self.configure(fg_color=COLORS["bg_dark"])
        self.title("NetXend")
        self.geometry("1200x750")
        self.minsize(1000, 650)
        
        # Load config first
        self.config = load_config()
        if not self.config['display_name']:
            self.config['display_name'] = socket.gethostname()
            save_config(self.config)
        
        # Apply saved theme at startup
        saved_theme = self.config.get("theme", "dark")
        if saved_theme == "light":
            ctk.set_appearance_mode("light")
        
        # Load icon (platform-aware)
        self.load_icon()
        self.setup_ui()
        self.setup_drag_and_drop()
        self.setup_system_tray()
        self.setup_keyboard_shortcuts()
        self.start_network_services()
        
        # Start automatic scanning
        self.start_auto_scan()
        
        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Determine modifier key (Cmd on macOS, Ctrl on Windows/Linux)
        mod = "Command" if platform.system() == "Darwin" else "Control"
        
        # Cmd/Ctrl+O: Open file dialog
        self.bind(f"<{mod}-o>", lambda e: self.select_files())
        self.bind(f"<{mod}-O>", lambda e: self.select_files())
        
        # Cmd/Ctrl+Shift+O: Open folder dialog
        self.bind(f"<{mod}-Shift-o>", lambda e: self.select_folder())
        self.bind(f"<{mod}-Shift-O>", lambda e: self.select_folder())
        
        # Cmd/Ctrl+,: Open settings
        self.bind(f"<{mod}-comma>", lambda e: self.open_settings())
        
        # Cmd/Ctrl+N: Scan network
        self.bind(f"<{mod}-n>", lambda e: self.scan_network())
        self.bind(f"<{mod}-N>", lambda e: self.scan_network())
        
        # Cmd/Ctrl+D: Open downloads folder
        self.bind(f"<{mod}-d>", lambda e: self.open_downloads_folder())
        self.bind(f"<{mod}-D>", lambda e: self.open_downloads_folder())
        
        # Escape: Deselect peer
        self.bind("<Escape>", lambda e: self.deselect_peer())
        
        # Cmd/Ctrl+Q: Quit (handled natively on macOS, need for other platforms)
        if platform.system() != "Darwin":
            self.bind(f"<{mod}-q>", lambda e: self.on_closing())
            self.bind(f"<{mod}-Q>", lambda e: self.on_closing())
    
    def deselect_peer(self):
        """Deselect the currently selected peer"""
        self.selected_peer = None
        self.status_label.configure(text="No peer selected")
        self.status_icon.configure(text_color=COLORS["text_secondary"])
        
        # Update selection state for all peer frames
        for frame in self.peers_container.winfo_children():
            if isinstance(frame, UserFrame):
                frame.set_selected(False)

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
    
    def setup_system_tray(self):
        """Setup system tray icon and menu"""
        self.tray_icon = None
        
        if not TRAY_AVAILABLE:
            return
        
        # On macOS, pystray can be unstable - make optional
        if platform.system() == "Darwin":
            # Skip tray on macOS for now due to stability issues
            # The app works fine without it
            print("System tray disabled on macOS (use Cmd+Q to quit)")
            return
        
        try:
            # Create tray icon image
            self.tray_icon_image = self._create_tray_icon()
            
            # Create tray menu
            menu = (
                TrayItem("Show NetXend", self.show_from_tray),
                TrayItem("Open Downloads", self.open_downloads_from_tray),
                pystray.Menu.SEPARATOR,
                TrayItem("Quit", self.quit_from_tray)
            )
            
            self.tray_icon = pystray.Icon(
                "NetXend",
                self.tray_icon_image,
                "NetXend - File Sharing",
                menu
            )
            
            # Start tray in background thread
            self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
            self.tray_thread.start()
        except Exception as e:
            print(f"System tray not available: {e}")
            self.tray_icon = None
    
    def _create_tray_icon(self) -> Image.Image:
        """Create a simple tray icon image"""
        # Create a 64x64 icon
        size = 64
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Draw a colored circle
        accent_color = COLORS["accent"]
        draw.ellipse([4, 4, size-4, size-4], fill=accent_color)
        
        # Draw an arrow inside
        arrow_points = [
            (size//2, 12),      # Top
            (size//2 + 16, 36), # Right
            (size//2 + 6, 36),  # Right inner
            (size//2 + 6, 52),  # Bottom right
            (size//2 - 6, 52),  # Bottom left
            (size//2 - 6, 36),  # Left inner
            (size//2 - 16, 36), # Left
        ]
        draw.polygon(arrow_points, fill='white')
        
        return image
    
    def show_from_tray(self, icon=None, item=None):
        """Show the window from system tray"""
        self.after(0, self.deiconify)
        self.after(0, self.lift)
        self.after(0, self.focus_force)
    
    def open_downloads_from_tray(self, icon=None, item=None):
        """Open downloads folder from tray"""
        self.after(0, self.open_downloads_folder)
    
    def quit_from_tray(self, icon=None, item=None):
        """Quit the app from system tray"""
        if self.tray_icon:
            self.tray_icon.stop()
        self.after(0, self.force_quit)
    
    def force_quit(self):
        """Force quit the application"""
        self.running = False
        self.destroy()
    
    def minimize_to_tray(self):
        """Minimize window to system tray"""
        if TRAY_AVAILABLE and self.tray_icon:
            self.withdraw()
        else:
            self.iconify()
    
    def on_closing(self):
        """Handle window close - minimize to tray or quit"""
        if TRAY_AVAILABLE and self.tray_icon and self.config.get("minimize_to_tray", True):
            self.minimize_to_tray()
        else:
            if self.tray_icon:
                self.tray_icon.stop()
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
        
        # Config already loaded in __init__, just use it
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
        
        # Settings button at bottom of sidebar
        settings_btn_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        settings_btn_frame.pack(side="bottom", fill="x", padx=8, pady=8)
        
        self.settings_btn = ctk.CTkButton(
            settings_btn_frame,
            text="⚙️ Settings",
            width=200,
            height=40,
            corner_radius=20,
            fg_color=COLORS["card_bg"],
            hover_color=COLORS["bg_light"],
            font=("SF Pro Display", 13) if platform.system() == "Darwin" else ("Segoe UI", 13),
            command=self.open_settings
        )
        self.settings_btn.pack(fill="x")

        # ========== MAIN CONTENT ==========
        self.main_content = ctk.CTkFrame(self, fg_color=COLORS["bg_dark"], corner_radius=0)
        self.main_content.grid(row=1, column=1, sticky="nsew", padx=0, pady=0)
        self.main_content.grid_rowconfigure(0, weight=1)
        self.main_content.grid_rowconfigure(1, weight=0)
        self.main_content.grid_columnconfigure(0, weight=1)
        self.main_content.grid_columnconfigure(1, weight=0)  # Transfer queue column

        # ========== DROP ZONE ==========
        self.drop_zone = ctk.CTkFrame(
            self.main_content,
            corner_radius=20,
            border_width=3,
            border_color=COLORS["border"],
            fg_color=COLORS["card_bg"]
        )
        self.drop_zone.grid(row=0, column=0, sticky="nsew", padx=(40, 20), pady=40)
        
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
        
        # Buttons container
        buttons_frame = ctk.CTkFrame(drop_content, fg_color="transparent")
        buttons_frame.pack()
        
        # Select files button
        self.select_btn = ctk.CTkButton(
            buttons_frame,
            text="Select Files",
            width=140,
            height=44,
            corner_radius=22,
            font=("SF Pro Display", 14, "bold") if platform.system() == "Darwin" else ("Segoe UI", 14, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self.select_files
        )
        self.select_btn.pack(side="left", padx=(0, 12))
        
        # Select folder button
        self.select_folder_btn = ctk.CTkButton(
            buttons_frame,
            text="Select Folder",
            width=140,
            height=44,
            corner_radius=22,
            font=("SF Pro Display", 14, "bold") if platform.system() == "Darwin" else ("Segoe UI", 14, "bold"),
            fg_color=COLORS["bg_light"],
            hover_color=COLORS["accent"],
            command=self.select_folder
        )
        self.select_folder_btn.pack(side="left")
        
        # Make drop zone clickable
        for widget in [self.drop_zone, drop_content, self.upload_icon_label, self.drop_title, self.drop_subtitle]:
            widget.bind("<Button-1>", self.select_files)
        
        # Hover effects for drop zone
        self.drop_zone.bind("<Enter>", self.on_drop_zone_enter)
        self.drop_zone.bind("<Leave>", self.on_drop_zone_leave)
        
        # ========== TRANSFER QUEUE PANEL ==========
        self.transfer_panel = TransferQueuePanel(self.main_content)
        self.transfer_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 24), pady=40)
        self.transfer_panel.configure(width=320)
        self.transfer_panel.grid_propagate(False)
        self.transfer_panel.on_cancel_callback = self.cancel_transfer
        self.transfer_panel.on_retry_callback = self.retry_transfer
        
        # ========== STATUS BAR ==========
        self.status_bar = ctk.CTkFrame(
            self.main_content,
            height=80,
            fg_color=COLORS["bg_medium"],
            corner_radius=16
        )
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=40, pady=(0, 24))
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
            save_folder = self.get_save_folder()
            if platform.system() == "Darwin":  # macOS
                subprocess.run(["open", str(save_folder)])
            elif platform.system() == "Windows":
                subprocess.run(["explorer", str(save_folder)])
            else:  # Linux
                subprocess.run(["xdg-open", str(save_folder)])
        except Exception as e:
            print(f"Could not open folder: {e}")
    
    def open_settings(self):
        """Open the settings dialog"""
        SettingsDialog(self, self.config, on_save=self.apply_settings)
    
    def apply_settings(self, new_config: dict):
        """Apply new settings and save"""
        old_name = self.config.get("display_name", "")
        old_theme = self.config.get("theme", "dark")
        self.config = new_config
        save_config(self.config)
        
        # Update display name if changed
        if old_name != new_config.get("display_name", ""):
            self.self_user.name_label.configure(text=new_config["display_name"])
        
        # Update save folder if changed
        new_save = new_config.get("save_location", "")
        if new_save:
            global SAVE_FOLDER
            SAVE_FOLDER = Path(new_save)
            if not SAVE_FOLDER.exists():
                SAVE_FOLDER.mkdir(parents=True)
        
        # Apply theme change
        new_theme = new_config.get("theme", "dark")
        if old_theme != new_theme:
            self.apply_theme(new_theme)
        
        self.update_progress(0, "✓ Settings saved", "success")
    
    def apply_theme(self, theme: str):
        """Apply theme (dark/light)"""
        global COLORS
        if theme == "light":
            COLORS = COLORS_LIGHT.copy()
            ctk.set_appearance_mode("light")
        else:
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
            ctk.set_appearance_mode("dark")
        
        # Update main window
        self.configure(fg_color=COLORS["bg_dark"])
        self.header.configure(fg_color=COLORS["bg_medium"])
        self.sidebar.configure(fg_color=COLORS["bg_medium"])
        self.main_content.configure(fg_color=COLORS["bg_dark"])
        self.drop_zone.configure(fg_color=COLORS["card_bg"], border_color=COLORS["border"])
        self.status_bar.configure(fg_color=COLORS["bg_medium"])
    
    def get_save_folder(self) -> Path:
        """Get the current save folder from config or default"""
        save_location = self.config.get("save_location", "")
        if save_location:
            return Path(save_location)
        return SAVE_FOLDER
    
    def setup_drag_and_drop(self):
        """Setup native drag and drop support"""
        # Try to use tkinterdnd2 if available (best cross-platform drag-drop)
        # Note: tkinterdnd2 requires special Tk initialization and may not work
        # with CustomTkinter. This is optional functionality.
        try:
            from tkinterdnd2 import DND_FILES, TkinterDnD
            # Check if tkdnd is actually available in Tk
            self.tk.call('package', 'require', 'tkdnd')
            # If we get here, tkinterdnd2 is available
            self.drop_zone.drop_target_register(DND_FILES)
            self.drop_zone.dnd_bind('<<Drop>>', self.handle_drop)
            self.drop_zone.dnd_bind('<<DragEnter>>', lambda e: self.on_drop_zone_enter(e))
            self.drop_zone.dnd_bind('<<DragLeave>>', lambda e: self.on_drop_zone_leave(e))
            self.drop_title.configure(text="Drop files here to send")
            self.drop_subtitle.configure(text="or drag & drop anywhere in this area")
        except Exception:
            # tkinterdnd2 not available or not working - just use click to select
            # This is expected on macOS and some Linux configurations
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

    def select_folder(self, event=None):
        """Select a folder to send (will be zipped automatically)"""
        folder_path = filedialog.askdirectory(title="Select Folder to Send")
        if folder_path:
            self.handle_folder(folder_path)

    def handle_folder(self, folder_path: str):
        """Zip and send a folder"""
        if not self.selected_peer:
            messagebox.showwarning("No Peer Selected", "Please select a peer first!")
            return
        
        if not self.peers.get(self.selected_peer):
            messagebox.showwarning("Peer Offline", "Selected peer is no longer available.")
            self.selected_peer = None
            return
        
        folder_name = os.path.basename(folder_path)
        
        # Update status
        self.update_progress(0, f"📦 Zipping folder: {folder_name}...", "progress")
        
        # Zip in a thread to avoid UI freeze
        def zip_and_send():
            try:
                zip_path = self.zip_folder(folder_path)
                if zip_path:
                    self.after(0, lambda: self.handle_files([zip_path], is_folder=True))
            except Exception as e:
                self.after(0, lambda: self.update_progress(0, f"✗ Error zipping: {str(e)}", "error"))
        
        threading.Thread(target=zip_and_send, daemon=True).start()

    def zip_folder(self, folder_path: str) -> Optional[str]:
        """Zip a folder and return the path to the zip file"""
        folder_name = os.path.basename(folder_path)
        
        # Create temp directory for zip file
        temp_dir = tempfile.gettempdir()
        zip_filename = f"{folder_name}.zip"
        zip_path = os.path.join(temp_dir, zip_filename)
        
        # Remove existing zip if present
        if os.path.exists(zip_path):
            os.remove(zip_path)
        
        # Create zip file
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, os.path.dirname(folder_path))
                    zipf.write(file_path, arcname)
        
        return zip_path

    def handle_files(self, files, is_folder: bool = False):
        if not self.selected_peer:
            messagebox.showwarning("No Peer Selected", "Please select a peer first!")
            return
        
        if not self.peers.get(self.selected_peer):
            messagebox.showwarning("Peer Offline", "Selected peer is no longer available.")
            self.selected_peer = None
            return
        
        peer_info = self.peers.get(self.selected_peer, {})
        peer_name = peer_info.get('hostname', self.selected_peer)
        
        for file_path in files:
            # Create Transfer object
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            
            transfer = Transfer(
                file_path=file_path,
                file_name=file_name,
                file_size=file_size,
                peer_ip=self.selected_peer,
                peer_name=peer_name,
                direction="send",
                is_folder=is_folder
            )
            
            # Add to active transfers and UI
            self.active_transfers[transfer.id] = transfer
            self.transfer_panel.add_transfer(transfer)
            
            # Start transfer thread
            threading.Thread(
                target=self.send_file,
                args=(transfer,),
                daemon=True
            ).start()
    
    def cancel_transfer(self, transfer: Transfer):
        """Cancel an active transfer"""
        transfer.cancelled = True
        transfer.status = TransferStatus.CANCELLED
        transfer.end_time = time.time()
        
        # Clean up partial file for received transfers
        if transfer.direction == "receive" and transfer.file_path:
            try:
                partial_file = Path(transfer.file_path)
                if partial_file.exists():
                    partial_file.unlink()
                    print(f"Cleaned up partial file: {partial_file}")
            except Exception as e:
                print(f"Could not clean up partial file: {e}")
        
        self.after(0, lambda: self.transfer_panel.update_transfer(transfer.id))
        self.after(0, lambda: self.update_progress(0, f"Transfer cancelled", "info"))
    
    def retry_transfer(self, transfer: Transfer):
        """Retry a failed transfer"""
        # Check if peer is still available
        if transfer.peer_ip not in self.peers:
            self.update_progress(0, f"✗ Peer {transfer.peer_name} is offline", "error")
            return
        
        # Check if file still exists
        if not os.path.exists(transfer.file_path):
            self.update_progress(0, f"✗ File no longer exists: {transfer.file_name}", "error")
            return
        
        # Remove old transfer from queue
        self.transfer_panel.remove_transfer(transfer.id)
        if transfer.id in self.active_transfers:
            del self.active_transfers[transfer.id]
        
        # Create new transfer with fresh state
        new_transfer = Transfer(
            file_path=transfer.file_path,
            file_name=transfer.file_name,
            file_size=transfer.file_size,
            peer_ip=transfer.peer_ip,
            peer_name=transfer.peer_name,
            direction="send",
            is_folder=transfer.is_folder
        )
        
        # Add to active transfers and UI
        self.active_transfers[new_transfer.id] = new_transfer
        self.transfer_panel.add_transfer(new_transfer)
        
        # Start transfer thread
        threading.Thread(
            target=self.send_file,
            args=(new_transfer,),
            daemon=True
        ).start()
        
        self.update_progress(0, f"Retrying: {transfer.file_name}", "progress")
    
    def save_to_history(self, transfer: Transfer):
        """Save a completed transfer to history"""
        history_entry = transfer_to_dict(transfer)
        self.transfer_history.append(history_entry)
        save_transfer_history(self.transfer_history)

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
        transfer = None
        expected_checksum = None
        try:
            file_info = conn.recv(1024).decode()
            file_info = json.loads(file_info)
            file_name = file_info['name']
            total_size = file_info['size']
            expected_checksum = file_info.get('checksum')  # May be None for older clients
            
            # Get peer name if we know them
            peer_name = self.peers.get(addr[0], {}).get('hostname', addr[0])
            
            # Create transfer object for receive
            transfer = Transfer(
                file_path="",  # Will be set after save
                file_name=file_name,
                file_size=total_size,
                peer_ip=addr[0],
                peer_name=peer_name,
                direction="receive"
            )
            transfer.checksum = expected_checksum
            transfer.status = TransferStatus.ACTIVE
            transfer.start_time = time.time()
            
            # Add to UI
            self.active_transfers[transfer.id] = transfer
            self.after(0, lambda: self.transfer_panel.add_transfer(transfer))
            
            # Get configured save folder
            save_folder = self.get_save_folder()
            if not save_folder.exists():
                save_folder.mkdir(parents=True)
            
            # Handle duplicate filenames
            save_path = save_folder / file_name
            if save_path.exists():
                base, ext = os.path.splitext(file_name)
                counter = 1
                while save_path.exists():
                    save_path = save_folder / f"{base}_{counter}{ext}"
                    counter += 1
            
            transfer.file_path = str(save_path)
            
            received = 0
            start_time = time.time()
            last_update = start_time
            
            with open(save_path, 'wb') as f:
                while received < total_size:
                    # Check for cancellation
                    if transfer.cancelled:
                        raise Exception("Transfer cancelled")
                    
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
                        
                        # Update transfer object
                        transfer.progress = progress
                        transfer.speed = speed
                        transfer.bytes_transferred = received
                        
                        # Update UI
                        self.after(0, lambda: self.transfer_panel.update_transfer(transfer.id))
                        
                        # Also update status bar
                        p, s, fn = progress, speed, file_name
                        self.after(0, lambda p=p, s=s, fn=fn: self.update_progress(
                            p, f"⬇ Receiving: {fn} ({p:.1f}%) - {format_speed(s)}", "progress"
                        ))
                        last_update = current_time

            conn.sendall(b'ACK')
            
            # Mark complete
            transfer.status = TransferStatus.COMPLETED
            transfer.progress = 100
            transfer.end_time = time.time()
            
            # Verify checksum if provided
            verification_status = ""
            if expected_checksum:
                self.after(0, lambda: self.update_progress(100, f"Verifying checksum...", "progress"))
                received_checksum = calculate_file_checksum(str(save_path))
                if received_checksum == expected_checksum:
                    transfer.checksum_verified = True
                    verification_status = " ✓"
                else:
                    transfer.checksum_verified = False
                    verification_status = " ⚠️ (checksum mismatch)"
            
            # Auto-extract zip files (sent folders)
            final_name = save_path.name
            if save_path.suffix.lower() == '.zip':
                try:
                    save_folder = self.get_save_folder()
                    extract_dir = save_folder / save_path.stem
                    if extract_dir.exists():
                        # Add counter for duplicate folders
                        counter = 1
                        while extract_dir.exists():
                            extract_dir = save_folder / f"{save_path.stem}_{counter}"
                            counter += 1
                    
                    with zipfile.ZipFile(save_path, 'r') as zipf:
                        zipf.extractall(extract_dir)
                    
                    # Remove the zip file after extraction
                    os.remove(save_path)
                    final_name = f"📁 {extract_dir.name}"
                    transfer.file_name = extract_dir.name
                    transfer.file_path = str(extract_dir)
                except Exception as zip_error:
                    print(f"Auto-extract failed: {zip_error}")
                    final_name = save_path.name  # Keep as zip if extraction fails
            
            # Save to history
            self.save_to_history(transfer)
            
            self.after(0, lambda: self.transfer_panel.update_transfer(transfer.id))
            self.after(0, lambda: self.update_progress(
                100, f"✓ Received: {final_name} ({format_size(total_size)}){verification_status}", "success"
            ))
            
            # Play receive sound
            self.play_sound("receive")
            
            # Show notification on macOS
            if platform.system() == "Darwin":
                self.show_notification("File Received", f"{save_path.name}")
            
        except Exception as e:
            if transfer:
                if not transfer.cancelled:
                    transfer.status = TransferStatus.FAILED
                    transfer.error_message = str(e)
                    self.play_sound("error")
                    self.after(0, lambda: self.transfer_panel.update_transfer(transfer.id))
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
    
    def play_sound(self, sound_type: str = "complete"):
        """Play system sounds for events"""
        if not self.config.get("sound_enabled", True):
            return
        
        try:
            if platform.system() == "Darwin":
                # macOS system sounds
                if sound_type == "complete":
                    os.system('afplay /System/Library/Sounds/Glass.aiff &')
                elif sound_type == "receive":
                    os.system('afplay /System/Library/Sounds/Ping.aiff &')
                elif sound_type == "error":
                    os.system('afplay /System/Library/Sounds/Basso.aiff &')
            elif platform.system() == "Windows":
                import winsound
                if sound_type == "complete":
                    winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
                elif sound_type == "receive":
                    winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)
                elif sound_type == "error":
                    winsound.PlaySound("SystemHand", winsound.SND_ALIAS | winsound.SND_ASYNC)
        except Exception as e:
            print(f"Sound playback error: {e}")

    def send_file(self, transfer: Transfer):
        """Send a file to a peer using Transfer object"""
        transfer.status = TransferStatus.ACTIVE
        transfer.start_time = time.time()
        self.after(0, lambda: self.transfer_panel.update_transfer(transfer.id))
        
        try:
            # Calculate checksum before sending
            self.after(0, lambda: self.update_progress(0, f"Calculating checksum for {transfer.file_name}...", "progress"))
            transfer.checksum = calculate_file_checksum(transfer.file_path)
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(30)  # Connection timeout
                sock.connect((transfer.peer_ip, PORT))
                
                # Send file metadata with checksum
                file_info = {
                    'name': transfer.file_name,
                    'size': transfer.file_size,
                    'checksum': transfer.checksum
                }
                sock.sendall(json.dumps(file_info).encode())
                time.sleep(0.1)

                sent = 0
                start_time = time.time()
                last_update = start_time
                
                with open(transfer.file_path, 'rb') as f:
                    while sent < transfer.file_size:
                        # Check for cancellation
                        if transfer.cancelled:
                            raise Exception("Transfer cancelled")
                        
                        data = f.read(BUFFER_SIZE)
                        sock.sendall(data)
                        sent += len(data)
                        
                        # Update progress (throttled)
                        current_time = time.time()
                        if current_time - last_update >= 0.1:
                            elapsed = current_time - start_time
                            speed = sent / elapsed if elapsed > 0 else 0
                            progress = sent / transfer.file_size * 100
                            
                            # Update transfer object
                            transfer.progress = progress
                            transfer.speed = speed
                            transfer.bytes_transferred = sent
                            
                            # Update UI
                            self.after(0, lambda: self.transfer_panel.update_transfer(transfer.id))
                            
                            # Also update status bar
                            p, s, fn = progress, speed, transfer.file_name
                            self.after(0, lambda p=p, s=s, fn=fn: self.update_progress(
                                p, f"⬆ Sending: {fn} ({p:.1f}%) - {format_speed(s)}", "progress"
                            ))
                            last_update = current_time

                sock.settimeout(10)  # Timeout for ACK
                if sock.recv(3) == b'ACK':
                    transfer.status = TransferStatus.COMPLETED
                    transfer.progress = 100
                    transfer.end_time = time.time()
                    
                    # Save to history
                    self.save_to_history(transfer)
                    
                    # Play completion sound
                    self.play_sound("complete")
                    
                    self.after(0, lambda: self.transfer_panel.update_transfer(transfer.id))
                    self.after(0, lambda: self.update_progress(
                        100, f"✓ Sent: {transfer.file_name} ({format_size(transfer.file_size)})", "success"
                    ))
                    
        except socket.timeout:
            transfer.status = TransferStatus.FAILED
            transfer.error_message = "Connection timeout"
            self.play_sound("error")
            self.after(0, lambda: self.transfer_panel.update_transfer(transfer.id))
            self.after(0, lambda: self.update_progress(0, f"✗ Timeout sending to {transfer.peer_name}", "error"))
        except ConnectionRefusedError:
            transfer.status = TransferStatus.FAILED
            transfer.error_message = "Connection refused"
            self.play_sound("error")
            self.after(0, lambda: self.transfer_panel.update_transfer(transfer.id))
            self.after(0, lambda: self.update_progress(0, f"✗ Connection refused by {transfer.peer_name}", "error"))
        except Exception as e:
            if not transfer.cancelled:
                transfer.status = TransferStatus.FAILED
                transfer.error_message = str(e)
                self.play_sound("error")
                self.after(0, lambda: self.transfer_panel.update_transfer(transfer.id))
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
