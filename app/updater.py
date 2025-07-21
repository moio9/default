import os
import re
import requests
import tempfile
import subprocess

def get_github_releases(owner, repo, tag=None):
    if tag:
        url = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}"
    else:
        url = f"https://api.github.com/repos/{owner}/{repo}/releases"
        
    headers = {'User-Agent': 'ShortcutLauncher/1.0'}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"GitHub API error: {str(e)}")
        return []
    except Exception as e:
        print(f"Connection error: {str(e)}")
        return []

def is_newer_version(new_version, current_version):
    new_clean = re.sub(r'\D', '', new_version)
    current_clean = re.sub(r'\D', '', current_version)
    
    try:
        return int(new_clean) > int(current_clean)
    except ValueError:
        return new_version > current_version