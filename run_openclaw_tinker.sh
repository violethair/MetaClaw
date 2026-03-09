export TINKER_API_KEY=""
export OPENAI_API_KEY=""

python3 examples/run_conversation_replay.py
# python3 examples/run_conversation_rl.py

# python - <<'EOF'
#   import asyncio, sys
#   sys.path.insert(0, ".")
#   from metaclaw.prm_scorer import PRMScorer

#   async def test():
#       scorer = PRMScorer(
#           prm_url="https://openai-api.shenmishajing.workers.dev/v1",
#           prm_model="gpt-5.2",
#           api_key="",
#           prm_m=1,
#       )
#       result = await scorer.evaluate(
#           response="The capital of France is Paris.",
#           next_state="Thanks, that's correct!",
#       )
#       print(result)

#   asyncio.run(test())
#   EOF

