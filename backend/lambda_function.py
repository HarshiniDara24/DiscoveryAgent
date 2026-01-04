import json, base64, uuid, boto3

from utils import build_pdf_from_text_or_markdown, read_file_bytes

AWS_REGION = "us-west-2"
AGENT_ID = "AFFKQS2DKC"
AGENT_ALIAS_ID = "XMP1DXWXDC"

bedrock_agent = boto3.client(
    "bedrock-agent-runtime",
    region_name=AWS_REGION
)

def lambda_handler(event, context):
    try:
        # ✅ API Gateway sends body as string
        if "body" not in event:
            raise Exception("Missing body in request")

        body = event["body"]

        # Handle base64 encoded body (API Gateway setting)
        if event.get("isBase64Encoded", False):
            body = base64.b64decode(body).decode("utf-8")

        payload = json.loads(body)

        # ✅ Now safely read files
        if "files" not in payload:
            raise Exception("Missing 'files' in request body")

        files = payload["files"]

        combined_text = ""

        for f in files:
            filename = f["filename"]
            content = read_file_bytes(filename, f["content"])  # base64 decode
            combined_text += f"\n\n=== START FILE: {filename} ===\n\n"
            combined_text += content

        session_id = str(uuid.uuid4())

        response = bedrock_agent.invoke_agent(
            agentId=AGENT_ID,
            agentAliasId=AGENT_ALIAS_ID,
            sessionId=session_id,
            inputText=combined_text[:14000]
        )

        output = ""
        for e in response["completion"]:
            if "chunk" in e:
                output += e["chunk"]["bytes"].decode()

        pdf_bytes = build_pdf_from_text_or_markdown(output)

        return {
            "statusCode": 200,
            "isBase64Encoded": True,
            "headers": {
                "Content-Type": "application/pdf",
                "Content-Disposition": "attachment; filename=result.pdf"
            },
            "body": base64.b64encode(pdf_bytes).decode("utf-8")
        }

    except Exception as e:
        print("ERROR:", str(e))  # shows in CloudWatch
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)})
        }
