# NetXend

NetXend is a lightweight, cross-platform file sharing application that allows users to easily transfer files between computers on the same local network. Built with Python and CustomTkinter, it provides a modern, user-friendly interface for quick file sharing without the need for complex setup or internet connectivity.

![NetXend Screenshot](screenshot.png)

## Features

- 🔍 Automatic peer discovery on local network
- 📁 Drag-and-drop file sharing
- 🎨 Modern, dark-mode interface
- 👤 Customizable user profiles
- 💻 Cross-platform support (Windows, macOS, Linux)
- 🚀 Fast direct file transfers
- 🔐 Local network only for enhanced security

## Installation

### Prerequisites

- Python 3.8 or higher
- Git (for installation and updates)

### Install Steps

1. Clone the repository:
```bash
git clone https://github.com/Hackeinstein/NetXend.git
```

2. Navigate to the project directory:
```bash
cd NetXend
```

3. Install required dependencies:
```bash
pip install customtkinter pillow
```

4. Run the application:
```bash
python netxend.py
```

## Usage

### Quick Start

1. Launch NetXend on two or more computers on the same network
2. The application will automatically discover other NetXend users
3. Click on a user in the left panel to select them as the recipient
4. Click the "Click to Select Files" area or drag files into it to start sharing

### Features Guide

#### User Profile
- Click the "Edit" button next to your name to customize your display name
- Your avatar color is automatically generated but remains consistent

#### Finding Peers
- NetXend automatically scans for other users every 10 seconds
- Use the "Scan Network" button for manual network scanning
- Only users on the same local network will be discovered

#### Sending Files
1. Select the recipient from the left panel
2. Click the drop zone or drag files into it
3. Select the file(s) you want to send
4. The transfer will begin automatically

#### Receiving Files
- Files are automatically received when someone sends them to you
- Received files are saved in your Downloads/netxend folder
- Progress is shown in the application

## Troubleshooting

### Network Discovery Issues
- Ensure all computers are on the same local network
- Check if your firewall allows UDP port 65433
- Verify that broadcast traffic is allowed on your network
- Try running the application with administrator privileges

### File Transfer Issues
- Check if TCP port 65432 is open
- Ensure you have write permissions in the Downloads folder
- Verify that your firewall isn't blocking the application

## Development

### Project Structure
```
NetXend/
├── netxend.py         # Main application file
├── README.md          # Documentation
└── netxend_config.json # User configuration file
```

### Contributing
1. Fork the repository
2. Create a new branch for your feature
3. Commit your changes
4. Push to your branch
5. Create a Pull Request

### Building from Source
The application is currently distributed as source code. To create an executable:

1. Install PyInstaller:
```bash
pip install pyinstaller
```

2. Build the executable:
```bash
pyinstaller --onefile --windowed netxend.py
```

## Security Considerations

- NetXend operates only on local networks
- No data is sent over the internet
- File transfers are direct between peers
- No files are stored on any servers

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)
- Icon assets from [Lucide Icons](https://lucide.dev/)

## Support

If you encounter any issues or have questions:
1. Check the troubleshooting section
2. Look through existing GitHub issues
3. Create a new issue with detailed information about your problem

---

Made with ❤️ by [Hackeinstein](https://github.com/Hackeinstein)