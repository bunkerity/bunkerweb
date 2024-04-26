try:
    import ConfigParser as configparser
except ImportError:
    import configparser
import os
import pytest


def pytest_addoption(parser):
    parser.addoption('--config', action='store', default='modsec2-apache')


@pytest.fixture(scope='session')
def config(request):
    cp = configparser.RawConfigParser()
    cp.read(os.path.join(os.path.dirname(__file__), 'config.ini'))
    return dict(cp.items(request.config.getoption('--config')))
