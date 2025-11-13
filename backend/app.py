from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import boto3
import json
import io

from utils import read_file_to_text
from utils import generate_food_app_pdf,build_pdf_from_text
from utils import read_file_to_text, build_pdf_from_text, build_docx_from_text

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
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")


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
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"""
You are an enterprise application architect with deep expertise in both MERN stack systems and Guidewire InsuranceSuite.

Your task is to **analyze the structure of the input text**, detect the MERN-stack based architecture, and then **rewrite the document so that the application is implemented using the Guidewire ecosystem.**

Do not do word-by-word replacements. Instead, perform a **functional mapping**:

Frontend:
- MERN React UI → Guidewire Digital Portal (Jutro React Framework)

Backend:
- Node/Express API → Guidewire Integration Gateway + Service Layer
- Microservices → PolicyCenter / BillingCenter / ClaimCenter workflows

Database:
- MongoDB → Guidewire DataHub + Operational Data Store (ODS)

Feature Mapping:
- Order Placement → PolicyCenter Submission Flow
- Customer Account & Auth → Guidewire Identity & Access Management
- Payment Processing → BillingCenter Invoicing + Payment Plan Engine
- Order Tracking → ClaimCenter Service Request Case Tracking
- Restaurant Onboarding → Vendor Management / Producer Integration

Rewrite the document in the same structure:
- Introduction
- Objectives
- Technology / Platform Architecture (Guidewire)
- System Architecture (with modules explained)
- Data Flow (step-by-step)
- Key Features (mapped to Guidewire modules)
- Benefits
- Future Enhancements
- Conclusion

Ensure the rewritten output:
- Uses clear enterprise terminology
- Reflects real Guidewire implementation practices
- Is **NOT** tied to insurance domain — keep the Food Delivery domain exactly same.




Input:
{chunk}
"""
                        }
                    ]
                }
            ]

            body = json.dumps({
                "messages": messages,
                "max_tokens": 4000,
                "temperature": 0.2,
                "anthropic_version": "bedrock-2023-05-31"
            })

            response = bedrock.invoke_model(
                modelId="anthropic.claude-3-sonnet-20240229-v1:0",
                body=body,
                contentType="application/json",
                accept="application/json"
            )

            result = json.loads(response["body"].read().decode("utf-8"))
            transformed_chunk = result["content"][0]["text"].strip()
            transformed_full_text += transformed_chunk + "\n\n"

        # 4️⃣ Generate PDF from transformed text
        from utils import build_pdf_from_text
        # pdf_bytes = build_pdf_from_text(transformed_full_text)

        # # 5️⃣ Return PDF as download
        # return StreamingResponse(
        #     io.BytesIO(pdf_bytes),
        #     media_type="application/pdf",
        #     headers={"Content-Disposition": f"attachment; filename=Guidewire_{file.filename.split('.')[0]}.pdf"}
        # )

        from utils import build_pdf_from_text, build_docx_from_text

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

