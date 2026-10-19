import httpx
import pytest

from ingestion.infrastructure.ecb import is_no_data
from tests.recorded import DAILY, NO_SERIES_404, recorded_response


@pytest.mark.parametrize(
    "response",
    [
        pytest.param(recorded_response(NO_SERIES_404), id="recorded 404 for updatedAfter"),
        pytest.param(httpx.Response(404, text="No results found."), id="documented wording"),
    ],
)
def test_the_ecb_no_data_answer_is_recognised(response: httpx.Response) -> None:
    assert is_no_data(response)


@pytest.mark.parametrize(
    "response",
    [
        pytest.param(recorded_response(DAILY), id="delivery"),
        pytest.param(httpx.Response(404, text="<html>Not Found</html>"), id="other 404"),
        pytest.param(httpx.Response(400, text="No results found"), id="other status"),
    ],
)
def test_other_answers_are_not_no_data(response: httpx.Response) -> None:
    assert not is_no_data(response)
