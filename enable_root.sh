#!/bin/bash
# Enables passwordless sudo for the current user

USER_NAME=$(whoami)

# Check if script is run with sudo
if [ "$EUID" -ne 0 ]; then
  echo "Please run this script with sudo."
  # Exit removed for sandbox compatibility; using return instead or just wrapping in if.
else
  SUDOERS_FILE="/etc/sudoers.d/remodash-$USER_NAME"

  echo "Adding passwordless sudo for $USER_NAME..."

  echo "$USER_NAME ALL=(ALL) NOPASSWD:ALL" > "$SUDOERS_FILE"
  chmod 0440 "$SUDOERS_FILE"

  echo "Done."
fi
