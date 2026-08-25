from flask import Blueprint, abort, jsonify, render_template


views = Blueprint("views", __name__)


YES_NO = [("0", "No"), ("1", "Yes")]

CONDITIONS = {
    "heart": {
        "name": "Heart disease",
        "short_name": "Heart",
        "eyebrow": "Cardiovascular assessment",
        "summary": "Explore patterns associated with heart disease using 11 commonly collected clinical measurements.",
        "overview": "Heart disease describes several conditions that affect the heart, including coronary artery disease, rhythm disorders, valve disease and conditions of the heart muscle. Many risk factors can be managed with appropriate clinical care and healthy lifestyle choices.",
        "symptoms_intro": "Seek medical advice if you notice symptoms such as:",
        "symptoms": ["Chest pressure, tightness or pain", "Shortness of breath", "Unusual fatigue", "Cold sweats or nausea", "Lightheadedness or sudden dizziness"],
        "accuracy": 90,
        "image": "images/disease_img/theheart1.jpg",
        "card_image": "images/model_img/heart.jpg",
        "fields": [
            {"name": "age", "label": "Age", "hint": "Age in years", "min": 1, "max": 120},
            {"name": "Gender", "label": "Sex", "type": "select", "options": [("1", "Male"), ("0", "Female")]},
            {"name": "cp", "label": "Chest pain type", "type": "select", "options": [("0", "Typical angina"), ("1", "Atypical angina"), ("2", "Non-anginal pain"), ("3", "Asymptomatic")]},
            {"name": "trestbps", "label": "Resting blood pressure", "hint": "mm Hg", "min": 40, "max": 260},
            {"name": "chol", "label": "Serum cholesterol", "hint": "mg/dL", "min": 50, "max": 700, "step": "any"},
            {"name": "fbs", "label": "Fasting blood sugar above 120 mg/dL", "type": "select", "options": YES_NO},
            {"name": "restecg", "label": "Resting ECG result", "type": "select", "options": [("0", "Normal"), ("1", "ST–T wave abnormality"), ("2", "Left ventricular hypertrophy")]},
            {"name": "thalach", "label": "Maximum heart rate achieved", "hint": "beats per minute", "min": 30, "max": 240, "step": "any"},
            {"name": "exang", "label": "Exercise-induced angina", "type": "select", "options": [("0", "No"), ("1", "Yes")]},
            {"name": "oldpeak", "label": "ST depression (oldpeak)", "hint": "Relative to rest", "min": 0, "max": 10, "step": "any"},
            {"name": "slope", "label": "Peak exercise ST slope", "type": "select", "options": [("0", "Upsloping"), ("1", "Flat"), ("2", "Downsloping")]},
        ],
    },
    "diabete": {
        "name": "Diabetes",
        "short_name": "Diabetes",
        "eyebrow": "Metabolic assessment",
        "summary": "Review diabetes-associated patterns using eight health and family-history measurements.",
        "overview": "Diabetes mellitus affects how the body uses blood glucose. Persistently high blood sugar can lead to serious health problems, but screening and early clinical guidance can help people manage risk and choose appropriate next steps.",
        "symptoms_intro": "Common signs can include:",
        "symptoms": ["Increased thirst or hunger", "Frequent urination", "Unexplained weight loss", "Fatigue or irritability", "Blurred vision"],
        "accuracy": 86,
        "image": "images/disease_img/thediabete1.jpg",
        "card_image": "images/model_img/diabete.jpg",
        "fields": [
            {"name": "pregnancies", "label": "Pregnancies", "hint": "Number of pregnancies", "min": 0, "max": 30},
            {"name": "Glucose", "label": "Plasma glucose", "hint": "mg/dL", "min": 0, "max": 400, "step": "any"},
            {"name": "blood_pressure", "label": "Diastolic blood pressure", "hint": "mm Hg", "min": 0, "max": 200, "step": "any"},
            {"name": "BSkinThickness", "label": "Triceps skin-fold thickness", "hint": "mm", "min": 0, "max": 120, "step": "any"},
            {"name": "Insulin", "label": "2-hour serum insulin", "hint": "µU/mL", "min": 0, "max": 1000, "step": "any"},
            {"name": "BMI", "label": "Body mass index", "hint": "kg/m²", "min": 0, "max": 100, "step": "any"},
            {"name": "DiabetesPedigreeFunction", "label": "Diabetes pedigree function", "hint": "Family-history score", "min": 0, "max": 3, "step": "any"},
            {"name": "Age", "label": "Age", "hint": "Age in years", "min": 1, "max": 120},
        ],
    },
    "kidney": {
        "name": "Kidney disease",
        "short_name": "Kidney",
        "eyebrow": "Renal assessment",
        "summary": "Evaluate patterns linked with chronic kidney disease across 15 clinical and lifestyle indicators.",
        "overview": "Chronic kidney disease is a gradual loss of kidney function. Early stages may have few noticeable symptoms, while later stages can allow fluid and waste to build up in the body. Clinical testing is essential for diagnosis and treatment planning.",
        "symptoms_intro": "Possible signs that deserve clinical attention include:",
        "symptoms": ["Nausea or loss of appetite", "Fatigue and sleep problems", "Changes in urination", "Swelling in the feet or ankles", "Shortness of breath"],
        "accuracy": 98,
        "image": "images/disease_img/thekidney1.jpg",
        "card_image": "images/model_img/kidney.jpg",
        "fields": [
            {"name": "age", "label": "Age", "hint": "Age in years", "min": 1, "max": 120},
            {"name": "blood_pressure", "label": "Blood pressure", "hint": "mm Hg", "min": 30, "max": 260, "step": "any"},
            {"name": "Specific_Gravity", "label": "Urine specific gravity", "hint": "Typically 1.002–1.030", "min": 1, "max": 1.1, "step": "0.001"},
            {"name": "Blood_Glucose_Random", "label": "Random blood glucose", "hint": "mg/dL", "min": 0, "max": 700, "step": "any"},
            {"name": "Blood_Urea", "label": "Blood urea", "hint": "mg/dL", "min": 0, "max": 400, "step": "any"},
            {"name": "Serum_Creatinine", "label": "Serum creatinine", "hint": "mg/dL", "min": 0, "max": 80, "step": "any"},
            {"name": "Hemoglobin", "label": "Hemoglobin", "hint": "g/dL", "min": 0, "max": 30, "step": "any"},
            {"name": "Pus Cell Clumps", "label": "Pus cell clumps", "type": "select", "options": [("0", "Not present"), ("1", "Present")]},
            {"name": "Bacteria", "label": "Bacteria", "type": "select", "options": [("0", "Not present"), ("1", "Present")]},
            {"name": "Hypertension", "label": "Hypertension", "type": "select", "options": YES_NO},
            {"name": "Diabetes Mellitus", "label": "Diabetes mellitus", "type": "select", "options": YES_NO},
            {"name": "Coronary Artery Disease", "label": "Coronary artery disease", "type": "select", "options": YES_NO},
            {"name": "Appetite", "label": "Appetite", "type": "select", "options": [("0", "Good"), ("1", "Poor")]},
            {"name": "Pedal Edema", "label": "Pedal edema", "type": "select", "options": YES_NO},
            {"name": "Anemia", "label": "Anemia", "type": "select", "options": YES_NO},
        ],
    },
    "liver": {
        "name": "Liver disease",
        "short_name": "Liver",
        "eyebrow": "Hepatic assessment",
        "summary": "Explore liver-disease patterns using ten standard blood-test and demographic measurements.",
        "overview": "The liver supports digestion, metabolism and removal of harmful substances. Viral infections, alcohol use, metabolic conditions and inherited factors can damage it over time. Medical assessment can identify causes and guide treatment.",
        "symptoms_intro": "Possible liver-related symptoms include:",
        "symptoms": ["Yellowing of the skin or eyes", "Abdominal pain or swelling", "Dark urine or pale stool", "Persistent fatigue", "Nausea or loss of appetite"],
        "accuracy": 84,
        "image": "images/disease_img/theliver1.jpg",
        "card_image": "images/model_img/liver.jpg",
        "fields": [
            {"name": "age", "label": "Age", "hint": "Age in years", "min": 1, "max": 120},
            {"name": "Total_Bilirubin", "label": "Total bilirubin", "hint": "mg/dL", "min": 0, "max": 100, "step": "any"},
            {"name": "Direct_Bilirubin", "label": "Direct bilirubin", "hint": "mg/dL", "min": 0, "max": 50, "step": "any"},
            {"name": "Alkaline_Phosphotase", "label": "Alkaline phosphatase", "hint": "IU/L", "min": 0, "max": 3000, "step": "any"},
            {"name": "Alamine_Aminotransferase", "label": "Alanine aminotransferase", "hint": "IU/L", "min": 0, "max": 3000, "step": "any"},
            {"name": "Aspartate_Aminotransferase", "label": "Aspartate aminotransferase", "hint": "IU/L", "min": 0, "max": 5000, "step": "any"},
            {"name": "Total_Protiens", "label": "Total proteins", "hint": "g/dL", "min": 0, "max": 20, "step": "any"},
            {"name": "Albumin", "label": "Albumin", "hint": "g/dL", "min": 0, "max": 10, "step": "any"},
            {"name": "Albumin_and_Globulin_Ratio", "label": "Albumin / globulin ratio", "min": 0, "max": 5, "step": "any"},
            {"name": "Gender", "label": "Sex", "type": "select", "options": [("0", "Male"), ("1", "Female")]},
        ],
    },
    "stroke": {
        "name": "Stroke risk",
        "short_name": "Stroke",
        "eyebrow": "Neurological risk assessment",
        "summary": "Review stroke-associated patterns using nine demographic, lifestyle and health indicators.",
        "overview": "A stroke occurs when blood flow to part of the brain is interrupted or reduced. It is a medical emergency. Recognising warning signs and getting immediate treatment can reduce brain damage and other complications.",
        "symptoms_intro": "Use the FAST warning signs and seek emergency help immediately for:",
        "symptoms": ["Face drooping", "Arm weakness", "Speech difficulty", "Sudden vision or balance changes", "A sudden, severe headache"],
        "accuracy": 81,
        "image": "images/disease_img/thestroke1.jpg",
        "card_image": "images/model_img/stroke.jpg",
        "fields": [
            {"name": "age", "label": "Age", "hint": "Age in years", "min": 1, "max": 120},
            {"name": "avg_glucose_level", "label": "Average glucose level", "hint": "mg/dL", "min": 0, "max": 700, "step": "any"},
            {"name": "hypertension", "label": "Hypertension", "type": "select", "options": [("1", "Yes"), ("0", "No")]},
            {"name": "heart_disease", "label": "Heart disease", "type": "select", "options": [("1", "Yes"), ("0", "No")]},
            {"name": "Gender", "label": "Sex", "type": "select", "options": [("1", "Male"), ("0", "Female")]},
            {"name": "ever_married", "label": "Ever married", "type": "select", "options": [("1", "Yes"), ("0", "No")]},
            {"name": "work_type", "label": "Work type", "type": "select", "options": [("0", "Private"), ("1", "Self-employed"), ("2", "Government job"), ("3", "Children / caregiving"), ("4", "Never worked")]},
            {"name": "Residence_type", "label": "Residence type", "type": "select", "options": [("1", "Urban"), ("0", "Rural")]},
            {"name": "Smoking_status", "label": "Smoking status", "type": "select", "options": [("0", "Never smoked"), ("1", "Sometimes"), ("2", "Formerly smoked"), ("3", "Currently smokes")]},
        ],
    },
    "pneumonia": {
        "name": "Pneumonia",
        "short_name": "Pneumonia",
        "eyebrow": "Chest X-ray assessment",
        "summary": "Upload a chest X-ray for an image-based screening result from the pneumonia model.",
        "overview": "Pneumonia is an infection that inflames the air sacs in one or both lungs. Symptoms range from mild to severe and clinical diagnosis may involve an examination, chest imaging and laboratory tests.",
        "symptoms_intro": "Symptoms can include:",
        "symptoms": ["Cough, sometimes with phlegm", "Fever, chills or sweating", "Shortness of breath", "Chest pain when breathing or coughing", "Fatigue or confusion"],
        "accuracy": 91,
        "image": "images/disease_img/thepneumonia1.jpg",
        "card_image": "images/model_img/pneumonia.jpg",
        "fields": [],
    },
}


@views.app_context_processor
def inject_site_data():
    return {"conditions": CONDITIONS}


@views.get("/")
def home():
    return render_template("base.html")


@views.get("/health")
def health():
    return jsonify(status="healthy", service="AI Healthcare Hub"), 200


@views.get("/<condition>")
def condition_page(condition):
    data = CONDITIONS.get(condition)
    if data is None:
        abort(404)
    return render_template("condition.html", condition=condition, data=data)


@views.get("/<condition>_form")
def condition_form(condition):
    data = CONDITIONS.get(condition)
    if data is None:
        abort(404)
    if condition == "pneumonia":
        return render_template("pneumonia.html", condition=condition, data=data)
    return render_template("assessment_form.html", condition=condition, data=data)
