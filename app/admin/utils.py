from functools import wraps
from flask import session, redirect, url_for, flash

def admin_required(f):
    """
    Decorador para restringir o acesso a rotas do admin.
    Verifica se 'is_admin' está na sessão.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Você precisa estar logado como administrador para acessar esta página.', 'warning')
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function