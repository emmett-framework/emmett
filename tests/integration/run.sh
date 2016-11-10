#!/usr/bin/env bash

source setup.sh

source ./env/bin/activate

cd ../../

python setup.py install

cd tests/integration

python run.py --test &

sleep 1

py.test -v -s --driver PhantomJS ./selenium_test.py
exit_code=$?

pkill -9 -f run.py && exit ${exit_code}
