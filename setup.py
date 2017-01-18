from setuptools import setup, find_packages

setup(
    name='rss-checker',
    version='0.2.1',
    author='Matusz Moneta',
    author_email='mateuszmoneta@gmail.com',
    install_requires=[
        'requests>2,<3',
        'click>6,<7',
        'dateparser>0.5,<1',
        'pyaml',
    ],
    packages=find_packages(),
    entry_points={
        'console_scripts': ['rss-checker=rss_checker.main:check',
                            'rss-checkd=rss_checker.main:checkd'],
    }
)
