import json

from backend.app.qwen_runtime import AwsLambdaModelRunner


class FakeLambdaClient:
    def __init__(self):
        self.calls = []

    def invoke(self, **kwargs):
        self.calls.append(kwargs)
        return {"StatusCode": 202}


def test_aws_warmup_uses_async_content_free_invocation():
    client = FakeLambdaClient()
    runner = AwsLambdaModelRunner("healthai-reasoner", "test-model", client=client)

    assert runner.warm() is True
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["FunctionName"] == "healthai-reasoner"
    assert call["InvocationType"] == "Event"
    assert json.loads(call["Payload"]) == {"operation": "warmup"}
