import time
import traceback
from functools import wraps
from urllib.parse import urlparse

import pydantic

from flask import g, request, current_app, jsonify, Response
from flask_jwt_extended import (
    verify_jwt_in_request,
    get_jwt,
    get_jwt_identity,
    create_access_token,
    create_refresh_token,
    jwt_required,
)
from werkzeug.exceptions import BadRequest, InternalServerError, HTTPException, Forbidden

from qcfractal.app import main, storage_socket
from qcfractal.app.helpers import _valid_encodings, SerializedResponse
from qcfractal.portal.serialization import deserialize, serialize
from qcfractal.exceptions import UserReportableError, AuthenticationFailure
from qcfractal.interface.models import UserInfo
from qcfractal.policyuniverse import Policy
from typing import Optional, Type, Callable
import qcelemental


@main.before_request
def before_request_func():
    ###############################################################
    # Deserialize the various encodings we support (like msgpack) #
    ###############################################################

    # Store timing information in the request/app context
    # g here refers to flask.g
    g.request_start = time.time()

    # The rest of this function is only for old endpoints
    if request.path.startswith("/v1/"):
        return

    # default to "application/json"
    content_type = request.headers.get("Content-Type", "application/json")
    encoding = _valid_encodings.get(content_type, None)

    if encoding is None:
        raise BadRequest(f"Did not understand Content-Type {content_type}")

    try:
        # Check to see if we have a json that is encoded as bytes rather than a string
        if (encoding == "json") and isinstance(request.data, bytes):
            blob = request.data.decode()
        else:
            blob = request.data

        if blob:
            request.data = qcelemental.util.deserialize(blob, encoding)
        else:
            request.data = None
    except Exception as e:
        raise BadRequest(f"Could not deserialize body. {e}")


