from pathlib import Path
from setuptools import setup, find_packages


def get_version():
    module_file = Path(
        Path(__file__).parent, 'src',
        *find_packages('src')[-1].split('.'), '__init__.py'
    )
    return module_file.read_text().split("VERSION = '")[1].split("'")[0]


setup(
    name='cryptocom-exchange',
    version=get_version(),
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
            'pytest<6',
            'pytest-asyncio',
            'pytest-cov',
            'pytest-env',
            'pytest-doctestplus',
            'pytest-pythonpath',
            'autopep8',
            'sphinx',
            'sphinx_rtd_theme',
            'setuptools',
            'twine',
            'doc8'
        ]
    },
    zip_safe=True
)
