import os

# This is a placeholder for now. 
# We will replace the hardcoded paths later.
HOME = os.path.expanduser("~")
TEMPLATES_DIR = os.path.join(HOME, ".local/share/shortcut_launcher/templates")

def delete_template(name):
    path = os.path.join(TEMPLATES_DIR, name)
    try:
        os.remove(path)
        print(f"Template deleted: {name}")
    except Exception as e:
        print(f"Could not delete: {str(e)}")