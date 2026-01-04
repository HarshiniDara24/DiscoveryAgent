Step 1: python -m venv venv
Step 2 :venv\Scripts\activate     
Step 3 :pip install -r requirements.txt
Step 4: uvicorn main:app --reload





# AWS Bedrock + Lambda Setup Documentation

This document provides end-to-end steps to set up an AWS-based solution using **IAM**, **Amazon Bedrock**, **AWS Lambda**, **Lambda Layers (via Docker)**, and **API Gateway** with **CORS and stages** enabled.

---

## 1. Create an IAM User

### 1.1 Create IAM User

1. Login to **AWS Console**
2. Navigate to **IAM → Users → Create user**
3. Enter a user name (e.g., `bedrock-lambda-user`)
4. Select **Access key – Programmatic access**
5. Click **Next**

### 1.2 Attach Permissions

Attach the following policies:

* `AWSLambdaFullAccess`
* `AmazonAPIGatewayAdministrator`
* `IAMFullAccess` (or scoped IAM permissions)
* `CloudWatchLogsFullAccess`

Click **Create user** and download the **Access Key & Secret Key**.

---

## 2. Grant Amazon Bedrock Permissions

### 2.1 Create Custom Bedrock Policy

Go to **IAM → Policies → Create policy → JSON** and paste:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
        "bedrock:ListFoundationModels"
      ],
      "Resource": "*"
    }
  ]
}
```

Name the policy: `AmazonBedrockInvokePolicy`

### 2.2 Attach Policy to IAM User / Role

Attach this policy to:

* IAM User (for local testing)
* OR Lambda Execution Role (recommended)

---

## 3. Create Lambda Execution Role

1. Go to **IAM → Roles → Create role**
2. Select **AWS service → Lambda**
3. Attach policies:

   * `AWSLambdaBasicExecutionRole`
   * `AmazonBedrockInvokePolicy`
4. Name the role: `lambda-bedrock-execution-role`

---

## 4. Create Lambda Function

1. Go to **AWS Lambda → Create function**
2. Choose **Author from scratch**
3. Function name: `bedrock-file-processor`
4. Runtime: **Python 3.10 or 3.11**
5. Execution role: **Use existing role** → select `lambda-bedrock-execution-role`
6. Click **Create function**

---

## 5. Prepare Lambda Layer Using Docker (Required for lxml, pdfplumber)

> AWS Lambda uses Amazon Linux, so packages must be built using Docker.

### 5.1 Create Folder Structure

```bash
mkdir lambda_layer
cd lambda_layer
mkdir python
```

### 5.2 Create requirements.txt

```txt
pdfplumber
lxml
pip
```

### 5.3 Run Docker to Install Packages

```bash
docker run --rm -v "%cd%":/var/task \
  public.ecr.aws/sam/build-python3.10\
  pip install -r requirements.txt -t python/
```

> On Linux/Mac replace `%cd%` with `$(pwd)`

### 5.4 Zip the Layer

```bash
zip -r lambda_layer.zip python
```

---

## 6. Create Lambda Layer

1. Go to **Lambda → Layers → Create layer**
2. Name: `pdf-lxml-layer`
3. Upload `lambda_layer.zip`
4. Runtime: Python 3.10 / 3.11
5. Click **Create**

### 6.1 Attach Layer to Lambda

1. Open your Lambda function
2. Scroll to **Layers → Add a layer**
3. Choose **Custom layer** → select `pdf-lxml-layer`
4. Click **Add**

---

## 7. Update Lambda Function Code

* Add logic to read files (Base64)
* Use `pdfplumber` for PDFs
* Use `lxml` for DOCX / XML parsing
* Invoke **Amazon Bedrock** using `boto3`

Ensure:

```python
import pdfplumber
from lxml import etree
```

---

## 8. Configure Lambda Settings

### 8.1 Increase Timeout & Memory

* Timeout: **60–120 seconds**
* Memory: **1024 MB or higher**


## 9. Create API Gateway

1. Go to **API Gateway → Create API**
2. Choose **REST API**
3. API name: `discovery-agentapi`
4. Click **Create API**

---

## 10. Create Resource & Method

### 10.1 Create Resource

* Resource name: `/discovery-agent`

### 10.2 Create Method

* Method: **POST**
* Integration type: **Lambda Function**
* Lambda Function: `clean-file-agent`
* Enable **Lambda Proxy Integration**

---

## 11. Enable CORS

1. Select `/discovery-agent` resource
2. Click **Actions → Enable CORS**
3. Allow:

   * Access-Control-Allow-Origin: `*`
   * Headers: `Content-Type,Authorization`
   * Methods: `POST,OPTIONS`
4. Click **Enable CORS and replace existing CORS headers**

---

## 12. Deploy API (Stages)

1. Click **Actions → Deploy API**
2. Stage name: `default`
3. Click **Deploy**

### 12.1 API Endpoint

```txt
https://<api-id>.execute-api.<region>.amazonaws.com/dev/process
```

---

## 13. Test End-to-End Flow

* Upload files from React UI
* API Gateway → Lambda
* Lambda reads files
* Lambda invokes Amazon Bedrock
* Response returned to UI

---

## 14. Common Issues & Fixes

### lxml Import Error

✔ Always use Docker-built layers

### Timeout Errors

✔ Increase Lambda timeout & memory

### CORS Errors

✔ Ensure OPTIONS method exists
✔ Redeploy API after enabling CORS

---

## 15. Final Architecture

React UI → API Gateway → Lambda → Amazon Bedrock

---

✅ Setup Complete
