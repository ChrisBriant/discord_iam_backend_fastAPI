from openai import OpenAI
import os
import dotenv
import json
import random
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

dotenv_file = PROJECT_ROOT / ".env"

if os.path.isfile(dotenv_file):
    dotenv.load_dotenv(dotenv_file)

API_KEY = os.environ.get("OPENAI_API_KEY")

fake_event_prompt_id = "pmpt_6a683c57295c81909bb67c760fe0e7220940b0bc39d34960"


def get_fake_event():
    client = OpenAI(api_key=API_KEY)

    online_or_physical = random.choice(["0", "1"])

    try:
        response = client.responses.create(
            prompt={
                "id": fake_event_prompt_id,
                "version": "3",
                # "variables": {
                #     "online": online_or_physical
                # }
            },

            input=[
                {
                    "role" : "user",
                    "content" : f"""
                        online="{online_or_physical}"
                    """
                }
                
            ],
            text={
                "format": {
                "type": "text"
                }
            },
            reasoning={},
            max_output_tokens=2048,
            store=True,
            include=["web_search_call.action.sources"]
        )
        print("RESPONSE DATA", response)
        #response_data = response.output[1].content[0].text
        # Convert string to dict
        json_str = None

        for item in response.output:
            if item.type == "message":
                for content in item.content:
                    if content.type == "output_text":
                        json_str = content.text
                        break

        if json_str is None:
            raise ValueError("No JSON response found")
        
        response_dict = json.loads(json_str)

        # Output directory
        # output_dir = Path(PROJECT_ROOT) / "files/answers"
        # os.makedirs(output_dir, exist_ok=True)

        # output_file = output_dir / f"{uuid.uuid4()}.json"

        # # Now write to file
        # with open(output_file, "w", encoding="utf-8") as f:
        #     json.dump(response_dict, f, indent=2)


        # print(f"✅ Interview question answer saved to: {output_file}")
        return response_dict
    except Exception as e:
        print("Error encountered while trying to get suggested answer", e)

if __name__ == "__main__":
    reponse_data = get_fake_event()
    print("RESPONSE DATA", reponse_data)