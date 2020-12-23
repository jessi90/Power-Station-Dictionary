# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/06-ci-cd.ipynb (unless otherwise specified).

__all__ = ['app', 'get_current_package_version', 'increment_package_version', 'set_current_package_version']

# Cell
import os
import typer
from warnings import warn
from configparser import ConfigParser

# Cell
app = typer.Typer()

# Cell
@app.command()
def get_current_package_version(settings_fp: str='settings.ini'):
    config = ConfigParser(delimiters=['='])
    config.read(settings_fp)
    version = config.get('DEFAULT', 'version')

    return version

# Cell
@app.command()
def increment_package_version(old_version: str, increment_level: str='micro'):
    increment = lambda rev: str(int(rev)+1)

    major, minor, micro = old_version.split('.') # naming from - https://the-hitchhikers-guide-to-packaging.readthedocs.io/en/latest/specification.html#sequence-based-scheme

    if increment_level == 'major':
        major = increment(major)
    elif increment_level == 'minor':
        minor = increment(minor)
    elif increment_level == 'micro':
        micro = increment(micro)

    new_version = '.'.join([major, minor, micro])

    return new_version

# Cell
@app.command()
def set_current_package_version(version: str, settings_fp: str='settings.ini'):
    config = ConfigParser(delimiters=['='])
    config.read(settings_fp)

    config.set('DEFAULT', 'version', version)

    with open(settings_fp, 'w') as configfile:
        config.write(configfile)

    return

# Cell
if __name__ == '__main__' and '__file__' in globals():
    app()