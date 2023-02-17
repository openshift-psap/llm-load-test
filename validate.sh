#!/bin/bash

json_verify < config.json
python -m flake8 ghz_frontend.py
python -m pylint ghz_frontend.py

