"""
Weppy
-----

Weppy is a web framework for Python based on web2py and inspired to Flask.


Weppy is simple
---------------

Save in a hello.py:

.. code:: python

    from weppy import App
    app = App(__name__)

    @app.expose("/")
    def hello():
        return "Hello World!"

    if __name__ == "__main__":
        app.run()


And Easy to Setup
-----------------

And run it:

.. code:: bash

    $ pip install weppy
    $ python hello.py
     * Running on http://localhost:8000/


Links
-----

* `website <http://weppy.org>`_
* `documentation <http://weppy.org/docs>`_
* `git repo <http://github.com/gi0baro/weppy>`_

"""

from setuptools import setup
setup(
    name='weppy',
    version='0.1',
    url='http://github.com/gi0baro/weppy/',
    license='GPLv3',
    author='Giovanni Barillari',
    author_email='gi0baro@d4net.org',
    description='The web framework for humans',
    #long_description=__doc__,
    packages=['weppy', 'weppy.dal', 'weppy.dal.adapters', 'weppy.dal.helpers',
              'weppy.language', 'weppy.language.plurals', 'weppy.tools',
              'weppy.libs'],
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    install_requires=[
        'click>=0.6',
        'pyaes',
        'pyyaml'
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    entry_points='''
        [console_scripts]
        weppy=weppy.cli:main
    ''',
    #cmdclass={'audit': run_audit},
    #test_suite=''
)
