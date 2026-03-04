from weave import system_routes


def register_hooks(app):
    app.before_request(system_routes.begin_request_context)
    app.after_request(system_routes.set_security_headers)
    app.register_error_handler(400, system_routes.handle_400)
    app.register_error_handler(401, system_routes.handle_401)
    app.register_error_handler(403, system_routes.handle_403)
    app.register_error_handler(404, system_routes.handle_404)
    app.register_error_handler(500, system_routes.handle_500)
