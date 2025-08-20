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

The SQL Setup file has the commands that need to be run to set up the requisite permissions in Snowflake.

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

Run the following from the terminal

```bash
docker build --platform=linux/amd64 -t local/spcs-deepseek:latest deepseek/ 
docker build --platform=linux/amd64 -t local/spcs-ui:latest ui/
```

```bash
docker tag local/spcs-deepseek:latest <your_snowflake_registry>/repo_image/deepseek_image 
docker tag local/spcs-ui:latest <your_snowflake_registry>/repo_image/ui_image
```

```bash
snow spcs image-registry login
```

```bash
docker push <your_snowflake_registry>/repo_image/deepseek_image d
docker push <your_snowflake_registry>/repo_image/ui_image
```


### YAML Specification for Service Deployment
This YAML file defines how the Deepseek AI model and UI are deployed on Snowflake's container services.

```yaml
spec:
  containers:
    - name: deepseek
      image: /deepseek_db/public/deepseek_repo_image/repo_image/deepseek_image
      resources:
        requests:
          nvidia.com/gpu: 4  # Requesting 4 GPUs for model execution
        limits:
          nvidia.com/gpu: 4  # Limiting to 4 GPUs to avoid over-allocation
      env:
        MODEL: deepseek-ai/DeepSeek-R1-Distill-Qwen-32B  # Model to be used
        HF_TOKEN: #insert here. It should begin with hf_
        TENSOR_PARALLEL_SIZE: 4  # Parallelism setting for distributed model
        GPU_MEMORY_UTILIZATION: 0.99  # GPU memory utilization threshold
        MAX_MODEL_LEN: 75000  # Maximum model input length
        VLLM_API_KEY: dummy  # API key for vLLM integration
      volumeMounts:
        - name: models
          mountPath: /models
        - name: dshm
          mountPath: /dev/shm
    - name: ui
      image: /deepseek_db/public/deepseek_repo_image/repo_image/ui_image
      env:
        MODEL: deepseek-ai/DeepSeek-R1-Distill-Qwen-32B
  endpoints:
    - name: chat
      port: 8500  # Port exposed for chat service
      public: true  # Publicly accessible endpoint
    - name: api
      port: 8000
      public: false
  volumes:
    - name: models
      source: block  # Block storage for models
      size: 100Gi  # Allocate 100 GiB for models
    - name: dshm
      source: memory  # Memory-backed storage for shared memory
      size: 10Gi  # Allocate 10 GiB for shared memory
  networkPolicyConfig:
    allowInternetEgress: true  # Enable outbound internet access for the service
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
USE ROLE DEEPSEEK_ROLE;

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

A blog can be found [here](https://medium.com/@chimp/deploying-deepseek-on-snowflake-using-snowpark-container-servicess-50918db7833e). Please note, some details have been changed
