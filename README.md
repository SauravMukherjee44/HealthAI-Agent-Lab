# AI Healthcare Hub

AI-assisted educational screening for heart disease, diabetes, kidney disease,
liver disease, stroke risk and pneumonia patterns. The Flask application uses
the trained models in `website/app_models` and includes responsive assessment,
upload and result experiences.

> This project is an educational screening tool, not a medical device or a
> substitute for diagnosis by a qualified healthcare professional.

## Run locally

1. Create and activate a Python virtual environment.
2. Install the dependencies with `pip install -r requirements.txt`.
3. Start the app with `python app.py`.
4. Open `http://127.0.0.1:5000`.

For a production process, start the app with `gunicorn app:app`.

## Render deployment

The included `render.yaml` configures the web process and `/health` health
check. A GitHub Actions workflow pings that endpoint every 10 minutes.

To enable the scheduled health check, add a GitHub repository Actions secret
named `RENDER_APP_URL` containing the public Render service URL, for example
`https://your-service.onrender.com`. You can run the workflow manually once to
confirm the endpoint is reachable.

GitHub schedules are best-effort and can occasionally run late. Render's free
service behavior and usage limits still apply.
