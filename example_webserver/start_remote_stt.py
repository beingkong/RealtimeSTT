#!/usr/bin/env python3
"""
Startup script for Remote STT Server
Checks dependencies and starts the server
"""

import sys
import subprocess
import importlib.util
import os

def check_package(package_name, import_name=None):
    """Check if a package is installed"""
    if import_name is None:
        import_name = package_name
    
    spec = importlib.util.find_spec(import_name)
    return spec is not None

def install_package(package_name):
    """Install a package using pip"""
    print(f"Installing {package_name}...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        return True
    except subprocess.CalledProcessError:
        return False

def check_and_install_dependencies():
    """Check and install required dependencies"""
    dependencies = [
        ("websockets", "websockets"),
        ("numpy", "numpy"),
        ("scipy", "scipy"),
        ("RealtimeSTT", "RealtimeSTT"),
    ]
    
    missing_packages = []
    
    print("Checking dependencies...")
    for package_name, import_name in dependencies:
        if not check_package(package_name, import_name):
            missing_packages.append(package_name)
            print(f"❌ {package_name} not found")
        else:
            print(f"✅ {package_name} found")
    
    if missing_packages:
        print(f"\nMissing packages: {', '.join(missing_packages)}")
        response = input("Would you like to install them now? (y/n): ").lower().strip()
        
        if response == 'y' or response == 'yes':
            for package in missing_packages:
                if not install_package(package):
                    print(f"❌ Failed to install {package}")
                    return False
                else:
                    print(f"✅ Successfully installed {package}")
        else:
            print("Cannot proceed without required dependencies.")
            return False
    
    return True

def get_server_info():
    """Get server connection information"""
    import socket
    
    # Get local IP address
    try:
        # Connect to a remote address to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except:
        local_ip = "localhost"
    
    return local_ip

def main():
    print("=" * 60)
    print("Remote STT Server Startup")
    print("=" * 60)
    
    # Check dependencies
    if not check_and_install_dependencies():
        print("\n❌ Dependency check failed. Exiting.")
        sys.exit(1)
    
    print("\n✅ All dependencies satisfied!")
    
    # Get server info
    local_ip = get_server_info()
    
    print("\n" + "=" * 60)
    print("SERVER INFORMATION")
    print("=" * 60)
    print(f"🌐 Web Interface URL:")
    print(f"   http://{local_ip}:8000/remote_stt_client.html")
    print(f"   http://localhost:8000/remote_stt_client.html")
    print()
    print(f"🔌 External Access (Port Mapping):")
    print(f"   http://YOUR_EXTERNAL_IP:11195/remote_stt_client.html")
    print()
    print(f"🔌 WebSocket Server: ws://{local_ip}:8002")
    print()
    print("📱 USAGE INSTRUCTIONS:")
    print("1. Start this server on your SSH remote machine")
    print("2. Open the Web Interface URL in your LOCAL browser")
    print("   - Use port 8000 for local access")
    print("   - Use port 11195 for external access")
    print("3. Allow microphone access when prompted")
    print("4. Click 'Start Recording' and speak!")
    print()
    print("💡 PORT MAPPING INFO:")
    print("   Internal Port 8000 -> External Port 11195")
    print("   WebSocket uses port 8002 (no mapping needed)")
    print("=" * 60)
    
    # Import and start the server
    try:
        from remote_stt_server import main as start_server
        print("\n🚀 Starting Remote STT Server...")
        start_server()
    except ImportError:
        print("\n❌ Could not import remote_stt_server.py")
        print("Make sure remote_stt_server.py is in the same directory.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped by user.")
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
