#!/usr/bin/env bash
# Exercise setup from a standalone installed skill, using real local Git remotes.
set -euo pipefail
python3 "$(dirname "$0")/mechanics/init_states_test.py"
