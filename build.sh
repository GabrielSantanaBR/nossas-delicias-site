#!/usr/bin/env bash
set -o errexit
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py collectstatic --noinput
# The branch still uses syncdb-style tables while it is in active development.
# Before the production database is created we can replace this with explicit migrations.
python manage.py migrate --run-syncdb --noinput
