from setuptools import setup, find_packages

setup(
    name='rss-checker',
    version='0.0.5',
    author='Matusz Moneta',
    author_email='mateuszmoneta@gmail.com',
    install_requires=[
        'requests>2,<3',
        'click>6,<7',
        'dateparser>0.5,<1',
    ],
    packages=find_packages(),
    entry_points={
        'console_scripts': ['rss-checker=rss_checker.main:check'],
    }
)
