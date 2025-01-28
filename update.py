import subprocess
import os
import sys
from pathlib import Path
import shutil
import time

def run_command(command):
    """Run a shell command and return its output"""
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
        print(f"Error executing command: {e.cmd}")
        print(f"Error output: {e.stderr}")
        return None

def check_git_installed():
    """Check if git is installed on the system"""
    if run_command("git --version"):
        return True
    return False

def check_repository_exists():
    """Check if .git directory exists in current directory"""
    return os.path.exists(".git")

def backup_current_code():
    """Create a backup of the current code"""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_dir = f"backup_{timestamp}"
    
    try:
        # Create backup directory
        os.makedirs(backup_dir)
        
        # Copy all .py files
        for file in Path(".").glob("*.py"):
            shutil.copy2(file, backup_dir)
            
        print(f"Backup created in: {backup_dir}")
        return True
    except Exception as e:
        print(f"Error creating backup: {e}")
        return False

def update_repository():
    """Update the repository from GitHub"""
    print("\nNetXend Updater")
    print("="*50)
    
    # Check if git is installed
    if not check_git_installed():
        print("Error: Git is not installed. Please install Git first.")
        sys.exit(1)
    
    # Repository URL
    repo_url = "https://github.com/Hackeinstein/NetXend.git"
    
    try:
        if check_repository_exists():
            print("Existing repository found. Creating backup...")
            if not backup_current_code():
                if input("Backup failed. Continue anyway? (y/n): ").lower() != 'y':
                    sys.exit(1)
            
            print("\nFetching updates...")
            run_command("git fetch origin")
            
            print("Checking for changes...")
            current = run_command("git rev-parse HEAD")
            latest = run_command("git rev-parse origin/main")
            
            if current == latest:
                print("\nYour code is already up to date!")
                return
            
            print("\nUpdating code...")
            result = run_command("git pull origin main")
            
            if result:
                print("\nUpdate successful!")
                print("\nUpdated files:")
                run_command("git diff --name-only HEAD@{1} HEAD")
            else:
                print("\nError during update. Please check error messages above.")
        
        else:
            print("No existing repository found. Cloning fresh copy...")
            if os.listdir():
                print("Creating backup of existing files...")
                if not backup_current_code():
                    if input("Backup failed. Continue anyway? (y/n): ").lower() != 'y':
                        sys.exit(1)
            
            result = run_command(f"git clone {repo_url} temp_clone")
            
            if result is not None:
                # Move all files from temp_clone to current directory
                for item in os.listdir("temp_clone"):
                    source = os.path.join("temp_clone", item)
                    dest = os.path.join(".", item)
                    
                    if os.path.isdir(source):
                        if os.path.exists(dest):
                            shutil.rmtree(dest)
                        shutil.copytree(source, dest)
                    else:
                        if os.path.exists(dest):
                            os.remove(dest)
                        shutil.copy2(source, dest)
                
                # Remove temp clone directory
                shutil.rmtree("temp_clone")
                print("\nFresh copy downloaded successfully!")
            else:
                print("\nError during clone. Please check error messages above.")
    
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        update_repository()
        print("\nUpdate process completed!")
        input("\nPress Enter to exit...")
    except KeyboardInterrupt:
        print("\n\nUpdate cancelled by user.")
        sys.exit(0)