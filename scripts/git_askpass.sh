#!/bin/sh
# GIT_ASKPASS helper for Unix-like systems.
#
# Git invokes this script with a prompt string as the first argument.
# We respond based on whether the prompt asks for username or password.
#
# The API_TOKEN environment variable is injected by the Launcher
# (see launcher/index.ts). This script does NOT read .env.

case "$1" in
  *[Uu]sername*)
    # GitHub accepts any non-empty username when the password is a PAT.
    echo "x-access-token"
    ;;
  *[Pp]assword*)
    if [ -z "$API_TOKEN" ]; then
      echo "ERROR: API_TOKEN is not set in the environment" >&2
      exit 1
    fi
    echo "$API_TOKEN"
    ;;
  *)
    echo "ERROR: unrecognized prompt: $1" >&2
    exit 1
    ;;
esac