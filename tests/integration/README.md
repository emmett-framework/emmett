# Integration Testing

Integration (selenium) tests help to reduce bugs that can't be found using the weppy test client.

## Requirements

Integration tests require [PhantomJS](http://phantomjs.org/) on PATH.

If iOS user you may use `brew install phantomjs`, or download from link above and extract executable to you path.

## Run

__Run from `tests/integration` directory!__

The _precise_ way to run phantomjs alongside pytest-selenium is a pain to perform
so a `run.sh` was created for ease of use. Simply:

```
. ./setup.sh

bash run.sh
```
