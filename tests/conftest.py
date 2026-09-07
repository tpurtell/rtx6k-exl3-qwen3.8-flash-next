import logging
import pytest

@pytest.fixture
def caplog_vllm(caplog):
    logger = logging.getLogger('vllm')
    logger.addHandler(caplog.handler)
    try:
        yield caplog
    finally:
        logger.removeHandler(caplog.handler)
