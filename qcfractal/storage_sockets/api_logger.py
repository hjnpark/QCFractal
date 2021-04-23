"""
Copywrite:
This product includes GeoLite2 data created by MaxMind, available from
https://www.maxmind.com
(attribution requirement)
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Dict, Optional, Any
    from werkzeug.wrappers import BaseRequest
    from ..config import FractalConfig


class API_AccessLogger:
    """
    Extract access information from HTTP requests to be saved by the database
    Calculate geo data using geoip2 if the library and its files are available
    otherwise, just extracts the basic information
    """

    def __init__(self, qcf_config: FractalConfig):
        self.enabled = qcf_config.log_access

        geo_file_path = qcf_config.geo_file_path
        self.geoip2_reader = None

        if geo_file_path:
            try:
                import geoip2.database

                self.geoip2_reader = geoip2.database.Reader(geo_file_path)
                logger.info(f"Initialized geoip2 with {geo_file_path} successfully.")
            except ImportError:
                logger.warning(
                    f"Cannot import geoip2 module. To use API access logging, you need "
                    f"to install it manually using `pip install geoip2`"
                )
            except FileNotFoundError:
                logger.error(
                    f"Geoip cites file cannot be read from {geo_file_path}.\n"
                    f"Make sure to manually download the file from: \n"
                    f"https://geolite.maxmind.com/download/geoip/database/GeoLite2-City.tar.gz\n"
                    f"Then, set the geo_file_path in qcfractal_config.yaml in your base_folder "
                    f"(default base_folder is ~/.qca/qcfractal/qcfractal_config.yaml)."
                )

    def get_api_access_log(self, request: BaseRequest, extra_params: Optional[Dict[str, Any]] = None):

        log: Dict[str, Any] = {}

        log["access_type"] = request.path[1:]  # remove /
        log["access_method"] = request.method  # GET or POST

        # get the real IP address behind a proxy or ngnix
        real_ip = request.headers.get("X-Real-IP", None)

        # The IP address is the last address listed in access_route, which
        # comes from the X-FORWARDED-FOR header
        # (If access_route is empty, use the original request ip)
        if real_ip is None:
            real_ip = request.access_route[-1] if len(request.access_route) > 0 else request.remote_addr

        log["ip_address"] = real_ip
        log["user_agent"] = request.headers["User-Agent"]

        # TODO: extract needed info, maybe handle by caller
        log["extra_params"] = extra_params
        # Or, will saved as string anyway
        # log.extra_access_params = request.json

        # extra geo data if available
        extra = self.get_geoip2_data(log["ip_address"])
        log.update(extra)

        return log

    def get_geoip2_data(self, ip_address: str) -> Dict[str, Any]:
        out: Dict[str, Any] = {}

        if not self.geoip2_reader:
            return out

        try:
            loc_data = self.geoip2_reader.city(ip_address)
            out["city"] = loc_data.city.name
            out["country"] = loc_data.country.name
            out["country_code"] = loc_data.country.iso_code
            out["ip_lat"] = str(loc_data.location.latitude)
            out["ip_long"] = str(loc_data.location.longitude)
            out["postal_code"] = loc_data.postal.code
            out["subdivision"] = loc_data.subdivisions.most_specific.name
        except:  # lgtm [py/catch-base-exception]
            logger.error(f"Problem getting geoip2 data for {ip_address}")

        return out
