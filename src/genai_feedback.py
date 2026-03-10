import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("gemini-1.5-flash")


def generate_driver_feedback(row):

    prompt = f"""
You are an assistant helping rideshare drivers improve performance.

Driver metrics:
velocity_delta: {row['velocity_delta']}
stress_score: {row['stress_score']}
trip_quality: {row['trip_quality_rating']}
flag_count: {row['flag_count']}

Write 2-3 short sentence of feedback for the driver.
Be encouraging and actionable.
"""

    response = model.generate_content(prompt)

    return response.text