def wrap_route(body_model: Optional[Type], query_model: Optional[Type[pydantic.BaseModel]] = None) -> Callable:
    def decorate(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            content_type = request.headers.get("Content-Type")

            # Find an appropriate return type (from the "Accept" header)
            # Flask helpfully parses this for us
            # By default, use plain json
            # possible_types = ['application/msgpack', 'application/json']
            possible_types = ["application/msgpack", "application/json"]
            accept_type = request.accept_mimetypes.best_match(possible_types, "application/json")

            # 1.) The body is stored in request.data
            if body_model is not None:
                if content_type is None:
                    raise BadRequest("No Content-Type specified")

                if not request.data:
                    raise BadRequest("Expected body, but it is empty")

                try:
                    deserialized_data = deserialize(request.data, content_type)
                    request.validated_data = pydantic.parse_obj_as(deserialized_data, body_model)
                except Exception as e:
                    raise BadRequest("Invalid body: " + str(e))

            # 2.) Query parameters are in request.args
            if query_model is not None:
                try:
                    request.validated_args = query_model(**request.args.to_dict(False))
                except Exception as e:
                    raise BadRequest("Invalid request arguments: " + str(e))

            # Now call the function, and validate the output
            ret = fn(*args, **kwargs)

            # Serialize the output
            serialized = serialize(ret, accept_type)
            return Response(serialized, content_type=accept_type)

        return wrapper

    return decorate


@main.after_request
def after_request_func(response: SerializedResponse):

    # Determine the time the request took
    # g here refers to flask.g
    request_duration = time.time() - g.request_start

    exclude_uris = ["/task_queue", "/service_queue", "/queue_manager"]

    # No associated data, so skip all of this
    # (maybe caused by not using portal or not using the REST API correctly?)
    if request.data is None:
        return response

    log_access = current_app.config["QCFRACTAL_CONFIG"].log_access
    if log_access and request.method == "GET" and request.path not in exclude_uris:
        # What we are going to log to the DB
        log = {}
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

        log["request_duration"] = request_duration
        log["user"] = g.user if "user" in g else None

        if isinstance(response.response, (bytes, str)):
            log["response_bytes"] = len(response.response)

        storage_socket.serverinfo.save_access(log)

    return response


@main.errorhandler(InternalServerError)
def handle_internal_error(error):
    # For otherwise unhandled errors
    # Do not report the details to the user. Instead, log it,
    # and send the user the error id

    # Obtain the original exception that caused the error
    # original = getattr(error, "original_exception", None)

    # Copy the headers to a dict, and remove the JWT stuff
    headers = dict(request.headers.items())
    headers.pop("Authorization", None)

    user = g.user if "user" in g else None
    error_log = {
        "error_text": traceback.format_exc(),
        "user": user,
        "request_path": request.full_path,
        "request_headers": str(headers),
        "request_body": str(request.data)[:8192],
    }

    # Log it to the internal error table
    err_id = storage_socket.serverinfo.save_error(error_log)

    msg = error.description + f"  **Refer to internal error id {err_id} when asking your admin**"
    return jsonify(msg=msg), error.code


@main.errorhandler(HTTPException)
def handle_http_exception(error):
    # This handles many errors, such as NotFound, Unauthorized, etc
    # These are all reportable to the user
    return jsonify(msg=str(error)), error.code


@main.errorhandler(UserReportableError)
def handle_userreport_error(error):
    # This handles any errors that are reportable to the user
    return jsonify(msg=str(error)), 400


@main.errorhandler(AuthenticationFailure)
def handle_auth_error(error):
    # This handles Authentication errors (invalid user, password, etc)
    return jsonify(msg=str(error)), 401


def check_access(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        """
        Call the route (fn) if allowed to access the url using the given
        permissions in the JWT token in the request headers

        1- If no security (JWT_ENABLED=False), always allow
        2- If JWT_ENABLED:
            if read allowed (allow_read=True), use the default read permissions
            otherwise, check against the logged-in user permissions
            from the headers' JWT token
        """

        # current_app.logger.debug(f"JWT_ENABLED: {current_app.config['JWT_ENABLED']}")
        # current_app.logger.debug(f"ALLOW_UNAUTHENTICATED_READ: {current_app.config['ALLOW_UNAUTHENTICATED_READ']}")
        # current_app.logger.debug(f"SECRET_KEY: {current_app.secret_key}")
        # current_app.logger.debug(f"SECRET_KEY: {current_app.config['SECRET_KEY']}")
        # current_app.logger.debug(f"JWT_SECRET_KEY: {current_app.config['JWT_SECRET_KEY']}")
        # current_app.logger.debug(f"JWT_ACCESS_TOKEN_EXPIRES: {current_app.config['JWT_ACCESS_TOKEN_EXPIRES']}")
        # current_app.logger.debug(f"JWT_REFRESH_TOKEN_EXPIRES: {current_app.config['JWT_REFRESH_TOKEN_EXPIRES']}")

        # if no auth required, always allowed
        if not current_app.config["JWT_ENABLED"]:
            return fn(*args, **kwargs)

        # load read permissions from DB if not read
        global _read_permissions
        if not _read_permissions:
            _read_permissions = storage_socket.roles.get("read").permissions

        # if read is allowed without login, use read_permissions
        # otherwise, check logged-in permissions
        if current_app.config["ALLOW_UNAUTHENTICATED_READ"]:
            # don't raise exception if no JWT is found
            verify_jwt_in_request(optional=True)
        else:
            # read JWT token from request headers
            verify_jwt_in_request(optional=False)

        claims = get_jwt()
        permissions = claims.get("permissions", {})

        try:
            # host_url = request.host_url
            identity = get_jwt_identity() or "anonymous"
            resource = urlparse(request.url).path.split("/")[1]
            context = {
                "Principal": identity,
                "Action": request.method,
                "Resource": resource
                # "IpAddress": request.remote_addr,
                # "AccessTime": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            }
            current_app.logger.info(f"Permissions: {permissions}")
            current_app.logger.info(f"Context: {context}")
            policy = Policy(permissions)
            if not policy.evaluate(context):
                if not Policy(_read_permissions).evaluate(context):
                    return Forbidden(f"User {identity} is not authorized to access '{resource}' resource.")

            # Store the user in the global app/request context
            g.user = identity

        except Exception as e:
            current_app.logger.info("Error in evaluating JWT permissions: \n" + str(e))
            return BadRequest("Error in evaluating JWT permissions")

        return fn(*args, **kwargs)

    return wrapper


@main.route("/register", methods=["POST"])
def register():
    if request.is_json:
        username = request.json["username"]
        password = request.json["password"]
        fullname = request.json["fullname"]
        email = request.json["email"]
        organization = request.json["organization"]
    else:
        username = request.form["username"]
        password = request.form["password"]
        fullname = request.form["fullname"]
        email = request.form["email"]
        organization = request.form["organization"]

    role = "read"
    try:
        user_info = UserInfo(
            username=username,
            enabled=True,
            fullname=fullname,
            email=email,
            organization=organization,
            role=role,
        )
    except Exception as e:
        return jsonify(msg=f"Invalid user information: {str(e)}"), 500

    # add returns the password. Raises exception on error
    # Exceptions should be handled property by the flask errorhandlers
    pw = storage_socket.users.add(user_info, password=password)
    if password is None or len(password) == 0:
        return jsonify(msg="New user created!"), 201
    else:
        return jsonify(msg="New user created! Password is '{pw}'"), 201


@main.route("/login", methods=["POST"])
def login():
    try:
        if request.is_json:
            username = request.json["username"]
            password = request.json["password"]
        else:
            username = request.form["username"]
            password = request.form["password"]
    except Exception:
        raise AuthenticationFailure("Invalid/malformed login request")

    if username is None:
        raise AuthenticationFailure("No username provided for login")
    if password is None:
        raise AuthenticationFailure("No password provided for login")

    # Raises exceptions on error
    # Also raises AuthenticationFailure if the user is invalid or the password is incorrect
    # This should be handled properly by the flask errorhandlers
    permissions = storage_socket.users.verify(username, password)

    access_token = create_access_token(identity=username, additional_claims={"permissions": permissions})
    # expires_delta=datetime.timedelta(days=3))
    refresh_token = create_refresh_token(identity=username)
    return jsonify(msg="Login succeeded!", access_token=access_token, refresh_token=refresh_token), 200


@main.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    username = get_jwt_identity()
    permissions = storage_socket.users.get_permissions(username)
    ret = {"access_token": create_access_token(identity=username, additional_claims={"permissions": permissions})}
    return jsonify(ret), 200


@main.route("/fresh-login", methods=["POST"])
def fresh_login():
    if request.is_json:
        username = request.json["username"]
        password = request.json["password"]
    else:
        username = request.form["username"]
        password = request.form["password"]

    # Raises exceptions on error
    # Also raises AuthenticationFailure if the user is invalid or the password is incorrect
    # This should be handled properly by the flask errorhandlers
    permissions = storage_socket.users.verify(username, password)

    access_token = create_access_token(
        identity=username, additionalclaims={"permissions": permissions.dict()}, fresh=True
    )
    return jsonify(msg="Fresh login succeeded!", access_token=access_token), 200
