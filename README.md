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
docker build --platform=linux/amd64 -t local/spcs-relay:latest relay/
```

```bash
docker tag local/spcs-deepseek:latest <your_snowflake_registry>/repo_image/deepseek_image 
docker tag local/spcs-ui:latest <your_snowflake_registry>/repo_image/ui_image
docker tag local/spcs-relay:latest <your_snowflake_registry>/repo_image/relay_image
```

```bash
snow spcs image-registry login
```

```bash
docker push <your_snowflake_registry>/repo_image/deepseek_image
docker push <your_snowflake_registry>/repo_image/ui_image
docker push <your_snowflake_registry>/repo_image/relay_image
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
        HF_TOKEN:  #input your hugging face token here. It should begin with hf_
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
    - name: relay
      image: /deepseek_db/public/deepseek_repo_image/repo_image/relay_image
  endpoints:
    - name: chat
      port: 8500  # Port exposed for chat service
      public: true  # Publicly accessible endpoint
    - name: api
      port: 8000
      public: false
    - name: relay
      port: 8600
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
You need to upload this file to the stage created in the setup

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
CALL SYSTEM$GET_SERVICE_LOGS('DEEPSEEK', '0', 'deepseek', '1000');
CALL SYSTEM$GET_SERVICE_LOGS('DEEPSEEK', '0', 'relay', '1000');
```

There are a variety of different ways we can now test this.

The function below is a service function that wraps around the endpoint. It allows us to then call the SPCS service from a SQL funtion.

```sql
CREATE OR REPLACE FUNCTION deepseek_chat_udf(text varchar)
   RETURNS varchar
   SERVICE=deepseek
   ENDPOINT=relay
   AS '/relay';

SELECT deepseek_chat_udf('Whats the capital of New Zealand');
```
In the above, you will not be able to get streaming responses. This means it will think, and then when the answer is prepared, it will return it all at once

The other way we can test is to access the public endpoint os the Streamlit app, which talks to the deepseek model on the back end.

To get the endpoint (this is dynamically assigned), run the following

```sql
SHOW ENDPOINTS IN SERVICE DEEPSEEK;
```

Copy the ingress_url and paste it in a browser. You will be asked to authenticate, and then you can chat with deepseek. Please use "chat" mode on the laft hand side.

Please note, if you get the following error:

openai.APIConnectionError: Connection error.

it might be because the service is not ready yey (even though the container says it is). We do not have arror handling for that in the code. Please wait a few minutes before debugging.

A blog can be found [here](https://medium.com/@chimp/deploying-deepseek-on-snowflake-using-snowpark-container-servicess-50918db7833e). Please note, some details have been changed

Suspend your service when you are done by running

```sql
ALTER SERVICE DEEPSEEK SUSPEND;
```

# Deploying Deepseek AI on Snowflake Using Snowpark Container Services to build a RAG

We can extend on the above by building a RAG. Usually we would use Cortex Search which abstracts away alot of these steps. For availability reasons, it may be necessary to build it on Snowflake components

First we need an embedding model. The EMBEDDINGS_ON_CONTAINER notebook creates an embedding model and registers it on the model registry. We then use this later in the RAG.

Before running the notebook, run the following SQL

```sql
-- Initilally we need to set up the account to download and run an Open Source Embedding model on SPCS

USE ROLE ACCOUNTADMIN;
SET USERNAME = (SELECT CURRENT_USER());
SELECT $USERNAME;

-- Using ACCOUNTADMIN, create a new role for this exercise and grant to applicable users
CREATE ROLE IF NOT EXISTS DEEPSEEK_ROLE;
GRANT ROLE DEEPSEEK_ROLE to USER identifier($USERNAME);

-- Next create a new database and schema,
USE ROLE DEEPSEEK_ROLE;
CREATE DATABASE IF NOT EXISTS DEEPSEEK_DB;
CREATE SCHEMA IF NOT EXISTS EMBEDDING_MODEL_HOL_SCHEMA;

-- Create network rule and external access integration for pypi to allow users to pip install python packages within notebooks (on container runtimes)
USE ROLE ACCOUNTADMIN;

