.PHONY: install install-voice install-qwen install-qwen-training train test dev-api dev-api-voice dev-api-agentic dev-web build-web eval eval-qwen eval-qwen-adapter build-qwen-data finetune-qwen validate-infra

install:
	python3 -m venv .agent-venv
	.agent-venv/bin/pip install -r backend/requirements-dev.txt
	cd frontend && npm install

install-voice:
	mkdir -p .moonshine-cache
	MOONSHINE_VOICE_CACHE=$(CURDIR)/.moonshine-cache .agent-venv/bin/moonshine-voice download --stt --language en --model-arch 2

install-qwen:
	docker desktop enable model-runner --tcp=12434
	docker model pull hf.co/Qwen/Qwen3-0.6B-GGUF:Q8_0

install-qwen-training:
	python3 -m venv .qwen-venv
	.qwen-venv/bin/pip install "mlx-lm[train]"

train:
	.agent-venv/bin/python -m backend.training.train_models --model all
	.agent-venv/bin/python -m backend.training.train_pneumonia

test:
	.agent-venv/bin/ruff check backend
	.agent-venv/bin/pytest backend/tests
	cd frontend && npm run build

eval:
	.agent-venv/bin/python -m backend.evaluation.run_agent_eval

eval-qwen:
	.agent-venv/bin/python -m backend.evaluation.run_qwen_eval

eval-qwen-adapter:
	.qwen-venv/bin/python -m backend.finetuning.evaluate_adapter

build-qwen-data:
	.agent-venv/bin/python -m backend.finetuning.build_dataset

finetune-qwen: build-qwen-data
	.qwen-venv/bin/mlx_lm.lora --config backend/finetuning/lora_config.yaml

dev-api:
	.agent-venv/bin/uvicorn backend.app.main:app --reload --port 8000

dev-api-voice:
	MOONSHINE_VOICE_CACHE=$(CURDIR)/.moonshine-cache HEALTHAI_MOONSHINE_CACHE_DIR=$(CURDIR)/.moonshine-cache HEALTHAI_VOICE_ENABLED=true .agent-venv/bin/uvicorn backend.app.main:app --reload --port 8000

dev-api-agentic:
	MOONSHINE_VOICE_CACHE=$(CURDIR)/.moonshine-cache HEALTHAI_MOONSHINE_CACHE_DIR=$(CURDIR)/.moonshine-cache HEALTHAI_VOICE_ENABLED=true HEALTHAI_ORCHESTRATOR_BACKEND=auto .agent-venv/bin/uvicorn backend.app.main:app --reload --port 8000

dev-web:
	cd frontend && npm run dev

build-web:
	cd frontend && npm run build

validate-infra:
	sam validate --lint --template-file infrastructure/template.yaml --region eu-north-1
	sam validate --lint --template-file infrastructure/budget.template.yaml --region us-east-1
