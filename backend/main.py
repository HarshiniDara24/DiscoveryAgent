
# clean_file_endpoint_agent_console.py
from fastapi import FastAPI, UploadFile, File, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from typing import List
import boto3
import io
import re
import time
import uuid
from botocore.exceptions import ReadTimeoutError

# your local utils - must exist in project
from utils import read_file_to_text, build_pdf_from_text_or_markdown

# ---------------------------
# Configuration - change if needed
# ---------------------------
AWS_REGION = "us-west-2"
AGENT_ID = "WV377KFVLT"
AGENT_ALIAS_ID = "KLFEGE8GJ0"

# maximum safe characters to send as input (tweak per agent model / limits)
# Keep conservative to avoid agent truncation on the backend
MAX_INPUT_CHARS = 14000  # adjust upward if you know your agent can accept more

# ---------------------------
# Setup
# ---------------------------
app = FastAPI()
router = APIRouter()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bedrock_agent = boto3.client("bedrock-agent-runtime", region_name=AWS_REGION)


# ---------------------------
# Helpers
# ---------------------------
def call_bedrock_agent_input_only(input_text: str, session_id: str, retries: int = 2, wait: int = 3) -> str:
    """
    Call the Bedrock Agent that has its prompt configured in AWS Console.
    IMPORTANT: We only pass inputText (no system/user prompt strings).
    This collects chunk events from response['completion'] and concatenates them.
    """
    attempt = 0
    while True:
        try:
            response = bedrock_agent.invoke_agent(
                agentId=AGENT_ID,
                agentAliasId=AGENT_ALIAS_ID,
                sessionId=session_id,
                inputText=input_text,
            )

            output = ""
            for event in response.get("completion", []):
                # 'chunk' events contain partial bytes of output
                if "chunk" in event and "bytes" in event["chunk"]:
                    output += event["chunk"]["bytes"].decode()
            return output.strip()

        except Exception as exc:
            attempt += 1
            # retry on network timeout-like errors
            if attempt <= retries and ("Read timed out" in str(exc) or isinstance(exc, ReadTimeoutError)):
                print(f"[Bedrock] Read timeout - retrying {attempt}/{retries} ...")
                time.sleep(wait)
                continue
            # otherwise bubble up
            print("[Bedrock] Error invoking agent:", exc)
            raise


def _simple_local_compress(text: str, max_chars: int = MAX_INPUT_CHARS) -> str:
    """
    Deterministic, local compression to reduce input size **without** calling any model.
    Strategy:
      - Remove extremely long code blocks and large base64 blobs (replace with placeholders)
      - Collapse whitespace
      - If still too long, keep head & tail with a TRUNCATED marker
    This keeps all business text while removing heavy binary/code noise that bloats tokens.
    """
    if not text:
        return text

    t = text

    # Remove very long fenced code blocks (```...```) - replace with placeholder
    t = re.sub(r"```[\\s\\S]{200,}?```", "\n\n[CODE_BLOCK_REMOVED - too long to include]\n\n", t)

    # Remove extremely long single-line base64-like strings (likely attachments)
    t = re.sub(r"[A-Za-z0-9+/]{500,}={0,2}", "[LARGE_BASE64_REMOVED]", t)

    # Remove long XML/JSON values that are obviously payloads (heuristic)
    t = re.sub(r'(<\?xml[\\s\\S]{2000,}?\?>)', '[LARGE_XML_REMOVED]', t)
    t = re.sub(r'(\{[\\s\\S]{4000,}\})', '[LARGE_JSON_REMOVED]', t)

    # Collapse multiple whitespace/newlines
    t = t.replace("\r", " ")
    t = re.sub(r"\n{2,}", "\n\n", t)
    t = re.sub(r"\s+", " ", t).strip()

    # If still too long, keep the head and tail
    if len(t) > max_chars:
        head = t[: int(max_chars * 0.7)]
        tail = t[-int(max_chars * 0.3) :]
        t = head + "\n\n...DOCUMENT_TRUNCATED... (middle omitted)\n\n" + tail

    return t


# ---------------------------
# Endpoint
# ---------------------------
@router.post("/clean-file")
async def clean_file(files: List[UploadFile] = File(...)):
    """
    Accept multiple files, merge them into one combined document, compress locally,
    send only inputText to the Bedrock Agent (prompt lives in the console), and return PDF.
    """
    try:
        combined_parts = []

        # Read and combine all files
        for f in files:
            try:
                raw_text = await read_file_to_text(f)
            except Exception as e:
                combined_parts.append(f"\n\n=== ERROR READING {f.filename}: {str(e)} ===\n\n")
                continue

            if not raw_text or not raw_text.strip():
                combined_parts.append(f"\n\n=== NO TEXT FOUND IN {f.filename} ===\n\n")
                continue

            header = f"\n\n=== START FILE: {f.filename} ===\n\n"
            combined_parts.append(header + raw_text.strip())

        if not combined_parts:
            return JSONResponse({"error": "No readable text found in any uploaded file."}, status_code=400)

        combined_text = "\n\n".join(combined_parts)

        # Local compression (no prompts, deterministic)
        compressed_input = _simple_local_compress(combined_text)

        # IMPORTANT: We send ONLY the compressed_input as inputText.
        session_id = str(uuid.uuid4())
        agent_output = call_bedrock_agent_input_only(compressed_input, session_id)

        # Prepend header and perform safe dedupe of exact lines (but preserve file markers)
        final_text = "COMBINED OUTPUT FOR ALL UPLOADED FILES\n\n" + agent_output

        cleaned_lines = []
        seen = set()
        for line in final_text.split("\n"):
            key = line.strip()
            if key.startswith("=== START FILE:") or key.startswith("COMBINED OUTPUT"):
                cleaned_lines.append(line)
                continue
            if key and key not in seen:
                cleaned_lines.append(line)
                seen.add(key)
            elif not key:
                cleaned_lines.append(line)

        final_text = "\n".join(cleaned_lines)

        # Convert to PDF using your existing util
        final_pdf_bytes = build_pdf_from_text_or_markdown(final_text)

        return StreamingResponse(
            io.BytesIO(final_pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=Guidewire_Combined_Output.pdf"},
        )

    except Exception as exc:
        print("/clean-file error:", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


# Register router
app.include_router(router)

