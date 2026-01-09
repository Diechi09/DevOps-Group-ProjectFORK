"""Application Insights telemetry helpers for custom metrics and logs."""
import logging
import os
from typing import Optional

DEFAULT_CONNECTION_STRING = (
    "InstrumentationKey=e0b63799-fea2-4eaa-b16c-51796f166920;"
    "IngestionEndpoint=https://westeurope-5.in.applicationinsights.azure.com/;"
    "LiveEndpoint=https://westeurope.livediagnostics.monitor.azure.com/;"
    "ApplicationId=485c12ed-ecd0-4f39-966b-770f3f364413"
)

try:
    from opencensus.ext.azure.metrics_exporter import MetricsExporter
    from opencensus.ext.azure.log_exporter import AzureLogHandler
    from opencensus.stats import aggregation as aggregation_module
    from opencensus.stats import measure as measure_module
    from opencensus.stats import stats as stats_module
    from opencensus.stats import view as view_module
    from opencensus.tags import tag_key, tag_map

    OPENCENSUS_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency guard
    MetricsExporter = None
    AzureLogHandler = None
    aggregation_module = None
    measure_module = None
    stats_module = None
    view_module = None
    tag_key = None
    tag_map = None
    OPENCENSUS_AVAILABLE = False

logger = logging.getLogger(__name__)


REQUEST_LATENCY_MS = measure_module.MeasureFloat(  # type: ignore[arg-type]
    "request_latency_ms", "Request latency in milliseconds"
) if OPENCENSUS_AVAILABLE else None
REQUEST_COUNT = measure_module.MeasureInt(  # type: ignore[arg-type]
    "request_count", "Total number of requests"
) if OPENCENSUS_AVAILABLE else None
ERROR_COUNT = measure_module.MeasureInt(  # type: ignore[arg-type]
    "request_error_count", "Number of failed requests"
) if OPENCENSUS_AVAILABLE else None
REFRESH_COUNT = measure_module.MeasureInt(  # type: ignore[arg-type]
    "refresh_count", "Number of refresh operations triggered"
) if OPENCENSUS_AVAILABLE else None

METHOD_KEY = tag_key.TagKey("method") if OPENCENSUS_AVAILABLE else None
ENDPOINT_KEY = tag_key.TagKey("endpoint") if OPENCENSUS_AVAILABLE else None
STATUS_KEY = tag_key.TagKey("status_code") if OPENCENSUS_AVAILABLE else None
REFRESH_STATUS_KEY = tag_key.TagKey("refresh_status") if OPENCENSUS_AVAILABLE else None


