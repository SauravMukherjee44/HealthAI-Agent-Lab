from .model_identity import model_identity
from .schemas import AssessmentField, FieldOption, ModelSummary

YES_NO = [FieldOption(value=0, label="No"), FieldOption(value=1, label="Yes")]


HEART_FIELDS = [
    AssessmentField(name="age", label="Age", minimum=18, maximum=100, hint="Years"),
    AssessmentField(
        name="sex",
        label="Sex",
        field_type="select",
        options=[FieldOption(value=0, label="Female"), FieldOption(value=1, label="Male")],
    ),
    AssessmentField(
        name="chest_pain",
        label="Chest pain type",
        field_type="select",
        options=[
            FieldOption(value=1, label="Typical angina"),
            FieldOption(value=2, label="Atypical angina"),
            FieldOption(value=3, label="Non-anginal pain"),
            FieldOption(value=4, label="Asymptomatic"),
        ],
    ),
    AssessmentField(name="resting_bp", label="Resting blood pressure", minimum=50, maximum=260, hint="mm Hg"),
    AssessmentField(name="serum_cholesterol", label="Serum cholesterol", minimum=50, maximum=700, hint="mg/dL"),
    AssessmentField(
        name="fasting_blood_sugar", label="Fasting blood sugar above 120 mg/dL", field_type="select", options=YES_NO
    ),
    AssessmentField(
        name="resting_ecg",
        label="Resting ECG",
        field_type="select",
        options=[
            FieldOption(value=0, label="Normal"),
            FieldOption(value=1, label="ST-T abnormality"),
            FieldOption(value=2, label="Left ventricular hypertrophy"),
        ],
    ),
    AssessmentField(name="max_heart_rate", label="Maximum heart rate", minimum=40, maximum=240, hint="beats/min"),
    AssessmentField(name="exercise_angina", label="Exercise-induced angina", field_type="select", options=YES_NO),
    AssessmentField(name="oldpeak", label="ST depression", minimum=0, maximum=10, hint="Relative to rest"),
    AssessmentField(
        name="st_slope",
        label="Peak exercise ST slope",
        field_type="select",
        options=[
            FieldOption(value=1, label="Upsloping"),
            FieldOption(value=2, label="Flat"),
            FieldOption(value=3, label="Downsloping"),
        ],
    ),
    AssessmentField(name="major_vessels", label="Major vessels visible", minimum=0, maximum=3),
    AssessmentField(
        name="thal",
        label="Thal test",
        field_type="select",
        options=[
            FieldOption(value=3, label="Normal"),
            FieldOption(value=6, label="Fixed defect"),
            FieldOption(value=7, label="Reversible defect"),
        ],
    ),
]


DIABETES_FIELDS = [
    AssessmentField(name="age", label="Age", minimum=18, maximum=100, hint="Years"),
    AssessmentField(
        name="gender",
        label="Gender",
        field_type="select",
        options=[FieldOption(value=0, label="Female"), FieldOption(value=1, label="Male")],
    ),
    *[
        AssessmentField(name=name, label=label, field_type="select", options=YES_NO)
        for name, label in [
            ("polyuria", "Frequent urination"),
            ("polydipsia", "Excessive thirst"),
            ("sudden_weight_loss", "Sudden weight loss"),
            ("weakness", "Persistent weakness"),
            ("polyphagia", "Excessive hunger"),
            ("genital_thrush", "Genital thrush"),
            ("visual_blurring", "Blurred vision"),
            ("itching", "Persistent itching"),
            ("irritability", "Irritability"),
            ("delayed_healing", "Delayed healing"),
            ("partial_paresis", "Partial muscle weakness"),
            ("muscle_stiffness", "Muscle stiffness"),
            ("alopecia", "Hair loss"),
            ("obesity", "Obesity"),
        ]
    ],
]


