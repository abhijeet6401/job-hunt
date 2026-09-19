import os
import sys
import asyncio
from dotenv import load_dotenv

sys.path.insert(0, ".")
load_dotenv()
from services.search import search_jobs, search_social_posts

async def main():
    groq_k = os.environ.get("GROQ_API_KEY")
    tavily_k = os.environ.get("TAVILY_API_KEY")

    async def log_progress(msg):
        print(f"[PROGRESS] {msg[:90]}")

    print("--- 1. Testing search_jobs (YC + Top Startup Boards) ---")
    jobs = await search_jobs("product", groq_k, tavily_k, progress_callback=log_progress)
    yc_jobs = [j for j in jobs if j.get("is_yc")]
    print(f"Total jobs: {len(jobs)} | YC jobs: {len(yc_jobs)}")
    for j in jobs[:6]:
        print(f"  * [{j.get('source')}] {j.get('company')} — {j.get('role')} (Match: {j.get('match_score')})")

    print("\n--- 2. Testing search_social_posts (Founder Posts) ---")
    posts = await search_social_posts("product", groq_k, tavily_k, progress_callback=log_progress)
    print(f"Total verified founder posts: {len(posts)}")
    for p in posts[:4]:
        print(f"  * {p.get('poster_name')} ({p.get('poster_role')}, {p.get('company')}): {p.get('role_hiring')} [YC: {p.get('is_yc')}]")

if __name__ == "__main__":
    asyncio.run(main())
