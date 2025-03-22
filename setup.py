"""
Setup script for preparing the Render environment
This script is run by the build command to prepare the persistent disk
"""
import os
import shutil

def setup_render_directories():
    """Set up directory structure for Render deployment"""
    print("Setting up directories for Render deployment...")
    
    # Check if running on Render with disk
    if 'RENDER' in os.environ and os.path.exists("/opt/render/project/src/data"):
        print("Running on Render with persistent disk...")
        base_path = "/opt/render/project/src/data"
        
        # Create directories
        os.makedirs(os.path.join(base_path, "uploads"), exist_ok=True)
        os.makedirs(os.path.join(base_path, "database"), exist_ok=True)
        
        print(f"Created directories in {base_path}")
        
        # Create placeholder files to ensure directories are preserved
        for dirname in ["uploads", "database"]:
            gitkeep_path = os.path.join(base_path, dirname, ".gitkeep")
            if not os.path.exists(gitkeep_path):
                with open(gitkeep_path, 'w') as f:
                    f.write("")
                print(f"Created {gitkeep_path}")
        
        # If we have local data, copy it to the disk
        if os.path.exists("database/emails.db"):
            if not os.path.exists(f"{base_path}/database/emails.db"):
                shutil.copy("database/emails.db", f"{base_path}/database/emails.db")
                print("Copied database to persistent disk")
        
        print("Directory setup complete!")
    else:
        print("Not running on Render with disk or disk not mounted.")
        print("Using local directories...")
        
        # Create local directories
        os.makedirs("uploads", exist_ok=True)
        os.makedirs("database", exist_ok=True)

if __name__ == "__main__":
    setup_render_directories() 