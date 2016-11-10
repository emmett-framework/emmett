#!/usr/bin/env bash
# ------------------------------------------------------------------
# [Michael J. Davis]
#    setup.sh
#          Easily setup python's virtualenv, install requirements.
# ------------------------------------------------------------------

{
  [[ "${BASH_SOURCE[0]}" != $0 ]]
} || {
  echo "
  Please run script as 'source'
  "
  exit 1
}

# ------------------------------------------------------------------
#  DESIGNATE REQUIRED PYTHON VERSION
# ------------------------------------------------------------------
PYTHON_VERSION="$TRAVIS_PYTHON_VERSION"

THIS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# ------------------------------------------------------------------
#  RUN SETUP
# ------------------------------------------------------------------
if [ ! -d ${THIS_DIR}/env ]
then
    {
        curl -O https://raw.githubusercontent.com/mijdavis2/ezpz-setup/master/ezpz-setup.sh
        source ${THIS_DIR}/ezpz-setup.sh -r ${PYTHON_VERSION}
    } && {
        mv ${THIS_DIR}/ezpz-setup.sh ${THIS_DIR}/env/
    } || {
        echo "Setup failed!"
        echo "Try removing THIS_DIR/env and THIS_DIR/tmp"
        echo "TODO:"
        echo "    implement '--update' arg to download fresh copy of ezpz-setup.sh"
    }
else
    {
        source ${THIS_DIR}/env/ezpz-setup.sh -r ${PYTHON_VERSION}
    } || {
        echo "Setup failed!"
        echo "Try removing THIS_DIR/env and THIS_DIR/tmp"
        echo "TODO:"
        echo "    implement '--update' arg to download fresh copy of ezpz-setup.sh"
    }
fi

cd ../../

python setup.py install

cd tests/integration

source ./env/bin/activate
