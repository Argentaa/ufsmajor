import os
from flask import Flask
from supabase import create_client, Client
from config import Config

# Inicializa o cliente Supabase
# Usaremos a service key aqui para ter permissões de escrita no backend
supabase: Client = create_client(
    os.environ.get("SUPABASE_URL"),
    os.environ.get("SUPABASE_SERVICE_KEY")
)

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Registro dos Blueprints
    from app.main.routes import main
    from app.admin.routes import admin
    from app.api.routes import api

    app.register_blueprint(main)
    app.register_blueprint(admin, url_prefix='/admin')
    app.register_blueprint(api, url_prefix='/api')

    return app