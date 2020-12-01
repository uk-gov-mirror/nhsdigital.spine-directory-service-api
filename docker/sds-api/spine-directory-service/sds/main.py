from typing import Optional, Dict, Any

import tornado.httpserver
import tornado.ioloop
import tornado.web
from tornado import httputil
from tornado.routing import Matcher

import lookup.sds_client_factory
from lookup.sds_client import SDSClient
from request import healthcheck_handler, routing_reliability_handler, accredited_system_handler
from request.error_handler import ErrorHandler
from utilities import config, secrets
from utilities import integration_adaptors_logger as log

logger = log.IntegrationAdaptorsLogger(__name__)


def start_tornado_server(sds_client: SDSClient) -> None:
    """Start the Tornado server

    :param sds_client: The sds client component to be used when servicing requests.
    """

    class CaseInsensitiveRouteMatcher(Matcher):
        def __init__(self, path) -> None:
            super().__init__()
            self.path = path

        def match(self, request: httputil.HTTPServerRequest) -> Optional[Dict[str, Any]]:
            return {} if request.path.lower() == self.path.lower() else None

    handler_dependencies = {"sds_client": sds_client}
    application = tornado.web.Application([
        (CaseInsensitiveRouteMatcher("/endpoint"), routing_reliability_handler.RoutingReliabilityRequestHandler, handler_dependencies),
        (CaseInsensitiveRouteMatcher("/device"), accredited_system_handler.AccreditedSystemRequestHandler, handler_dependencies),
        (CaseInsensitiveRouteMatcher("/healthcheck"), healthcheck_handler.HealthcheckHandler)
    ], default_handler_class=ErrorHandler)
    server = tornado.httpserver.HTTPServer(application)
    server_port = int(config.get_config('SERVER_PORT', default='9000'))
    server.listen(server_port)

    logger.info('Starting router server at port {server_port}', fparams={'server_port': server_port})
    tornado_io_loop = tornado.ioloop.IOLoop.current()
    try:
        tornado_io_loop.start()
    except KeyboardInterrupt:
        logger.warning('Keyboard interrupt')
        pass
    finally:
        tornado_io_loop.stop()
        tornado_io_loop.close(True)
    logger.info('Server shut down, exiting...')


def main():
    config.setup_config("SDS")
    secrets.setup_secret_config("SDS")
    log.configure_logging('sds')

    sds_client = lookup.sds_client_factory.get_sds_client()
    start_tornado_server(sds_client)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.critical('Fatal exception in main application', exc_info=True)
    finally:
        logger.info('Exiting application')