LIVER_FIELDS = [
    AssessmentField(name="age", label="Age", minimum=18, maximum=90, hint="Years"),
    AssessmentField(
        name="gender",
        label="Sex",
        field_type="select",
        options=[FieldOption(value=0, label="Female"), FieldOption(value=1, label="Male")],
    ),
    AssessmentField(
        name="total_bilirubin", label="Total bilirubin", minimum=0, maximum=100, hint="mg/dL · laboratory result"
    ),
    AssessmentField(
        name="direct_bilirubin", label="Direct bilirubin", minimum=0, maximum=50, hint="mg/dL · laboratory result"
    ),
    AssessmentField(
        name="alkaline_phosphatase",
        label="Alkaline phosphatase",
        minimum=0,
        maximum=3000,
        hint="IU/L · laboratory result",
    ),
    AssessmentField(
        name="alanine_aminotransferase",
        label="Alanine aminotransferase (ALT)",
        minimum=0,
        maximum=3000,
        hint="IU/L · laboratory result",
    ),
    AssessmentField(
        name="aspartate_aminotransferase",
        label="Aspartate aminotransferase (AST)",
        minimum=0,
        maximum=5000,
        hint="IU/L · laboratory result",
    ),
    AssessmentField(
        name="total_proteins", label="Total proteins", minimum=0, maximum=20, hint="g/dL · laboratory result"
    ),
    AssessmentField(name="albumin", label="Albumin", minimum=0, maximum=10, hint="g/dL · laboratory result"),
    AssessmentField(
        name="albumin_globulin_ratio", label="Albumin / globulin ratio", minimum=0, maximum=5, hint="Laboratory result"
    ),
]


KIDNEY_FIELDS = [
    AssessmentField(name="age", label="Age", minimum=2, maximum=100, hint="Years"),
    AssessmentField(name="blood_pressure", label="Blood pressure", minimum=30, maximum=260, hint="mm Hg"),
    AssessmentField(name="specific_gravity", label="Urine specific gravity", minimum=1, maximum=1.1, hint="Urinalysis"),
    AssessmentField(
        name="albumin",
        label="Urine albumin category",
        field_type="select",
        options=[FieldOption(value=value, label=str(value)) for value in range(6)],
    ),
    AssessmentField(
        name="sugar",
        label="Urine sugar category",
        field_type="select",
        options=[FieldOption(value=value, label=str(value)) for value in range(6)],
    ),
    AssessmentField(
        name="red_blood_cells",
        label="Red blood cells",
        field_type="select",
        options=[FieldOption(value=0, label="Normal"), FieldOption(value=1, label="Abnormal")],
    ),
    AssessmentField(
        name="pus_cell",
        label="Pus cells",
        field_type="select",
        options=[FieldOption(value=0, label="Normal"), FieldOption(value=1, label="Abnormal")],
    ),
    AssessmentField(
        name="pus_cell_clumps",
        label="Pus cell clumps",
        field_type="select",
        options=[FieldOption(value=0, label="Not present"), FieldOption(value=1, label="Present")],
    ),
    AssessmentField(
        name="bacteria",
        label="Bacteria",
        field_type="select",
        options=[FieldOption(value=0, label="Not present"), FieldOption(value=1, label="Present")],
    ),
    AssessmentField(name="blood_glucose_random", label="Random blood glucose", minimum=0, maximum=700, hint="mg/dL"),
    AssessmentField(name="blood_urea", label="Blood urea", minimum=0, maximum=400, hint="mg/dL"),
    AssessmentField(name="serum_creatinine", label="Serum creatinine", minimum=0, maximum=80, hint="mg/dL"),
    AssessmentField(name="sodium", label="Sodium", minimum=80, maximum=200, hint="mEq/L"),
    AssessmentField(name="potassium", label="Potassium", minimum=1, maximum=60, hint="mEq/L"),
    AssessmentField(name="hemoglobin", label="Hemoglobin", minimum=0, maximum=30, hint="g/dL"),
    AssessmentField(name="packed_cell_volume", label="Packed cell volume", minimum=5, maximum=70, hint="%"),
    AssessmentField(
        name="white_blood_cell_count", label="White blood cell count", minimum=1000, maximum=30000, hint="cells/cmm"
    ),
    AssessmentField(
        name="red_blood_cell_count", label="Red blood cell count", minimum=1, maximum=10, hint="millions/cmm"
    ),
    AssessmentField(name="hypertension", label="Hypertension", field_type="select", options=YES_NO),
    AssessmentField(name="diabetes_mellitus", label="Diabetes mellitus", field_type="select", options=YES_NO),
    AssessmentField(
        name="coronary_artery_disease", label="Coronary artery disease", field_type="select", options=YES_NO
    ),
    AssessmentField(
        name="appetite",
        label="Appetite",
        field_type="select",
        options=[FieldOption(value=0, label="Good"), FieldOption(value=1, label="Poor")],
    ),
    AssessmentField(name="pedal_edema", label="Pedal edema", field_type="select", options=YES_NO),
    AssessmentField(name="anemia", label="Anemia", field_type="select", options=YES_NO),
]


