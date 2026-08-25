from flask import Blueprint, abort, render_template, request
from .app_functions import ValuePredictor, pred
import base64
import os
from uuid import uuid4
from werkzeug.utils import secure_filename

prediction = Blueprint('prediction', __name__)

dir_path = os.path.dirname(os.path.realpath(__file__))
UPLOAD_FOLDER = os.path.join(dir_path, 'uploads')
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}



@prediction.route('/predict', methods=["POST", 'GET'])
def predict():
    if request.method == "POST":
        condition = request.args.get('condition', '')
        expected_fields = {'diabete': 8, 'stroke': 9, 'liver': 10, 'heart': 11, 'kidney': 15}
        if condition not in expected_fields or len(request.form) != expected_fields[condition]:
            abort(400)
        try:
            to_predict_list = [float(value) for value in request.form.values()]
            result, page = ValuePredictor(to_predict_list)
        except (TypeError, ValueError, OverflowError):
            abort(400)
        if page != condition:
            abort(400)
        return render_template("result.html", prediction=result, page=page)
    else:
        return render_template('base.html')

@prediction.route('/upload', methods=['POST','GET'])
def upload_file():
    if request.method == "GET":
        return render_template('pneumonia.html')

    file = request.files.get("file")
    if not file or not file.filename:
        abort(400)
    original_name = secure_filename(file.filename)
    extension = original_name.rsplit('.', 1)[-1].lower() if '.' in original_name else ''
    if extension not in ALLOWED_EXTENSIONS:
        abort(400)

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    stored_name = f"{uuid4().hex}.{extension}"
    file_path = os.path.join(UPLOAD_FOLDER, stored_name)
    file.save(file_path)
    try:
        result = pred(file_path)
    except Exception:
        try:
            os.remove(file_path)
        except OSError:
            pass
        abort(400)

    with open(file_path, 'rb') as uploaded_image:
        image_data = base64.b64encode(uploaded_image.read()).decode('ascii')
    try:
        os.remove(file_path)
    except OSError:
        pass

    label = 'Pneumonia' if result > 0.5 else 'Normal'
    confidence = result if result > 0.5 else 1 - result
    return render_template(
        'deep_pred.html',
        image_file_name=original_name,
        image_data=f'data:image/{"jpeg" if extension in {"jpg", "jpeg"} else "png"};base64,{image_data}',
        label=label,
        accuracy=confidence * 100,
    )
