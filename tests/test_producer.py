from unittest.mock import MagicMock, patch

import pytest

from src.producer import fetch_stock_data, publish_to_kafka


SAMPLE_API_RESPONSE = [
    {
        "symbol": "NVDA",
        "name": "NVIDIA Corporation",
        "change": 1.78,
        "price": 119.37,
        "changesPercentage": 1.51,
    },
    {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "change": -0.79,
        "price": 229.00,
        "changesPercentage": -0.34,
    },
]


@patch("src.producer.requests.get")
def test_fetch_stock_data_returns_list(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = SAMPLE_API_RESPONSE
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    result = fetch_stock_data()

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["symbol"] == "NVDA"


@patch("src.producer.requests.get")
def test_fetch_stock_data_raises_on_non_list(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {"error": "invalid"}
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    with pytest.raises(ValueError, match="Expected list"):
        fetch_stock_data()


def test_publish_to_kafka():
    mock_producer = MagicMock()

    publish_to_kafka(mock_producer, SAMPLE_API_RESPONSE)

    mock_producer.send.assert_called_once_with("test_kafka_aws", value=SAMPLE_API_RESPONSE)
    mock_producer.flush.assert_called_once()
