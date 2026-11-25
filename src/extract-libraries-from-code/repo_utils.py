import subprocess
import os
import shutil

def download_github_repo(repo_url: str, destination: str = "./"):
    
    parts = repo_url.rstrip("/").split("/")
    if len(parts) < 2:
        print("Invalid GitHub repository URL.")
        return False
    
    username, repo_name = parts[-2], parts[-1].replace(".git", "")
    folder_name = f"{username}_{repo_name}"
    target_path = os.path.join(destination, folder_name)

    if os.path.exists(target_path):
        print(f"Repository '{folder_name}' already exists at {target_path}. Skipping download.")
        return target_path

    try:
        subprocess.run(["git", "clone", repo_url, target_path], check=True)
        print(f"Successfully cloned {repo_url} to {target_path}")

        return target_path
    except subprocess.CalledProcessError as e:
        print(f"Error cloning repository: {e}")
        return ''
    



def delete_directory(dir_path: str):
    try:
        shutil.rmtree(dir_path)
        print(f"Successfully deleted directory: {dir_path}")
        return True
    
    except FileNotFoundError:
        print(f"Directory not found: {dir_path}")
    except PermissionError:
        print(f"Permission denied: {dir_path}")
    except Exception as e:
        print(f"Error deleting directory: {e}")
    return False

