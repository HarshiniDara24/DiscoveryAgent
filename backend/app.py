from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import boto3
import json
import io
import uuid
from utils import read_file_to_text
import re
from utils import read_file_to_text, build_pdf_from_text_or_markdown, build_docx_from_text
# from utils import build_pdf_from_text, build_docx_from_text
app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Bedrock client (your config)
#bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
bedrock_agent = boto3.client("bedrock-agent-runtime", region_name="us-west-2")


def call_bedrock_agent(text_chunk: str) -> str:
    response = bedrock_agent.invoke_agent(
        agentId="WV377KFVLT",
        agentAliasId="B7HMS35UT4",
       
        sessionId=str(uuid.uuid4()),
        inputText=text_chunk
    )

    output = ""
    for event in response["completion"]:
        if "chunk" in event:
            output += event["chunk"]["bytes"].decode()
        elif "returnControl" in event:
            pass
        elif "trace" in event:
            pass


    return output.strip()



@app.get("/")
def home():
    return {"message": "Claude File Cleaner API is running 🚀"}


@app.post("/clean-file")
async def clean_file(file: UploadFile = File(...)):
    """
    Transform an uploaded PDF/DOCX/TXT into a Guidewire application document.
    Automatically splits content into chunks and continues from previous output
    to generate all Sections 1–11 without truncation.
    """
    try:
        # 1️⃣ Extract text from uploaded file
        text = await read_file_to_text(file)
        if not text.strip():
            return {"error": "No readable text found in file."}

        # 2️⃣ Helper function for chunked processing with continuation
        def process_in_chunks(text: str, chunk_size=2500, overlap=500) -> str:
            transformed_full_text = ""
            i = 0
            chunk_index = 1

            while i < len(text):
                chunk = text[i:i+chunk_size]
                # Prepend instruction to continue from previous output if not first chunk
                prompt_chunk = chunk
                if i != 0:
                    prompt_chunk = (
                        "Continue the Guidewire document from the previous output, "
                        "keeping all table structures and flowcharts intact:\n\n"
                        + chunk
                    )

                transformed_chunk = call_bedrock_agent(prompt_chunk)
                transformed_full_text += transformed_chunk + "\n\n"

                print(f"Processed chunk {chunk_index}")
                i += chunk_size - overlap
                chunk_index += 1

            return transformed_full_text

        # 3️⃣ Generate full transformed document
        transformed_full_text = process_in_chunks(text)

        # 4️⃣ Determine original file type and generate output
        ext = file.filename.lower().split(".")[-1]

        if ext == "pdf":
            output_bytes = build_pdf_from_text_or_markdown(transformed_full_text)
            media_type = "application/pdf"
            filename = f"Guidewire_{file.filename.split('.')[0]}.pdf"

        elif ext in ["docx", "doc"]:
            output_bytes = build_docx_from_text(transformed_full_text)
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            filename = f"Guidewire_{file.filename.split('.')[0]}.docx"

        else:
            output_bytes = transformed_full_text.encode("utf-8")
            media_type = "text/plain"
            filename = f"Guidewire_{file.filename.split('.')[0]}.txt"

        return StreamingResponse(
            io.BytesIO(output_bytes),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        print("Error:", e)
        return {"error": str(e)}
