from pathlib import Path

from sparkcityx.weather_pipeline_cli import build_parser

from unittest.mock import MagicMock, patch

from sparkcityx.weather_pipeline_cli import build_parser, run_cli


def test_weather_pipeline_cli_defaults_to_safe_preview() -> None:
    args = build_parser().parse_args([])

    assert args.source == Path("data/raw/weather_data.parquet")
    assert args.apply is False
    assert args.batch_size == 1_000
    assert args.env_file == Path("secrets/.env")


@patch("sparkcityx.weather_pipeline_cli.connect_database")
@patch("sparkcityx.weather_pipeline_cli.run_weather_pipeline")
@patch("sparkcityx.weather_pipeline_cli.create_spark_session")
def test_weather_pipeline_cli_preview_never_opens_database(
    create_spark_session_mock,
    run_weather_pipeline_mock,
    connect_database_mock,
) -> None:
    spark = MagicMock()
    pipeline_result = MagicMock(
        valid=True,
        record_count=36_000,
        applied=False,
        load_result=None,
    )

    create_spark_session_mock.return_value = spark
    run_weather_pipeline_mock.return_value = pipeline_result

    exit_code = run_cli([])

    assert exit_code == 0
    connect_database_mock.assert_not_called()
    run_weather_pipeline_mock.assert_called_once_with(
        spark,
        Path("data/raw/weather_data.parquet"),
        apply=False,
        batch_size=1_000,
    )
    spark.stop.assert_called_once_with()



@patch("sparkcityx.weather_pipeline_cli.load_dotenv")
@patch("sparkcityx.weather_pipeline_cli.connect_database")
@patch("sparkcityx.weather_pipeline_cli.run_weather_pipeline")
@patch("sparkcityx.weather_pipeline_cli.create_spark_session")
def test_weather_pipeline_cli_apply_uses_database_connection(
    create_spark_session_mock,
    run_weather_pipeline_mock,
    connect_database_mock,
    load_dotenv_mock,
    tmp_path,
) -> None:
    spark = MagicMock()
    connection = MagicMock()
    env_file = tmp_path / ".env"
    env_file.touch()

    create_spark_session_mock.return_value = spark
    connect_database_mock.return_value.__enter__.return_value = (
        connection
    )
    run_weather_pipeline_mock.return_value = MagicMock(
        source="data/raw/weather_data.parquet",
        valid=True,
        record_count=36_000,
        applied=True,
        load_result=MagicMock(rows_inserted=36_000),
    )

    exit_code = run_cli(
        [
            "--apply",
            "--env-file",
            str(env_file),
            "--batch-size",
            "500",
        ]
    )

    assert exit_code == 0
    load_dotenv_mock.assert_called_once_with(
        env_file,
        override=False,
    )
    connect_database_mock.assert_called_once_with()
    run_weather_pipeline_mock.assert_called_once_with(
        spark,
        Path("data/raw/weather_data.parquet"),
        connection=connection,
        apply=True,
        batch_size=500,
    )
    spark.stop.assert_called_once_with()