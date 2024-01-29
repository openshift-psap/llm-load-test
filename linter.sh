#!/bin/bash

json_verify < config.json
python -m flake8 *.py
python -m pylint *.py

