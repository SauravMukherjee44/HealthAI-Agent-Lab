FROM amazon/aws-lambda-python:3.12

COPY backend/requirements.txt ${LAMBDA_TASK_ROOT}/requirements.txt
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

COPY backend/app ${LAMBDA_TASK_ROOT}/app
COPY backend/artifacts ${LAMBDA_TASK_ROOT}/artifacts
COPY frontend/dist ${LAMBDA_TASK_ROOT}/frontend

ENV HEALTHAI_ARTIFACTS_DIR=${LAMBDA_TASK_ROOT}/artifacts
ENV HEALTHAI_FRONTEND_DIR=${LAMBDA_TASK_ROOT}/frontend

CMD ["app.main.handler"]
