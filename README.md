# Barrel - Emulation Shortcut Manager for Termux

Barrel is a versatile application designed for Termux users, offering a streamlined way to manage emulation environments and game/application shortcuts. Similar in concept to popular tools like **Bottles** and **Lutris** on desktop Linux, Barrel brings robust shortcut and Wine/emulator prefix management directly to your Android device via Termux.

## Key Features:
*   **Unified Shortcut Management:** Create, edit, and launch shortcuts for your emulated applications and games with ease.
*   **Wine/Emulator Prefix Handling:** Seamlessly manage multiple Wine prefixes and other emulation environments (e.g., Box64, Hangover), allowing for isolated and optimized setups.
*   **Template System:** Utilize customizable templates for pre-run and post-run scripts, enabling advanced configurations and automation for your shortcuts.
*   **Dual Interface:**
    *   **X11 GUI (tkinter):** A traditional graphical user interface for a familiar desktop-like experience when running Termux with an X server.
    *   **Termux:GUI (Native):** A lightweight, native Termux interface for managing your shortcuts directly within the Termux terminal, optimized for mobile use.

## Why Barrel?
If you're looking to organize your emulated Windows games or applications, manage different Wine versions, or simply create quick launchers for your Termux-based apps setups, Barrel provides a comprehensive solution tailored for the Termux environment.

## Installation:

### Method 1: Using the Installation Script

The easiest way to get Barrel running is by using the provided `install.sh` script. This script will set up the application in your local Termux environment.

1.  **Make the script executable:**
    ```bash
    chmod +x install.sh
    ```
2.  **Run the installation script:**
    ```bash
    ./install.sh
    ```
    This will install Barrel to `$HOME/.local/share/barrel` and create convenient symlinks in `$HOME/bin` (e.g., `barrel-x11`, `barrel-native`, `barrel-cli`) if `$HOME/bin` is in your PATH.

### Method 2: Standalone Executable (via PyInstaller)

For a single-file executable (or a minimal set of files), you can compile Barrel using `PyInstaller`.

1.  **Install PyInstaller:**
    ```bash
    pip install pyinstaller
    ```
2.  **Compile the desired version:**
    *   For the X11 GUI version:
        ```bash
        pyinstaller --onefile barrel_x11.py
        ```
    *   For the native Termux:GUI version:
        ```bash
        pyinstaller --onefile barrel_native.py
        ```
    The compiled executable (e.g., `barrel_x11` or `barrel_native`) will be found in the `dist/` directory.

## Dependencies:

To get Barrel up and running, ensure you have the following dependencies installed:

```bash
# For the Termux:GUI interface
pip install termuxgui

# General Python dependencies
pip install requests
pip install ttkthemes

# For Wine/emulator tools (e.g., wrestool for icon extraction)
pkg install wltools
```

## Usage:
TODO

## Support the Project:

If you find Barrel useful and would like to support its development, consider a donation:

**Monero:** `46Mk8t9uLY7jnBXnyHMyVARvwk1Y7jcGEQwKLN8GtGGBioncjKLgkEa33jEN2ibgkQjoFZWVwXXwsM3vzAFz4RzV7psLow6`

**Bitcoin:** `bc1qgxp74eza7jaf4fdw5cl3sanqvnh0cjmz0w9scz`

**Ethereum:** `0xa024a505Ec24c7eA163985eC89D56eC89D56e614B9AdAae`

**PayPal:** [paypal.me/moioyoyo](https://paypal.me/moioyoyo)
