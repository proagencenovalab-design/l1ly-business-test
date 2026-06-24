LILY CHAT REPAIR UPDATE

Replace these 3 files in the root of your GitHub repository:
- agent.py
- main_lily_business.py
- memory.py

Then click Commit changes. Railway will redeploy automatically.

Main fixes:
- conversation repair mode
- no empty OpenAI replies
- max_output_tokens increased to 300
- empty database messages cleaned automatically
- empty replies are never stored or sent
- old BOOT TEST logs removed
- hard 18+ age gate retained
