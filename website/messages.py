from flask import Blueprint, render_template, request, redirect, url_for
from .models import Messages
from . import db

messages = Blueprint('messages', __name__)


@messages.route("/msg", methods=['GET', 'POST'])
def msg():
    if request.method == 'POST':

        name = request.form.get('name', '').strip()[:80]
        email = request.form.get('email', '').strip()[:120]
        message = request.form.get('message', '').strip()[:2000]
        if not name or not email or not message:
            return redirect(url_for('views.home') + '#contact')
        new_message = Messages(name=name, email=email, messages=message)
        db.session.add(new_message)
        db.session.commit()

        return redirect(url_for('views.home') + '#contact')
    else:
        return render_template(r'base.html')
