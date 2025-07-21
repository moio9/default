#!/bin/bash

# Define installation directory
INSTALL_DIR="$HOME/.local/share/barrel"
BIN_DIR="$HOME/bin"

echo "Starting Barrel installation..."

# 1. Create installation directory
mkdir -p "$INSTALL_DIR"
echo "Created installation directory: $INSTALL_DIR"

# 2. Copy application files
cp barrel_x11.py "$INSTALL_DIR/"
cp barrel_native.py "$INSTALL_DIR/"
cp -r app "$INSTALL_DIR/"
cp main.sh "$INSTALL_DIR/" # Copy main.sh as well, it might be useful

echo "Copied application files to $INSTALL_DIR"

# 3. Make main scripts executable
chmod +x "$INSTALL_DIR/barrel_x11.py"
chmod +x "$INSTALL_DIR/barrel_native.py"
chmod +x "$INSTALL_DIR/main.sh" # Make the shell script executable too

echo "Made main scripts executable."

# 4. Create symlinks for easy access (optional but recommended)
mkdir -p "$BIN_DIR"
if [ -w "$BIN_DIR" ]; then # Check if BIN_DIR is writable
    ln -sf "$INSTALL_DIR/barrel_x11.py" "$BIN_DIR/barrel-x11"
    ln -sf "$INSTALL_DIR/barrel_native.py" "$BIN_DIR/barrel-native"
    ln -sf "$INSTALL_DIR/main.sh" "$BIN_DIR/barrel-cli" # Symlink for the shell script
    echo "Created symlinks in $BIN_DIR. Make sure $BIN_DIR is in your PATH."
    echo "You can run the app using 'barrel-x11', 'barrel-native', or 'barrel-cli'."
else
    echo "Warning: Cannot create symlinks in $BIN_DIR (not writable). You can run the app directly from $INSTALL_DIR."
fi

# 5. Inform user about XDG directories (already handled by Python scripts, but good to mention)
echo ""
echo "Barrel uses XDG Base Directory Specification for configuration, data, and cache:"
echo "Config: ~/.config/shortcut_launcher"
echo "Data: ~/.local/share/shortcut_launcher"
echo "Cache: ~/.cache/shortcut_launcher"

echo ""
echo "Installation complete!"
echo "To run the X11 (GUI) version: python $INSTALL_DIR/barrel_x11.py"
echo "To run the native (Termux GUI) version: python $INSTALL_DIR/barrel_native.py"
echo "To run the CLI version: $INSTALL_DIR/main.sh"
echo ""
echo "If you created symlinks, you can also use 'barrel-x11', 'barrel-native', or 'barrel-cli' from any directory."
echo "Ensure $HOME/bin is in your PATH for symlinks to work."
echo "You might need to restart your Termux session or run 'source ~/.bashrc' (or equivalent) for PATH changes to take effect."
