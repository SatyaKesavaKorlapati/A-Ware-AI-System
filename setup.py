import os
import sys
import subprocess
import venv

def create_shortcut(venv_dir):
    if os.name != 'nt':
        return
        
    desktop = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')
    shortcut_path = os.path.join(desktop, "A-Ware Launcher.bat")
    
    project_dir = os.path.abspath(os.path.dirname(__file__))
    frontend_dir = os.path.join(project_dir, "frontend")
    
    bat_content = f"""@echo off
echo Starting A-Ware AI System...
cd /d "{project_dir}"
start cmd /k "{venv_dir}\\Scripts\\python.exe main.py"
cd /d "{frontend_dir}"
start cmd /k "npm run dev"
echo Both servers are starting!
exit
"""
    try:
        with open(shortcut_path, "w") as f:
            f.write(bat_content)
        print(f"✅ Desktop Launcher created at: {shortcut_path}")
    except Exception as e:
        print(f"⚠️ Failed to create desktop launcher: {e}")

def main():
    print("Welcome to A-Ware AI System Setup!")
    print("-----------------------------------")
    
    # Prompt for API keys
    gemini_key = input("Please enter your Gemini API Key: ").strip()
    tavily_key = input("Please enter your Tavily API Key (for Live Web Search): ").strip()
    
    print("\nCreating .env file...")
    with open(".env", "w", encoding="utf-8") as f:
        f.write(f"GEMINI_API_KEY={gemini_key}\n")
        f.write(f"TAVILY_API_KEY={tavily_key}\n")
    print("✅ .env file created.")
    
    # Prompt for Launcher
    create_exe = input("\nDo you want to create an 'A-Ware' launcher shortcut on your Desktop? (Y/n): ").strip().lower()
    
    # Check/Create virtual environment
    venv_dir = "awenv"
    if not os.path.exists(venv_dir):
        print(f"\nCreating Python virtual environment in '{venv_dir}'...")
        venv.create(venv_dir, with_pip=True)
        print("✅ Virtual environment created.")
    else:
        print(f"\n✅ Virtual environment '{venv_dir}' already exists.")
        
    # Get path to pip inside venv
    if os.name == 'nt':
        pip_path = os.path.join(venv_dir, "Scripts", "pip")
    else:
        pip_path = os.path.join(venv_dir, "bin", "pip")
        
    # Install requirements
    print("\nInstalling Python dependencies...")
    try:
        subprocess.check_call([pip_path, "install", "-r", "requirements.txt"])
        print("✅ Python dependencies installed successfully.")
    except subprocess.CalledProcessError:
        print("❌ Failed to install Python dependencies.")
        sys.exit(1)
        
    # Install npm packages for frontend
    frontend_dir = "frontend"
    if os.path.exists(frontend_dir):
        print(f"\nInstalling Node.js dependencies in '{frontend_dir}'...")
        try:
            # Need shell=True on Windows for npm
            subprocess.check_call(["npm", "install"], cwd=frontend_dir, shell=True)
            print("✅ Node.js dependencies installed successfully.")
        except subprocess.CalledProcessError:
            print("❌ Failed to install Node.js dependencies. Make sure Node.js is installed on your system.")
            sys.exit(1)
    else:
        print(f"\n⚠️ '{frontend_dir}' folder not found. Skipping Node.js setup.")
        
    print("\n-----------------------------------")
    print("Setup Complete! You are ready to go.")
    
    if create_exe == 'y' or create_exe == '':
        create_shortcut(venv_dir)
        print("You can double-click 'A-Ware Launcher.bat' on your Desktop to start both servers instantly!")
    else:
        print("To start the backend:")
        if os.name == 'nt':
            print(f"    {venv_dir}\\Scripts\\python main.py")
        else:
            print(f"    {venv_dir}/bin/python main.py")
        print("To start the frontend:")
        print("    cd frontend && npm run dev")
    print("-----------------------------------")

if __name__ == "__main__":
    main()
