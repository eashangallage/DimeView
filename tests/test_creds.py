import json
import os

def check_credential_file(file_path):
    print(f"\n--- Checking: {file_path} ---")
    
    # 1. Check if path exists
    if not os.path.exists(file_path):
        print(f"❌ FILE NOT FOUND at: {file_path}")
        return

    # 2. Check file size
    file_size = os.path.getsize(file_path)
    print(f"File Size: {file_size} bytes")
    
    if file_size == 0:
        print("❌ ERROR: File is EMPTY. This is why your program is crashing.")
        print("   -> Solution: Copy your JSON content into this file.")
        return

    # 3. Validate JSON content
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            
        # 4. Check for critical keys (adjust 'project_id' if needed)
        if 'type' in data and 'project_id' in data:
            print("✅ SUCCESS: Valid JSON credentials found.")
            print(f"   Project ID: {data.get('project_id')}")
            print(f"   Type: {data.get('type')}")
        else:
            print("⚠️  WARNING: JSON is valid, but missing standard Service Account keys.")
            print(f"   Keys found: {list(data.keys())}")
            
    except json.JSONDecodeError as e:
        print(f"❌ JSON ERROR: Could not decode file. {e}")
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")

if __name__ == "__main__":
    # Get the project root directory (assuming this script is in /tests)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    
    print(f"Project Root detected: {project_root}")

    # Path 1: The one inside the package (likely the one your code uses)
    pkg_config = os.path.join(project_root, "src", "dimeview", "config", "DimeViewCreds.json")
    
    # Path 2: The one at the root (likely where you saved the real creds)
    root_config = os.path.join(project_root, "config", "DimeViewCreds.json")

    check_credential_file(pkg_config)
    check_credential_file(root_config)