ASSESSMENTS = {
    "heart": {"name": model_identity("heart").display_name, "fields": HEART_FIELDS},
    "diabetes": {"name": model_identity("diabetes").display_name, "fields": DIABETES_FIELDS},
    "kidney": {"name": model_identity("kidney").display_name, "fields": KIDNEY_FIELDS},
    "liver": {"name": model_identity("liver").display_name, "fields": LIVER_FIELDS},
}


MODEL_CATALOG = [
    ModelSummary(
        slug="heart",
        name=model_identity("heart").display_name,
        status="unavailable",
        release=model_identity("heart").release,
        version=model_identity("heart").release_id,
        base_model=model_identity("heart").base_model,
        description="UCI Statlog Heart baseline with a versioned 13-field schema; callable only when its validated ONNX artifact is present.",
    ),
    ModelSummary(
        slug="diabetes",
        name=model_identity("diabetes").display_name,
        status="unavailable",
        release=model_identity("diabetes").release,
        version=model_identity("diabetes").release_id,
        base_model=model_identity("diabetes").base_model,
        description="UCI early-stage diabetes symptom baseline with 16 explicit inputs; callable only when its validated ONNX artifact is present.",
    ),
    ModelSummary(
        slug="kidney",
        name=model_identity("kidney").display_name,
        status="unavailable",
        release=model_identity("kidney").release,
        version=model_identity("kidney").release_id,
        base_model=model_identity("kidney").base_model,
        description="UCI CKD research baseline with 24 explicit clinical and laboratory inputs.",
    ),
    ModelSummary(
        slug="liver",
        name=model_identity("liver").display_name,
        status="unavailable",
        release=model_identity("liver").release,
        version=model_identity("liver").release_id,
        base_model=model_identity("liver").base_model,
        description="UCI ILPD research baseline with 10 explicit demographic and laboratory inputs.",
    ),
    ModelSummary(
        slug="stroke",
        name=model_identity("stroke").display_name,
        status="legacy",
        release=model_identity("stroke").release,
        version=model_identity("stroke").release_id,
        base_model=model_identity("stroke").base_model,
        description="Historical pickle retained for provenance; not available to the agent.",
    ),
    ModelSummary(
        slug="pneumonia",
        name=model_identity("pneumonia").display_name,
        status="unavailable",
        release=model_identity("pneumonia").release,
        version=model_identity("pneumonia").release_id,
        base_model=model_identity("pneumonia").base_model,
        description="Pediatric PneumoniaMNIST image baseline; callable only with its reproducible ONNX artifact.",
    ),
]


def get_fields(condition: str) -> list[AssessmentField]:
    item = ASSESSMENTS.get(condition)
    return item["fields"] if item else []
