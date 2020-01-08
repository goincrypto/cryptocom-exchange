from setuptools import setup, find_packages

setup(
    name='cryptocom-exchange',
    version='0.1',
    description="""Provide description""",
    url='https://github.com/goincrypto/cryptocom-exchange',
    author='Yaroslav Rudenok [Morty Space]',
    author_email='goincrypto@gmail.com',
    license='MIT',
    classifiers=[
        # TODO: add classifiers
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    package_dir={'': 'src'},
    packages=find_packages('src'),
    install_requires=[
        'aiohttp'
    ],
    extras_require={
        'dev': [
            'pylint',
            'pycodestyle',
            'pytest',
            'pytest-asyncio',
            'pytest-cov',
            'pytest-env',
            'pytest-pythonpath',
            'autopep8',
            'sphinx',
            'setuptools',
            'wheel',
            'twine'
        ]
    },
    zip_safe=True
)
