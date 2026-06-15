import os
import sys
import subprocess
import venv

def main():
    print("Welcome to A-Ware AI System Setup!")
    print("-----------------------------------")
    
    # Prompt for API key
    gemini_key = input("Please enter your Gemini API Key: ").strip()
    
    # Write to .env
    print("\nCreating .env file...")
    with open(".env", "w", encoding="utf-8") as f:
        f.write(f"GEMINI_API_KEY={gemini_key}\n")
    print("✅ .env file created.")
    
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
