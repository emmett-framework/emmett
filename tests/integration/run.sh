#!/usr/bin/env bash

python run.py --test &

sleep 20

py.test -v -s --driver PhantomJS ./selenium_test_.py
exit_code=$?

pkill -9 -f run.py && exit ${exit_code}
