from unittest.mock import patch


def test_initial_data_main() -> None:
    with patch("app.initial_data.init") as mock_init:
        from app.initial_data import main

        main()
        mock_init.assert_called_once()
