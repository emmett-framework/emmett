"""
weppy is a full-stack python framework that includes everything needed
to easily create fast, scalable and secure web applications.

It's based on web2py and inspired by Flask.


Links
-----

* `website <http://weppy.org>`_
* `documentation <http://weppy.org/docs>`_
* `git repo <http://github.com/gi0baro/weppy>`_

"""

from setuptools import setup
setup(
    name='weppy',
    version='0.2',
    url='http://github.com/gi0baro/weppy/',
    license='BSD',
    author='Giovanni Barillari',
    author_email='gi0baro@d4net.org',
    description='The web framework for humans',
    long_description=__doc__,
    packages=['weppy', 'weppy.language', 'weppy.language.plurals',
              'weppy.tools', 'weppy.libs'],
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    install_requires=[
        'click>=0.6',
        'pyaes',
        'pyDAL>=15.02',
        'pyyaml'
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    entry_points='''
        [console_scripts]
        weppy=weppy.cli:main
    ''',
)
