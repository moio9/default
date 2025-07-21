import os
import requests
import urllib.request
import tarfile
import tempfile
import shutil
import glob

def install_dxvk_gplasync(show_error_cb, show_info_cb, select_version_cb, prefix_path):
    """Downloads and installs the latest DXVK-GPLAsync version."""
    project_id = "43488626"  # ID for Ph42oN/dxvk-gplasync
    api_url = f"https://gitlab.com/api/v4/projects/{project_id}/releases"
    download_path = None
    extract_dir = None

    try:
        # 1. Fetch release info from GitLab API
        resp = requests.get(api_url)
        resp.raise_for_status()
        releases = resp.json()
        if not releases:
            show_error_cb("Error", "No releases found on GitLab!")
            return

        # 2. Prepare options for version selection
        options = []
        assets = {}
        for rel in releases:
            title = rel.get('name', 'Release')
            for asset in rel.get('assets', {}).get('links', []):
                if asset.get('name', '').endswith(".tar.gz"):
                    option_label = f"{title} ({asset['name']})"
                    options.append(option_label)
                    assets[option_label] = asset['url']
        
        if not options:
            show_error_cb("Error", "No .tar.gz archives found in releases!")
            return

        # 3. Let the user choose a version using the provided callback
        selected = select_version_cb(options)
        if not selected:
            return
        url = assets[selected]

        # 4. Download the chosen archive
        download_path = os.path.join(tempfile.gettempdir(), os.path.basename(url))
        urllib.request.urlretrieve(url, download_path)

        # 5. Extract the archive to a temporary directory
        extract_dir = tempfile.mkdtemp()
        with tarfile.open(download_path, "r:gz") as tar:
            tar.extractall(path=extract_dir)

        # 6. Find the extracted folder (usually the only item in the temp dir)
        extracted_items = os.listdir(extract_dir)
        if not extracted_items:
            raise Exception("Extraction resulted in an empty directory.")
        dxvk_folder = os.path.join(extract_dir, extracted_items[0])

        # 7. Define target directories and create them
        system32 = os.path.join(prefix_path, "drive_c", "windows", "system32")
        syswow64 = os.path.join(prefix_path, "drive_c", "windows", "syswow64")
        os.makedirs(system32, exist_ok=True)
        os.makedirs(syswow64, exist_ok=True)

        # 8. Copy DLLs from the extracted folder to the prefix
        for dll in glob.glob(os.path.join(dxvk_folder, "x64", "*.dll")):
            shutil.copy(dll, system32)
        for dll in glob.glob(os.path.join(dxvk_folder, "x32", "*.dll")):
            shutil.copy(dll, syswow64)

        show_info_cb("Success", f"DXVK GPLAsync {selected} installed successfully!")

    except Exception as e:
        show_error_cb("Error", f"Installation failed:\n{str(e)}")

    finally:
        # 9. Cleanup downloaded and temporary files
        if download_path and os.path.exists(download_path):
            os.remove(download_path)
        if extract_dir and os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
