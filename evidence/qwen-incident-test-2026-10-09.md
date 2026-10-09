# Local Qwen incident test — 9 October 2026

Model: qwen2.5:3b via Ollama. Tested the actual LogSense /api/assistant route with a stored BGL program-loading incident. HTTP 200; mode rag_ollama; generated true; six retrieved sources; elapsed 21.53 seconds including local generation.

The answer separated observations, possible causes and checks, but omitted numbered citations and did not explicitly state that no verified resolution was available. It suggested filesystem corruption and fsck without adequate retrieved support or operational safeguards. This is a successful integration smoke test, not evidence of a correct or safe resolution. No remediation was executed. Formal answer-quality evaluation remains outstanding. Raw request outcome and returned evidence are in the accompanying JSON.

Provider selection and API-key override are request-scoped. Nine focused automated tests passed. The browser verified provider switching and the masked key input using a dummy value; no paid OpenAI request was made in this test.
