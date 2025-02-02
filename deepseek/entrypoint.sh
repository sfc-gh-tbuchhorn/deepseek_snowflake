#!/bin/bash

# This script starts the vLLM server with optional configurations for tensor parallelism,
# maximum model length, and GPU memory utilization.

# Initialize optional arguments array
optional_args=()

# Check if TENSOR_PARALLEL_SIZE is set and add it to optional arguments
if [ -n "$TENSOR_PARALLEL_SIZE" ]; then
  optional_args+=("--tensor-parallel-size" "$TENSOR_PARALLEL_SIZE")  # Sets the tensor parallelism size for distributed model execution
fi

# Check if MAX_MODEL_LEN is set and add it to optional arguments
if [ -n "$MAX_MODEL_LEN" ]; then
  optional_args+=("--max-model-len" "$MAX_MODEL_LEN")  # Defines the maximum length of the model input
fi

# Check if GPU_MEMORY_UTILIZATION is set and add it to optional arguments
if [ -n "$GPU_MEMORY_UTILIZATION" ]; then
  optional_args+=("--gpu-memory-utilization" "$GPU_MEMORY_UTILIZATION")  # Specifies the fraction of GPU memory to be utilized
fi

# Start the vLLM server with the specified model and optional arguments
# --download-dir specifies where models are downloaded
# --trust-remote-code allows the execution of remote code from model repositories
# --enforce-eager ensures the model runs in eager execution mode
python3 -m vllm.entrypoints.openai.api_server \
  --model $MODEL \
  --download-dir /models/ \
  --trust-remote-code \
  --enforce-eager \
  "${optional_args[@]}"
