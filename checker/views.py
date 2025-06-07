from django.shortcuts import render
from django.core.cache import cache
from .forms import WritingForm
from datetime import datetime, timedelta
from openai import OpenAI
import os
from decouple import config



client = OpenAI(api_key=config("OPENAI_API_KEY"))


# Set your OpenAI API key using new SDK
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "your-api-key"))

MAX_TOKENS_PER_IP = 1000  # limit per hour
TIME_PERIOD = timedelta(hours=1)
timeout_seconds = int(TIME_PERIOD.total_seconds())

def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    return x_forwarded_for.split(",")[0] if x_forwarded_for else request.META.get("REMOTE_ADDR")

def estimate_tokens(text):
    return int(len(text.split()) / 0.75)

def get_prompt(action, text):
    prompts = {
        "grammar": f"Check the grammar error in this text:\n{text}",
        "clarity": f"Is the sentence is understandable and clarity:\n{text}",
        "tone": f"Analyze the tone of this text (formal, casual, funny, rude, etc.):\n{text}",
        "enhance": f"Enhance the quality and fluency of this writing:\n{text}",
    }
    return prompts.get(action, f"Improve this text:\n{text}")

def home(request):
    form = WritingForm(request.POST or None)
    response_text = ""
    error = None
    user_ip = get_client_ip(request)
    current_time = datetime.now()

    last_request_time = cache.get(f"{user_ip}_last_request_time")
    request_count = cache.get(f"{user_ip}_request_count", 0)
    token_count = cache.get(f"{user_ip}_token_count", 0)

    if last_request_time:
        if current_time - last_request_time > TIME_PERIOD:
            request_count = 0
            token_count = 0
    else:
        last_request_time = current_time

    if request.method == "POST" and form.is_valid():
        action = request.POST.get("action")
        user_text = form.cleaned_data["text"]
        tokens_needed = estimate_tokens(user_text)

        if token_count + tokens_needed > MAX_TOKENS_PER_IP:
            error = "Rate limit exceeded. Please try again later."
        else:
            prompt = get_prompt(action, user_text)
            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=300,
                    temperature=0.7
                )
                response_text = response.choices[0].message.content.strip()
            except Exception as e:
                error = f"Error: {str(e)}"

            if not error:
                request_count += 1
                token_count += tokens_needed
                cache.set(f"{user_ip}_last_request_time", current_time, timeout=timeout_seconds)
                cache.set(f"{user_ip}_request_count", request_count, timeout=timeout_seconds)
                cache.set(f"{user_ip}_token_count", token_count, timeout=timeout_seconds)

    return render(request, "checker/home.html", {
        "form": form,
        "response": response_text,
        "error": error
    })
