from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
import os


db = SQLAlchemy()
DB_NAME = 'database.db'



def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(32))
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', f'sqlite:///{os.path.join(os.path.dirname(__file__), DB_NAME)}'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024
    db.init_app(app)

    from .views import views
    from .prediction import prediction
    from .messages import messages
    

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(prediction, url_prefix='/')
    app.register_blueprint(messages, url_prefix='/')

    from .models import Messages

    create_database(app)

    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; img-src 'self' data: blob:; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; script-src 'self'"
        )
        return response

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(413)
    @app.errorhandler(500)
    def handle_error(error):
        status = getattr(error, 'code', 500)
        messages = {
            400: ('We could not process that request', 'Check the information provided and try again.'),
            404: ('That page could not be found', 'The page may have moved or the address may be incorrect.'),
            413: ('That file is too large', 'Choose a JPG or PNG image smaller than 8 MB.'),
            500: ('Something went wrong', 'Please try again in a moment.'),
        }
        title, description = messages.get(status, messages[500])
        return render_template('error.html', status=status, error_title=title, error_description=description), status

    return app


def create_database(app):
    with app.app_context():
        db.create_all()
