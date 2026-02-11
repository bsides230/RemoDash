#!/usr/bin/env python3
import os
import sys

# GIT_ASKPASS receives the prompt as the first argument.
# We use this to determine whether to return username or password.
prompt = sys.argv[1] if len(sys.argv) > 1 else ""
prompt_lower = prompt.lower()

if "username" in prompt_lower:
    print(os.environ.get("GIT_USERNAME", ""))
elif "password" in prompt_lower:
    print(os.environ.get("GIT_PASSWORD", ""))
else:
    # Default fallback to password
    print(os.environ.get("GIT_PASSWORD", ""))
