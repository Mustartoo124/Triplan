Ollama Setup Guide
1. Install Ollama
Download from https://ollama.com/download and run the installer (Windows .exe).

2. Pull a model
```bash
ollama pull llama3.2       # ~2 GB, good balance
# or
ollama pull qwen2.5:7b     # strong multilingual (good for Vietnamese content)
# or
ollama pull mistral        # fast, lightweight
```

3. Verify Ollama is running
```bash
ollama serve               # starts the server (runs on port 11434)
# In another terminal:
curl http://localhost:11434/v1/models
```

4. Configure .env
```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1
CHAT_MODEL=llama3.2
LLM_MODEL=llama3.2   
```

5. Start the API
```bash
uvicorn main:app --reload
```

Usage example (streaming chat)
After generating an itinerary via POST /api/v1/plan, pass it into chat:

```bash
curl -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{ "itinerary": {...}, "user_input": {...}, "messages": [{"role":"user","content":"What should I know about Day 1?"}] }'
```