class TelemetryClient:
    """Encapsulates Application Insights logging and custom metrics."""

    def __init__(self, connection_string: Optional[str]):
        self.connection_string = connection_string
        self.enabled = bool(
            connection_string and OPENCENSUS_AVAILABLE and hasattr(stats_module, "stats_recorder")
        )

        if self.enabled:
            self._configure_metrics_exporter(connection_string)  # type: ignore[arg-type]
            self._configure_log_handler(connection_string)  # type: ignore[arg-type]
        else:
            if not connection_string:
                logger.info("Application Insights disabled (no connection string set)")
            elif not OPENCENSUS_AVAILABLE:
                logger.warning("Application Insights disabled (opencensus not installed)")

    @classmethod
    def from_environment(cls) -> "TelemetryClient":
        return cls(_resolve_connection_string())

    def _configure_metrics_exporter(self, connection_string: str) -> None:
        view_manager = stats_module.stats.view_manager  # type: ignore[union-attr]

        # Register measures/views once
        if REQUEST_LATENCY_MS:
            latency_view = view_module.View(  # type: ignore[call-arg]
                name="request_latency_distribution",
                description="Request duration by endpoint/method/status",
                columns=[METHOD_KEY, ENDPOINT_KEY, STATUS_KEY],  # type: ignore[list-item]
                measure=REQUEST_LATENCY_MS,
                aggregation=aggregation_module.DistributionAggregation(
                    [10, 50, 100, 250, 500, 1000, 2000, 5000]
                ),
            )
            self._safe_register_view(view_manager, latency_view)

        if REQUEST_COUNT:
            count_view = view_module.View(  # type: ignore[call-arg]
                name="request_count_by_endpoint",
                description="Request counts grouped by endpoint/method/status",
                columns=[METHOD_KEY, ENDPOINT_KEY, STATUS_KEY],  # type: ignore[list-item]
                measure=REQUEST_COUNT,
                aggregation=aggregation_module.CountAggregation(),
            )
            self._safe_register_view(view_manager, count_view)

        if ERROR_COUNT:
            error_view = view_module.View(  # type: ignore[call-arg]
                name="request_error_count",
                description="Count of failed requests grouped by endpoint/method/status",
                columns=[METHOD_KEY, ENDPOINT_KEY, STATUS_KEY],  # type: ignore[list-item]
                measure=ERROR_COUNT,
                aggregation=aggregation_module.CountAggregation(),
            )
            self._safe_register_view(view_manager, error_view)

        if REFRESH_COUNT:
            refresh_view = view_module.View(  # type: ignore[call-arg]
                name="refresh_invocations",
                description="Number of refresh operations (API-triggered)",
                columns=[REFRESH_STATUS_KEY],  # type: ignore[list-item]
                measure=REFRESH_COUNT,
                aggregation=aggregation_module.CountAggregation(),
            )
            self._safe_register_view(view_manager, refresh_view)

        exporter = MetricsExporter(connection_string=connection_string, export_interval=60)
        view_manager.register_exporter(exporter)
        logger.info("Application Insights metrics exporter configured")

    def _configure_log_handler(self, connection_string: str) -> None:
        handler = AzureLogHandler(connection_string=connection_string)
        logging.getLogger().addHandler(handler)
        logger.info("Application Insights log handler attached")

    @staticmethod
    def _safe_register_view(view_manager, view) -> None:
        try:
            view_manager.register_view(view)
        except ValueError:
            # View already registered; ignore
            pass

    def record_request(self, *, duration_ms: float, status_code: int, endpoint: str, method: str) -> None:
        if not self.enabled:
            return

        tag_map_instance = tag_map.TagMap()  # type: ignore[operator]
        tag_map_instance.insert(METHOD_KEY, method)  # type: ignore[arg-type]
        tag_map_instance.insert(ENDPOINT_KEY, endpoint)  # type: ignore[arg-type]
        tag_map_instance.insert(STATUS_KEY, str(status_code))  # type: ignore[arg-type]

        measurement_map = stats_module.stats_recorder.new_measurement_map()  # type: ignore[union-attr]
        if REQUEST_COUNT:
            measurement_map.measure_int_put(REQUEST_COUNT, 1)  # type: ignore[arg-type]
        if REQUEST_LATENCY_MS:
            measurement_map.measure_float_put(REQUEST_LATENCY_MS, duration_ms)  # type: ignore[arg-type]
        if ERROR_COUNT and status_code >= 400:
            measurement_map.measure_int_put(ERROR_COUNT, 1)  # type: ignore[arg-type]
        measurement_map.record(tag_map_instance)

    def record_refresh(self, *, success: bool) -> None:
        if not self.enabled or REFRESH_COUNT is None:
            return

        tag_map_instance = tag_map.TagMap()  # type: ignore[operator]
        tag_map_instance.insert(REFRESH_STATUS_KEY, "success" if success else "failed")  # type: ignore[arg-type]

        measurement_map = stats_module.stats_recorder.new_measurement_map()  # type: ignore[union-attr]
        measurement_map.measure_int_put(REFRESH_COUNT, 1)  # type: ignore[arg-type]
        measurement_map.record(tag_map_instance)


def _resolve_connection_string() -> Optional[str]:
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    instrumentation_key = os.getenv("APPINSIGHTS_INSTRUMENTATIONKEY")

    if not connection_string and instrumentation_key:
        connection_string = f"InstrumentationKey={instrumentation_key}"

    if not connection_string:
        connection_string = DEFAULT_CONNECTION_STRING

    return connection_string


def get_connection_string() -> Optional[str]:
    """Expose resolved Application Insights connection string for other modules."""

    return _resolve_connection_string()


telemetry_client = TelemetryClient.from_environment()
