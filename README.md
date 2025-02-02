# deepseek_snowflake

# Deploying Deepseek AI on Snowflake Using Snowpark Container Services

In this blog, we will walk through the process of deploying Deepseek AI using Snowflake's Snowpark Container Services. The goal is to set up a robust AI chat hub that leverages GPU resources for efficient AI/ML model inference. This deployment integrates Snowflake's powerful data cloud capabilities with the flexibility of custom container services, ensuring a scalable and secure environment.

## Prerequisites

Before diving into the deployment, ensure you have the following:

1. **Snowflake Account** with appropriate permissions.
2. **Snowflake Snowpark Container Services** enabled.
3. **Hugging Face Token** for model access.
4. **Docker** installed for container management.
5. **Python 3.10** and required libraries listed in `requirements.txt`.

## Step 1: Setting Up the Snowflake Environment

### Granting Permissions and Creating Database
First, we assign the necessary roles and permissions to ensure our services can bind endpoints and access required resources.

```sql
-- Assign Account Admin Role and Grant Permissions
USE ROLE ACCOUNTADMIN;
GRANT BIND SERVICE ENDPOINT ON ACCOUNT TO ROLE DS_ROLE;

-- Switch to DS_ROLE and Create Database
USE ROLE DS_ROLE;
CREATE DATABASE IF NOT EXISTS LLM;
USE DATABASE LLM;
```

### Creating Compute Resources
We create a compute pool that specifies GPU resources for our AI models.

```sql
-- Create Compute Pool for GPU Resources
CREATE COMPUTE POOL GPU_NV_S
  MIN_NODES = 1
  MAX_NODES = 4
  INSTANCE_FAMILY = GPU_NV_S;
```

### Setting Up Storage and Networking
We set up stages for storing models and service specifications, and configure external access for Hugging Face API calls.

```sql
-- Create Image Repository and Stages
CREATE OR REPLACE IMAGE REPOSITORY REPO_IMAGE;
CREATE OR REPLACE STAGE MODELS DIRECTORY = (ENABLE = TRUE) ENCRYPTION = (TYPE='SNOWFLAKE_SSE');
CREATE OR REPLACE STAGE SPECS DIRECTORY = (ENABLE = TRUE) ENCRYPTION = (TYPE='SNOWFLAKE_SSE');

-- Configure External Access
CREATE OR REPLACE NETWORK RULE HUGGING_FACE_NETWORK MODE = EGRESS TYPE = HOST_PORT VALUE_LIST = ('0.0.0.0');
CREATE OR REPLACE EXTERNAL ACCESS INTEGRATION HUGGING_FACE_INTEGRATION ALLOWED_NETWORK_RULES = (HUGGING_FACE_NETWORK) ENABLED = TRUE;
GRANT USAGE ON INTEGRATION HUGGING_FACE_INTEGRATION TO ROLE DS_ROLE;
```

## Step 2: Preparing the Container Services

### Dockerfile Configuration
We prepare a Dockerfile to containerize our Streamlit UI for the AI chat hub.

```dockerfile
# Use the official lightweight Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app
COPY /* /app

# Install dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# Expose Streamlit port
EXPOSE 8501

# Run Streamlit app
ENTRYPOINT ["streamlit", "run", "ui.py", "--server.port=8500", "--server.address=0.0.0.0"]
```

### YAML Specification for Service Deployment
This YAML file defines how the Deepseek AI model and UI are deployed on Snowflake's container services.

```yaml
spec:
  containers:
    - name: deepseek
      image: <image_location>deepseek_image  # Replace <image_location> with your actual registry path
      resources:
        requests:
          nvidia.com/gpu: 4
        limits:
          nvidia.com/gpu: 4
      env:
        MODEL: deepseek-ai/DeepSeek-R1-Distill-Qwen-32B
        HF_TOKEN: <your_hugging_face_token>  # Replace with your Hugging Face token
        TENSOR_PARALLEL_SIZE: 4
        GPU_MEMORY_UTILIZATION: 0.99
        MAX_MODEL_LEN: 75000
        VLLM_API_KEY: <your_api_key>  # Replace with your VLLM API key
      volumeMounts:
        - name: models
          mountPath: /models
        - name: dshm
          mountPath: /dev/shm

    - name: ui
      image: <image_location>ui_image  # Replace <image_location> with your actual registry path
      env:
        MODEL: deepseek-ai/DeepSeek-R1-Distill-Qwen-32B

  endpoints:
    - name: chat
      port: 8501
      public: true

  volumes:
    - name: models
      source: block
      size: 100Gi
    - name: dshm
      source: memory
      size: 10Gi

  networkPolicyConfig:
    allowInternetEgress: true
```

## Step 3: Launching the AI Chat Hub

### Starting the vLLM Server
A shell script is used to initialize the vLLM server with appropriate environment configurations.

```bash
#!/bin/bash

# Initialize optional arguments
optional_args=()

# Add optional arguments based on environment variables
[ -n "$TENSOR_PARALLEL_SIZE" ] && optional_args+=("--tensor-parallel-size" "$TENSOR_PARALLEL_SIZE")
[ -n "$MAX_MODEL_LEN" ] && optional_args+=("--max-model-len" "$MAX_MODEL_LEN")
[ -n "$GPU_MEMORY_UTILIZATION" ] && optional_args+=("--gpu-memory-utilization" "$GPU_MEMORY_UTILIZATION")

# Start vLLM server
python3 -m vllm.entrypoints.openai.api_server \
  --model $MODEL \
  --download-dir /models/ \
  --trust-remote-code \
  --enforce-eager \
  "${optional_args[@]}"
```

### Deploying the Service
Once everything is set up, deploy the service using the specifications provided.

```sql
-- Use the DS_ROLE to create and manage the service
USE ROLE DS_ROLE;

-- Deploy the Deepseek AI service
CREATE SERVICE DEEPSEEK
  IN COMPUTE POOL GPU_NV_S
  FROM @SPECS SPEC='spec.yml'
  EXTERNAL_ACCESS_INTEGRATIONS = (HUGGING_FACE_INTEGRATION);

-- Verify service status
SHOW SERVICES;
CALL SYSTEM$GET_SERVICE_STATUS('DEEPSEEK');
CALL SYSTEM$GET_SERVICE_LOGS('DEEPSEEK', '0', 'deepseek', '1000');
```

## Conclusion

