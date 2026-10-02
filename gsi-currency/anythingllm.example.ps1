# Copy values to your own launcher/profile. Never commit the real API key.
$env:ANYTHINGLLM_BASE_URL="http://localhost:3001"
$env:ANYTHINGLLM_API_KEY="CHANGE_ME"
$env:ANYTHINGLLM_WORKSPACE_SLUG="gsi-academy"
$env:ANYTHINGLLM_EMBED_ID="CHANGE_ME"
streamlit run app/studio.py
