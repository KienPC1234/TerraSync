# 1. Import the library
from inference_sdk import InferenceHTTPClient

# 2. Connect to your workflow
client = InferenceHTTPClient(
    api_url="https://serverless.roboflow.com",
    api_key="u5p8jGeuTJwkNwIhPb2x"
)

# 3. Run your workflow on an image
result = client.run_workflow(
    workspace_name="tham-hoa-thin-nhin",
    workflow_id="detect-count-and-visualize-2",
    images={
        "image": "1041580-378780.jpg" # Path to your image file
    },
    use_cache=True # Speeds up repeated requests
)

# 4. Get your results
with open("test.json","w") as f:
    f.write(str(result)) 
    
