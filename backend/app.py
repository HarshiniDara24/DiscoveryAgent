from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import boto3
import json
import io
import uuid
from utils import read_file_to_text

from utils import read_file_to_text, build_pdf_from_text, build_docx_from_text
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
        agentAliasId="DU33NRPMSU",
       
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
    Transform an uploaded MERN stack PDF into a Guidewire application PDF.
    """
    try:
        # 1️⃣ Extract text from uploaded file
        text = await read_file_to_text(file)
        if not text.strip():
            return {"error": "No readable text found in file."}

        # 2️⃣ Split into safe chunks
        chunk_size = 3500
        chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
        transformed_full_text = ""

        # 3️⃣ Send chunks to Claude AI
        for chunk in chunks:
            transformed_chunk = call_bedrock_agent(chunk)
            transformed_full_text += transformed_chunk + "\n\n"


        # 4️⃣ Generate PDF from transformed text
       
        # pdf_bytes = build_pdf_from_text(transformed_full_text)

        # # 5️⃣ Return PDF as download
        # return StreamingResponse(
        #     io.BytesIO(pdf_bytes),
        #     media_type="application/pdf",
        #     headers={"Content-Disposition": f"attachment; filename=Guidewire_{file.filename.split('.')[0]}.pdf"}
        # )

        

# Determine original file type
        ext = file.filename.lower().split(".")[-1]

        if ext == "pdf":
            output_bytes = build_pdf_from_text(transformed_full_text)
            media_type = "application/pdf"
            filename = f"Guidewire_{file.filename.split('.')[0]}.pdf"

        elif ext in ["docx", "doc"]:
            output_bytes = build_docx_from_text(transformed_full_text)
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            filename = f"Guidewire_{file.filename.split('.')[0]}.docx"

        else:
            # default fallback
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