CREATE NETWORK RULE IF NOT EXISTS pypi_network_rule
  MODE = EGRESS
  TYPE = HOST_PORT
  VALUE_LIST = ('pypi.org', 'pypi.python.org', 'pythonhosted.org',  'files.pythonhosted.org');

CREATE EXTERNAL ACCESS INTEGRATION IF NOT EXISTS pypi_access_integration
  ALLOWED_NETWORK_RULES = (pypi_network_rule)
  ENABLED = true;

-- Create network rule and external access integration for users to access data and models from Hugging Face
USE ROLE DEEPSEEK_ROLE;

CREATE OR REPLACE NETWORK RULE hf_network_rule
  MODE = EGRESS
  TYPE = HOST_PORT
  VALUE_LIST = ('huggingface.co', 'www.huggingface.co', 'cdn-lfs.huggingface.co', 'cdn-lfs-us-1.huggingface.co');

USE ROLE ACCOUNTADMIN;

CREATE EXTERNAL ACCESS INTEGRATION IF NOT EXISTS hf_access_integration
  ALLOWED_NETWORK_RULES = (hf_network_rule)
  ENABLED = true;

USE ROLE DEEPSEEK_ROLE;

create or replace network rule allow_all_rule
  TYPE = 'HOST_PORT'
  MODE= 'EGRESS'
  VALUE_LIST = ('0.0.0.0:443','0.0.0.0:80');

USE ROLE ACCOUNTADMIN;

CREATE OR REPLACE EXTERNAL ACCESS INTEGRATION allow_all_integration
  ALLOWED_NETWORK_RULES = (allow_all_rule)
  ENABLED = true;
  
GRANT USAGE ON INTEGRATION pypi_access_integration TO ROLE DEEPSEEK_ROLE;
GRANT USAGE ON INTEGRATION hf_access_integration TO ROLE DEEPSEEK_ROLE;
GRANT USAGE ON INTEGRATION allow_all_integration TO ROLE DEEPSEEK_ROLE;

-- Create a snowpark optimized virtual warehouse access of a virtual warehouse for newly created role
CREATE OR REPLACE WAREHOUSE EMBEDDING_MODEL_HOL_WAREHOUSE WITH
  WAREHOUSE_SIZE = 'MEDIUM';
  
GRANT USAGE ON WAREHOUSE EMBEDDING_MODEL_HOL_WAREHOUSE to ROLE DEEPSEEK_ROLE;

-- Create compute pool to leverage GPUs (see docs - https://docs.snowflake.com/en/developer-guide/snowpark-container-services/working-with-compute-pool)

--DROP COMPUTE POOL IF EXISTS GPU_NV_S_COMPUTE_POOL;

CREATE COMPUTE POOL IF NOT EXISTS GPU_NV_S_COMPUTE_POOL
    MIN_NODES = 4
    MAX_NODES = 4
    INSTANCE_FAMILY = GPU_NV_S;

-- Grant usage of compute pool to newly created role
GRANT OWNERSHIP ON COMPUTE POOL GPU_NV_S_COMPUTE_POOL TO ROLE DEEPSEEK_ROLE;

-- Create image repository
USE ROLE DEEPSEEK_ROLE;

CREATE IMAGE REPOSITORY IF NOT EXISTS my_inference_images;

USE ROLE ACCOUNTADMIN;
GRANT CREATE SERVICE ON SCHEMA EMBEDDING_MODEL_HOL_SCHEMA TO ROLE DEEPSEEK_ROLE;
```

The second step is to use the embedding model over unstructured documents in Snowflake. The second notebook RAGTOAI_PROCESSING does this. It then calls a vector similarity function to find the most relevant chunk given an input. Finally, it then calls the service function we create in a small streamlit example.

To set this up, we will need a stage for our unstructured documents. Run the below:

```sql
-- Below is to set up the Stage for the RAG demo

USE ROLE DEEPSEEK_ROLE;

use database DEEPSEEK_DB;
create schema RAGTOAI;

CREATE OR REPLACE STAGE DEEPSEEK_DB.RAGTOAI.DOCS
DIRECTORY = (ENABLE = TRUE); -- upload the pdfs to this stage
```

Then upload the files in the docs folder to the stage.
