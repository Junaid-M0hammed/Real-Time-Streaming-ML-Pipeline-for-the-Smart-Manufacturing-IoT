#!/usr/bin/env python3
"""
Dependency installation script for the real-time streaming ML pipeline.
Handles installation with fallback options and better error handling.
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(command, description):
    """Run a command and handle errors gracefully."""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, 
                              capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        if e.stdout:
            print(f"STDOUT: {e.stdout}")
        if e.stderr:
            print(f"STDERR: {e.stderr}")
        return False

def install_dependencies():
    """Install dependencies with fallback options."""
    
    # Upgrade pip first
    if not run_command("pip install --upgrade pip", "Upgrading pip"):
        print("⚠️  Failed to upgrade pip, continuing anyway...")
    
    # Try installing core dependencies first
    core_deps = [
        "numpy>=1.24.0",
        "pandas>=2.0.0",
        "scikit-learn>=1.3.0",
        "streamlit>=1.25.0"
    ]
    
    print("\n📦 Installing core dependencies...")
    for dep in core_deps:
        if not run_command(f"pip install {dep}", f"Installing {dep}"):
            print(f"⚠️  Failed to install {dep}, trying without version constraint...")
            # Try without version constraint
            dep_name = dep.split('>=')[0]
            if not run_command(f"pip install {dep_name}", f"Installing {dep_name} (latest)"):
                print(f"❌ Failed to install {dep_name}")
                return False
    
    # Install remaining dependencies
    remaining_deps = [
        "kafka-python>=2.0.0",
        "pyspark>=3.4.0",
        "joblib>=1.3.0",
        "requests>=2.28.0",
        "matplotlib>=3.6.0",
        "pillow>=9.0.0",
        "seaborn>=0.12.0",
        "plotly>=5.15.0"
    ]
    
    print("\n📦 Installing additional dependencies...")
    for dep in remaining_deps:
        if not run_command(f"pip install {dep}", f"Installing {dep}"):
            print(f"⚠️  Failed to install {dep}, trying without version constraint...")
            dep_name = dep.split('>=')[0]
            if not run_command(f"pip install {dep_name}", f"Installing {dep_name} (latest)"):
                print(f"⚠️  Failed to install {dep_name}, skipping...")
    
    return True

def verify_installation():
    """Verify that key packages are installed."""
    print("\n🔍 Verifying installation...")
    
    required_packages = [
        "numpy", "pandas", "sklearn", "streamlit", 
        "kafka", "pyspark", "joblib", "requests",
        "matplotlib", "PIL", "seaborn", "plotly"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package} - OK")
        except ImportError:
            print(f"❌ {package} - MISSING")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n⚠️  Missing packages: {', '.join(missing_packages)}")
        return False
    else:
        print("\n🎉 All required packages are installed!")
        return True

if __name__ == "__main__":
    print("🚀 Starting dependency installation for Real-time Streaming ML Pipeline")
    print("=" * 70)
    
    # Check if we're in a virtual environment
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("✅ Virtual environment detected")
    else:
        print("⚠️  No virtual environment detected. Consider using one.")
    
    # Install dependencies
    if install_dependencies():
        print("\n✅ Dependency installation completed")
        
        # Verify installation
        if verify_installation():
            print("\n🎉 Setup completed successfully!")
            print("\nYou can now run the Streamlit dashboard with:")
            print("streamlit run src/streamlit_dashboard.py")
        else:
            print("\n⚠️  Some packages may be missing. Please check the output above.")
    else:
        print("\n❌ Dependency installation failed")
        sys.exit(1) 