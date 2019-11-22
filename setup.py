"""
Emmett is a full-stack python web framework designed with simplicity in mind.


Links
-----

* `git repo <http://github.com/emmett-framework/emmett>`_

"""

import platform
import re

from setuptools import find_packages, setup

with open('emmett/__init__.py', 'r', encoding='utf8') as f:
    version = re.search(r'__version__ = "(.*?)"', f.read(), re.M).group(1)


_requirements_basic = [
    'aiofiles==0.4.0',
    'click>=0.6',
    'h11~=0.8.0',
    'pendulum>=2.0.0',
    'pyaes',
    'pyDAL==17.3',
    'python-rapidjson~=0.8.0',
    'pyyaml',
    'renoir==1.0.0b1',
    'uvicorn==0.9.1',
    'websockets>=8.0'
]

if platform.system() == 'Windows' or platform.system().startswith('CYGWIN'):
    requirements = _requirements_basic
else:
    requirements = sorted(_requirements_basic + [
        'httptools~=0.0.13',
        'uvloop~=0.13.0'
    ])


setup(
    name='Emmett',
    version=version,
    url='http://github.com/emmett-framework/emmett/',
    license='BSD',
    author='Giovanni Barillari',
    author_email='gi0baro@d4net.org',
    description='The web framework for inventors',
    long_description=__doc__,
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    python_requires='>=3.7',
    install_requires=requirements,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Framework :: AsyncIO',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7'
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    entry_points={
        'console_scripts': ['emmett = emmett.cli:main']
    }
)
